from abc import ABC, abstractmethod


class MonitorListener(ABC):
    @abstractmethod
    def start(self) -> None:
        """
        Start listening for monitor changes.
        """
        pass

    @abstractmethod
    def stop(self) -> None:
        """
        Stop listening for monitor changes.
        """
        pass


class WindowManager(ABC):
    @abstractmethod
    def get_windows(self) -> list[dict]:
        """
        Get a list of all visible windows with their handles, titles, and rectangles.

        Returns:
            list[dict]: A list of dictionaries containing window handles, titles,
            and rectangles.
        """
        pass

    def _point_in_rect(self, x, y, rect):
        left, top, right, bottom = rect
        return left <= x < right and top <= y < bottom

    def window_at_point(self, x: int, y: int, windows: list[dict]) -> dict | None:
        """
        Find the window at a given point (x, y) from a list of windows.

        Args:
            x (int): The x-coordinate of the point.
            y (int): The y-coordinate of the point.
            windows (list[dict]): A list of window dictionaries with "rect" keys.

        Returns:
            dict | None: The window dictionary at the given point, or None if not found.
        """
        for w in windows:
            if self._point_in_rect(x, y, w["rect"]):
                return w
        return None

    def windows_at_point(self, x: int, y: int, windows: list[dict]) -> list[dict]:
        """
        Find all windows at a given point (x, y) from a list of windows.

        Args:
            x (int): The x-coordinate of the point.
            y (int): The y-coordinate of the point.
            windows (list[dict]): A list of window dictionaries with "rect" keys.

        Returns:
            list[dict]: The list of all window dictionaries at the given point.
        """
        return [w for w in windows if self._point_in_rect(x, y, w["rect"])]

    @abstractmethod
    def focus_window(self, window: dict, point: tuple[int, int] | None = None) -> None:
        """
        Bring the specified window to the foreground and select typing option.

        Args:
            window (dict): The window to focus.
            point (tuple[int, int], optional): Screen coordinates (x, y) of gaze.
        """
        pass

    @abstractmethod
    def get_screen_size(self) -> tuple[int, int]:
        """
        Get the screen size (width, height).

        Returns:
            tuple[int, int]: The screen width and height.
        """
        pass

    @abstractmethod
    def list_video_devices(self) -> dict[str, int]:
        """
        Returns a list of available camera indices.

        Returns:
            dict[str, int]: A dictionary mapping camera names to their indices.
        """
        pass

    @abstractmethod
    def get_focused_window(self) -> dict | None:
        """
        Returns the currently focused window.

        Returns:
            dict | None: The focused window dictionary, or None if no window is focused.
        """
        pass

    @abstractmethod
    def window_key(self, window: dict) -> str:
        """
        Returns a unique key for a given window.

        Args:
            window (dict): The window dictionary.

        Returns:
            str: A unique key representing the window.
        """
        pass

    @abstractmethod
    def notify(self, title: str) -> None:
        """
        Show a system notification.

        Args:
            title (str): The title of the notification.
        """
        pass

    @abstractmethod
    def create_monitor_listener(self, callback) -> MonitorListener | None:
        """
        Create an OS-specific monitor change listener.

        Args:
            callback: Callable to invoke when monitor changes are detected.

        Returns:
            MonitorListener | None: A monitor listener instance, or None if unavailable.
        """
        pass
