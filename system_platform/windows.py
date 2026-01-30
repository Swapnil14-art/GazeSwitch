import win32api
import win32com.client
import win32gui

from system_platform.window_manager import WindowManager


class WindowsWindowManager(WindowManager):
    windows_to_exclude = ["Windows Input Experience", "Rainmeter", "Program Manager"]

    def get_windows(self) -> list[dict]:
        """
        Get a list of all visible windows with their handles, titles, and rectangles.

        Returns:
            list[dict]: A list of dictionaries containing window handles, titles,
            and rectangles.
        """
        windows = []

        def callback(hwnd, _):
            if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
                rect = win32gui.GetWindowRect(hwnd)
                title = win32gui.GetWindowText(hwnd)
                windows.append({"hwnd": hwnd, "title": title, "rect": rect})

        win32gui.EnumWindows(callback, None)

        windows = [
            w
            for w in windows
            if not any(excl in w["title"] for excl in self.windows_to_exclude)
        ]

        return windows

    def window_at_point(self, x: int, y: int, windows: list[dict]):
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
            left, top, right, bottom = w["rect"]
            if left <= x <= right and top <= y <= bottom:
                return w
        return None

    def focus_window(self, window: dict) -> None:
        """
        Bring the specified window to the foreground.

        Args:
            window (dict): The window to focus.
        """
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys("%")
            win32gui.SetForegroundWindow(window["hwnd"])
        except Exception as e:
            print(f"Could not focus window: {e}")

    def get_screen_size(self):
        return win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)
