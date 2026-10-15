import sys

from core.tracker import GazeTracker
from tests.fixtures.dummy_window_manager import DummyWindowManager


def test_alt_tab_cycling_fallback():
    wm = DummyWindowManager()
    tracker = GazeTracker(wm)

    # Windows in wm: Window A, B, C
    # At (50, 50), only Window A exists (len(window_stack) == 1)
    # The Alt+Tab refinement should cycle through all windows (A -> B -> C -> A)
    windows = wm.get_windows()
    assert len(windows) == 3

    tracker._cycle_windows_at_gaze(50, 50, windows, reverse=False)
    assert wm.focused_window["title"] == "Window A"

    tracker._cycle_windows_at_gaze(50, 50, windows, reverse=False)
    assert wm.focused_window["title"] == "Window B"

    tracker._cycle_windows_at_gaze(50, 50, windows, reverse=False)
    assert wm.focused_window["title"] == "Window C"

    tracker._cycle_windows_at_gaze(50, 50, windows, reverse=False)
    assert wm.focused_window["title"] == "Window A"

    tracker.shutdown()


def test_alt_tab_cycling_reverse():
    wm = DummyWindowManager()
    tracker = GazeTracker(wm)

    windows = wm.get_windows()
    # Reverse cycling: A -> C -> B -> A
    tracker._cycle_windows_at_gaze(50, 50, windows, reverse=False)
    assert wm.focused_window["title"] == "Window A"

    tracker._cycle_windows_at_gaze(50, 50, windows, reverse=True)
    assert wm.focused_window["title"] == "Window C"

    tracker.shutdown()


def test_no_mouse_movement_in_codebase():
    """Verify that mouse movement APIs like SetCursorPos or pyautogui are not used."""
    import inspect

    from system_platform import windows as win_module

    source = inspect.getsource(win_module)
    assert "SetCursorPos" not in source
    assert "pyautogui" not in source
    assert "mouse" not in source.lower() or "monitor" in source.lower()


def test_select_typing_option_api():
    if sys.platform.startswith("win"):
        from system_platform.windows import WindowsWindowManager

        wm = WindowsWindowManager()
        assert hasattr(wm, "select_typing_option")
        # Ensure it handles non-existent or invalid hwnd gracefully without crashing
        res = wm.select_typing_option(0, point=(100, 100))
        assert res is False


def test_typing_removes_eye_sensor():
    import time

    from tests.fixtures.dummy_tracker import DummyTracker

    wm = DummyWindowManager()
    tracker = DummyTracker()
    gaze_tracker = GazeTracker(window_manager=wm)
    gaze_tracker.estimators[0] = tracker

    # Simulate user actively typing right now
    gaze_tracker.last_keystroke_time = time.time()

    # User gazes at (50, 50) which is on Window A
    tracker.get_data = lambda: {"gaze": {"x": 50, "y": 50}, "timestamp": time.time()}

    # Run step: should NOT focus any window because typing is active
    gaze_tracker._run_tracker_step()
    assert wm.focused_window is None

    # After typing stops, eye sensor activates and focuses window
    gaze_tracker.last_keystroke_time = time.time() - 2.0
    while not wm.focused_window:
        gaze_tracker._run_tracker_step()
        time.sleep(0.01)

    assert wm.focused_window is not None
    assert wm.focused_window["title"] == "Window A"
    gaze_tracker.shutdown()


def test_one_euro_filter_responsiveness_and_jitter():
    from trackers.eyetrax_tracker import GazeFilter2D, OneEuroFilter

    filt = OneEuroFilter(min_cutoff=1.2, beta=0.06)

    # 1. Steady fixation with noisy jitter around (500, 500)
    t = 1000.0
    outputs = []
    for i in range(20):
        t += 0.02
        noise = -3.0 if i % 2 == 0 else 3.0
        val = filt.filter(500.0 + noise, timestamp=t)
        outputs.append(val)

    # Filtered output should suppress jitter (variance of output < input jitter)
    import numpy as np

    assert np.std(outputs[5:]) < 2.5

    # 2. Saccade (sudden jump from 500 to 1200)
    t += 0.02
    jump_val = filt.filter(1200.0, timestamp=t)
    # Filter should respond rapidly due to high beta cutoff scaling
    assert jump_val > 800.0

    # 3. 2D Filter saccade reset
    gaze_2d = GazeFilter2D(screen_w=1920, screen_h=1080)
    gaze_2d.step(100, 100, timestamp=1000.0)
    # Huge jump exceeds saccade threshold -> snaps immediately
    sx, sy = gaze_2d.step(1200, 800, timestamp=1000.05)
    assert sx == 1200
    assert sy == 800


