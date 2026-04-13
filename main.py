import logging
import os
import sys
import tkinter as tk
import warnings
from logging.handlers import RotatingFileHandler
from threading import Thread

from core.tracker import GazeTracker
from system_platform.utils import get_log_dir
from system_platform.window_manager import WindowManager
from ui.tray import create_tray_icon

warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf")

root = tk.Tk()
root.withdraw()


def setup_logging():
    log_file = os.path.join(get_log_dir(), "gaze_control.log")

    handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8",
    )

    formatter = logging.Formatter(
        "%(asctime)s | %(levelname)s | %(name)s | %(message)s"
    )
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(handler)

    logging.info("Application starting")


def create_window_manager() -> WindowManager:
    if sys.platform.startswith("win"):
        from system_platform.windows import WindowsWindowManager

        return WindowsWindowManager()
    elif sys.platform == "darwin":
        from system_platform.macos import MacOSWindowManager

        return MacOSWindowManager()
    else:
        from system_platform.linux import LinuxWindowManager

        return LinuxWindowManager()


def main():
    setup_logging()
    wm = create_window_manager()
    tracker = GazeTracker(wm)
    Thread(
        target=create_tray_icon,
        args=(
            tracker,
            root,
        ),
        daemon=True,
    ).start()
    root.mainloop()


if __name__ == "__main__":
    main()
