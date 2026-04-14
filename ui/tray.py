import logging
import os
import sys
import tkinter as tk
from functools import partial
from tkinter import ttk

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


def create_tray_icon(tracker: GazeTracker, root: tk.Tk) -> None:
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
        item(
            "Configure Monitors && Cameras",
            lambda icon, item: (root.after(0, open_config_window, tracker, root)),
        ),
        hotkey_menu,
        item("Exit", partial(exit_app, tracker=tracker, root=root)),
    )

    icon = pystray.Icon("GazeControl", image, "Gaze Control", menu)
    icon.run()


def start_tracking(tracker: GazeTracker):
    """
    Start tracking and show a notification.

    Args:
        tracker (GazeTracker): The tracker instance to start tracking on.
    """
    tracker.wm.notify("Starting tracking, please wait...")
    tracker.start_tracking()
    tracker.wm.notify("Tracking Started")


def open_config_window(tracker: GazeTracker, root: tk.Tk):
    """
    Open a configuration window to select monitors, camera mappings, and manage cameras.
    """
    was_running = tracker.running
    if was_running:
        tracker.stop_tracking()

    window = tk.Toplevel(root)
    window.title("Monitor & Camera Configuration")
    window.resizable(False, False)

    # Icon
    icon_path = resource_path("media/icon_black.png")
    tk_img = tk.PhotoImage(file=icon_path)
    window.iconphoto(False, tk_img)

    window.transient()
    window.grab_set()
    window.focus()

    # Styling
    window.configure(bg="#f5f5f5")
    style = ttk.Style()
    style.theme_use("default")

    style.configure("TFrame", background="#f5f5f5")
    style.configure("TLabel", background="#f5f5f5", font=("Segoe UI", 10))
    style.configure("Header.TLabel", font=("Segoe UI", 11, "bold"))

    style.configure("Clean.TCheckbutton", background="#f5f5f5", padding=0)

    main_frame = ttk.Frame(window, padding=20)
    main_frame.pack(fill="both", expand=True)

    # Monitor config section
    monitor_section = ttk.Frame(main_frame)
    monitor_section.pack(fill="x", pady=(0, 10))

    ttk.Label(
        monitor_section, text="Monitor Configuration", style="Header.TLabel"
    ).pack(anchor="w", pady=(0, 5))

    container = ttk.Frame(monitor_section)
    container.pack(fill="x")

    # Headers
    ttk.Label(container, text="Monitor", style="Header.TLabel").grid(
        row=0, column=0, sticky="w", padx=5
    )
    ttk.Label(container, text="Enabled", style="Header.TLabel").grid(
        row=0, column=1, padx=5
    )
    ttk.Label(container, text="Camera", style="Header.TLabel").grid(
        row=0, column=2, padx=5
    )
    ttk.Label(container, text="Resolution", style="Header.TLabel").grid(
        row=0, column=3, padx=5
    )

    monitors = tracker.monitor_rects
    cameras = tracker.wm.list_video_devices()
    camera_names = list(cameras.keys())

    existing = tracker.config.get("monitor_camera_mapping", {})
    selections = {}

    for row, monitor in enumerate(monitors, start=1):
        monitor_id = monitor["id"]
        config = existing.get(monitor_id, {})

        ttk.Label(container, text=f"Monitor {monitor_id}").grid(
            row=row, column=0, sticky="w", padx=5, pady=5
        )

        enabled_var = tk.BooleanVar(value=config.get("enabled", True))
        ttk.Checkbutton(
            container, variable=enabled_var, style="Clean.TCheckbutton"
        ).grid(row=row, column=1)

        # Camera dropdown
        camera_var = tk.StringVar()

        camera_index = config.get("camera_index")
        default_cam = next(
            (name for name, idx in cameras.items() if idx == camera_index), None
        )
        if default_cam:
            camera_var.set(default_cam)
        elif camera_names:
            camera_var.set(camera_names[0])

        dropdown = ttk.Combobox(
            container,
            textvariable=camera_var,
            values=camera_names,
            state="readonly",
            width=25,
        )
        dropdown.grid(row=row, column=2, padx=5)

        # Resolution
        width = monitor["right"] - monitor["left"]
        height = monitor["bottom"] - monitor["top"]

        ttk.Label(container, text=f"{width}x{height}").grid(row=row, column=3)

        selections[monitor_id] = {
            "enabled": enabled_var,
            "camera": camera_var,
        }

    # Separator between monitor and camera sections
    ttk.Separator(main_frame, orient="horizontal").pack(fill="x", pady=10)

    # Camera management section
    camera_section = ttk.Frame(main_frame)
    camera_section.pack(fill="x")

    ttk.Label(camera_section, text="Camera Management", style="Header.TLabel").pack(
        anchor="w", pady=(0, 5)
    )

    camera_list_frame = ttk.Frame(camera_section)
    camera_list_frame.pack(fill="x")

    # Get currently used cameras
    used_camera_indexes = set()
    for monitor_id, config in existing.items():
        if config.get("enabled"):
            idx = config.get("camera_index")
            if idx is not None:
                used_camera_indexes.add(idx)

    # Map index to name
    index_to_name = {v: k for k, v in cameras.items()}

    for row, cam_idx in enumerate(sorted(used_camera_indexes)):
        cam_name = index_to_name.get(cam_idx, f"Camera {cam_idx}")

        ttk.Label(camera_list_frame, text=cam_name).grid(
            row=row, column=0, sticky="w", padx=5, pady=3
        )

        state = "disabled" if cam_idx not in tracker.camera_cap_mapping else "normal"
        ttk.Button(
            camera_list_frame,
            text="Release",
            command=lambda idx=cam_idx: tracker.release_camera(idx),
            state=state,
        ).grid(row=row, column=1, padx=5)

    def save():
        monitor_config = {}

        for monitor_id, vars in selections.items():
            camera_name = vars["camera"].get()
            enabled = vars["enabled"].get()

            camera_index = cameras.get(camera_name)

            monitor_config[monitor_id] = {
                "enabled": enabled,
                "camera_index": camera_index,
            }

        tracker.update_monitor_camera_mapping(monitor_config)

        if was_running:
            tracker.start_tracking()

        tracker.wm.notify("Configuration saved")
        window.destroy()

    button_frame = ttk.Frame(main_frame)
    button_frame.pack(fill="x", pady=(15, 0))

    ttk.Button(button_frame, text="Cancel", command=window.destroy).pack(
        side="right", padx=5
    )
    ttk.Button(button_frame, text="Save", command=save).pack(side="right")

    # Release all button if there are any used cameras
    if used_camera_indexes:
        ttk.Button(
            button_frame,
            text="Release All",
            command=lambda: [
                tracker.release_camera(idx) for idx in used_camera_indexes
            ],
        ).pack(side="left")

    # Adjust window size to fit content
    window.update_idletasks()
    window.geometry(f"{window.winfo_reqwidth()}x{window.winfo_reqheight()}")


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


def exit_app(icon, _, tracker: GazeTracker, root: tk.Tk):
    """
    Exit the application by stopping tracking, the tray icon, and
    the Tkinter root window.
    """
    tracker.stop_tracking()
    for camera_index in list(tracker.camera_cap_mapping.keys()):
        tracker.release_camera(camera_index)
    icon.stop()
    root.quit()
    root.destroy()
