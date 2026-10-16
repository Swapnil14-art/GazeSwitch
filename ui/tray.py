import logging
import os
import sys
import threading
import tkinter as tk
from functools import partial
from tkinter import ttk

import cv2
import pystray
from PIL import Image, ImageTk
from pystray import MenuItem as item

from core.tracker import GazeTracker
from system_platform.utils import get_model_dir
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


def build_tray_menu(tracker: GazeTracker, root: tk.Tk) -> pystray.Menu:
    """
    Build the system tray menu.
    This is separated into its own function to allow dynamic updates.
    """

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

    # Calibration submenu
    def make_calibrate_item(label: str, monitor_id: int | None = None):
        """
        Helper to create a pystray MenuItem for a calibration option.

        Args:
            label (str): The base label for the menu item (e.g., "Monitor 0").
            monitor_id (int, optional): The monitor for the given calibration option.
            Defaults to None.
        """
        return item(
            label,
            lambda icon, item: calibrate_action(tracker, monitor_id),
        )

    def calibrate_action(tracker: GazeTracker, monitor_id: int | None = None):
        def worker():
            if monitor_id is None:
                tracker.wm.notify("Starting calibration for all monitors...")
                tracker.calibrate()
            else:
                tracker.wm.notify(f"Starting calibration for monitor {monitor_id}...")
                tracker.calibrate(monitor_id=monitor_id)

        threading.Thread(target=worker, daemon=True).start()

    calibrate_menu = item(
        "Calibrate",
        pystray.Menu(
            item("All Monitors", lambda icon, item: calibrate_action(tracker)),
            *[
                make_calibrate_item(f"Monitor {m['id']}", m["id"])
                for m in tracker.monitor_rects
            ],
        ),
    )

    return pystray.Menu(
        item(
            "Start Tracking",
            lambda icon, item: start_tracking(tracker),
            checked=lambda item: tracker.running,
        ),
        item("Stop Tracking", lambda icon, item: tracker.stop_tracking()),
        calibrate_menu,
        item(
            "Configure Monitors && Cameras",
            lambda icon, item: root.after(0, open_config_window, tracker, root),
        ),
        hotkey_menu,
        item("Exit", partial(exit_app, tracker=tracker, root=root)),
    )


def create_tray_icon(tracker: GazeTracker, root: tk.Tk) -> None:
    """
    Create and run the system tray icon with menu options.
    """
    icon_path = resource_path("media/icon.png")
    image = Image.open(icon_path)

    icon = pystray.Icon(
        "GazeControl", image, "Gaze Control", menu=build_tray_menu(tracker, root)
    )

    # Store callback reference in tracker for dynamic menu updates when monitors change
    def rebuild_menu():
        root.after(
            0,
            lambda: (
                setattr(icon, "menu", build_tray_menu(tracker, root)),
                icon.update_menu(),
            ),
        )

    tracker.on_monitors_changed = rebuild_menu  # type: ignore[reportAttributeAccessIssue]

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


def is_monitor_calibrated(monitor_id: int) -> bool:
    """
    Check if a trained calibration model exists for the given monitor.
    """
    model_path = os.path.join(get_model_dir(), f"gaze_model_{monitor_id}.pkl")
    return os.path.isfile(model_path) and os.path.getsize(model_path) > 0


def preview_camera(
    camera_index: int,
    camera_name: str,
    parent: tk.Toplevel,
    tracker: GazeTracker,
):
    """
    Open a clean live camera preview window to test video feed.
    """
    preview_win = tk.Toplevel(parent)
    preview_win.title(f"Camera Preview - {camera_name or f'Camera {camera_index}'}")
    preview_win.resizable(False, False)
    preview_win.configure(bg="#0f172a")

    label = tk.Label(preview_win, bg="#0f172a")
    label.pack(padx=12, pady=12)

    status_var = tk.StringVar(value="Connecting to camera...")
    status_label = tk.Label(
        preview_win,
        textvariable=status_var,
        font=("Segoe UI", 9),
        bg="#0f172a",
        fg="#94a3b8",
    )
    status_label.pack(pady=(0, 6))

    is_active = [True]

    def update_frame():
        if not is_active[0]:
            return
        ret, frame = tracker.get_preview_frame(camera_index)
        if ret and frame is not None:
            frame_rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            h, w, _ = frame_rgb.shape
            target_w = 420
            target_h = int(h * (target_w / w))
            frame_resized = cv2.resize(frame_rgb, (target_w, target_h))
            img = Image.fromarray(frame_resized)
            imgtk = ImageTk.PhotoImage(image=img)
            label.imgtk = imgtk
            label.configure(image=imgtk)
            status_var.set(f"Live Video ({w}×{h})")
        else:
            status_var.set("Waiting for video frames...")
        preview_win.after(33, update_frame)

    def close_preview():
        is_active[0] = False
        preview_win.destroy()

    btn_frame = tk.Frame(preview_win, bg="#0f172a")
    btn_frame.pack(fill="x", pady=(0, 10))
    ttk.Button(btn_frame, text="Close Preview", command=close_preview).pack()

    preview_win.protocol("WM_DELETE_WINDOW", close_preview)
    preview_win.after(40, update_frame)


