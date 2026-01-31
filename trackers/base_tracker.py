from abc import ABC, abstractmethod
from typing import Any, Dict


class BaseTracker(ABC):
    """
    Abstract base for gaze tracking wrappers.
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

    @abstractmethod
    def stop(self):
        """
        Stop the tracker and release any resources.
        """
