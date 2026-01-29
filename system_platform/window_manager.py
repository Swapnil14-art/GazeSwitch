from abc import ABC, abstractmethod


class WindowManager(ABC):
    @abstractmethod
    def get_windows(self) -> list[dict]:
        pass

    @abstractmethod
    def window_at_point(self, x: int, y: int, windows: list[dict]) -> dict | None:
        pass

    @abstractmethod
    def focus_window(self, window: dict) -> None:
        pass

    @abstractmethod
    def get_screen_size(self) -> tuple[int, int]:
        pass