def test_eyetrax_confidence_and_blink_handling():
    from unittest.mock import MagicMock

    import numpy as np

    from trackers.eyetrax_tracker import EyeTraxWrapper

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    # Clean 100x100 white frame
    frame = np.full((100, 100, 3), 128, dtype=np.uint8)
    mock_cap.read.return_value = (True, frame)

    tracker = EyeTraxWrapper(cap=mock_cap)
    tracker.tracker = MagicMock()

    # Normal face tracking
    tracker.tracker.extract_features.return_value = (np.array([0.0, 0.0, 0.0]), False)
    tracker.tracker.predict.return_value = [(400.0, 300.0)]

    data = tracker.get_data()
    assert data["gaze"]["x"] == 400
    assert data["gaze"]["y"] == 300
    assert data["confidence"] > 0.5

    # Blink detection -> x=None, y=None, confidence=0
    tracker.tracker.extract_features.return_value = (np.array([0.0, 0.0, 0.0]), True)
    data = tracker.get_data()
    assert data["gaze"]["x"] is None
    assert data["gaze"]["y"] is None
    assert data["confidence"] == 0.0

    # Head turned away (>0.6 rad) -> x=None, y=None, confidence=0
    # Last 3 items in features are [yaw, pitch, roll]
    extreme_head = np.array([0.0, 0.0, 0.0, 0.85, 0.1, 0.0])
    tracker.tracker.extract_features.return_value = (extreme_head, False)
    data = tracker.get_data()
    assert data["gaze"]["x"] is None
    assert data["confidence"] == 0.0

    # Recovery: eyes return to normal center position
    normal_head = np.array([0.0, 0.0, 0.0, 0.0, 0.0, 0.0])
    tracker.tracker.extract_features.return_value = (normal_head, False)
    tracker.tracker.predict.return_value = [(700.0, 500.0)]
    data = tracker.get_data()
    assert data["gaze"]["x"] == 700
    assert data["gaze"]["y"] == 500


def test_windows_snap_layouts_point_in_rect():
    from tests.fixtures.dummy_window_manager import DummyWindowManager

    wm = DummyWindowManager()
    # Simulate Windows 11 2-window Snap Layout:
    # Left window: (0, 0, 960, 1080)
    # Right window: (960, 0, 1920, 1080)
    snap_left = {"hwnd": 1, "title": "Left Window", "rect": (0, 0, 960, 1080)}
    snap_right = {"hwnd": 2, "title": "Right Window", "rect": (960, 0, 1920, 1080)}
    windows = [snap_left, snap_right]

    # Point at x=959 is in Left Window
    w1 = wm.window_at_point(959, 500, windows)
    assert w1["title"] == "Left Window"

    # Point exactly on border at x=960 cleanly belongs to Right Window without ambiguity
    w2 = wm.window_at_point(960, 500, windows)
    assert w2["title"] == "Right Window"


def test_switching_latency_target_window():
    import time

    from tests.fixtures.dummy_tracker import DummyTracker

    wm = DummyWindowManager()
    tracker = DummyTracker()
    gaze_tracker = GazeTracker(window_manager=wm)
    gaze_tracker.estimators[0] = tracker

    # Window B is at rect (100, 100, 200, 200)
    tracker.get_data = lambda: {"gaze": {"x": 150, "y": 150}, "timestamp": time.time()}

    start_time = time.time()
    # Step until window is focused
    while not wm.focused_window:
        gaze_tracker._run_tracker_step()
        time.sleep(0.01)

    elapsed_ms = (time.time() - start_time) * 1000
    assert wm.focused_window["title"] == "Window B"
    # Latency should be roughly 100-250 ms (DWELL_TIME is 120ms)
    assert 80 <= elapsed_ms <= 300
    gaze_tracker.shutdown()


def test_repeated_switching_prevented():
    import time

    from tests.fixtures.dummy_tracker import DummyTracker

    wm = DummyWindowManager()
    tracker = DummyTracker()
    gaze_tracker = GazeTracker(window_manager=wm)
    gaze_tracker.estimators[0] = tracker

    focus_count = [0]
    orig_focus = wm.focus_window

    def mock_focus(w, point=None):
        focus_count[0] += 1
        orig_focus(w, point=point)

    wm.focus_window = mock_focus

    tracker.get_data = lambda: {"gaze": {"x": 50, "y": 50}, "timestamp": time.time()}

    # Focus Window A
    while not wm.focused_window:
        gaze_tracker._run_tracker_step()
        time.sleep(0.01)

    assert focus_count[0] == 1

    # Keep gazing at Window A for another 10 steps
    for _ in range(10):
        gaze_tracker._run_tracker_step()

    # focus_window should not have been called repeatedly
    assert focus_count[0] == 1
    gaze_tracker.shutdown()


