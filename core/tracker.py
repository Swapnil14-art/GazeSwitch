import logging
import time
from threading import Thread

import cv2
from pynput import keyboard
from screeninfo import get_monitors

from core.dwell_learner import DwellLearner
from system_platform.config import load_config, save_config
from system_platform.window_manager import WindowManager
from trackers.base_tracker import BaseTracker
from trackers.eyetrax_tracker import EyeTraxWrapper

logger = logging.getLogger(__name__)

DWELL_TIME = 0.5  # seconds
TYPING_IDLE_TIME = 1.0  # seconds
POLL_INTERVAL = 0.05  # seconds
CYCLE_RESET_TIME = 1.5  # seconds
MONITOR_CHECK_INTERVAL = 10.0  # seconds
DEFAULT_CAMERA_INDEX = 0
DEFAULT_MANUAL_OVERRIDE_HOTKEY = "<alt>+\\"
DEFAULT_CYCLE_WINDOWS_HOTKEY = "<alt>+]"
DEFAULT_CYCLE_WINDOWS_REVERSE_HOTKEY = "<alt>+["

# REGRET_WINDOW and SUCCESS_WINDOW define how user behaviour is interpreted.
# They are not hard thresholds, but are used to derive signal strength
# for adaptive learning (early corrections - regret, long stays - success).

# If the user corrects focus within this window after an automatic
# gaze focus, it is treated as a regret event (focus happened too early).
REGRET_WINDOW = 1.0  # seconds

# If the user stays in the auto-focused window longer than this,
# the focus timing is considered successful.
SUCCESS_WINDOW = 2.0  # seconds


