import logging
import os

import notify2
from ewmh import EWMH
from pyudev import Context
from screeninfo import get_monitors
from Xlib import display

from system_platform.window_manager import MonitorListener, WindowManager

logger = logging.getLogger(__name__)


class LinuxWindowManager(WindowManager):
    windows_to_exclude = ["Desktop Icons"]

    def __init__(self):
        self.server = self._get_display_server()

        # X11 setup
        if self.server == "x11":
            self.disp = display.Display()
            self.root = self.disp.screen().root
            self.ewmh = EWMH()
            notify2.init("GazeControl")

    def _get_display_server(self):
        """
        Detect whether the system is using X11 or Wayland.
        """
        if os.environ.get("WAYLAND_DISPLAY"):
            return "wayland"
        return "x11"

    def _get_absolute_geometry(self, hwnd) -> tuple[int, int, int, int]:
        """
        Returns (left, top, right, bottom) of a window in absolute screen coordinates.

        Args:
            hwnd: X11 window object

        Returns:
            tuple[int, int, int, int]: A tuple (left, top, right, bottom) representing
            the window's absolute position on the screen.
        """
        try:
            # Get window geometry (client area)
            geom = hwnd.get_geometry()
            x, y, w, h = geom.x, geom.y, geom.width, geom.height

            # Walk up the parent chain to get absolute coordinates
            parent = hwnd.query_tree().parent
            while parent:
                pgeom = parent.get_geometry()
                x += pgeom.x
                y += pgeom.y
                if parent.id == self.disp.screen().root.id:
                    break
                parent = parent.query_tree().parent

            return x, y, x + w, y + h
        except Exception as e:
            logger.error(
                "Error computing absolute geometry for window: %s", e, exc_info=True
            )
            return 0, 0, 0, 0

    def get_windows(self) -> list[dict]:
        windows = []

        if self.server != "x11":
            return windows

        # Fetch all top-level client windows
        for win in self.ewmh.getClientList():
            try:
                title = self.ewmh.getWmName(win).decode("utf-8", errors="replace")
                if not title:
                    continue

                if any(excl in title for excl in self.windows_to_exclude):
                    continue

                rect = self._get_absolute_geometry(win)

                # Skip tiny or invisible windows
                if rect[2] <= 50 or rect[3] <= 50:
                    continue

                windows.append({"hwnd": win, "title": title, "rect": rect})
            except Exception as e:
                logger.error("Error while fetching window: %s", e, exc_info=True)
                continue

        return windows

    def focus_window(self, window: dict) -> None:
        if self.server == "x11":
            try:
                self.ewmh.setActiveWindow(window["hwnd"])
                self.ewmh.display.flush()
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
            hwnd = self.ewmh.getActiveWindow()
            if not hwnd:
                return None

            title = self.ewmh.getWmName(hwnd).decode("utf-8", errors="replace")
            if not title:
                return None

            rect = self._get_absolute_geometry(hwnd)
            return {
                "hwnd": hwnd,
                "title": title,
                "rect": rect,
            }
        return None

    def window_key(self, window: dict) -> str:
        return window["hwnd"]

    def notify(self, title: str) -> None:
        try:
            n = notify2.Notification(title)
            n.show()
        except Exception as e:
            logger.debug(f"Notification failed: {e}")

    def create_monitor_listener(self, callback) -> MonitorListener | None:
        raise NotImplementedError("Only works on Linux")