_active_config_window: tk.Toplevel | None = None


def open_config_window(tracker: GazeTracker, root: tk.Tk):
    """
    Open an enhanced configuration window to select monitors, camera mappings,
    preview feeds, run calibration, and manage devices.
    """
    global _active_config_window
    if _active_config_window is not None:
        try:
            if _active_config_window.winfo_exists():
                _active_config_window.lift()
                _active_config_window.focus_force()
                return
        except Exception:
            _active_config_window = None

    was_running = tracker.running
    if was_running:
        tracker.stop_tracking()

    window = tk.Toplevel(root)
    _active_config_window = window
    window.title("Monitor & Camera Setup")
    window.resizable(False, False)

    def on_close():
        global _active_config_window
        _active_config_window = None
        if was_running and not tracker.running:
            tracker.start_tracking()
        window.destroy()

    window.protocol("WM_DELETE_WINDOW", on_close)

    icon_path = resource_path("media/icon_black.png")
    if os.path.exists(icon_path):
        tk_img = tk.PhotoImage(file=icon_path)
        window.iconphoto(False, tk_img)

    window.transient(root)
    window.grab_set()
    window.focus()

    window.configure(bg="#f8fafc")
    style = ttk.Style()
    style.theme_use("default")

    style.configure("Modern.TFrame", background="#f8fafc")
    style.configure("Card.TFrame", background="#ffffff")
    style.configure(
        "HeaderTitle.TLabel",
        font=("Segoe UI", 12, "bold"),
        foreground="#0f172a",
        background="#f8fafc",
    )
    style.configure(
        "SubTitle.TLabel",
        font=("Segoe UI", 9),
        foreground="#64748b",
        background="#f8fafc",
    )
    style.configure(
        "Section.TLabel",
        font=("Segoe UI", 10, "bold"),
        foreground="#334155",
        background="#f8fafc",
    )

    main_canvas = tk.Frame(window, bg="#f8fafc")
    main_canvas.pack(fill="both", expand=True, padx=18, pady=16)

    # 1. Header Banner
    header_box = tk.Frame(main_canvas, bg="#f8fafc")
    header_box.pack(fill="x", pady=(0, 12))
    ttk.Label(
        header_box,
        text="Display & Camera Settings",
        style="HeaderTitle.TLabel",
    ).pack(anchor="w")
    ttk.Label(
        header_box,
        text="Assign cameras to displays, preview video feeds, and verify calibration.",
        style="SubTitle.TLabel",
    ).pack(anchor="w", pady=(2, 0))

    # 2. Monitors Section
    ttk.Label(
        main_canvas,
        text="🖥️ Connected Displays",
        style="Section.TLabel",
    ).pack(anchor="w", pady=(4, 6))

    monitors = tracker.monitor_rects
    cameras = dict(tracker.wm.list_video_devices())
    camera_names = list(cameras.keys())
    existing = tracker.config.get("monitor_camera_mapping", {})

    selections = {}
    calib_labels = {}
    dropdowns = []

    monitors_container = tk.Frame(main_canvas, bg="#f8fafc")
    monitors_container.pack(fill="x", pady=(0, 10))

    for monitor in monitors:
        m_id = monitor["id"]
        cfg = existing.get(m_id, {})

        card = tk.Frame(
            monitors_container,
            bg="#ffffff",
            bd=1,
            relief="solid",
            highlightthickness=0,
        )
        card.pack(fill="x", pady=4, ipady=6, ipadx=8)

        # Header within card
        top_row = tk.Frame(card, bg="#ffffff")
        top_row.pack(fill="x", padx=8, pady=(4, 4))

        is_primary = m_id == 0 or (monitor["left"] == 0 and monitor["top"] == 0)
        disp_title = f"Display {m_id}"
        tk.Label(
            top_row,
            text=disp_title,
            font=("Segoe UI", 10, "bold"),
            fg="#0f172a",
            bg="#ffffff",
        ).pack(side="left")

        if is_primary:
            tk.Label(
                top_row,
                text="Primary",
                font=("Segoe UI", 8, "bold"),
                fg="#1d4ed8",
                bg="#dbeafe",
                padx=5,
                pady=1,
            ).pack(side="left", padx=6)

        w_m, h_m = monitor["width"], monitor["height"]
        x_m, y_m = monitor["left"], monitor["top"]
        info_text = f"{w_m}×{h_m} (x={x_m}, y={y_m})"
        tk.Label(
            top_row,
            text=info_text,
            font=("Segoe UI", 8),
            fg="#64748b",
            bg="#ffffff",
        ).pack(side="left", padx=4)

        # Calibration pill
        calibrated = is_monitor_calibrated(m_id)
        pill_text = "✓ Calibrated" if calibrated else "⚠ Needs Calibration"
        pill_fg = "#15803d" if calibrated else "#b45309"
        pill_bg = "#dcfce7" if calibrated else "#fef3c7"
        calib_lbl = tk.Label(
            top_row,
            text=pill_text,
            font=("Segoe UI", 8, "bold"),
            fg=pill_fg,
            bg=pill_bg,
            padx=6,
            pady=1,
        )
        calib_lbl.pack(side="right")
        calib_labels[m_id] = calib_lbl

        # Controls row
        ctrl_row = tk.Frame(card, bg="#ffffff")
        ctrl_row.pack(fill="x", padx=8, pady=(2, 4))

        enabled_var = tk.BooleanVar(value=cfg.get("enabled", True))
        chk = ttk.Checkbutton(
            ctrl_row,
            text="Enable Tracking",
            variable=enabled_var,
        )
        chk.pack(side="left", padx=(0, 10))

        tk.Label(
            ctrl_row,
            text="Camera:",
            font=("Segoe UI", 9),
            fg="#334155",
            bg="#ffffff",
        ).pack(side="left", padx=(0, 4))

        camera_var = tk.StringVar()
        cfg_cam_idx = cfg.get("camera_index")
        default_cam = next(
            (name for name, idx in cameras.items() if idx == cfg_cam_idx), None
        )
        if default_cam:
            camera_var.set(default_cam)
        elif camera_names:
            camera_var.set(camera_names[0])

        cb = ttk.Combobox(
            ctrl_row,
            textvariable=camera_var,
            values=camera_names,
            state="readonly",
            width=22,
        )
        cb.pack(side="left", padx=(0, 8))
        dropdowns.append(cb)

        # Preview button
        def make_preview_cmd(cam_v=camera_var):
            def cmd():
                c_name = cam_v.get()
                c_idx = cameras.get(c_name, 0)
                preview_camera(c_idx, c_name, window, tracker)

            return cmd

        ttk.Button(
            ctrl_row,
            text="Preview",
            command=make_preview_cmd(camera_var),
        ).pack(side="left", padx=3)

        # Calibrate button
        def make_calib_cmd(mon_id=m_id, lbl=calib_lbl):
            def cmd():
                def worker():
                    tracker.wm.notify(f"Starting calibration for monitor {mon_id}...")
                    try:
                        tracker.calibrate(monitor_id=mon_id)
                        if is_monitor_calibrated(mon_id):

                            def update_ui():
                                lbl.configure(
                                    text="✓ Calibrated",
                                    fg="#15803d",
                                    bg="#dcfce7",
                                )
                                tracker.wm.notify(
                                    f"Monitor {mon_id} calibrated successfully!"
                                )

                            root.after(0, update_ui)
                    except Exception as e:
                        logger.exception(
                            f"Calibration failed for monitor {mon_id}: {e}"
                        )
                        tracker.wm.notify(f"Calibration failed: {e}")

                threading.Thread(target=worker, daemon=True).start()

            return cmd

        ttk.Button(
            ctrl_row,
            text="Calibrate",
            command=make_calib_cmd(m_id, calib_lbl),
        ).pack(side="left", padx=3)

        selections[m_id] = {
            "enabled": enabled_var,
            "camera": camera_var,
        }

    # 3. Camera Management Section
    ttk.Label(
        main_canvas,
        text="📷 Camera Devices & Diagnostics",
        style="Section.TLabel",
    ).pack(anchor="w", pady=(8, 6))

    cam_card = tk.Frame(
        main_canvas,
        bg="#ffffff",
        bd=1,
        relief="solid",
        highlightthickness=0,
    )
    cam_card.pack(fill="x", pady=(0, 10), ipady=6, ipadx=8)

    # Toolbar inside camera card
    tool_row = tk.Frame(cam_card, bg="#ffffff")
    tool_row.pack(fill="x", padx=8, pady=(4, 6))

    devices_list_frame = tk.Frame(cam_card, bg="#ffffff")
    devices_list_frame.pack(fill="x", padx=8, pady=(0, 4))

    def update_camera_devices_ui():
        for widget in devices_list_frame.winfo_children():
            widget.destroy()

        if not cameras:
            tk.Label(
                devices_list_frame,
                text="No camera devices detected. Connect a webcam and click Refresh.",
                font=("Segoe UI", 9, "italic"),
                fg="#94a3b8",
                bg="#ffffff",
            ).pack(anchor="w", pady=4)
            return

        for name, idx in cameras.items():
            row_frame = tk.Frame(devices_list_frame, bg="#ffffff")
            row_frame.pack(fill="x", pady=2)

            in_use = (
                idx in tracker.camera_cap_mapping
                and tracker.camera_cap_mapping[idx].isOpened()
            )
            status_text = "● Active" if in_use else "○ Available"
            status_fg = "#16a34a" if in_use else "#64748b"

            tk.Label(
                row_frame,
                text=f"{name} (Index {idx})",
                font=("Segoe UI", 9),
                fg="#1e293b",
                bg="#ffffff",
            ).pack(side="left")

            tk.Label(
                row_frame,
                text=status_text,
                font=("Segoe UI", 8, "bold"),
                fg=status_fg,
                bg="#ffffff",
            ).pack(side="left", padx=8)

            # Actions
            ttk.Button(
                row_frame,
                text="Preview",
                command=lambda c_idx=idx, c_name=name: preview_camera(
                    c_idx, c_name, window, tracker
                ),
            ).pack(side="right", padx=2)

            def make_rel_cmd(c_idx=idx):
                def cmd():
                    tracker.release_camera(c_idx)
                    update_camera_devices_ui()

                return cmd

            rel_btn = ttk.Button(
                row_frame,
                text="Release",
                command=make_rel_cmd(idx),
                state="normal" if in_use else "disabled",
            )
            rel_btn.pack(side="right", padx=2)

    def refresh_devices():
        new_cams = tracker.wm.list_video_devices()
        cameras.clear()
        cameras.update(new_cams)
        new_names = list(cameras.keys())
        for d in dropdowns:
            d["values"] = new_names
            if d.get() not in new_names and new_names:
                d.set(new_names[0])
        update_camera_devices_ui()
        tracker.wm.notify("Camera devices refreshed")

    def release_all_action():
        for c_idx in list(tracker.camera_cap_mapping.keys()):
            tracker.release_camera(c_idx)
        update_camera_devices_ui()
        tracker.wm.notify("All cameras released")

    ttk.Button(
        tool_row,
        text="🔄 Refresh Devices",
        command=refresh_devices,
    ).pack(side="left", padx=(0, 6))

    ttk.Button(
        tool_row,
        text="Release All Cameras",
        command=release_all_action,
    ).pack(side="left")

    update_camera_devices_ui()

    # 4. Bottom Buttons
    bottom_bar = tk.Frame(main_canvas, bg="#f8fafc")
    bottom_bar.pack(fill="x", pady=(10, 0))

    def save():
        global _active_config_window
        _active_config_window = None
        monitor_config = {}
        for m_id, v in selections.items():
            cam_name = v["camera"].get()
            enabled = v["enabled"].get()
            cam_idx = cameras.get(cam_name, 0)
            monitor_config[m_id] = {
                "enabled": enabled,
                "camera_index": cam_idx,
            }

        tracker.update_monitor_camera_mapping(monitor_config)
        if was_running and not tracker.running:
            tracker.start_tracking()
        window.destroy()

    ttk.Button(bottom_bar, text="Cancel", command=on_close).pack(
        side="right", padx=(6, 0)
    )
    ttk.Button(bottom_bar, text="Save & Apply", command=save).pack(side="right")

    window.update_idletasks()
    req_w = max(window.winfo_reqwidth(), 560)
    req_h = window.winfo_reqheight()

    # Center window on screen
    sw = window.winfo_screenwidth()
    sh = window.winfo_screenheight()
    x_pos = (sw - req_w) // 2
    y_pos = (sh - req_h) // 2
    window.geometry(f"{req_w}x{req_h}+{x_pos}+{y_pos}")


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
    the Tkinter root window safely on the Tk main thread.
    """
    try:
        tracker.shutdown()
    except Exception as e:
        logger.exception(f"Error during tracker shutdown on exit: {e}")
    icon.stop()
    root.after(0, lambda: (root.quit(), root.destroy()))
