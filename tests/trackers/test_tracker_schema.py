from unittest.mock import MagicMock

from tests.fixtures.dummy_tracker import DummyTracker
from trackers.eyetrax_tracker import EyeTraxWrapper
from trackers.gaze_follower_tracker import GazeFollowerWrapper


def assert_valid_gaze_schema(data):
    assert "gaze" in data
    assert "x" in data["gaze"]
    assert "y" in data["gaze"]
    assert "timestamp" in data


def test_dummy_tracker_schema():
    tracker = DummyTracker()
    data = tracker.get_data()
    assert_valid_gaze_schema(data)


def test_eyetrax_tracker_schema():
    tracker = EyeTraxWrapper(cap=MagicMock())

    tracker.cap.read.return_value = (True, MagicMock())  # type: ignore[union-attr]

    tracker.tracker.predict = MagicMock(return_value=[(100, 200)])
    tracker.tracker.extract_features = MagicMock(return_value=(MagicMock(), False))

    data = tracker.get_data()
    assert_valid_gaze_schema(data)


def test_gazefollower_tracker_schema():
    tracker = GazeFollowerWrapper()

    class FakeGazeInfo:
        calibrated_gaze_coordinates = (300, 400)
        timestamp = 123456.0

    tracker.gaze_follower = MagicMock()
    tracker.gaze_follower.get_gaze_info.return_value = FakeGazeInfo()

    data = tracker.get_data()
    assert_valid_gaze_schema(data)
