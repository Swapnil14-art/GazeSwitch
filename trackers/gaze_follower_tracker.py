from typing import Any

from gazefollower import GazeFollower
from gazefollower.calibration import SVRCalibration

from system_platform.utils import get_model_dir
from trackers.base_tracker import BaseTracker


class GazeFollowerWrapper(BaseTracker):
    def __init__(
        self,
        calibrate: bool,
        calibration_mode: str = "",
        model_dir: str = get_model_dir(),
    ):
        self.gaze_follower = GazeFollower(
            calibration=SVRCalibration(model_save_path=model_dir + calibration_mode)
        )

        if calibrate:
            self.gaze_follower.calibrate()
            self.gaze_follower.calibration.save_model()

        self.gaze_follower.start_sampling()

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
        gaze_info = self.gaze_follower.get_gaze_info()

        if gaze_info:
            result = {
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
                "left_openness": gaze_info.left_openness,
                "right_openness": gaze_info.right_openness,
                "event": gaze_info.event,
                "status": gaze_info.status,
                "tracking_state": gaze_info.tracking_state,
                "timestamp": gaze_info.timestamp,
            }
        else:
            result = {
                "gaze": {"x": None, "y": None},
                "left_openness": None,
                "right_openness": None,
                "event": None,
                "status": False,
                "tracking_state": None,
                "timestamp": None,
            }

        return result

    def stop(self):
        self.gaze_follower.stop_sampling()
        self.gaze_follower.release()

    def __str__(self):
        return "gazefollower"
