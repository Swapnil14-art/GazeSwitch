import json
import logging
import threading
from typing import Any

from system_platform.utils import get_app_data_dir

CONFIG_FILE = get_app_data_dir() / "config.json"
_save_lock = threading.Lock()

logger = logging.getLogger(__name__)


def load_config() -> dict[str, Any]:
    """
    Load configuration from the config file.

    Returns:
        dict[str, Any]: The loaded configuration as a dictionary.
    """
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r") as f:
            config = json.load(f)

            # Convert monitor IDs to int when possible, preserving string IDs
            if "monitor_camera_mapping" in config:
                try:
                    parsed_mapping = {}
                    for k, v in config["monitor_camera_mapping"].items():
                        try:
                            key = int(k)
                        except (ValueError, TypeError):
                            key = str(k)
                        parsed_mapping[key] = v
                    config["monitor_camera_mapping"] = parsed_mapping
                except Exception as e:
                    logger.warning(
                        f"Invalid monitor IDs in config: {e}. Using default config."
                    )
                    return {}

            return config
    except Exception as e:
        logger.error(f"Failed to load config: {e}. Using default config.")
        return {}


def save_config(config: dict[str, Any]) -> None:
    """
    Save configuration to the config file.

    Args:
        config (dict[str, str]): The configuration dictionary to save.
    """
    with _save_lock:
        get_app_data_dir().mkdir(parents=True, exist_ok=True)

        with open(CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
