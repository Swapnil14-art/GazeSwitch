import os
import time
from typing import Any

import cv2
from eyetrax import GazeEstimator, run_9_point_calibration
from eyetrax.filters import KDESmoother

from system_platform.utils import get_model_dir
from trackers.base_tracker import BaseTracker


class EyeTraxWrapper(BaseTracker):
    def __init__(
        self,
        cap: cv2.VideoCapture,
        screen_width: int,
        screen_height: int,
        monitor_index: int = 0,
        model_dir: str = get_model_dir(),
    ):
        self.tracker = GazeEstimator()
        self.cap = cap
        self.monitor_index = monitor_index

        self.model_path = f"{model_dir}/gaze_model_{monitor_index}.pkl"
        self.model_loaded = False

        self.confidence_level = 0.95
        self.screen_width = screen_width
        self.screen_height = screen_height

    def is_ready(self) -> bool:
        if not os.path.exists(self.model_path):
            return False

        if not os.path.isfile(self.model_path):
            return False

        if os.path.getsize(self.model_path) == 0:
            return False

        return True

    def is_camera_ready(self) -> bool:
        return self.cap is not None and self.cap.isOpened()

    def preload_model(self):
        if self.is_ready():
            self.tracker.load_model(self.model_path)
            self.model_loaded = True

            self.smoother = KDESmoother(
                self.screen_width, self.screen_height, confidence=self.confidence_level
            )

    def preload_camera(self):
        if not self.cap:
            return

        if not self.is_camera_ready():
            for _ in range(3):
                self.cap.read()
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

        ret, frame = self.cap.read()  # type: ignore[reportOptionalMemberAccess]
        if not ret or frame is None:
            return {"gaze": {"x": None, "y": None}, "timestamp": time.time()}

        features, blink = self.tracker.extract_features(frame)

        if features is not None and not blink:
            x, y = self.tracker.predict([features])[0]
            x_pred, y_pred = self.smoother.step(x, y)
        else:
            x_pred = y_pred = None

        result = {"gaze": {"x": x_pred, "y": y_pred}, "timestamp": time.time()}

        return result

    def stop(self):
        pass

    def __str__(self):
        return "eyetrax"
