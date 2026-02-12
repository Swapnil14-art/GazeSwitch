import logging
import os
import sys
from functools import partial

import pystray
from PIL import Image
from pystray import MenuItem as item

from core.tracker import GazeTracker
from ui.hotkey_capture import capture_hotkey

logger = logging.getLogger(__name__)


def resource_path(relative_path: str) -> str:
    """
    Get absolute path to a resource, works in dev and PyInstaller onefile.
    """
    if getattr(sys, "frozen", False):
        # PyInstaller unpacks files to _MEIPASS
        base_path = getattr(sys, "_MEIPASS")
    else:
        # Normal Python dev environment
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


def create_tray_icon(tracker: GazeTracker) -> None:
    """
    Create and run the system tray icon with menu options.
    """
    icon_path = resource_path("media/icon.png")
    image = Image.open(icon_path)

    """
    pystray invokes menu item action callbacks with two arguments (icon, item), 
    even if they are not needed by the implementation. The parameters are therefore 
    accepted for compatibility but intentionally unused.
    """
    # Build dynamic submenu for video devices
    video_devices = tracker.wm.list_video_devices()

    def make_video_item(name: str, idx: int):
        def callback(icon, item):
            tracker.set_video_device(idx)

        def checked(item):
            return tracker.current_camera == idx

        return item(name, callback, checked=checked)

    video_menu = item(
        "Select Camera",
        pystray.Menu(
            *[make_video_item(name, idx) for name, idx in list(video_devices.items())]
        ),
    )

    menu = (
        item(
            "Start Tracking",
            lambda icon, item: start_tracking(tracker),
            checked=lambda item: tracker.running,
        ),
        item("Stop Tracking", lambda icon, item: tracker.stop_tracking()),
        item("Calibrate", lambda icon, item: tracker.calibrate()),
        video_menu,
        item(
            lambda item: f"Change Manual Override ({tracker.manual_override_hotkey})",
            lambda icon, item: change_manual_override_hotkey(icon, tracker),
        ),
        item("Exit", partial(exit_app, tracker=tracker)),
    )

    icon = pystray.Icon("GazeControl", image, "Gaze Control", menu)
    icon.run()


def start_tracking(tracker: GazeTracker):
    """
    Start tracking and show a notification.

    Args:
        tracker (GazeTracker): The tracker instance to start tracking on.
    """
    tracker.start_tracking()
    tracker.wm.notify("Tracking Started")


def change_manual_override_hotkey(icon, tracker: GazeTracker):
    """
    Change the manual override hotkey by capturing a new key combination.

    Args:
        icon (_type_): The system tray icon.
        tracker (GazeTracker): The tracker instance to update the hotkey for.
    """
    logger.info("Press new hotkey combination for manual override...")

    def on_complete(hotkey):
        tracker.update_manual_override_hotkey(hotkey)
        icon.update_menu()
        logger.info(f"New shortcut: {hotkey}")

    capture_hotkey(on_complete)


def exit_app(icon, _, tracker: GazeTracker):
    """
    Exit the application by stopping tracking and the tray icon.
    """
    tracker.stop_tracking()
    icon.stop()
