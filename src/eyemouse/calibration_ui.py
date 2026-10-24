"""Full-screen calibration routine (OpenCV window). The maths lives in ``calibration.py``."""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from typing import Any, Protocol

import numpy as np

from ._types import FloatArray, Frame
from .calibration import GazeModel, SampleCollector, calibration_targets
from .config import CalibrationConfig
from .errors import CalibrationAborted, CalibrationError, MissingDependencyError
from .features import Observation

log = logging.getLogger(__name__)

WINDOW = "EyeMouse calibration"
ESC = 27
SPACE = 32
ENTER = 13

#: Leave-one-out error as a fraction of the screen diagonal.
GOOD_FRACTION = 0.06
FAIR_FRACTION = 0.12


class _FrameSource(Protocol):
    def read(self, timeout: float = ...) -> Frame | None: ...


class _Tracker(Protocol):
    def process(self, frame: Frame, t: float) -> Observation | None: ...


def quality_label(fraction: float) -> str:
    if fraction < GOOD_FRACTION:
        return "good"
    if fraction < FAIR_FRACTION:
        return "fair - consider recalibrating"
    return "poor - please recalibrate (better light, face the camera, keep still)"


def run_calibration(
    cfg: CalibrationConfig,
    camera: _FrameSource,
    tracker: _Tracker,
    screen: tuple[int, int],
    clock: Callable[[], float] = time.monotonic,
) -> GazeModel:
    """Show calibration targets, collect gaze samples and fit a :class:`GazeModel`."""
    try:
        import cv2
    except ImportError as exc:
        raise MissingDependencyError("opencv-python", "vision") from exc

    width, height = screen
    targets = calibration_targets(width, height, cfg.grid, cfg.margin)
    cv2.namedWindow(WINDOW, cv2.WINDOW_NORMAL)
    cv2.setWindowProperty(WINDOW, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
    try:
        _message_screen(
            cv2,
            screen,
            [
                "EyeMouse calibration",
                "",
                "Sit comfortably, face the camera, and keep your head still.",
                "Look at each dot until it disappears. Keep your eyes open.",
                f"{len(targets)} points - about {_estimate_seconds(cfg, len(targets))} seconds.",
                "",
                "SPACE = start     ESC = cancel",
            ],
            wait_for=(SPACE, ENTER),
        )
        features: list[FloatArray] = []
        for index, (tx, ty) in enumerate(targets, start=1):
            features.append(
                _collect_point(
                    cv2, cfg, camera, tracker, screen, (tx, ty), index, len(targets), clock
                )
            )
        model = GazeModel.fit(features, targets, screen, cfg.ridge)
        log.info(
            "Calibration done: rmse=%.0f px, leave-one-out=%.0f px (%.1f%% of diagonal)",
            model.rmse_px,
            model.loo_rmse_px,
            100 * model.quality_fraction,
        )
        _message_screen(
            cv2,
            screen,
            [
                "Calibration complete",
                "",
                f"Estimated accuracy: about {model.loo_rmse_px:.0f} px "
                f"({100 * model.quality_fraction:.1f}% of the screen diagonal)",
                f"Quality: {quality_label(model.quality_fraction)}",
                "",
                "Press any key to continue",
            ],
            wait_for=None,
        )
        return model
    finally:
        cv2.destroyWindow(WINDOW)


def _estimate_seconds(cfg: CalibrationConfig, n_points: int) -> int:
    return round(n_points * (cfg.settle_s + cfg.collect_s) + 3)


def _collect_point(
    cv2: Any,
    cfg: CalibrationConfig,
    camera: _FrameSource,
    tracker: _Tracker,
    screen: tuple[int, int],
    target: tuple[int, int],
    index: int,
    total: int,
    clock: Callable[[], float],
) -> FloatArray:
    width, height = screen
    base = np.zeros((height, width, 3), dtype=np.uint8)
    duration = cfg.settle_s + cfg.collect_s
    for attempt in range(cfg.max_retries + 1):
        collector = SampleCollector(cfg.min_samples)
        start = clock()
        while True:
            elapsed = clock() - start
            if elapsed >= duration:
                break
            frame = camera.read(timeout=0.5)
            now = clock()
            if frame is not None:
                obs = tracker.process(frame, now)
                if (
                    now - start >= cfg.settle_s
                    and obs is not None
                    and min(obs.ear_left, obs.ear_right) >= cfg.min_open_ear
                ):
                    collector.add(obs.feature_vector())
            canvas = base.copy()
            _draw_target(cv2, canvas, target, min(elapsed / duration, 1.0), index, total, attempt)
            cv2.imshow(WINDOW, canvas)
            if cv2.waitKey(1) & 0xFF == ESC:
                raise CalibrationAborted("Calibration cancelled.")
        result = collector.result()
        if result is not None:
            return result
        log.warning(
            "Point %d/%d: only %d usable samples (need %d); retrying",
            index,
            total,
            len(collector),
            cfg.min_samples,
        )
    raise CalibrationError(
        f"Could not read your eyes at point {index}/{total}. Make sure your face is well lit, "
        "fully visible, and your eyes stay open while you look at the dot."
    )


def _draw_target(
    cv2: Any,
    canvas: Frame,
    target: tuple[int, int],
    progress: float,
    index: int,
    total: int,
    attempt: int,
) -> None:
    height = canvas.shape[0]
    unit = max(height // 54, 8)
    radius = int(unit * (3.0 - 2.0 * progress))  # ring shrinks onto the dot
    cv2.circle(canvas, target, radius, (255, 255, 255), 2)
    cv2.circle(canvas, target, unit // 2 + 2, (255, 255, 255), -1)
    cv2.circle(canvas, target, max(unit // 5, 2), (0, 0, 255), -1)
    label = f"{index}/{total}" + (f"  (retry {attempt})" if attempt else "")
    cv2.putText(canvas, label, (20, 40), cv2.FONT_HERSHEY_SIMPLEX, height / 900, (160, 160, 160), 2)


def _message_screen(
    cv2: Any, screen: tuple[int, int], lines: list[str], wait_for: tuple[int, ...] | None
) -> None:
    width, height = screen
    canvas = np.zeros((height, width, 3), dtype=np.uint8)
    scale = height / 900
    y = int(height * 0.3)
    for i, text in enumerate(lines):
        size = scale * (1.4 if i == 0 else 0.9)
        (text_w, _), _ = cv2.getTextSize(text, cv2.FONT_HERSHEY_SIMPLEX, size, 2)
        cv2.putText(
            canvas,
            text,
            ((width - text_w) // 2, y),
            cv2.FONT_HERSHEY_SIMPLEX,
            size,
            (255, 255, 255),
            2,
        )
        y += int(55 * scale)
    cv2.imshow(WINDOW, canvas)
    while True:
        key = cv2.waitKey(50) & 0xFF
        if key == ESC and wait_for is not None:
            raise CalibrationAborted("Calibration cancelled.")
        if wait_for is None and key != 0xFF:
            return
        if wait_for is not None and key in wait_for:
            return
