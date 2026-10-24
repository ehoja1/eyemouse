from __future__ import annotations

from pathlib import Path

import pytest

from eyemouse.config import Config, load_config
from eyemouse.errors import ConfigError

EXAMPLE = Path(__file__).resolve().parents[1] / "config.example.toml"


def write(tmp_path, text: str) -> Path:
    path = tmp_path / "cfg.toml"
    path.write_text(text, encoding="utf-8")
    return path


def test_defaults_are_valid():
    Config().validate()


def test_example_file_documents_exactly_the_defaults():
    assert load_config(EXAMPLE) == Config()


def test_values_are_overridden_from_toml(tmp_path):
    cfg = load_config(write(tmp_path, "[camera]\nindex = 2\n[blink]\nrequired_blinks = 2\n"))
    assert cfg.camera.index == 2
    assert cfg.blink.required_blinks == 2
    assert cfg.camera.width == 640  # untouched values keep their defaults


def test_integers_are_accepted_for_float_fields(tmp_path):
    cfg = load_config(write(tmp_path, "[cursor]\ndeadzone_px = 8\n"))
    assert cfg.cursor.deadzone_px == 8.0
    assert isinstance(cfg.cursor.deadzone_px, float)


def test_unknown_section_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="Unknown config section"):
        load_config(write(tmp_path, "[nope]\nx = 1\n"))


def test_unknown_key_is_rejected_with_suggestions(tmp_path):
    with pytest.raises(ConfigError, match="unknown key"):
        load_config(write(tmp_path, "[blink]\nrequired_blink = 3\n"))


def test_wrong_type_is_rejected(tmp_path):
    with pytest.raises(ConfigError, match="must be float"):
        load_config(write(tmp_path, '[cursor]\nbeta = "fast"\n'))


def test_booleans_are_not_accepted_as_numbers(tmp_path):
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, "[camera]\nindex = true\n"))


def test_numbers_are_not_accepted_as_booleans(tmp_path):
    with pytest.raises(ConfigError):
        load_config(write(tmp_path, "[ui]\npreview = 1\n"))


def test_all_validation_problems_are_reported_together(tmp_path):
    text = '[blink]\nclose_ratio = 0.95\nrequired_blinks = 1\n[cursor]\nbutton = "side"\n'
    with pytest.raises(ConfigError) as info:
        load_config(write(tmp_path, text))
    message = str(info.value)
    assert "close_ratio" in message
    assert "required_blinks" in message
    assert "button" in message


def test_missing_file_is_a_clean_error(tmp_path):
    with pytest.raises(ConfigError, match="not found"):
        load_config(tmp_path / "missing.toml")


def test_invalid_toml_is_a_clean_error(tmp_path):
    with pytest.raises(ConfigError, match="Invalid TOML"):
        load_config(write(tmp_path, "[camera\nindex = 1"))


def test_section_must_be_a_table(tmp_path):
    with pytest.raises(ConfigError, match="must be a table"):
        load_config(write(tmp_path, "camera = 3\n"))
