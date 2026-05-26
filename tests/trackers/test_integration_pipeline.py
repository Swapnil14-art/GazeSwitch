from core.tracker import GazeTracker
from tests.fixtures.dummy_tracker import DummyTracker
from tests.fixtures.dummy_window_manager import DummyWindowManager


def test_gaze_tracker_dwell_focus():
    wm = DummyWindowManager()
    tracker = DummyTracker()
    gaze_tracker = GazeTracker(window_manager=wm)
    gaze_tracker.estimators[0] = tracker

    while True:
        gaze_tracker._run_tracker_step()
        if wm.focused_window:
            break

    assert wm.focused_window is not None
    assert "Window A" in wm.focused_window["title"]


def test_gaze_tracker_manual_override():
    wm = DummyWindowManager()
    tracker = DummyTracker()
    gaze_tracker = GazeTracker(window_manager=wm)
    gaze_tracker.estimators[0] = tracker

    # Focus initial window
    tracker.get_data = lambda: {"gaze": {"x": 50, "y": 50}, "timestamp": 123456.0}
    gaze_tracker._run_tracker_step()
    initial_window = wm.focused_window

    # Move gaze and trigger manual override
    tracker.get_data = lambda: {"gaze": {"x": 160, "y": 160}, "timestamp": 123456.0}
    gaze_tracker.manual_override_triggered = True
    gaze_tracker._run_tracker_step()

    assert wm.focused_window is not None
    assert wm.focused_window != initial_window
    assert wm.focused_window["title"] == "Window B"


def test_gaze_tracker_notifications():
    wm = DummyWindowManager()
    wm.notify("Test notification")
    assert "Test notification" in wm.notifications
