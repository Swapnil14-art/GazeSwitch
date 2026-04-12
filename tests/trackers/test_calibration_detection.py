from trackers.eyetrax_tracker import EyeTraxWrapper
from trackers.gaze_follower_tracker import GazeFollowerWrapper


def test_model_exists_eyetrax(tmp_path):
    model_file = tmp_path / "gaze_model.pkl"
    model_file.write_text("fake model")

    tracker = EyeTraxWrapper(cap=None)
    tracker.model_path = str(model_file)

    assert tracker.is_ready() is True


def test_model_missing_eyetrax(tmp_path):
    tracker = EyeTraxWrapper(cap=None)
    tracker.model_path = str(tmp_path / "missing_model.pkl")

    assert tracker.is_ready() is False


def test_model_exists_gazefollower(tmp_path):
    model_file = tmp_path / "gaze_model.pkl"
    model_file.write_text("fake model")

    tracker = GazeFollowerWrapper()
    tracker.model_path = str(model_file)

    assert tracker.is_ready() is True


def test_model_missing_gazefollower(tmp_path):
    tracker = GazeFollowerWrapper()
    tracker.model_path = str(tmp_path / "missing_model.pkl")

    assert tracker.is_ready() is False
