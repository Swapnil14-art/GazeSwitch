import logging
import os
import sys
from functools import partial

import pystray
from PIL import Image
from pystray import MenuItem as item

from core.tracker import GazeTracker

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

    def make_video_item(idx: int, name: str):
        def callback(icon, item):
            tracker.set_video_device(idx)

        def checked(item):
            return tracker.current_camera == idx

        return item(name, callback, checked=checked)

    video_menu = item(
        "Select Camera",
        pystray.Menu(*[make_video_item(idx, name) for idx, name in video_devices]),
    )

    menu = (
        item("Start Tracking", lambda icon, item: tracker.start_tracking()),
        item("Stop Tracking", lambda icon, item: tracker.stop_tracking()),
        item("Calibrate", lambda icon, item: tracker.calibrate()),
        video_menu,
        item("Exit", partial(exit_app, tracker=tracker)),
    )

    icon = pystray.Icon("GazeControl", image, "Gaze Control", menu)
    icon.run()


def exit_app(icon, _, tracker: GazeTracker):
    """
    Exit the application by stopping tracking and the tray icon.
    """
    tracker.stop_tracking()
    icon.stop()
