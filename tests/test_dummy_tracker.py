from trackers.base_tracker import BaseTracker


class DummyTracker(BaseTracker):
    def set_video_device(self, device_index: int):
        pass

    def get_data(self):
        return {"gaze": {"x": 50, "y": 100}, "timestamp": 123456.0}

    def stop(self):
        pass


def test_dummy_tracker_get_data():
    tracker = DummyTracker()
    data = tracker.get_data()
    assert data["gaze"]["x"] == 50
    assert data["gaze"]["y"] == 100
    assert data["timestamp"] == 123456.0
