from typing import Any

import cv2
from eyetrax import GazeEstimator, run_9_point_calibration

from trackers.base_tracker import BaseTracker


class EyeTraxWrapper(BaseTracker):
    def __init__(self, calibrate: bool = False):
        self.tracker = GazeEstimator()

        if calibrate:
            run_9_point_calibration(self.tracker)
            self.tracker.save_model("models/eyetrax/gaze_model.pkl")
        else:
            self.tracker.load_model("models/eyetrax/gaze_model.pkl")

        self.cap = cv2.VideoCapture(0)

    def get_data(self) -> dict[str, Any]:
        ret, frame = self.cap.read()
        features, blink = self.tracker.extract_features(frame)
        x, y = (
            self.tracker.predict([features])[0]
            if features and not blink
            else (None, None)
        )

        result = {
            "gaze": {"x": x, "y": y},
        }

        return result

    def stop(self):
        self.cap.release()
