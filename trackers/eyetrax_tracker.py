import os
import time
from typing import Any

from eyetrax import GazeEstimator, run_9_point_calibration

from system_platform.utils import get_model_dir
from trackers.base_tracker import BaseTracker


class EyeTraxWrapper(BaseTracker):
    def __init__(self, cap, monitor_index: int = 0, model_dir: str = get_model_dir()):
        self.tracker = GazeEstimator()
        self.cap = cap
        self.monitor_index = monitor_index

        self.model_path = f"{model_dir}/gaze_model_{monitor_index}.pkl"

        self.model_loaded = False

    def is_ready(self) -> bool:
        return os.path.exists(self.model_path)

    def is_camera_ready(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def preload_model(self):
        if self.is_ready():
            self.tracker.load_model(self.model_path)
            self.model_loaded = True

    def preload_camera(self):
        if not self.is_camera_ready():
            for _ in range(3):
                self.cap.read()  # type: ignore
                time.sleep(0.01)

    def calibrate(self, device_index: int):
        run_9_point_calibration(self.tracker, device_index, self.monitor_index)
        self.tracker.save_model(self.model_path)
        self.model_loaded = True

    def start(self):
        if not self.model_loaded:
            self.preload_model()

        self.preload_camera()

    def get_data(self) -> dict[str, Any]:
        if not self.is_camera_ready():
            raise RuntimeError("Camera not started")

        _, frame = self.cap.read()  # type: ignore
        features, blink = self.tracker.extract_features(frame)
        x, y = (
            self.tracker.predict([features])[0]
            if features is not None and not blink
            else (None, None)
        )

        result = {"gaze": {"x": x, "y": y}, "timestamp": time.time()}

        return result

    def stop(self):
        pass

    def release_camera(self):
        if self.cap:
            self.cap.release()
            self.cap = None

    def __str__(self):
        return "eyetrax"
