import ctypes
import logging
import threading
import time
from ctypes import wintypes

import win32api
import win32con
import win32gui
import win32process
from pygrabber.dshow_graph import FilterGraph
from winotify import Notification, audio

from system_platform.window_manager import MonitorListener, WindowManager
from ui.tray import resource_path

logger = logging.getLogger(__name__)


def enable_per_monitor_dpi_v2() -> bool:
    """
    Enable Windows Per-Monitor DPI Awareness V2 so that DWM and Win32
    return true physical pixel coordinates matching monitor bounds and camera gaze.
    """
    try:
        # DPI_AWARENESS_CONTEXT_PER_MONITOR_AWARE_V2 = -4
        res = ctypes.windll.user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4))
        if res:
            logger.info("Per-Monitor V2 DPI awareness enabled successfully")
            return True
    except Exception as e:
        logger.debug(f"SetProcessDpiAwarenessContext failed: {e}")

    try:
        # PROCESS_PER_MONITOR_DPI_AWARE = 2
        res = ctypes.windll.shcore.SetProcessDpiAwareness(2)
        if res == 0:
            logger.info("Per-Monitor DPI awareness (shcore) enabled")
            return True
    except Exception as e:
        logger.debug(f"SetProcessDpiAwareness failed: {e}")

    try:
        res = ctypes.windll.user32.SetProcessDPIAware()
        if res:
            logger.info("Process DPI aware enabled (legacy fallback)")
            return True
    except Exception as e:
        logger.debug(f"SetProcessDPIAware fallback failed: {e}")

    return False


# Initialize DPI awareness on module load
enable_per_monitor_dpi_v2()

try:
    dwmapi = ctypes.windll.dwmapi
