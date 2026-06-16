from unittest.mock import MagicMock, patch

from trackers.eyetrax_tracker import EyeTraxWrapper


def test_preload_model_calls_load_model_eyetrax():
    tracker = EyeTraxWrapper(cap=MagicMock())
    tracker.model_path = "fake_path.pkl"

    tracker.model_loaded = False
    with patch.object(tracker.tracker, "load_model") as mock_load:
        with (
            patch("os.path.exists", return_value=True),
            patch("os.path.isfile", return_value=True),
            patch("os.path.getsize", return_value=100),
        ):
            tracker.preload_model()
            mock_load.assert_called_once_with("fake_path.pkl")
            assert tracker.model_loaded is True


def test_preload_model_does_not_load_when_model_not_ready_eyetrax():
    tracker = EyeTraxWrapper(cap=MagicMock())

    with patch.object(tracker.tracker, "load_model") as mock_load:
        with patch("os.path.exists", return_value=False):
            tracker.preload_model()
            mock_load.assert_not_called()
            assert tracker.model_loaded is False
