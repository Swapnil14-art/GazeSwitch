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

    def get_focused_window(self) -> dict | None:
        raise NotImplementedError("Only works on MacOS")

    def window_key(self, window: dict) -> str:
        raise NotImplementedError("Only works on MacOS")

    def notify(self, title: str) -> None:
        raise NotImplementedError("Only works on MacOS")
