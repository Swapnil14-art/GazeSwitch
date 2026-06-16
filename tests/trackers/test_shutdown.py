from unittest.mock import MagicMock

from trackers.eyetrax_tracker import EyeTraxWrapper


def test_stop_no_release_camera_eyetrax():
    tracker = EyeTraxWrapper(cap=MagicMock())
    tracker.stop()
    tracker.cap.release.assert_not_called()  # type: ignore[union-attr]