def test_disconnected_camera_handled_gracefully():
    from unittest.mock import MagicMock

    from trackers.eyetrax_tracker import EyeTraxWrapper

    # Camera is closed/unplugged
    closed_cap = MagicMock()
    closed_cap.isOpened.return_value = False

    tracker = EyeTraxWrapper(cap=closed_cap)
    # Must NOT raise RuntimeError, but return empty gaze dict
    data = tracker.get_data()
    assert data["gaze"]["x"] is None
    assert data["gaze"]["y"] is None
    assert data["confidence"] == 0.0


def test_calibrate_releases_and_resumes_cameras():
    from unittest.mock import MagicMock, patch

    wm = DummyWindowManager()
    tracker = GazeTracker(window_manager=wm)
    mock_estimator = MagicMock()
    tracker.estimators[0] = mock_estimator
    tracker.monitor_camera_mapping[0] = {"enabled": True, "camera_index": 0}
    tracker.running = True

    mock_cap = MagicMock()
    mock_cap.isOpened.return_value = True
    tracker.camera_cap_mapping[0] = mock_cap

    with (
        patch("cv2.VideoCapture") as mock_cv2_cap,
        patch.object(tracker, "start_tracking") as mock_start,
        patch.object(tracker, "stop_tracking") as mock_stop,
    ):
        tracker.calibrate(monitor_id=0)

        # 1. Stop tracking was called to pause during calibration
        mock_stop.assert_called_once()
        # 2. Old cap was released
        mock_cap.release.assert_called_once()
        # 3. Estimator.calibrate was called with camera_index
        mock_estimator.calibrate.assert_called_once_with(0)
        # 4. New camera capture was reacquired
        mock_cv2_cap.assert_called_with(0)
        # 5. Tracking was resumed
        mock_start.assert_called_once()

    tracker.shutdown()


def test_calibrate_blocks_concurrent_runs():
    from unittest.mock import MagicMock

    wm = DummyWindowManager()
    tracker = GazeTracker(window_manager=wm)
    tracker.estimators[0] = MagicMock()

    # Simulate calibration lock already acquired
    tracker._calib_lock.acquire()
    tracker.calibrate(monitor_id=0)

    # Should notify that calibration is already in progress
    assert any("already in progress" in n for n in wm.notifications)
    tracker._calib_lock.release()
    tracker.shutdown()


def test_list_video_devices_handles_duplicates():
    import sys
    from unittest.mock import patch

    if sys.platform.startswith("win"):
        from system_platform.windows import WindowsWindowManager

        wm = WindowsWindowManager()
        with patch(
            "system_platform.windows.FilterGraph.get_input_devices",
            return_value=["HD Pro Webcam", "HD Pro Webcam"],
        ):
            devs = wm.list_video_devices()
            assert "HD Pro Webcam" in devs
            assert "HD Pro Webcam #2" in devs
            assert devs["HD Pro Webcam"] == 0
            assert devs["HD Pro Webcam #2"] == 1


def test_clear_frame_cache():
    import numpy as np

    from trackers.eyetrax_tracker import _FRAME_CACHE, clear_frame_cache

    _FRAME_CACHE[999] = (100.0, True, np.zeros((10, 10, 3)))
    assert 999 in _FRAME_CACHE
    clear_frame_cache(999)
    assert 999 not in _FRAME_CACHE

    _FRAME_CACHE[1] = (100.0, True, np.zeros((10, 10, 3)))
    _FRAME_CACHE[2] = (100.0, True, np.zeros((10, 10, 3)))
    clear_frame_cache()
    assert len(_FRAME_CACHE) == 0


