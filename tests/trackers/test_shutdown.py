from unittest.mock import MagicMock

from trackers.eyetrax_tracker import EyeTraxWrapper
from trackers.gaze_follower_tracker import GazeFollowerWrapper


def test_stop_no_release_camera_eyetrax():
    tracker = EyeTraxWrapper()
    tracker.cap = MagicMock()
    tracker.stop()
    tracker.cap.release.assert_not_called()


def test_stop_no_release_camera_gazefollower():
    tracker = GazeFollowerWrapper()
    fake_gf = MagicMock()
    tracker.gaze_follower = fake_gf
    tracker.stop()
    fake_gf.stop_sampling.assert_called_once()
    fake_gf.release.assert_not_called()


def test_release_camera_eyetrax():
    tracker = EyeTraxWrapper()
    mock_cap = MagicMock()
    tracker.cap = mock_cap
    tracker.release_camera()
    mock_cap.release.assert_called_once()
    assert tracker.cap is None


def test_release_camera_gazefollower():
    tracker = GazeFollowerWrapper()
    fake_gf = MagicMock()
    tracker.gaze_follower = fake_gf
    tracker.camera = MagicMock()
    tracker.release_camera()
    fake_gf.release.assert_called_once()
    assert tracker.camera is None
