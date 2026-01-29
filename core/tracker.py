import time
from threading import Thread

from pynput import keyboard

from system_platform.window_manager import WindowManager
from trackers.eyetrax_tracker import EyeTraxWrapper

DWELL_TIME = 0.8  # seconds
TYPING_IDLE_TIME = 1.0  # seconds
POLL_INTERVAL = 0.05  # seconds


class GazeTracker:
    def __init__(self, window_manager: WindowManager):
        self.wm = window_manager
        self.running = False
        self.current_window = None
        self.estimator = None
        self.last_keystroke_time = time.time()

        self.screen_width, self.screen_height = self.wm.get_screen_size()

        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        self.keyboard_listener.start()

    def _on_key_press(self, _):
        self.last_keystroke_time = time.time()

    def start_tracking(self, icon=None, _=None):
        """
        Start the gaze tracking process.

        This function is used as pystray menu callbacks. pystray invokes menu
        callbacks with two arguments (icon, menu_item), even if they are not
        needed by the implementation. The parameters are therefore accepted
        for compatibility but intentionally unused.

        Args:
            icon (pystray.Icon | None): The system tray icon instance provided
                by pystray when invoked from the tray menu. Optional to allow
                manual invocation.
            _ (pystray.MenuItem | None): The menu item that triggered the callback.
                Unused by design.
        """
        if self.running:
            return

        self.running = True
        self.estimator = EyeTraxWrapper(False, "with_glasses")
        Thread(target=self._run_tracker, daemon=True).start()
        print("Tracking started")

    def stop_tracking(self, icon=None, _=None):
        """
        Stop the gaze tracking process.

        This function is used as pystray menu callbacks. pystray invokes menu
        callbacks with two arguments (icon, menu_item), even if they are not
        needed by the implementation. The parameters are therefore accepted
        for compatibility but intentionally unused.

        Args:
            icon (pystray.Icon | None): The system tray icon instance provided
                by pystray when invoked from the tray menu. Optional to allow
                manual invocation.
            _ (pystray.MenuItem | None): The menu item that triggered the callback.
                Unused by design.
        """
        self.running = False
        if self.estimator:
            self.estimator.stop()
        print("Tracking stopped")

    def _run_tracker(self):
        """
        Main loop to track gaze and focus windows accordingly.
        """
        last_target = None
        gaze_dwell_start = 0.0
        intent_idle_since = 0.0

        while self.running:
            now = time.time()

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
                print(f"Predicted gaze at: ({x}, {y})")
                windows = self.wm.get_windows()
                target_window = self.wm.window_at_point(int(x), int(y), windows)

                if target_window:
                    # Reset dwell timer if target changes
                    if target_window != last_target:
                        last_target = target_window
                        gaze_dwell_start = now

                    # Check intent conditions
                    gaze_dwell = now - gaze_dwell_start
                    intent_idle = (
                        now - intent_idle_since if intent_idle_since > 0.0 else 0.0
                    )

                    if (
                        gaze_dwell >= DWELL_TIME
                        and intent_idle >= TYPING_IDLE_TIME
                        and (
                            not self.current_window
                            or target_window != self.current_window
                        )
                    ):
                        print(f"Focusing window: {target_window}")
                        self.wm.focus_window(target_window)
                        self.current_window = target_window

                        # Reset to prevent immediate re-trigger
                        gaze_dwell_start = now
                        intent_idle_since = now
                else:
                    # No window detected, reset gaze dwell
                    last_target = None
                    gaze_dwell_start = 0.0
            else:
                # Invalid gaze, reset gaze dwell
                last_target = None
                gaze_dwell_start = 0.0

            time.sleep(POLL_INTERVAL)
