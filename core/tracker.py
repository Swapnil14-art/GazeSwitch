import logging
import time
from threading import Thread

from pynput import keyboard

from system_platform.config import load_config, save_config
from system_platform.window_manager import WindowManager
from trackers.eyetrax_tracker import EyeTraxWrapper

logger = logging.getLogger(__name__)

DWELL_TIME = 0.5  # seconds
TYPING_IDLE_TIME = 1.0  # seconds
POLL_INTERVAL = 0.05  # seconds
DEFAULT_MANUAL_OVERRIDE_HOTKEY = "<alt>+\\"
DEFAULT_CAMERA_INDEX = 0


class GazeTracker:
    def __init__(self, window_manager: WindowManager):
        self.config = load_config()
        camera_name = self.config.get("camera_name", "")

        self.wm = window_manager
        self.estimator = None
        self.current_camera = self.wm.list_video_devices().get(
            camera_name, DEFAULT_CAMERA_INDEX
        )

        self.running = False
        self.current_window = None
        self.last_keystroke_time = time.time()

        self.screen_width, self.screen_height = self.wm.get_screen_size()

        # Keyboard listener for typing detection
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        self.keyboard_listener.start()

        # Manual override hotkey
        self.manual_override_triggered = False
        self.manual_override_hotkey = self.config.get(
            "manual_override_hotkey", DEFAULT_MANUAL_OVERRIDE_HOTKEY
        )
        self.hotkey_listener = None
        self._start_hotkey_listener()

    def _on_key_press(self, _):
        self.last_keystroke_time = time.time()

    def _start_hotkey_listener(self):
        """
        Start the hotkey listener for manual override.
        """
        if self.hotkey_listener:
            self.hotkey_listener.stop()

        self.hotkey_listener = keyboard.GlobalHotKeys(
            {self.manual_override_hotkey: self._manual_override}
        )
        self.hotkey_listener.start()

    def _manual_override(self):
        """
        Triggers an immediate focus on the current gaze target,
        bypassing dwell/idle checks.
        """
        self.manual_override_triggered = True
        logger.info("Manual override triggered")

    def _same_window(self, a: dict | None, b: dict | None) -> bool:
        """
        Check if two window dictionaries represent the same window.

        Args:
            a (dict | None): _window dictionary or None
            b (dict | None): _window dictionary or None

        Returns:
            bool: True if the two window dictionaries represent the same window,
            False otherwise.
        """
        if not a or not b:
            return False
        return self.wm.window_key(a) == self.wm.window_key(b)

    def _sync_focused_window(self):
        """
        Sync the currently focused window with the tracker's state.
        """
        focused = self.wm.get_focused_window()
        if focused and not self._same_window(focused, self.current_window):
            self.current_window = focused
            logger.debug(f"OS focus changed to: {focused.get('title')}")

    def update_manual_override_hotkey(self, hotkey: str):
        """
        Update the manual override hotkey.

        Args:
            hotkey (str): The new hotkey combination.
        """
        self.manual_override_hotkey = hotkey
        self.config["manual_override_hotkey"] = hotkey
        save_config(self.config)

        self._start_hotkey_listener()
        logger.info(f"Manual override hotkey set to {hotkey}")

    def set_video_device(self, device_index: int):
        """
        Set the video device for the tracker.
        """
        if device_index == self.current_camera:
            return

        self.current_camera = device_index
        self.config["camera_name"] = list(self.wm.list_video_devices().keys())[
            device_index
        ]
        save_config(self.config)

        if self.estimator:
            self.estimator.set_video_device(device_index)
        logger.info(f"Video device set to {device_index}")

    def calibrate(self, icon=None, _=None):
        """
        Starts the calibration process.
        """
        self.estimator = EyeTraxWrapper(self.current_camera, calibrate=True)

    def start_tracking(self):
        """
        Start the gaze tracking process.
        """
        if self.running:
            return

        if not self.estimator:
            self.estimator = EyeTraxWrapper(self.current_camera)

        self.running = True

        Thread(target=self._run_tracker, daemon=True).start()
        logger.info("Tracking started")

    def stop_tracking(self):
        """
        Stop the gaze tracking process.
        """
        self.running = False
        if self.estimator:
            self.estimator.stop()
        logger.info("Tracking stopped")

    def _run_tracker(self):
        """
        Main loop to track gaze and focus windows accordingly.
        """
        last_target = None
        gaze_dwell_start = 0.0
        intent_idle_since = 0.0

        while self.running:
            now = time.time()

            # Keep current_window in sync with OS focus
            self._sync_focused_window()

            data = self.estimator.get_data()  # type: ignore
            x = data["gaze"]["x"]
            y = data["gaze"]["y"]

            # Determine if the user is actively typing or not
            typing_idle = (now - self.last_keystroke_time) >= TYPING_IDLE_TIME

            if not typing_idle:
                intent_idle_since = 0.0
            elif intent_idle_since == 0.0:
                intent_idle_since = now

            if (
                x is not None
                and y is not None
                and 0 < x < self.screen_width
                and 0 < y < self.screen_height
            ):
                logger.debug(f"Predicted gaze at: ({x}, {y})")
                windows = self.wm.get_windows()
                target_window = self.wm.window_at_point(int(x), int(y), windows)

                if target_window:
                    # Reset dwell timer if target changes
                    if not self._same_window(target_window, last_target):
                        last_target = target_window
                        gaze_dwell_start = now

                    # Check intent conditions
                    gaze_dwell = now - gaze_dwell_start
                    intent_idle = (
                        now - intent_idle_since if intent_idle_since > 0.0 else 0.0
                    )

                    if self.manual_override_triggered or (
                        gaze_dwell >= DWELL_TIME
                        and intent_idle >= TYPING_IDLE_TIME
                        and (
                            not self.current_window
                            or not self._same_window(target_window, self.current_window)
                        )
                    ):
                        logger.info(
                            f"Focusing window via gaze: {target_window.get('title')}"
                        )
                        self.wm.focus_window(target_window)
                        self.current_window = target_window

                        # Reset to prevent immediate re-trigger
                        gaze_dwell_start = now
                        intent_idle_since = now
                        self.manual_override_triggered = False
                else:
                    # No window detected, reset gaze dwell
                    last_target = None
                    gaze_dwell_start = 0.0
            else:
                # Invalid gaze, reset gaze dwell
                last_target = None
                gaze_dwell_start = 0.0

            time.sleep(POLL_INTERVAL)
