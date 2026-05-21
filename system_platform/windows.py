import logging
import threading

import win32api
import win32com.client
import win32con
import win32gui
from pygrabber.dshow_graph import FilterGraph
from winotify import Notification, audio

from system_platform.window_manager import MonitorListener, WindowManager
from ui.tray import resource_path

logger = logging.getLogger(__name__)


class WindowsMonitorListener(MonitorListener):
    def __init__(self, callback):
        self.callback = callback
        self.hwnd = None
        self.running = False
        self.thread = None
        self.class_name = "GazeControlMonitorListener"

    def start(self) -> None:
        if self.running:
            return
        self.running = True
        self.thread = threading.Thread(target=self._create_listener_window, daemon=True)
        self.thread.start()
        logger.info("Windows monitor listener started")

    def stop(self) -> None:
        self.running = False

        hwnd = self.hwnd
        self.hwnd = None

        if hwnd:
            try:
                win32gui.PostMessage(hwnd, win32con.WM_CLOSE, 0, 0)
            except Exception as e:
                logger.debug(f"Error posting quit message: {e}")

    def _create_listener_window(self) -> None:
        """
        Create a hidden window to receive WM_DISPLAYCHANGE messages.
        """
        try:
            wc = win32gui.WNDCLASS()
            wc.lpszClassName = self.class_name  # type: ignore
            wc.lpfnWndProc = self._wnd_proc  # type: ignore

            try:
                class_atom = win32gui.RegisterClass(wc)
            except win32gui.error as e:
                logger.debug(f"Window class already registered: {e}")
                class_atom = self.class_name

            # Create hidden window
            self.hwnd = win32gui.CreateWindow(
                class_atom,
                "GazeControl Monitor Listener",
                win32con.WS_OVERLAPPED,
                0,
                0,
                1,
                1,
                0,
                0,
                win32api.GetModuleHandle(None),
                None,
            )

            logger.debug(f"Listener window created: hwnd={self.hwnd}")
            win32gui.PumpMessages()
        except Exception as e:
            logger.error(f"Failed to create monitor listener: {e}", exc_info=True)
        finally:
            hwnd = self.hwnd
            self.hwnd = None

            if hwnd:
                try:
                    win32gui.DestroyWindow(hwnd)
                except Exception as e:
                    logger.debug(f"Error destroying listener window: {e}")

    def _wnd_proc(self, hwnd, msg, wparam, lparam):
        if msg == win32con.WM_DISPLAYCHANGE:
            logger.debug(f"WM_DISPLAYCHANGE received: wparam={wparam}, lparam={lparam}")
            try:
                self.callback()
            except Exception as e:
                logger.error(f"Callback error: {e}", exc_info=True)
            return 0
        elif msg == win32con.WM_CLOSE:
            win32gui.DestroyWindow(hwnd)
            return 0
        elif msg == win32con.WM_DESTROY:
            win32gui.PostQuitMessage(0)
            return 0

        return win32gui.DefWindowProc(hwnd, msg, wparam, lparam)


class WindowsWindowManager(WindowManager):
    windows_to_exclude = [
        "Windows Input Experience",
        "Rainmeter",
        "Program Manager",
        "New notification",
        "System tray overflow window",
    ]

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

    def focus_window(self, window: dict) -> None:
        try:
            shell = win32com.client.Dispatch("WScript.Shell")
            # SendKeys("%") simulates an ALT press to satisfy Windows' foreground-window
            # security restrictions. SetForegroundWindow() often fails without recent
            # user input, and this workaround tricks Windows into allowing the focus
            # change.
            shell.SendKeys("%")
            win32gui.SetForegroundWindow(window["hwnd"])
        except Exception as e:
            logger.exception(f"Could not focus window: {e}")

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

    def create_monitor_listener(self, callback) -> MonitorListener | None:
        return WindowsMonitorListener(callback)
