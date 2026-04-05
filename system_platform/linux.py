import logging
import os

import notify2
from pyudev import Context
from screeninfo import get_monitors
from Xlib import X, display

from system_platform.window_manager import WindowManager

logger = logging.getLogger(__name__)


class LinuxWindowManager(WindowManager):
    windows_to_exclude = []

    def __init__(self):
        self.server = self.get_display_server()

        # X11 setup
        if self.server == "x11":
            self.disp = display.Display()
            self.root = self.disp.screen().root

    def get_display_server(self):
        """
        Detect whether the system is using X11 or Wayland.
        """
        if os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        return "x11"

    def get_windows(self) -> list[dict]:
        windows = []
        if self.server == "x11":

            def _get_children(win):
                try:
                    for child in win.query_tree().children:
                        yield child
                        yield from _get_children(child)
                except Exception:
                    return

            for win in _get_children(self.root):
                name = win.get_wm_name()
                if name and not any(excl in name for excl in self.windows_to_exclude):
                    geom = win.get_geometry()
                    windows.append(
                        {
                            "hwnd": win,
                            "title": name,
                            "rect": (geom.x, geom.y, geom.width, geom.height),
                        }
                    )
        return windows

    def focus_window(self, window: dict) -> None:
        if self.server == "x11":
            try:
                window["hwnd"].set_input_focus(X.RevertToParent, X.CurrentTime)
                self.disp.sync()
            except Exception as e:
                logger.error(f"Could not focus window: {e}")

    def get_screen_size(self) -> tuple[int, int]:
        monitor = get_monitors()[0]
        return monitor.width, monitor.height

    def list_video_devices(self) -> dict[str, int]:
        devices = {}
        context = Context()

        for index, device in enumerate(context.list_devices(subsystem="video4linux")):
            device_name = device.get("ID_MODEL", device.sys_name)

            if device_name in devices.keys():
                continue

            devices[device_name] = index 
        
        return devices

    def get_focused_window(self) -> dict | None:
        if self.server == "x11":
            hwnd = self.disp.get_input_focus().focus
            if not hwnd:
                return None

            title = hwnd.get_wm_name()
            if not title:
                return None

            if any(excl in title for excl in self.windows_to_exclude):
                return None

            rect = hwnd.get_geometry()
            return {
                "hwnd": hwnd,
                "title": title,
                "rect": (rect.x, rect.y, rect.width, rect.height),
            }
        return None

    def window_key(self, window: dict) -> str:
        return window["hwnd"]

    def notify(self, title: str) -> None:
        try:
            notify2.init("GazeControl")
            n = notify2.Notification(title)
            n.show()
        except Exception as e:
            logger.debug(f"Notification failed: {e}")
