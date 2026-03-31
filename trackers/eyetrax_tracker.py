import os
import time
from typing import Any

import cv2
from eyetrax import GazeEstimator, run_9_point_calibration

from system_platform.utils import get_model_dir
from trackers.base_tracker import BaseTracker


class EyeTraxWrapper(BaseTracker):
    def __init__(self, calibration_mode: str = "", model_dir: str = get_model_dir()):
        self.tracker = GazeEstimator()
        self.cap = None

        self.model_suffix = f"_{calibration_mode}" if calibration_mode else ""
        self.model_path = f"{model_dir}/gaze_model{self.model_suffix}.pkl"

        self.model_loaded = False

    def is_ready(self) -> bool:
        return os.path.exists(self.model_path)

    def is_camera_ready(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def preload_model(self):
        if self.is_ready():
            self.tracker.load_model(self.model_path)
            self.model_loaded = True

    def preload_camera(self, device_index: int):
        if not self.is_camera_ready():
            cap = cv2.VideoCapture(device_index)

            for _ in range(3):
                cap.read()
                time.sleep(0.01)

            self.cap = cap

    def calibrate(self, device_index: int):
        run_9_point_calibration(self.tracker, device_index)
        self.tracker.save_model(self.model_path)
        self.model_loaded = True

    def start(self, device_index: int):
        if not self.model_loaded:
            self.preload_model()

        self.preload_camera(device_index)

    def set_video_device(self, device_index: int):
        if self.cap is not None:
            self.cap.release()
            self.cap = None

        self.preload_camera(device_index)

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
