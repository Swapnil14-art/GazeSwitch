import os
import platform
from pathlib import Path


def get_model_dir() -> str:
    system = platform.system()

    if system == "Windows":
        base = Path(os.getenv("LOCALAPPDATA", Path.home()))
        model_dir = base / "GazeControl" / "models"

    elif system == "Darwin":
        base = Path.home() / "Library" / "Application Support"
        model_dir = base / "GazeControl" / "models"

    else:
        base = Path.home() / ".local" / "share"
        model_dir = base / "GazeControl" / "models"

    model_dir.mkdir(parents=True, exist_ok=True)
    return str(model_dir)
