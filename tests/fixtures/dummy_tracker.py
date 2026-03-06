from trackers.base_tracker import BaseTracker


class DummyTracker(BaseTracker):
    def is_ready(self):
        return True

    def preload(self):
        pass

    def calibrate(self, device_index):
        pass

    def start(self, device_index):
        pass

    def set_video_device(self, device_index):
        pass

    def stop(self):
        pass

    def get_data(self):
        return {"gaze": {"x": 50, "y": 50}, "timestamp": 123456.0}
