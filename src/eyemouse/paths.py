"""Per-user file locations (config, cache) that follow each operating system's conventions."""

from __future__ import annotations

from pathlib import Path

from platformdirs import user_cache_dir, user_config_dir

APP_NAME = "eyemouse"


def config_dir() -> Path:
    return Path(user_config_dir(APP_NAME, appauthor=False))


def cache_dir() -> Path:
    return Path(user_cache_dir(APP_NAME, appauthor=False))


def default_calibration_path() -> Path:
    return config_dir() / "calibration.json"


def default_model_path() -> Path:
    return cache_dir() / "face_landmarker.task"
