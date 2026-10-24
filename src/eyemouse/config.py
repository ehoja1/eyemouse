"""Typed configuration with TOML loading and validation.

All tunables live here so that behaviour can be adjusted without touching code. See
``config.example.toml`` for a fully documented file.
"""

from __future__ import annotations

import dataclasses
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from .errors import ConfigError

if sys.version_info >= (3, 11):
    import tomllib
else:  # pragma: no cover - exercised only on Python 3.10
    import tomli as tomllib


@dataclass
class CameraConfig:
    index: int = 0
    width: int = 640
    height: int = 480
    fps: int = 30


@dataclass
class TrackingConfig:
    #: Path to ``face_landmarker.task``. Empty = download once into the user cache.
    model_path: str = ""
    #: Where the model is downloaded from when ``model_path`` is empty (https only).
    model_url: str = (
        "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
        "face_landmarker/float16/latest/face_landmarker.task"
    )
    #: Optional SHA-256 of the model file; verified after download / on load when set.
    model_sha256: str = ""
    min_detection_confidence: float = 0.5
    min_presence_confidence: float = 0.5
    min_tracking_confidence: float = 0.5


@dataclass
class BlinkConfig:
    #: Number of quick blinks that make a click.
    required_blinks: int = 3
    #: Eyes count as closed when EAR drops below ``baseline * close_ratio``.
    close_ratio: float = 0.70
    #: ...and as open again above ``baseline * open_ratio`` (hysteresis).
    open_ratio: float = 0.80
    #: The cursor is frozen as soon as EAR drops below ``baseline * freeze_ratio``.
    freeze_ratio: float = 0.88
    #: Closures shorter than this are treated as sensor noise.
    min_blink_s: float = 0.03
    #: Closures longer than this are deliberate, not blinks (they reset the sequence).
    max_blink_s: float = 0.40
    #: Maximum time between the end of one blink and the start of the next.
    max_gap_s: float = 0.50
    #: Maximum duration of the whole blink sequence.
    max_sequence_s: float = 2.0
    #: Ignore blinks for this long after a click.
    refractory_s: float = 0.80
    #: Time spent measuring the open-eye baseline when tracking starts.
    warmup_s: float = 1.5
    #: Keep the cursor frozen this long after the eyes reopen.
    settle_s: float = 0.15
    #: Closing both eyes for this long toggles pause/resume. 0 disables the gesture.
    long_close_s: float = 2.0
    #: Adaptation speed of the open-eye baseline (0 = fixed).
    baseline_alpha: float = 0.01


@dataclass
class CursorConfig:
    #: One Euro filter: lower = smoother but laggier at rest.
    min_cutoff: float = 1.0
    #: One Euro filter: higher = less lag during fast eye movements.
    beta: float = 0.01
    d_cutoff: float = 1.0
    #: Ignore cursor changes smaller than this many pixels.
    deadzone_px: float = 6.0
    #: A click lands where the cursor was this long before the first blink started.
    click_lookback_s: float = 0.25
    button: str = "left"
    #: Pause automatically when the physical mouse is moved.
    yield_to_hardware_mouse: bool = True
    hardware_threshold_px: float = 50.0


@dataclass
class CalibrationConfig:
    #: ``grid`` x ``grid`` targets are shown.
    grid: int = 4
    #: Fraction of the screen kept free around the outermost targets.
    margin: float = 0.08
    settle_s: float = 0.7
    collect_s: float = 0.9
    min_samples: int = 10
    #: Samples are ignored while either eye's EAR is below this value (eye closed).
    min_open_ear: float = 0.15
    ridge: float = 0.1
    max_retries: int = 2
    #: Where the calibration is stored. Empty = per-user config directory.
    file: str = ""


@dataclass
class UiConfig:
    preview: bool = False
    mirror_preview: bool = True


