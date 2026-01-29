import time
from threading import Thread
from pynput import keyboard
import win32com.client
import win32gui
import win32api
from trackers.eyetrax_tracker import EyeTraxWrapper

import pystray
from pystray import MenuItem as item
from PIL import Image

DWELL_TIME = 0.8 # seconds
TYPING_IDLE_TIME = 1.0 # seconds
POLL_INTERVAL = 0.05 # seconds

last_keystroke_time = time.time()
current_window = None
estimator = None
running = False

windows_to_exclude = ["Windows Input Experience", "Rainmeter", "Program Manager"]

screen_width = win32api.GetSystemMetrics(0)
screen_height = win32api.GetSystemMetrics(1)

last_keystroke_time = time.time()

def on_key_press(_):
    global last_keystroke_time
    last_keystroke_time = time.time()

keyboard_listener = keyboard.Listener(on_press=on_key_press)
keyboard_listener.start()


def get_windows() -> list[dict]:
    """
    Get a list of all visible windows with their handles, titles, and rectangles.

    Returns:
        list[dict]: A list of dictionaries containing window handles, titles, and rectangles.
    """
    windows = []

    def callback(hwnd, _):
        if win32gui.IsWindowVisible(hwnd) and win32gui.GetWindowText(hwnd):
            rect = win32gui.GetWindowRect(hwnd)
            title = win32gui.GetWindowText(hwnd)
            windows.append({"hwnd": hwnd, "title": title, "rect": rect})

    win32gui.EnumWindows(callback, None)
    return windows


def window_at_point(x: int, y: int, windows: list[dict]) -> dict | None:
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


def focus_window(hwnd: int) -> None:
    """
    Bring the specified window to the foreground.

    Args:
        hwnd (int): The handle of the window to focus.
    """
    try:
        shell = win32com.client.Dispatch("WScript.Shell")
        shell.SendKeys("%")
        win32gui.SetForegroundWindow(hwnd)
    except Exception as e:
        print(f"Could not focus window: {e}")


def run_tracker() -> None:
    """
    Main loop to track gaze and focus windows accordingly.
    """
    global current_window, running, estimator, screen_width, screen_height
    
    last_target_hwnd = None
    gaze_dwell_start = 0.0
    intent_idle_since = 0.0

    while running:
        now = time.time()

        # Get gaze data
        data = estimator.get_data()  # type: ignore
        x = data["gaze"]["x"]
        y = data["gaze"]["y"]

        # Determine if the user is actively typing or ot
        typing_idle = (now - last_keystroke_time) >= TYPING_IDLE_TIME

        if not typing_idle:
            intent_idle_since = 0.0
        elif intent_idle_since == 0.0:
            intent_idle_since = now    

        if x is not None and y is not None and 0 < x < screen_width and 0 < y < screen_height:
            print(f"Predicted gaze at: ({x}, {y})")
            windows = [
                w for w in get_windows()
                if not any(excl in w["title"] for excl in windows_to_exclude)
            ]

            target_window = window_at_point(int(x), int(y), windows)

            if target_window:
                target_window_hwnd = target_window["hwnd"]

                # Reset dwell timer if target changes
                if last_target_hwnd != target_window_hwnd:
                    last_target_hwnd = target_window["hwnd"]
                    gaze_dwell_start = now
                
                # Check intent conditions
                gaze_dwell = now - gaze_dwell_start
                intent_idle = now - intent_idle_since if intent_idle_since > 0.0 else 0.0
                
                if (
                    gaze_dwell >= DWELL_TIME
                    and intent_idle >= TYPING_IDLE_TIME
                ):
                    if not current_window or target_window_hwnd != current_window["hwnd"]:
                        print(f"Focusing window: {target_window["title"]}")
                        current_window = target_window
                        focus_window(target_window_hwnd)

                        # Reset to prevent immediate re-trigger
                        gaze_dwell_start = now
                        intent_idle_since = now
            else:
                # No window detected, reset gaze dwell
                last_target_hwnd = None
                gaze_dwell_start = 0.0
        else:
            # Invalid gaze, reset gaze dwell
            last_target_hwnd = None
            gaze_dwell_start = 0.0

        time.sleep(POLL_INTERVAL)


def start_tracking(icon=None, _=None) -> None:
    """
    Start the gaze tracking process.

    This function is used as a pystray menu callback. pystray invokes menu
    callbacks with two arguments (icon, menu_item), even if they are not
    needed by the implementation. The parameters are therefore accepted
    for compatibility but intentionally unused.

    Args:
        icon (pystray.Icon | None): The system tray icon instance provided
            by pystray when invoked from the tray menu. Optional to allow
            manual invocation.
        _ (pystray.MenuItem | None): The menu item that triggered the callback.
            Unused by design.
    """
    global running, estimator
    if running:
        return

    running = True
    estimator = EyeTraxWrapper(False, "with_glasses")
    Thread(target=run_tracker, daemon=True).start()
    print("Tracking started")


def stop_tracking(icon=None, _=None) -> None:
    """
    Stop the gaze tracking process.

    This function is used as a pystray menu callback. pystray invokes menu
    callbacks with two arguments (icon, menu_item), even if they are not
    needed by the implementation. The parameters are therefore accepted
    for compatibility but intentionally unused.

    Args:
        icon (pystray.Icon | None): The system tray icon instance provided
            by pystray when invoked from the tray menu. Optional to allow
            manual invocation.
        _ (pystray.MenuItem | None): The menu item that triggered the callback.
            Unused by design.
    """
    global running, estimator
    running = False
    if estimator:
        estimator.stop()  # type: ignore
    print("Tracking stopped")


def exit_app(icon, _):
    """
    Exit the application by stopping tracking and the tray icon.

    This function is used as a pystray menu callback. pystray invokes menu
    callbacks with two arguments (icon, menu_item), even if they are not
    needed by the implementation. The parameters are therefore accepted
    for compatibility but intentionally unused.

    Args:
        icon (pystray.Icon | None): The system tray icon instance provided
            by pystray when invoked from the tray menu. Optional to allow
            manual invocation.
        _ (pystray.MenuItem | None): The menu item that triggered the callback.
            Unused by design.
    """
    stop_tracking()
    icon.stop()


def create_tray_icon() -> None:
    """
    Create and run the system tray icon with menu options.
    """
    image = Image.open("media/icon.png")

    menu = (
        item("Start Tracking", start_tracking),
        item("Stop Tracking", stop_tracking),
        item("Exit", exit_app),
    )

    icon = pystray.Icon("GazeControl", image, "Gaze Control", menu)
    icon.run()


if __name__ == "__main__":
    create_tray_icon()