except Exception:
    dwmapi = None


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

    def __init__(self):
        super().__init__()
        enable_per_monitor_dpi_v2()
        self._uia = None
        self._uia_initialized = False
        self._TreeScope_Descendants = None
        self._UIA_ControlTypePropertyId = None
        self._UIA_EditControlTypeId = None
        self._UIA_DocumentControlTypeId = None
        self._cached_windows: list[dict] = []
        self._last_windows_time: float = 0.0
        self._cache_ttl: float = 0.25

    def invalidate_window_cache(self) -> None:
        self._last_windows_time = 0.0

    def _init_uia(self):
        if self._uia_initialized:
            return
        self._uia_initialized = True
        try:
            import comtypes

            comtypes.CoInitialize()
            import comtypes.client

            comtypes.client.GetModule("UIAutomationCore.dll")
            from comtypes.gen.UIAutomationClient import (
                CUIAutomation,
                IUIAutomation,
                TreeScope_Descendants,
                UIA_ControlTypePropertyId,
                UIA_DocumentControlTypeId,
                UIA_EditControlTypeId,
            )

            self._uia = comtypes.client.CreateObject(
                CUIAutomation, interface=IUIAutomation
            )
            self._TreeScope_Descendants = TreeScope_Descendants
            self._UIA_ControlTypePropertyId = UIA_ControlTypePropertyId
            self._UIA_EditControlTypeId = UIA_EditControlTypeId
            self._UIA_DocumentControlTypeId = UIA_DocumentControlTypeId
        except Exception as e:
            logger.debug(f"Failed to initialize UIAutomation: {e}")
            self._uia = None

    def _get_uia(self):
        if not self._uia_initialized:
            self._init_uia()
        return self._uia

    def select_typing_option(
        self, hwnd: int, point: tuple[int, int] | None = None
    ) -> bool:
        """
        Detects if the screen or focused window has a typing option (such as an
        edit box, text area, document editing canvas, or search field) and
        selects/focuses it. Operates strictly via keyboard focus without mouse movement.

        Args:
            hwnd (int): The window handle.
            point (tuple[int, int] | None): Optional (x, y) gaze coordinates on screen.

        Returns:
            bool: True if an editable typing option was selected, False otherwise.
        """
        uia = self._get_uia()
        if uia:
            try:
                import comtypes

                comtypes.CoInitialize()
                target = None

                # 1. If gaze point (x, y) provided, check if gaze is on a typing field
                if point is not None:
                    try:
                        from ctypes.wintypes import tagPOINT

                        gx, gy = point
                        pt_elem = uia.ElementFromPoint(tagPOINT(int(gx), int(gy)))
                        if pt_elem:
                            walker = uia.ControlViewWalker
                            curr = pt_elem
                            for _ in range(4):
                                if not curr:
                                    break
                                if curr.CurrentControlType in (
                                    self._UIA_EditControlTypeId,
                                    self._UIA_DocumentControlTypeId,
                                ):
                                    target = curr
                                    break
                                curr = walker.GetParentElement(curr)
                    except Exception as e:
                        logger.debug(f"UIA ElementFromPoint lookup error: {e}")

                # 2. If no typing control directly under gaze, search in window
                if not target and hwnd:
                    try:
                        window_elem = uia.ElementFromHandle(hwnd)
                        if window_elem:
                            cond_edit = uia.CreatePropertyCondition(
                                self._UIA_ControlTypePropertyId,
                                self._UIA_EditControlTypeId,
                            )
                            cond_doc = uia.CreatePropertyCondition(
                                self._UIA_ControlTypePropertyId,
                                self._UIA_DocumentControlTypeId,
                            )
                            cond = uia.CreateOrCondition(cond_edit, cond_doc)
                            target = window_elem.FindFirst(
                                self._TreeScope_Descendants, cond
                            )
                    except Exception as e:
                        logger.debug(f"UIA window search error: {e}")

                # 3. If target found, set keyboard focus (select it for typing)
                if target:
                    try:
                        if target.CurrentIsKeyboardFocusable:
                            target.SetFocus()
                            name = target.CurrentName or "Text Control"
                            logger.info(f"Selected typing option via UIA: {name}")
                            return True
                    except Exception as e:
                        logger.debug(f"UIA SetFocus error: {e}")
            except Exception as e:
                logger.debug(f"UIA typing option search failed: {e}")

        # 4. Fallback for classic Win32 controls (Edit, RichEdit, Scintilla, etc.)
        try:
            edits = []

            def enum_cb(child, _):
                if win32gui.IsWindowVisible(child):
                    cls = win32gui.GetClassName(child).lower()
                    if any(
                        k in cls for k in ["edit", "richedit", "scintilla", "terminal"]
                    ):
                        edits.append(child)
                return True

            win32gui.EnumChildWindows(hwnd, enum_cb, None)
            if edits:
                child = edits[0]
                cur_thread = win32api.GetCurrentThreadId()
                target_thread, _ = win32process.GetWindowThreadProcessId(child)
                if cur_thread != target_thread:
                    win32process.AttachThreadInput(cur_thread, target_thread, True)
                    win32gui.SetFocus(child)
                    win32process.AttachThreadInput(cur_thread, target_thread, False)
                else:
                    win32gui.SetFocus(child)
                logger.info(f"Selected typing option via Win32 fallback: hwnd={child}")
                return True
        except Exception as e:
            logger.debug(f"Win32 fallback typing selection failed: {e}")

        return False

    def get_windows(self, force_refresh: bool = False) -> list[dict]:
        now = time.time()
        if (
            not force_refresh
            and self._cached_windows
            and (now - self._last_windows_time) < self._cache_ttl
        ):
            return self._cached_windows

        windows = []

        def is_cloaked(hwnd: int) -> bool:
            if not dwmapi:
                return False
            try:
                cloaked = wintypes.DWORD()
                hr = dwmapi.DwmGetWindowAttribute(
                    hwnd,
                    14,  # DWMWA_CLOAKED
                    ctypes.byref(cloaked),
                    ctypes.sizeof(cloaked),
                )
                return hr == 0 and cloaked.value != 0
            except Exception:
                return False

        def get_rect(hwnd: int) -> tuple[int, int, int, int]:
            if dwmapi:
                try:
                    rect = wintypes.RECT()
                    hr = dwmapi.DwmGetWindowAttribute(
                        hwnd,
                        9,  # DWMWA_EXTENDED_FRAME_BOUNDS
                        ctypes.byref(rect),
                        ctypes.sizeof(rect),
                    )
                    if hr == 0 and (rect.right > rect.left and rect.bottom > rect.top):
                        return (rect.left, rect.top, rect.right, rect.bottom)
                except Exception:
                    pass
            try:
                return win32gui.GetWindowRect(hwnd)
            except Exception:
                return (0, 0, 0, 0)

        def callback(hwnd, _):
            if not win32gui.IsWindow(hwnd) or not win32gui.IsWindowVisible(hwnd):
                return True

            title = win32gui.GetWindowText(hwnd)
            if not title or any(excl in title for excl in self.windows_to_exclude):
                return True

            if is_cloaked(hwnd):
                return True

            ex_style = win32gui.GetWindowLong(hwnd, win32con.GWL_EXSTYLE)
            if (ex_style & win32con.WS_EX_TOOLWINDOW) and not (
                ex_style & win32con.WS_EX_APPWINDOW
            ):
                return True

            rect = get_rect(hwnd)
            left, top, right, bottom = rect
            if right <= left or bottom <= top:
                return True

            windows.append({"hwnd": hwnd, "title": title, "rect": rect})
            return True

        try:
            win32gui.EnumWindows(callback, None)
        except Exception as e:
            logger.debug(f"EnumWindows query error: {e}")
        self._cached_windows = windows
        self._last_windows_time = now
        return windows

    def focus_window(self, window: dict, point: tuple[int, int] | None = None) -> None:
        hwnd = window.get("hwnd")
        if not hwnd or not win32gui.IsWindow(hwnd):
            return

        try:
            current_foreground = win32gui.GetForegroundWindow()
            if current_foreground != hwnd:
                if win32gui.IsIconic(hwnd):
                    win32gui.ShowWindow(hwnd, win32con.SW_RESTORE)
                else:
                    win32gui.ShowWindow(hwnd, win32con.SW_SHOW)

                cur_thread = win32api.GetCurrentThreadId()
                fore_thread = 0
                if current_foreground:
                    try:
                        fore_thread, _ = win32process.GetWindowThreadProcessId(
                            current_foreground
                        )
                    except Exception:
                        fore_thread = 0

                attached = False
                if fore_thread and fore_thread != cur_thread:
                    try:
                        win32process.AttachThreadInput(cur_thread, fore_thread, True)
                        attached = True
                    except Exception:
                        pass

                try:
                    win32gui.BringWindowToTop(hwnd)
                    win32gui.SetForegroundWindow(hwnd)
                except Exception:
                    try:
                        ctypes.windll.user32.AllowSetForegroundWindow(-1)
                        win32gui.SetForegroundWindow(hwnd)
                    except Exception:
                        pass
                finally:
                    if attached:
                        try:
                            win32process.AttachThreadInput(
                                cur_thread, fore_thread, False
                            )
                        except Exception:
                            pass
        except Exception as e:
            logger.exception(f"Could not focus window: {e}")

        # Invalidate cache so subsequent hit tests observe the new foreground Z-order
        self.invalidate_window_cache()

        # If the screen/window has a typing option, select it asynchronously
        # without moving mouse
        def async_select():
            try:
                self.select_typing_option(hwnd, point)
            except Exception as e:
                logger.debug(f"Could not select typing option: {e}")

        threading.Thread(target=async_select, daemon=True).start()

    def get_screen_size(self) -> tuple[int, int]:
        return win32api.GetSystemMetrics(0), win32api.GetSystemMetrics(1)

    def list_video_devices(self) -> dict[str, int]:
        try:
            graph = FilterGraph()
            device_names = graph.get_input_devices()
        except Exception as e:
            logger.debug(f"DirectShow video device query failed: {e}")
            device_names = []

        devices = {}
        counts = {}
        for idx, name in enumerate(device_names):
            if name in counts:
                counts[name] += 1
                unique_name = f"{name} #{counts[name]}"
            else:
                counts[name] = 1
                unique_name = name
            devices[unique_name] = idx

        return devices

    def get_focused_window(self) -> dict | None:
        hwnd = win32gui.GetForegroundWindow()
        if (
            not hwnd
            or not win32gui.IsWindow(hwnd)
            or not win32gui.IsWindowVisible(hwnd)
        ):
            return None

        title = win32gui.GetWindowText(hwnd)
        if not title or any(excl in title for excl in self.windows_to_exclude):
            return None

        rect = None
        if dwmapi:
            try:
                r = wintypes.RECT()
                hr = dwmapi.DwmGetWindowAttribute(
                    hwnd,
                    9,  # DWMWA_EXTENDED_FRAME_BOUNDS
                    ctypes.byref(r),
                    ctypes.sizeof(r),
                )
                if hr == 0 and (r.right > r.left and r.bottom > r.top):
                    rect = (r.left, r.top, r.right, r.bottom)
            except Exception:
                pass
        if not rect:
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
