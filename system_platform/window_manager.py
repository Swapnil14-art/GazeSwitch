from abc import ABC, abstractmethod


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

    @abstractmethod
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
        pass

    @abstractmethod
    def focus_window(self, window: dict) -> None:
        """
        Bring the specified window to the foreground.

        Args:
            window (dict): The window to focus.
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
    def list_video_devices(self) -> list[tuple[int, str]]:
        """
        Returns a list of available camera indices.

        Returns:
            list[tuple[int, str]]: A list of tuples containing camera
            indices and their names.
        """
        pass
