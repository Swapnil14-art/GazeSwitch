import json

from system_platform.utils import get_app_data_dir

CONFIG_FILE = get_app_data_dir() / "config.json"


def load_config() -> dict[str, str]:
    """
    Load configuration from the config file.

    Returns:
        dict[str, str]: The loaded configuration as a dictionary.
    """
    if not CONFIG_FILE.exists():
        return {}

    try:
        with open(CONFIG_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def save_config(config: dict[str, str]) -> None:
    """
    Save configuration to the config file.

    Args:
        config (dict[str, str]): The configuration dictionary to save.
    """
    get_app_data_dir().mkdir(parents=True, exist_ok=True)

    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f, indent=2)
