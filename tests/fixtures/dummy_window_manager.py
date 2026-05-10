from typing import Dict, List, Optional, Tuple

from system_platform.window_manager import WindowManager


class DummyWindowManager(WindowManager):
    def __init__(self):
        self.windows_list = [
            {"title": "Window A", "rect": (0, 0, 200, 200), "handle": 1},
            {"title": "Window B", "rect": (150, 150, 350, 350), "handle": 2},
            {"title": "Window C", "rect": (300, 0, 500, 200), "handle": 3},
        ]
        self.focused_window = None
        self.screen_size = (1920, 1080)
        self.video_devices = {"Camera 0": 0, "Camera 1": 1}
        self.notifications = []

    def get_windows(self) -> List[Dict]:
        return self.windows_list

    def window_at_point(self, x: int, y: int, windows: List[Dict]) -> Optional[Dict]:
        for w in reversed(windows):
            x0, y0, x1, y1 = w["rect"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                return w
        return None

    def windows_at_point(self, x: int, y: int, windows: List[Dict]) -> List[Dict]:
        result = []
        for w in windows:
            x0, y0, x1, y1 = w["rect"]
            if x0 <= x <= x1 and y0 <= y <= y1:
                result.append(w)
        return result

    def focus_window(self, window: Dict) -> None:
        self.focused_window = window

    def get_screen_size(self) -> Tuple[int, int]:
        return self.screen_size

    def list_video_devices(self) -> dict[str, int]:
        return self.video_devices

    def get_focused_window(self) -> Optional[Dict]:
        return self.focused_window

    def window_key(self, window: Dict) -> str:
        return str(window.get("handle", "unknown"))

    def notify(self, title: str) -> None:
        self.notifications.append(title)

    def create_monitor_listener(self, callback) -> None:
        pass
