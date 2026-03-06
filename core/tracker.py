import logging
import time
from threading import Thread

from pynput import keyboard

from system_platform.config import load_config, save_config
from system_platform.window_manager import WindowManager
from trackers.base_tracker import BaseTracker
from trackers.eyetrax_tracker import EyeTraxWrapper

logger = logging.getLogger(__name__)

DWELL_TIME = 0.5  # seconds
TYPING_IDLE_TIME = 1.0  # seconds
POLL_INTERVAL = 0.05  # seconds
CYCLE_RESET_TIME = 1.5  # seconds
DEFAULT_CAMERA_INDEX = 0
DEFAULT_MANUAL_OVERRIDE_HOTKEY = "<alt>+\\"
DEFAULT_CYCLE_WINDOWS_HOTKEY = "<alt>+]"
DEFAULT_CYCLE_WINDOWS_REVERSE_HOTKEY = "<alt>+["


class GazeTracker:
    def __init__(self, window_manager: WindowManager):
        self.config = load_config()
        camera_name = self.config.get("camera_name", "")

        self.wm = window_manager
        self.current_camera = self.wm.list_video_devices().get(
            camera_name, DEFAULT_CAMERA_INDEX
        )

        self.estimator: BaseTracker = EyeTraxWrapper()
        if self.estimator.is_ready():
            Thread(target=self._preload_estimator, daemon=True).start()

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

        # Cycle windows hotkeys
        self.cycle_windows_triggered = False
        self.cycle_windows_hotkey = self.config.get(
            "cycle_windows_hotkey", DEFAULT_CYCLE_WINDOWS_HOTKEY
        )
        self.cycle_windows_triggered_reverse = False
        self.cycle_windows_reverse_hotkey = self.config.get(
            "cycle_windows_reverse_hotkey", DEFAULT_CYCLE_WINDOWS_REVERSE_HOTKEY
        )

        # Cycling state for overlapping windows.
        # The initial stack of windows under the gaze point is stored because
        # focusing a window usually brings it to the top of the OS Z-order.
        # If we recomputed the stack every time, the order would change and
        # cycling would bounce between only the top two windows.
        # By freezing the initial stack we can cycle deterministically:
        # A → B → C → A even though the OS keeps reordering windows.
        self.cycle_stack = None
        self.cycle_index = 0
        self.last_cycle_time = 0

        self.hotkey_listener = None
        self._start_hotkey_listener()

        # Main loop state
        self._tracker_last_target = None
        self._tracker_gaze_dwell_start = 0.0
        self._tracker_intent_idle_since = 0.0

    def _preload_estimator(self):
        try:
            logger.info("Preloading gaze model...")
            self.estimator.preload()
            logger.info("Model preloaded")
        except Exception:
            logger.exception("Preload failed")

    def _on_key_press(self, _):
        self.last_keystroke_time = time.time()

    def _start_hotkey_listener(self):
        """
        Start the hotkey listener.
        """
        if self.hotkey_listener:
            self.hotkey_listener.stop()

        self.hotkey_listener = keyboard.GlobalHotKeys(
            {
                self.manual_override_hotkey: self._manual_override,
                self.cycle_windows_hotkey: self._cycle_windows,
                self.cycle_windows_reverse_hotkey: self._cycle_windows_reverse,
            }
        )
        self.hotkey_listener.start()

    def _manual_override(self):
        """
        Triggers an immediate focus on the current gaze target,
        bypassing dwell/idle checks.
        """
        self.manual_override_triggered = True
        logger.info("Manual override triggered")

    def _cycle_windows(self):
        """
        Cycle through all windows under the gaze point.
        """
        self.cycle_windows_triggered = True
        logger.info("Cycle windows hotkey triggered")

    def _cycle_windows_reverse(self):
        """
        Cycle through all windows under the gaze point in reverse.
        """
        self.cycle_windows_triggered_reverse = True
        logger.info("Reverse cycle windows hotkey triggered")

    def _cycle_windows_at_gaze(
        self, x: int, y: int, windows: list[dict], reverse: bool = False
    ):
        """
        Cycle focus through all windows located under the given gaze coordinates.

        This function finds every window whose rectangle contains the provided
        (x, y) screen position. The windows are assumed to be ordered by Z-order
        (topmost first). Each invocation moves focus to the next or previous window
        in that stack, depending on the `reverse` parameter, and wraps around at
        the ends.

        This allows the user to repeatedly trigger hotkeys to cycle forward or
        backward through overlapping windows at the gaze location.

        Args:
            x (int): X coordinate of the gaze position.
            y (int): Y coordinate of the gaze position.
            windows (list[dict]): A list of window dictionaries.
            reverse (bool, optional): If True, cycles backward through the stack.
                Defaults to False (forward cycling).
        """
        now = time.time()

        # If the user pauses for too long between cycle presses we treat the
        # next press as the start of a new cycle session and recompute the stack.
        # This prevents cycling through stale window lists if windows moved or
        # focus changed in the meantime.
        if now - self.last_cycle_time > CYCLE_RESET_TIME:
            self.cycle_stack = None
            self.cycle_index = 0

        self.last_cycle_time = now

        window_stack = self.wm.windows_at_point(x, y, windows)

        if len(window_stack) <= 1:
            return

        if self.cycle_stack is None:
            self.cycle_stack = window_stack

            # Determine where the currently focused window sits in the stored stack
            # so cycling continues from that position.
            found = False
            for i, w in enumerate(self.cycle_stack):
                if self._same_window(w, self.current_window):
                    self.cycle_index = i
                    found = True
                    break

            # If the current focused window isn't part of the stack (e.g. the user
            # Alt-Tabbed or clicked another window), start cycling from the top.
            # Setting -1 ensures the next increment selects index 0.
            if not found:
                self.cycle_index = -1

        # Move to the next or previous window in the stack depending on direction.
        # Wrap around at the ends so cycling becomes:
        # Forward:  A → B → C → A
        # Reverse:  A → C → B → A
        if reverse:
            self.cycle_index = (self.cycle_index - 1) % len(self.cycle_stack)
        else:
            self.cycle_index = (self.cycle_index + 1) % len(self.cycle_stack)
        next_window = self.cycle_stack[self.cycle_index]

        logger.info(f"Cycling focus to: {next_window.get('title')}")

        self.wm.focus_window(next_window)
        self.current_window = next_window

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

    def update_cycle_hotkey(self, hotkey: str, reverse: bool):
        """
        Update the cycle hotkey.

        Args:
            hotkey (str): The new hotkey combination.
            reverse (bool): Whether to update the reverse or forward
            cycle hotkey.
        """
        if reverse:
            self.cycle_windows_reverse_hotkey = hotkey
            self.config["cycle_windows_reverse_hotkey"] = hotkey
            action = "Cycle Reverse"
        else:
            self.cycle_windows_hotkey = hotkey
            self.config["cycle_windows_hotkey"] = hotkey
            action = "Cycle Forward"

        save_config(self.config)
        self._start_hotkey_listener()
        logger.info(f"{action} hotkey set to {hotkey}")

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
        logger.info("Starting calibration")
        self.estimator.calibrate(self.current_camera)
        logger.info("Calibration finished")

    def start_tracking(self):
        """
        Start the gaze tracking process.
        """
        if self.running:
            return

        if not self.estimator.is_ready():
            self.wm.notify("Calibration required before Tracking!")
            return

        self.estimator.start(self.current_camera)

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

    def _run_tracker_step(self):
        """
        Helper function to run a single iteration of the main
        tracking loop.
        """
        now = time.time()

        # Keep current_window in sync with OS focus
        self._sync_focused_window()

        data = self.estimator.get_data()  # type: ignore
        x = data["gaze"]["x"]
        y = data["gaze"]["y"]

        # Determine if the user is actively typing or not
        typing_idle = (now - self.last_keystroke_time) >= TYPING_IDLE_TIME

        if not typing_idle:
            self._tracker_intent_idle_since = 0.0
        elif self._tracker_intent_idle_since == 0.0:
            self._tracker_intent_idle_since = now

        if (
            x is not None
            and y is not None
            and 0 < x < self.screen_width
            and 0 < y < self.screen_height
        ):
            logger.debug(f"Predicted gaze at: ({x}, {y})")
            windows = self.wm.get_windows()

            # Cycling is handled immediately and independently of the normal
            # dwell/intent logic because it is an explicit user action.
            if self.cycle_windows_triggered or self.cycle_windows_triggered_reverse:
                reverse = self.cycle_windows_triggered_reverse
                self._cycle_windows_at_gaze(int(x), int(y), windows, reverse=reverse)

                self.cycle_windows_triggered = False
                self.cycle_windows_triggered_reverse = False

                # Skip the rest of the gaze intent logic this frame to avoid the
                # dwell-based focusing logic triggering immediately after cycling.
                time.sleep(POLL_INTERVAL)
                return

            target_window = self.wm.window_at_point(int(x), int(y), windows)

            if target_window:
                # Reset dwell timer if target changes
                if not self._same_window(target_window, self._tracker_last_target):
                    self._tracker_last_target = target_window
                    self._tracker_gaze_dwell_start = now

                    # Gaze moved to a different window region, so the overlap stack
                    # is no longer valid. Reset cycling so a new stack is computed.
                    self.cycle_stack = None
                    self.cycle_index = 0

                # Check intent conditions
                gaze_dwell = now - self._tracker_gaze_dwell_start
                intent_idle = (
                    now - self._tracker_intent_idle_since
                    if self._tracker_intent_idle_since > 0.0
                    else 0.0
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

                    # Reset cycling
                    self.cycle_stack = None
                    self.cycle_index = 0

                    # Reset to prevent immediate re-trigger
                    self._tracker_gaze_dwell_start = now
                    self._tracker_intent_idle_since = now
                    self.manual_override_triggered = False
            else:
                # No window detected, reset gaze dwell
                self._tracker_last_target = None
                self._tracker_gaze_dwell_start = 0.0

                self.cycle_stack = None
                self.cycle_index = 0
        else:
            # Invalid gaze, reset gaze dwell
            self._tracker_last_target = None
            self._tracker_gaze_dwell_start = 0.0

            self.cycle_stack = None
            self.cycle_index = 0

    def _run_tracker(self):
        """
        Main loop to track gaze and focus windows accordingly.
        """
        while self.running:
            self._run_tracker_step()
            time.sleep(POLL_INTERVAL)
