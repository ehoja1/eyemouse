"""``eyemouse doctor``: diagnose the most common setup problems in one command."""

from __future__ import annotations

import importlib
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

from . import __version__
from .calibration import GazeModel
from .calibration_ui import quality_label
from .camera import Camera
from .config import Config
from .cursor import PyAutoGuiBackend
from .errors import CalibrationError, EyeMouseError
from .models import ensure_face_model
from .paths import default_calibration_path, default_model_path

OK, WARN, FAIL, INFO = "[ OK ]", "[WARN]", "[FAIL]", "[info]"


class _Report:
    def __init__(self) -> None:
        self.failures = 0

    def line(self, tag: str, message: str) -> None:
        if tag == FAIL:
            self.failures += 1
        print(f"{tag} {message}")


def _check_package(report: _Report, module: str, extra: str, required: bool) -> None:
    try:
        mod = importlib.import_module(module)
    except ImportError:
        tag = FAIL if required else WARN
        report.line(tag, f'{module} not installed  ->  pip install -e ".[{extra}]"')
    except Exception as exc:  # e.g. pyautogui without a display
        report.line(WARN, f"{module} installed but unusable: {exc}")
    else:
        report.line(OK, f"{module} {getattr(mod, '__version__', '')}".rstrip())


def run_doctor(cfg: Config, *, fetch_model: bool = False, check_camera: bool = True) -> int:
    report = _Report()
    print(f"EyeMouse {__version__} - environment check\n")

    report.line(OK, f"Python {sys.version.split()[0]} on {sys.platform}")

    _check_package(report, "numpy", "all", required=True)
    _check_package(report, "cv2", "vision", required=True)
    _check_package(report, "mediapipe", "vision", required=True)
    _check_package(report, "pyautogui", "control", required=False)

    if sys.platform.startswith("linux"):
        if os.environ.get("XDG_SESSION_TYPE", "").lower() == "wayland":
            report.line(
                WARN,
                "Wayland session detected: pyautogui cannot move the cursor under Wayland. "
                "Log in with an 'X11 / Xorg' session, or use --dry-run.",
            )
        if not os.environ.get("DISPLAY"):
            report.line(WARN, "No DISPLAY set: no graphical desktop available to this shell.")

    _check_model(report, cfg, fetch_model)
    _check_screen(report)
    if check_camera:
        _check_camera(report, cfg)
    _check_calibration(report, cfg)

    print()
    if report.failures:
        print(f"{report.failures} problem(s) found. See docs/TROUBLESHOOTING.md.")
        return 1
    print("Everything required looks fine. Next: eyemouse run --preview")
    return 0


def _check_model(report: _Report, cfg: Config, fetch: bool) -> None:
    configured = Path(cfg.tracking.model_path).expanduser() if cfg.tracking.model_path else None
    path = configured or default_model_path()
    if path.is_file() or fetch:
        try:
            ensure_face_model(cfg.tracking)
            report.line(OK, f"Face model ready: {path}")
        except EyeMouseError as exc:
            report.line(FAIL, str(exc))
    else:
        report.line(
            WARN,
            f"Face model not downloaded yet ({path}). It is fetched automatically on first run, "
            "or now with:  eyemouse doctor --fetch-model",
        )


def _check_screen(report: _Report) -> None:
    try:
        width, height = PyAutoGuiBackend().screen_size()
        report.line(OK, f"Screen size {width}x{height}")
    except EyeMouseError as exc:
        report.line(WARN, f"Screen/mouse control unavailable: {exc}")


def _check_camera(report: _Report, cfg: Config) -> None:
    try:
        started = time.monotonic()
        with Camera(cfg.camera) as camera:
            frame = camera.read(timeout=3.0)
        if frame is None:
            report.line(FAIL, "Camera opened but returned no frame")
        else:
            h, w = frame.shape[:2]
            report.line(
                OK,
                f"Camera {cfg.camera.index}: {w}x{h} (opened in {time.monotonic() - started:.1f}s)",
            )
    except EyeMouseError as exc:
        report.line(FAIL, str(exc))


def _check_calibration(report: _Report, cfg: Config) -> None:
    path = (
        Path(cfg.calibration.file).expanduser()
        if cfg.calibration.file
        else default_calibration_path()
    )
    if not path.is_file():
        report.line(
            INFO, "Not calibrated yet (happens automatically on first run, or: eyemouse calibrate)"
        )
        return
    try:
        model = GazeModel.load(path)
    except CalibrationError as exc:
        report.line(WARN, f"Calibration file unusable: {exc}")
        return
    age_days = (datetime.now(timezone.utc) - datetime.fromisoformat(model.created)).days
    report.line(
        OK,
        f"Calibration: {model.n_points} points, accuracy ~{model.loo_rmse_px:.0f} px "
        f"({quality_label(model.quality_fraction)}), {age_days} day(s) old",
    )
