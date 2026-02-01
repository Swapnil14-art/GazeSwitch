from system_platform.window_manager import WindowManager


class MacOSWindowManager(WindowManager):
    def get_windows(self) -> list[dict]:
        raise NotImplementedError("Only works on MacOS")

    def window_at_point(self, x: int, y: int, windows: list[dict]) -> dict | None:
        raise NotImplementedError("Only works on MacOS")

    def focus_window(self, window: dict) -> None:
        raise NotImplementedError("Only works on MacOS")

    def get_screen_size(self) -> tuple[int, int]:
        raise NotImplementedError("Only works on MacOS")

    def list_video_devices(self) -> dict[str, int]:
        raise NotImplementedError("Only works on MacOS")
