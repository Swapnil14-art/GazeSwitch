import win32api
import win32com.client
import win32gui
from pygrabber.dshow_graph import FilterGraph

from system_platform.window_manager import WindowManager


class WindowsWindowManager(WindowManager):
    windows_to_exclude = ["Windows Input Experience", "Rainmeter", "Program Manager"]

    def get_windows(self) -> list[dict]:
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
        for w in windows:
            left, top, right, bottom = w["rect"]
            if left <= x <= right and top <= y <= bottom:
                return w
        return None

    def focus_window(self, window: dict) -> None:
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            shell.SendKeys("%")
            win32gui.SetForegroundWindow(window["hwnd"])
        except Exception as e:
            print(f"Could not focus window: {e}")

    def get_screen_size(self) -> tuple[int, int]:
        return win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)

    def list_video_devices(self) -> dict[str, int]:
        graph = FilterGraph()
        device_names = graph.get_input_devices()

        return {name: idx for idx, name in enumerate(device_names)}
