import os
import platform
from pathlib import Path

APP_NAME = "GazeControl"


def get_app_data_dir() -> Path:
    system = platform.system()

    if system == "Windows":
        return Path(os.getenv("LOCALAPPDATA", Path.home())) / APP_NAME

    elif system == "Darwin":
        return Path.home() / "Library" / "Application Support" / APP_NAME

    else:
        return Path.home() / ".local" / "share" / APP_NAME


def get_model_dir() -> str:
    path = get_app_data_dir() / "models"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)


def get_log_dir() -> str:
    path = get_app_data_dir() / "logs"
    path.mkdir(parents=True, exist_ok=True)
    return str(path)
