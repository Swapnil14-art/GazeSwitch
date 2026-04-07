from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTracker(ABC):
    """
    Abstract base for gaze tracking backends.
    """

    @abstractmethod
    def is_ready(self) -> bool:
        """
        Returns True if the tracker has a trained calibration model
        and is ready to start tracking.
        """

    @abstractmethod
    def is_camera_ready(self) -> bool:
        """
        Return True if the camera is initialised.
        """

    @abstractmethod
    def preload_model(self):
        """
        Optional: load model into memory so tracking can start instantly.
        Default does nothing.
        """
        pass

    @abstractmethod
    def preload_camera(self, device_index: int):
        """
        Optional: warm up the camera so tracking can start instantly.
        Default does nothing.
        """
        pass

    @abstractmethod
    def calibrate(self, device_index: int):
        """
        Run calibration and save the model.
        """

    @abstractmethod
    def start(self, device_index: int):
        """
        Start tracking (open camera / start sampling).
        """

    @abstractmethod
    def stop(self):
        """
        Stop tracking.
        """

    @abstractmethod
    def release_camera(self):
        """
        Release the camera resource if it's currently held.
        """

    @abstractmethod
    def set_video_device(self, device_index: int):
        """
        Set the video device by its index.

        Args:
            device_index (int): The index of the video device to use.
        """

    @abstractmethod
    def get_data(self) -> Dict[str, Any]:
        """
        Get the current gaze data from the tracker in the format:
        {
            "gaze": {"x": float | None, "y": float | None},
            ...
        }
        """
