from unittest.mock import MagicMock

from trackers.eyetrax_tracker import EyeTraxWrapper
from trackers.gaze_follower_tracker import GazeFollowerWrapper


def test_stop_releases_resources_eyetrax():
    tracker = EyeTraxWrapper()
    tracker.cap = MagicMock()
    tracker.stop()
    tracker.cap.release.assert_called_once()


def test_stop_releases_resources_gazefollower():
    tracker = GazeFollowerWrapper()
    fake_gf = MagicMock()
    tracker.gaze_follower = fake_gf
    tracker.stop()
    fake_gf.stop_sampling.assert_called_once()
    fake_gf.release.assert_called_once()
