import os
from typing import Any

from gazefollower import GazeFollower
from gazefollower.calibration import SVRCalibration
from gazefollower.camera import WebCamCamera

from system_platform.utils import get_model_dir
from trackers.base_tracker import BaseTracker


class GazeFollowerWrapper(BaseTracker):
    def __init__(self, calibration_mode: str = "", model_dir: str = get_model_dir()):
        self.model_path = model_dir + calibration_mode
        self.gaze_follower = None

    def is_ready(self) -> bool:
        return os.path.exists(self.model_path)

    def calibrate(self, device_index: int):
        self.gaze_follower = GazeFollower(
            camera=WebCamCamera(webcam_id=device_index),
            calibration=SVRCalibration(model_save_path=self.model_path),
        )

        self.gaze_follower.calibrate()
        self.gaze_follower.calibration.save_model()

    def start(self, device_index: int):
        if self.gaze_follower is None:
            self.gaze_follower = GazeFollower(
                camera=WebCamCamera(webcam_id=device_index),
                calibration=SVRCalibration(model_save_path=self.model_path),
            )

        self.gaze_follower.start_sampling()

    def set_video_device(self, device_index: int):
        if self.gaze_follower:
            self.gaze_follower.camera = WebCamCamera(webcam_id=device_index)

    def get_data(self) -> dict[str, Any]:
        """
        get_gaze_info() returns a GazeInfo object with attributes:
        - features: The features extracted from the gaze estimation model.
        - raw_gaze_coordinates: The x, y coordinates of the gaze point from the gaze
        estimation model.
        - calibrated_gaze_coordinates: The x, y coordinates of the gaze point from the
        calibration model.
        - filtered_gaze_coordinates: The x, y coordinates of the gaze point from
        the filter.
        - left_openness: The openness of the left eye.
        - right_openness: The openness of the right eye.
        - event: The type of eye movement event (default is EyeMovementEvent.UNKNOWN).
        - status: Indicates whether gaze estimation was successful (default is False).
        - tracking_state: The current state of gaze tracking
        (default is TrackingState.FACE_MISSING).
        - timestamp: The timestamp when gaze information was recorded (default is 0).
        """
        if self.gaze_follower:
            gaze_info = self.gaze_follower.get_gaze_info()

            if gaze_info:
                return {
                    "gaze": {
                        "x": (
                            gaze_info.calibrated_gaze_coordinates[0]
                            if gaze_info.calibrated_gaze_coordinates is not None
                            else None
                        ),
                        "y": (
                            gaze_info.calibrated_gaze_coordinates[1]
                            if gaze_info.calibrated_gaze_coordinates is not None
                            else None
                        ),
                    },
                    "timestamp": gaze_info.timestamp,
                }

        return {"gaze": {"x": None, "y": None}, "timestamp": None}

    def stop(self):
        if self.gaze_follower:
            self.gaze_follower.stop_sampling()
            self.gaze_follower.release()

    def __str__(self):
        return "gazefollower"
