import json

import settings


def _use_temp_settings_path(monkeypatch, tmp_path):
    path = tmp_path / "settings.json"
    monkeypatch.setattr(settings, "_settings_path", lambda: path)
    return path


def test_load_settings_returns_empty_dict_when_file_missing(monkeypatch, tmp_path):
    _use_temp_settings_path(monkeypatch, tmp_path)
    assert settings.load_settings() == {}


def test_load_settings_returns_empty_dict_on_invalid_json(monkeypatch, tmp_path):
    path = _use_temp_settings_path(monkeypatch, tmp_path)
    path.write_text("{not valid json")
    assert settings.load_settings() == {}


def test_save_settings_then_load_settings_round_trips(monkeypatch, tmp_path):
    _use_temp_settings_path(monkeypatch, tmp_path)
    settings.save_settings({"game_data_path": "C:\\game"})
    assert settings.load_settings() == {"game_data_path": "C:\\game"}


def test_save_settings_creates_parent_directories(monkeypatch, tmp_path):
    path = tmp_path / "nested" / "dir" / "settings.json"
    monkeypatch.setattr(settings, "_settings_path", lambda: path)
    settings.save_settings({"a": 1})
    assert path.exists()
    assert json.loads(path.read_text()) == {"a": 1}


def test_get_cached_game_data_path_returns_none_when_unset(monkeypatch, tmp_path):
    _use_temp_settings_path(monkeypatch, tmp_path)
    assert settings.get_cached_game_data_path() is None


def test_set_cached_game_data_path_preserves_other_keys(monkeypatch, tmp_path):
    path = _use_temp_settings_path(monkeypatch, tmp_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"other_key": "keep me"}))

    settings.set_cached_game_data_path("D:\\HD2\\data")

    assert settings.get_cached_game_data_path() == "D:\\HD2\\data"
    assert settings.load_settings()["other_key"] == "keep me"