@dataclass
class Config:
    camera: CameraConfig = field(default_factory=CameraConfig)
    tracking: TrackingConfig = field(default_factory=TrackingConfig)
    blink: BlinkConfig = field(default_factory=BlinkConfig)
    cursor: CursorConfig = field(default_factory=CursorConfig)
    calibration: CalibrationConfig = field(default_factory=CalibrationConfig)
    ui: UiConfig = field(default_factory=UiConfig)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Config:
        sections = {f.name: f for f in dataclasses.fields(cls)}
        unknown = sorted(set(data) - set(sections))
        if unknown:
            raise ConfigError(
                f"Unknown config section(s): {', '.join(unknown)}. "
                f"Valid sections: {', '.join(sections)}."
            )
        kwargs: dict[str, Any] = {}
        for name, value in data.items():
            section_cls = type(getattr(cls(), name))
            kwargs[name] = _build_section(section_cls, value, name)
        return cls(**kwargs)

    def validate(self) -> None:
        """Raise :class:`ConfigError` listing every problem found."""
        problems: list[str] = []
        c, t, b, u, k, ui = (
            self.camera,
            self.tracking,
            self.blink,
            self.cursor,
            self.calibration,
            self.ui,
        )

        def check(condition: bool, message: str) -> None:
            if not condition:
                problems.append(message)

        check(c.index >= 0, "camera.index must be >= 0")
        check(c.width > 0 and c.height > 0, "camera.width/height must be positive")
        check(c.fps > 0, "camera.fps must be positive")
        for name in ("min_detection_confidence", "min_presence_confidence"):
            check(0.0 <= getattr(t, name) <= 1.0, f"tracking.{name} must be in [0, 1]")
        check(
            0.0 <= t.min_tracking_confidence <= 1.0,
            "tracking.min_tracking_confidence must be in [0, 1]",
        )
        check(b.required_blinks >= 2, "blink.required_blinks must be >= 2")
        check(
            0.0 < b.close_ratio < b.open_ratio <= 1.0,
            "blink: require 0 < close_ratio < open_ratio <= 1",
        )
        check(
            b.open_ratio <= b.freeze_ratio <= 1.0,
            "blink: require open_ratio <= freeze_ratio <= 1",
        )
        check(0.0 <= b.min_blink_s < b.max_blink_s, "blink: require 0 <= min_blink_s < max_blink_s")
        check(b.max_gap_s > 0.0, "blink.max_gap_s must be positive")
        check(b.max_sequence_s >= b.max_blink_s, "blink.max_sequence_s must be >= max_blink_s")
        check(b.refractory_s >= 0.0 and b.settle_s >= 0.0, "blink: refractory_s/settle_s >= 0")
        check(b.warmup_s > 0.0, "blink.warmup_s must be positive")
        check(
            b.long_close_s == 0.0 or b.long_close_s > b.max_blink_s,
            "blink.long_close_s must be 0 (disabled) or greater than max_blink_s",
        )
        check(0.0 <= b.baseline_alpha <= 1.0, "blink.baseline_alpha must be in [0, 1]")
        check(u.min_cutoff > 0.0 and u.d_cutoff > 0.0 and u.beta >= 0.0, "cursor: filter params")
        check(u.deadzone_px >= 0.0, "cursor.deadzone_px must be >= 0")
        check(u.click_lookback_s >= 0.0, "cursor.click_lookback_s must be >= 0")
        check(u.button in {"left", "right", "middle"}, "cursor.button must be left/right/middle")
        check(u.hardware_threshold_px > 0.0, "cursor.hardware_threshold_px must be positive")
        check(k.grid >= 3, "calibration.grid must be >= 3")
        check(0.0 <= k.margin < 0.4, "calibration.margin must be in [0, 0.4)")
        check(k.settle_s >= 0.0 and k.collect_s > 0.0, "calibration: settle_s >= 0, collect_s > 0")
        check(k.min_samples >= 3, "calibration.min_samples must be >= 3")
        check(k.ridge >= 0.0, "calibration.ridge must be >= 0")
        check(k.max_retries >= 0, "calibration.max_retries must be >= 0")
        check(isinstance(ui.preview, bool), "ui.preview must be a boolean")
        if problems:
            raise ConfigError("Invalid configuration:\n  - " + "\n  - ".join(problems))


def _build_section(section_cls: type, data: Any, name: str) -> Any:
    if not isinstance(data, dict):
        raise ConfigError(f"[{name}] must be a table (got {type(data).__name__}).")
    known = {f.name for f in dataclasses.fields(section_cls)}
    unknown = sorted(set(data) - known)
    if unknown:
        raise ConfigError(
            f"[{name}] unknown key(s): {', '.join(unknown)}. "
            f"Valid keys: {', '.join(sorted(known))}."
        )
    defaults = section_cls()
    kwargs: dict[str, Any] = {}
    for key, value in data.items():
        expected = type(getattr(defaults, key))
        if expected is float and isinstance(value, int) and not isinstance(value, bool):
            value = float(value)
        is_bool_mismatch = isinstance(value, bool) != (expected is bool)
        if not isinstance(value, expected) or is_bool_mismatch:
            raise ConfigError(
                f"[{name}] {key} must be {expected.__name__} (got {type(value).__name__})."
            )
        kwargs[key] = value
    return section_cls(**kwargs)


def load_config(path: str | Path | None = None) -> Config:
    """Load and validate a configuration file (defaults when ``path`` is ``None``)."""
    if path is None:
        config = Config()
    else:
        file = Path(path)
        try:
            text = file.read_text(encoding="utf-8")
        except FileNotFoundError as exc:
            raise ConfigError(f"Config file not found: {file}") from exc
        except OSError as exc:
            raise ConfigError(f"Cannot read config file {file}: {exc}") from exc
        try:
            data = tomllib.loads(text)
        except tomllib.TOMLDecodeError as exc:
            raise ConfigError(f"Invalid TOML in {file}: {exc}") from exc
        config = Config.from_dict(data)
    config.validate()
    return config
