import sys
import warnings

from core.tracker import GazeTracker
from system_platform.window_manager import WindowManager
from ui.tray import create_tray_icon

warnings.filterwarnings("ignore", category=UserWarning, module="google.protobuf")


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
    wm = create_window_manager()
    tracker = GazeTracker(wm)
    create_tray_icon(tracker)


if __name__ == "__main__":
    main()
