from functools import partial

import pystray
from PIL import Image
from pystray import MenuItem as item

from core.tracker import GazeTracker


def create_tray_icon(tracker: GazeTracker) -> None:
    """
    Create and run the system tray icon with menu options.
    """
    image = Image.open("media/icon.png")

    menu = (
        item("Start Tracking", tracker.start_tracking),
        item("Stop Tracking", tracker.stop_tracking),
        item("Exit", partial(exit_app, tracker=tracker)),
    )

    icon = pystray.Icon("GazeControl", image, "Gaze Control", menu)
    icon.run()


def exit_app(icon, _, tracker: GazeTracker):
    """
    Exit the application by stopping tracking and the tray icon.

    This function is used as pystray menu callbacks. pystray invokes menu
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
    tracker.stop_tracking()
    icon.stop()