class GazeTracker:
    def __init__(self, window_manager: WindowManager):
        # Configuration
        self.config = load_config()

        # Window manager integration
        self.wm = window_manager

        # Monitor and camera configuration
        monitors = get_monitors()
        self.monitor_rects = [
            {
                "id": i,
                "name": m.name,
                "left": m.x,
                "top": m.y,
                "right": m.x + m.width,
                "bottom": m.y + m.height,
            }
            for i, m in enumerate(monitors)
        ]

        self.monitor_camera_mapping: dict[int, dict[str, bool | int]] = self.config.get(
            "monitor_camera_mapping", {}
        )
        if not self.monitor_camera_mapping:
            self.monitor_camera_mapping = {
                monitor["id"]: {"enabled": True, "camera_index": DEFAULT_CAMERA_INDEX}
                for monitor in self.monitor_rects
            }
            self.config["monitor_camera_mapping"] = self.monitor_camera_mapping
            save_config(self.config)

        unique_cameras = {
            config["camera_index"] for config in self.monitor_camera_mapping.values()
        }
        self.camera_cap_mapping = {
            camera_index: cv2.VideoCapture(camera_index)
            for camera_index in unique_cameras
        }

        self.virtual_left = min(m.x for m in monitors)
        self.virtual_top = min(m.y for m in monitors)
        self.virtual_right = max(m.x + m.width for m in monitors)
        self.virtual_bottom = max(m.y + m.height for m in monitors)
        self.virtual_width = self.virtual_right - self.virtual_left
        self.virtual_height = self.virtual_bottom - self.virtual_top

        self._last_monitor_check = time.time()

        # Gaze trackers
        self.estimators: dict[int, BaseTracker] = {}

        for monitor_id, config in self.monitor_camera_mapping.items():
            enabled = config.get("enabled", True)
            camera_index = config.get("camera_index", DEFAULT_CAMERA_INDEX)
            cap = self.camera_cap_mapping.get(camera_index)

            if not enabled:
                continue

            if not cap:
                logger.warning(
                    f"Camera {camera_index} not available for monitor "
                    f"{monitor_id}, skipping estimator creation"
                )
                continue

            estimator = EyeTraxWrapper(cap=cap, monitor_index=monitor_id)

            if estimator.is_ready():
                Thread(
                    target=self._preload_gaze_model,
                    args=(
                        estimator,
                        monitor_id,
                    ),
                    daemon=True,
                ).start()
            Thread(
                target=self._preload_camera,
                args=(
                    estimator,
                    monitor_id,
                ),
                daemon=True,
            ).start()

            self.estimators[monitor_id] = estimator

        # Runtime state
        self.running = False
        self.current_window = None
        self.last_keystroke_time = time.time()

        # Input listeners
        self.keyboard_listener = keyboard.Listener(on_press=self._on_key_press)
        self.keyboard_listener.start()

        # Manual override hotkey
        self.manual_override_triggered = False
        self.manual_override_hotkey = self.config.get(
            "manual_override_hotkey", DEFAULT_MANUAL_OVERRIDE_HOTKEY
        )

        # Cycle windows hotkeys
        self.cycle_forward_triggered = False
        self.cycle_windows_hotkey = self.config.get(
            "cycle_windows_hotkey", DEFAULT_CYCLE_WINDOWS_HOTKEY
        )
        self.cycle_reverse_triggered = False
        self.cycle_windows_reverse_hotkey = self.config.get(
            "cycle_windows_reverse_hotkey", DEFAULT_CYCLE_WINDOWS_REVERSE_HOTKEY
        )

        self.hotkey_listener = None
        self._start_hotkey_listener()

        # Cycling state for overlapping windows.
        # We freeze the initial window stack so cycling remains deterministic
        # even though focusing windows changes the OS Z-order.
        self.cycle_stack = None
        self.cycle_index = 0
        self.last_cycle_time = 0

        # Adaptive dwell learning state.
        # The learner dynamically adjusts the gaze dwell threshold based on
        # user behaviour (regret events vs successful focuses).
        initial_dwell = self.config.get("adaptive_dwell", DWELL_TIME)
        self.dwell_learner = DwellLearner(initial_dwell)

        # Track last automatic focus so we can detect regret or success
        self.last_auto_focus_time = None
        self.last_auto_focused_window = None

        # Main loop tracking state
        self._tracker_last_target = None
        self._tracker_gaze_dwell_start = 0.0
        self._tracker_intent_idle_since = 0.0

    def _preload_gaze_model(self, estimator: BaseTracker, monitor_id: int):
        try:
            logger.info(f"Preloading gaze model for monitor {monitor_id}...")
            estimator.preload_model()
            logger.info("Model preloaded")
        except Exception:
            logger.exception("Gaze model preload failed")

    def _preload_camera(self, estimator: BaseTracker, monitor_id: int):
        try:
            logger.info(f"Preloading camera for monitor {monitor_id}...")
            estimator.preload_camera()
            logger.info("Camera preloaded")
        except Exception:
            logger.exception("Camera preload failed")

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

        # Regret event - User used manual override shortly after
        # an automatic focus (focus happened too early)
        time_since_focus = (
            time.time() - self.last_auto_focus_time
            if self.last_auto_focus_time is not None
            else None
        )
        if time_since_focus and time_since_focus < REGRET_WINDOW:
            # Convert time into a normalised regret strength
            # - Immediate correction (time = 0) - strength = 1.0 (strong regret)
            # - Near the boundary (time = REGRET_WINDOW) - strength = 0.0 (weak regret)
            #
            # This creates a smooth gradient instead of a binary signal,
            # allowing the learner to adjust proportionally to how wrong it was.
            strength = 1 - (time_since_focus / REGRET_WINDOW)

            if self.dwell_learner.on_regret(strength):
                self._persist_dwell()

            self.last_auto_focus_time = None

    def _cycle_windows(self):
        """
        Cycle through all windows under the gaze point.
        """
        self.cycle_forward_triggered = True
        logger.info("Cycle windows hotkey triggered")

    def _cycle_windows_reverse(self):
        """
        Cycle through all windows under the gaze point in reverse.
        """
        self.cycle_reverse_triggered = True
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

        # Regret event - User manually switched window shortly after an
        # automatic focus
        time_since_focus = (
            time.time() - self.last_auto_focus_time
            if self.last_auto_focus_time is not None
            else None
        )
        if time_since_focus and time_since_focus < REGRET_WINDOW:
            if not self._same_window(focused, self.last_auto_focused_window):
                # Convert time into a normalised regret strength
                # - Immediate correction (time = 0) → strength = 1.0 (strong regret)
                # - Near the boundary (time = REGRET_WINDOW) → strength = 0.0 (weak)
                #
                # This creates a smooth gradient instead of a binary signal,
                # allowing the learner to adjust proportionally to how wrong it was.
                strength = 1 - (time_since_focus / REGRET_WINDOW)

                if self.dwell_learner.on_regret(strength):
                    self._persist_dwell()

                self.last_auto_focus_time = None

    def _persist_dwell(self):
        """
        Persist the learned dwell value to the config.

        This is only called when the learner actually changes the dwell
        threshold to avoid excessive disk writes.
        """
        dwell = self.dwell_learner.get()

        self.config["adaptive_dwell"] = dwell
        save_config(self.config)

        logger.debug(f"Adaptive dwell saved: {dwell:.2f}s")

    def update_monitor_camera_mapping(
        self, monitor_camera_mapping: dict[int, dict[str, bool | int]]
    ):
        """
        Update the monitor-camera mapping configuration.

        Args:
            monitor_camera_mapping (dict[int, dict]): A dictionary mapping monitor
            IDs to their configurations.
        """
        # Set up new cameras
        for monitor_id, config in monitor_camera_mapping.items():
            enabled = config.get("enabled")
            camera_index = config.get("camera_index")

            if (
                enabled
                and camera_index is not None
                and camera_index not in self.camera_cap_mapping
            ):
                self.camera_cap_mapping[camera_index] = cv2.VideoCapture(camera_index)

        # Update estimators
        for monitor_id, config in monitor_camera_mapping.items():
            enabled = config.get("enabled")
            camera_index = config.get("camera_index", DEFAULT_CAMERA_INDEX)

            estimator_exists = monitor_id in self.estimators

            if enabled:
                # Case 1: Monitor newly enabled (no estimator yet)
                if not estimator_exists:
                    cap = self.camera_cap_mapping.get(camera_index)
                    if not cap:
                        logger.warning(
                            f"Camera {camera_index} not available for monitor "
                            f"{monitor_id}, skipping estimator creation"
                        )
                        continue
                    estimator = EyeTraxWrapper(cap=cap, monitor_index=monitor_id)
                    self.estimators[monitor_id] = estimator
                else:
                    # Case 2: Monitor stays enabled, but camera might have changed
                    old_camera_index = self.monitor_camera_mapping[monitor_id].get(
                        "camera_index"
                    )
                    if camera_index != old_camera_index:
                        # Camera changed - update the estimator's camera reference
                        cap = self.camera_cap_mapping.get(camera_index)
                        self.estimators[monitor_id].cap = cap
            else:
                # Case 3: Monitor now disabled
                if estimator_exists:
                    del self.estimators[monitor_id]

        # Update local state and persist
        self.monitor_camera_mapping.update(monitor_camera_mapping)
        self.config["monitor_camera_mapping"] = self.monitor_camera_mapping
        save_config(self.config)

        # Clean up unused cameras
        enabled_cameras = {
            config["camera_index"]
            for config in self.monitor_camera_mapping.values()
            if config.get("enabled") and config.get("camera_index") is not None
        }
        cleaned = []
        for camera_index in list(self.camera_cap_mapping.keys()):
            if camera_index not in enabled_cameras:
                self.release_camera(camera_index)
                cleaned.append(camera_index)

        if cleaned:
            logger.info(f"Cleaned up unused cameras: {cleaned}")

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

    def calibrate(self, icon=None, _=None):
        """
        Starts the calibration process.
        """
        logger.info("Starting calibration")
        for monitor_id, estimator in self.estimators.items():
            camera_index = self.monitor_camera_mapping[monitor_id]["camera_index"]
            estimator.calibrate(camera_index)
        logger.info("Calibration finished")

    def start_tracking(self):
        """
        Start the gaze tracking process.
        """
        if self.running:
            return

        for estimator in self.estimators.values():
            if not estimator.is_ready():
                self.wm.notify("Calibration required before Tracking!")
                logger.warning("Calibration required before Tracking")
                return

        for estimator in self.estimators.values():
            estimator.start()

        self.running = True
        Thread(target=self._run_tracker, daemon=True).start()

        logger.info("Tracking started")

    def stop_tracking(self):
        """
        Stop the gaze tracking process.
        """
        self.running = False
        logger.info("Tracking stopped")

    def release_camera(self, camera_index: int):
        """
        Release the camera resource.
        """
        if self.running:
            self.wm.notify("Cannot release camera while tracking!")
            logger.warning("Cannot release camera while tracking")
            return

        if camera_index not in self.camera_cap_mapping:
            logger.debug(f"Camera {camera_index} not in use, no need to release")
            return

        self.camera_cap_mapping[camera_index].release()
        del self.camera_cap_mapping[camera_index]
        self.wm.notify("Camera released")
        logger.info("Camera released")

    def _refresh_monitors(self) -> None:
        """
        Detect and handle monitor changes at runtime.
        """
        current_monitors = get_monitors()
        current_count = len(current_monitors)

        if current_count != len(self.monitor_rects):
            logger.info(
                f"Monitor count changed from {len(self.monitor_rects)} to "
                f"{current_count}"
            )

            # Rebuild monitor list
            self.monitor_rects = [
                {
                    "id": i,
                    "name": m.name,
                    "left": m.x,
                    "top": m.y,
                    "right": m.x + m.width,
                    "bottom": m.y + m.height,
                }
                for i, m in enumerate(current_monitors)
            ]

            # Recalculate virtual desktop bounds
            self.virtual_left = min(m.x for m in current_monitors)
            self.virtual_top = min(m.y for m in current_monitors)
            self.virtual_right = max(m.x + m.width for m in current_monitors)
            self.virtual_bottom = max(m.y + m.height for m in current_monitors)
            self.virtual_width = self.virtual_right - self.virtual_left
            self.virtual_height = self.virtual_bottom - self.virtual_top

    def _get_monitor_at_position(self, x: int, y: int) -> dict | None:
        """
        Find which monitor contains the given screen coordinates.

        Args:
            x (int): X coordinate of the screen position in virtual desktop space.
            y (int): Y coordinate of the screen position in virtual desktop space.

        Returns:
            dict | None: The monitor dictionary containing the position, or None if
            no monitor contains it.
        """
        for monitor in self.monitor_rects:
            if (
                monitor["left"] <= x <= monitor["right"]
                and monitor["top"] <= y <= monitor["bottom"]
            ):
                return monitor
        return None

    def _run_tracker_step(self):
        """
        Helper function to run a single iteration of the main
        tracking loop.
        """
        now = time.time()

        # Periodically check for monitor changes every 10 seconds
        if now - self._last_monitor_check > MONITOR_CHECK_INTERVAL:
            self._refresh_monitors()
            self._last_monitor_check = now

        # Detect a successful auto-focus.
        # If the user stayed in the focused window long enough without correcting it,
        # we treat this as confirmation that the dwell timing was appropriate.
        time_since_focus = (
            time.time() - self.last_auto_focus_time
            if self.last_auto_focus_time is not None
            else None
        )
        if time_since_focus and time_since_focus > SUCCESS_WINDOW:
            # Convert time into a normalised success strength:
            # - Just above threshold → small strength (weak confirmation)
            # - Much longer stay → strength approaches 1.0 (strong confidence)
            #
            # This rewards the system more when the user clearly intended the focus.
            strength = min(1.0, (time_since_focus - SUCCESS_WINDOW) / SUCCESS_WINDOW)
            if self.dwell_learner.on_success(strength):
                self._persist_dwell()

            self.last_auto_focus_time = None

        # Keep current_window in sync with OS focus
        self._sync_focused_window()

        # Try each estimator and use the one where gaze falls within the monitor bounds
        x = y = None
        for monitor_id, estimator in self.estimators.items():
            monitor = self.monitor_rects[monitor_id]
            data = estimator.get_data()
            gx, gy = data["gaze"]["x"], data["gaze"]["y"]
            if gx is not None and gy is not None:
                x_virt, y_virt = gx + monitor["left"], gy + monitor["top"]

                # Only use this gaze data if it falls within this monitor's bounds
                if (
                    monitor["left"] <= x_virt <= monitor["right"]
                    and monitor["top"] <= y_virt <= monitor["bottom"]
                ):
                    x, y = x_virt, y_virt
                    break

        # Determine if the user is actively typing or not
        typing_idle = (now - self.last_keystroke_time) >= TYPING_IDLE_TIME

        if not typing_idle:
            self._tracker_intent_idle_since = 0.0
        elif self._tracker_intent_idle_since == 0.0:
            self._tracker_intent_idle_since = now

        if x is not None and y is not None:
            # Check if gaze falls within any actual monitor's bounds
            monitor = self._get_monitor_at_position(int(x), int(y))
            if not monitor:
                # Gaze is outside of all monitors (off-screen or in monitor gap)
                logger.debug(f"Gaze at ({x}, {y}) is outside all monitors - skipping")
                return

            logger.debug(f"Predicted gaze at: ({x}, {y}) on monitor {monitor['id']}")
            windows = self.wm.get_windows()

            # Cycling is handled immediately and independently of the normal
            # dwell/intent logic because it is an explicit user action.
            if self.cycle_forward_triggered or self.cycle_reverse_triggered:
                reverse = self.cycle_reverse_triggered
                self._cycle_windows_at_gaze(int(x), int(y), windows, reverse=reverse)

                self.cycle_forward_triggered = False
                self.cycle_reverse_triggered = False

                # Skip the rest of the gaze intent logic this frame to avoid the
                # dwell-based focusing logic triggering immediately after cycling.
                # Cycling is an explicit user action and should not be followed by
                # automatic focus logic in the same iteration.
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

                # Debug line to monitor dwell, idle, and threshold
                dwell_threshold = self.dwell_learner.get()
                logger.debug(
                    f"dwell={gaze_dwell:.2f} "
                    f"idle={intent_idle:.2f} "
                    f"threshold={dwell_threshold:.2f}"
                )

                if self.manual_override_triggered or (
                    gaze_dwell >= dwell_threshold
                    and intent_idle >= TYPING_IDLE_TIME
                    and (
                        not self.current_window
                        or not self._same_window(target_window, self.current_window)
                    )
                ):
                    logger.info(
                        f"Focusing window via gaze: {target_window.get('title')}"
                    )

                    logger.debug(
                        f"Adaptive dwell threshold: {self.dwell_learner.get():.2f}s"
                    )

                    self.wm.focus_window(target_window)
                    self.current_window = target_window

                    self.last_auto_focus_time = now
                    self.last_auto_focused_window = target_window
                    self.dwell_learner.on_focus()

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