def test_multi_monitor_enable_disable_and_resolution_update():
    from unittest.mock import MagicMock, patch

    wm = DummyWindowManager()
    tracker = GazeTracker(window_manager=wm)

    # Set up two monitors
    tracker.monitor_rects = [
        {
            "id": 0,
            "name": "Mon0",
            "left": 0,
            "top": 0,
            "right": 1920,
            "bottom": 1080,
            "width": 1920,
            "height": 1080,
        },
        {
            "id": 1,
            "name": "Mon1",
            "left": 1920,
            "top": 0,
            "right": 3840,
            "bottom": 1080,
            "width": 1920,
            "height": 1080,
        },
    ]

    est0 = MagicMock()
    est0.is_ready.return_value = True
    est0.is_camera_ready.return_value = True
    est0.screen_width = 1920
    est0.screen_height = 1080
    est0.smoother = MagicMock()
    est0.smoother.sw = 1920
    est0.smoother.sh = 1080

    est1 = MagicMock()
    est1.is_ready.return_value = False  # Not calibrated!
    est1.is_camera_ready.return_value = False

    tracker.estimators[0] = est0
    tracker.estimators[1] = est1

    # Monitor 0 is enabled, Monitor 1 is DISABLED
    tracker.monitor_camera_mapping = {
        0: {"enabled": True, "camera_index": 0},
        1: {"enabled": False, "camera_index": 1},
    }

    # Tracking should start successfully because disabled
    # Monitor 1's is_ready() is ignored
    with patch("threading.Thread.start"):
        tracker.start_tracking()
        assert tracker.running is True
        est0.start.assert_called_once()
        est1.start.assert_not_called()

    tracker.stop_tracking()

    # Test monitor resolution change
    class FakeMon:
        def __init__(self, x, y, w, h, name):
            self.x, self.y, self.width, self.height, self.name = x, y, w, h, name

    with patch(
        "core.tracker.get_monitors",
        return_value=[
            FakeMon(0, 0, 2560, 1440, "Mon0"),
            FakeMon(2560, 0, 1920, 1080, "Mon1"),
        ],
    ):
        tracker._refresh_monitors()
        assert tracker.monitor_rects[0]["width"] == 2560
        assert tracker.monitor_rects[0]["height"] == 1440
        assert est0.screen_width == 2560
        assert est0.screen_height == 1440
        assert est0.smoother.sw == 2560
        assert est0.smoother.sh == 1440

    tracker.shutdown()


def test_full_end_to_end_pipeline_flow(tmp_path):
    import time
    from unittest.mock import MagicMock, patch

    from tests.fixtures.dummy_tracker import DummyTracker

    wm = DummyWindowManager()
    tracker = GazeTracker(window_manager=wm)

    # 1. Configuration update & persistence
    mapping = {0: {"enabled": True, "camera_index": 0}}
    tracker.update_monitor_camera_mapping(mapping)
    assert tracker.monitor_camera_mapping[0]["enabled"] is True

    # 2. Calibration
    mock_est = MagicMock()
    mock_est.is_ready.return_value = True
    mock_est.is_camera_ready.return_value = True
    tracker.estimators[0] = mock_est

    with (
        patch("cv2.VideoCapture"),
        patch.object(tracker, "start_tracking"),
        patch.object(tracker, "stop_tracking"),
    ):
        tracker.calibrate(monitor_id=0)
        mock_est.calibrate.assert_called_once_with(0)

    # 3. Live Tracking Step -> Focus Window A
    dummy_est = DummyTracker()
    tracker.estimators[0] = dummy_est
    tracker.monitor_rects = [
        {
            "id": 0,
            "name": "Mon0",
            "left": 0,
            "top": 0,
            "right": 1920,
            "bottom": 1080,
            "width": 1920,
            "height": 1080,
        }
    ]

    # User looks at Window A (50, 50)
    dummy_est.get_data = lambda: {
        "gaze": {"x": 50, "y": 50},
        "confidence": 1.0,
        "timestamp": time.time(),
    }
    while not wm.focused_window:
        tracker._run_tracker_step()
        time.sleep(0.01)
    assert wm.focused_window["title"] == "Window A"

    # 4. User starts typing -> gaze switches to Window B (250, 250)
    tracker._on_key_press(None)
    dummy_est.get_data = lambda: {
        "gaze": {"x": 250, "y": 250},
        "confidence": 1.0,
        "timestamp": time.time(),
    }
    tracker._run_tracker_step()
    # Typing protection must suppress switch
    assert wm.focused_window["title"] == "Window A"

    # 5. User stops typing -> wait out idle time -> dwell completes ->
    # switches to Window B
    tracker.last_keystroke_time = time.time() - 1.5
    for _ in range(15):
        tracker._run_tracker_step()
        time.sleep(0.02)
    assert wm.focused_window["title"] == "Window B"

    # 6. Clean shutdown
    tracker.shutdown()
    assert tracker.running is False
