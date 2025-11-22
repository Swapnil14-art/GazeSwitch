from typing import Any

import cv2
from eyetrax import GazeEstimator, run_9_point_calibration

from trackers.base_tracker import BaseTracker


class EyeTraxWrapper(BaseTracker):
    def __init__(self, calibrate: bool, calibration_mode: str):
        self.tracker = GazeEstimator()

        if calibrate:
            run_9_point_calibration(self.tracker)
            self.tracker.save_model(f"models/eyetrax/gaze_model_{calibration_mode}.pkl")
        else:
            self.tracker.load_model(f"models/eyetrax/gaze_model_{calibration_mode}.pkl")

        self.cap = cv2.VideoCapture(0)

    def get_data(self) -> dict[str, Any]:
        _, frame = self.cap.read()
        features, blink = self.tracker.extract_features(frame)
        x, y = (
            self.tracker.predict([features])[0]
            if features is not None and not blink
            else (None, None)
        )

        result = {
            "gaze": {"x": x, "y": y},
        }

        return result

    def stop(self):
        self.cap.release()

    def __str__(self):
        return "eyetrax"
