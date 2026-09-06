import json
from pathlib import Path
from platformdirs import user_config_dir

APP_NAME = "hd2-repatcher"

def _settings_path() -> Path:
    return Path(user_config_dir(APP_NAME)) / "settings.json"


def load_settings() -> dict:
    path = _settings_path()
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text())
    except (json.JSONDecodeError, OSError):
        return {}


def save_settings(settings: dict) -> None:
    path = _settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2))


def get_cached_game_data_path() -> str | None:
    return load_settings().get("game_data_path")


def set_cached_game_data_path(path: str) -> None:
    settings = load_settings()
    settings["game_data_path"] = path
    save_settings(settings)
