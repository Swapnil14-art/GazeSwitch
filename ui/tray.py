import logging
import os
import sys
from functools import partial

import pystray
from PIL import Image
from pystray import MenuItem as item

from core.tracker import GazeTracker
from ui.hotkey_capture import capture_hotkey
from ui.hotkey_display import format_hotkey_for_display

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
    # Video devices submenu
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

    # Hotkey submenu
    def make_hotkey_item(label: str, hotkey_attr: str, action_type: str):
        """
        Helper to create a pystray MenuItem for a hotkey.

        Args:
            label (str): The base label for the menu item (e.g., "Manual Override").
            hotkey_attr (str): The attribute name on the tracker storing the hotkey.
            action_type (str): The type passed to change_hotkey when clicked.
        """
        return item(
            lambda item: (
                f"{label} ({format_hotkey_for_display(getattr(tracker, hotkey_attr))})"
            ),
            lambda icon, item: change_hotkey(icon, tracker, action_type),
        )

    hotkey_menu = item(
        "Configure Hotkeys",
        pystray.Menu(
            make_hotkey_item(
                "Manual Override", "manual_override_hotkey", "manual_override"
            ),
            make_hotkey_item("Cycle Forward", "cycle_windows_hotkey", "cycle_forward"),
            make_hotkey_item(
                "Cycle Reverse", "cycle_windows_reverse_hotkey", "cycle_reverse"
            ),
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
        hotkey_menu,
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


def change_hotkey(icon, tracker: GazeTracker, hotkey_type: str):
    """
    Capture and update a hotkey for a specific action.

    Args:
        icon (_type_): The system tray icon.
        tracker (GazeTracker): The tracker instance to update the hotkey for.
        hotkey_type (str): The hotkey to update.
    """
    action_name = {
        "manual_override": "Manual Override",
        "cycle_forward": "Cycle Forward",
        "cycle_reverse": "Cycle Reverse",
    }[hotkey_type]

    tracker.wm.notify(f"Press new hotkey for {action_name}...")

    def on_complete(hotkey):
        if hotkey_type == "manual_override":
            tracker.update_manual_override_hotkey(hotkey)
        elif hotkey_type == "cycle_forward":
            tracker.update_cycle_hotkey(hotkey, reverse=False)
        elif hotkey_type == "cycle_reverse":
            tracker.update_cycle_hotkey(hotkey, reverse=True)

        icon.update_menu()
        logger.info(f"New shortcut for {hotkey_type}: {hotkey}")
        tracker.wm.notify(
            f"{action_name} hotkey set to {format_hotkey_for_display(hotkey)}"
        )

    capture_hotkey(on_complete)


def exit_app(icon, _, tracker: GazeTracker):
    """
    Exit the application by stopping tracking and the tray icon.
    """
    tracker.stop_tracking()
    icon.stop()
