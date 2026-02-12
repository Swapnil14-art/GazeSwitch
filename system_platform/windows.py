import logging

import win32api
import win32com.client
import win32gui
from pygrabber.dshow_graph import FilterGraph
from winotify import Notification, audio

from system_platform.window_manager import WindowManager
from ui.tray import resource_path

logger = logging.getLogger(__name__)


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

    def get_focused_window(self) -> dict | None:
        hwnd = win32gui.GetForegroundWindow()
        if not hwnd:
            return None

        if not win32gui.IsWindowVisible(hwnd):
            return None

        title = win32gui.GetWindowText(hwnd)
        if not title:
            return None

        if any(excl in title for excl in self.windows_to_exclude):
            return None

        try:
            rect = win32gui.GetWindowRect(hwnd)
        except win32gui.error:
            return None

        return {
            "hwnd": hwnd,
            "title": title,
            "rect": rect,
        }

    def window_key(self, window: dict) -> str:
        return window["hwnd"]

    def notify(self, title: str) -> None:
        try:
            notification = Notification(
                app_id="GazeControl",
                title=title,
                duration="short",
                icon=resource_path("media/icon.ico"),
            )
            notification.set_audio(audio.Default, loop=False)
            notification.show()
        except Exception as e:
            logger.debug(f"Notification failed: {e}")
