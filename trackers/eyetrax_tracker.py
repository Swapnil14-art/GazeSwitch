import os
import time
from typing import Any

import cv2
from eyetrax import GazeEstimator, run_9_point_calibration

from system_platform.utils import get_model_dir
from trackers.base_tracker import BaseTracker


class EyeTraxWrapper(BaseTracker):
    def __init__(
        self,
        calibrate: bool,
        calibration_mode: str = "",
        model_dir: str = get_model_dir(),
    ):
        self.tracker = GazeEstimator()
        model_suffix = f"_{calibration_mode}" if calibration_mode else ""
        model_path = f"{model_dir}/gaze_model{model_suffix}.pkl"

        if calibrate or not os.path.exists(model_path):
            run_9_point_calibration(self.tracker, 1)
            self.tracker.save_model(model_path)
        else:
            self.tracker.load_model(model_path)

        self.cap = cv2.VideoCapture(1)

    def get_data(self) -> dict[str, Any]:
        _, frame = self.cap.read()
        features, blink = self.tracker.extract_features(frame)
        x, y = (
            self.tracker.predict([features])[0]
            if features is not None and not blink
            else (None, None)
        )

        result = {"gaze": {"x": x, "y": y}, "timestamp": time.time()}

        return result

    def stop(self):
        self.cap.release()

    def __str__(self):
        return "eyetrax"
