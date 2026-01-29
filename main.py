# from system_platform.macos import MacOSWindowManager
# from system_platform.linux import LinuxWindowManager
from core.tracker import GazeTracker
from system_platform.window_manager import WindowManager
from system_platform.windows import WindowsWindowManager
from ui.tray import create_tray_icon


def create_window_manager() -> WindowManager:
    return WindowsWindowManager()
    # if sys.platform.startswith("win"):
    #     return WindowsWindowManager()
    # elif sys.platform == "darwin":
    #     return MacOSWindowManager()
    # else:
    #     return LinuxWindowManager()


def main():
    wm = create_window_manager()
    tracker = GazeTracker(wm)
    create_tray_icon(tracker)


if __name__ == "__main__":
    main()
