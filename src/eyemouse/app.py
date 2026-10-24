"""Application wiring: camera -> tracker -> pipeline -> cursor.

``run_loop`` depends only on small protocols, so the whole loop can be exercised in tests
with fake cameras, trackers and cursors. ``run`` and ``calibrate_only`` assemble the real
components.
"""

from __future__ import annotations

import logging
import time
from collections.abc import Callable
from pathlib import Path
from typing import Protocol

from ._types import Frame
from .calibration import GazeModel
from .calibration_ui import quality_label, run_calibration
from .camera import Camera
from .config import Config
from .cursor import CursorBackend, DryRunBackend, HardwareMouseWatcher, PyAutoGuiBackend
from .errors import CalibrationError
from .features import Observation
from .paths import default_calibration_path
from .pipeline import Click, GazePipeline, Move, TogglePause
from .preview import PreviewWindow
from .tracker import FaceTracker

log = logging.getLogger(__name__)


class FrameSource(Protocol):
    def read(self, timeout: float = ...) -> Frame | None: ...


class ObservationSource(Protocol):
    def process(self, frame: Frame, t: float) -> Observation | None: ...


class PreviewLike(Protocol):
    def show(
        self,
        frame: Frame,
        obs: Observation | None,
        *,
        paused: bool,
        frozen: bool,
        fps: float,
    ) -> str | None: ...

    def close(self) -> None: ...


def run_loop(
    camera: FrameSource,
    tracker: ObservationSource,
    backend: CursorBackend,
    pipeline: GazePipeline,
    cfg: Config,
    *,
    preview: PreviewLike | None = None,
    clock: Callable[[], float] = time.monotonic,
    max_frames: int | None = None,
) -> int:
    """Process frames until the preview asks to quit (or ``max_frames``). Returns frame count."""
    watcher = HardwareMouseWatcher(cfg.cursor.hardware_threshold_px)
    last_commanded: tuple[int, int] | None = None
    frames = 0
    fps = 0.0
    previous_t: float | None = None

    def move(x: int, y: int) -> None:
        nonlocal last_commanded
        if (x, y) != last_commanded:
            backend.move_to(x, y)
            last_commanded = (x, y)
            watcher.commanded(x, y)

    while max_frames is None or frames < max_frames:
        frame = camera.read(timeout=1.0)
        if frame is None:
            continue
        t = clock()
        frames += 1
        if previous_t is not None and t > previous_t:
            instant = 1.0 / (t - previous_t)
            fps = instant if fps == 0.0 else 0.9 * fps + 0.1 * instant
        previous_t = t

        if (
            cfg.cursor.yield_to_hardware_mouse
            and not pipeline.paused
            and watcher.hijacked(backend.position())
        ):
            pipeline.set_paused(True)
            log.warning(
                "Physical mouse movement detected -> paused. "
                "Close your eyes for %.0f s (or press 'p' in the preview) to resume.",
                cfg.blink.long_close_s,
            )

        obs = tracker.process(frame, t)
        for action in pipeline.step(obs, t):
            if isinstance(action, Move):
                move(action.x, action.y)
            elif isinstance(action, Click):
                move(action.x, action.y)
                backend.click(action.button)
                log.info("Click (%s) at (%d, %d)", action.button, action.x, action.y)
            elif isinstance(action, TogglePause):
                log.info("Eye control %s", "PAUSED" if action.paused else "RESUMED")
                if not action.paused:
                    watcher.reset()
                    last_commanded = None

        if preview is not None:
            command = preview.show(
                frame,
                obs,
                paused=pipeline.paused,
                frozen=pipeline.is_gaze_frozen(t),
                fps=fps,
            )
            if command == "quit":
                break
            if command == "pause":
                pipeline.set_paused(not pipeline.paused)
                if not pipeline.paused:
                    watcher.reset()
                    last_commanded = None
                log.info("Eye control %s", "PAUSED" if pipeline.paused else "RESUMED")
    return frames


# ------------------------------------------------------------------ assembly
def _calibration_path(cfg: Config) -> Path:
    return (
        Path(cfg.calibration.file).expanduser()
        if cfg.calibration.file
        else (default_calibration_path())
    )


def _load_calibration(cfg: Config, screen: tuple[int, int]) -> GazeModel | None:
    path = _calibration_path(cfg)
    if not path.is_file():
        log.info("No calibration found at %s", path)
        return None
    try:
        model = GazeModel.load(path)
    except CalibrationError as exc:
        log.warning("Ignoring unusable calibration (%s)", exc)
        return None
    if model.screen != screen:
        log.warning(
            "Calibration was made for a %dx%d screen but this one is %dx%d; recalibrating.",
            *model.screen,
            *screen,
        )
        return None
    log.info(
        "Loaded calibration from %s (accuracy ~%.0f px, quality: %s)",
        path,
        model.loo_rmse_px,
        quality_label(model.quality_fraction),
    )
    return model


def _calibrate(
    cfg: Config, camera: Camera, tracker: FaceTracker, screen: tuple[int, int]
) -> GazeModel:
    model = run_calibration(cfg.calibration, camera, tracker, screen)
    path = _calibration_path(cfg)
    model.save(path)
    log.info("Calibration saved to %s", path)
    return model


def run(cfg: Config, *, dry_run: bool = False, recalibrate: bool = False) -> int:
    backend: CursorBackend = DryRunBackend() if dry_run else PyAutoGuiBackend()
    screen = backend.screen_size()
    log.info(
        "Screen: %dx%d%s", *screen, "  (dry-run: the real mouse will NOT move)" if dry_run else ""
    )

    with (
        Camera(cfg.camera) as camera,
        FaceTracker(cfg.tracking, keep_points=cfg.ui.preview) as tracker,
    ):
        model = None if recalibrate else _load_calibration(cfg, screen)
        if model is None:
            model = _calibrate(cfg, camera, tracker, screen)
        pipeline = GazePipeline(model, screen, cfg)
        preview = PreviewWindow(cfg.ui.mirror_preview) if cfg.ui.preview else None
        log.info(
            "Running. %d quick blinks = click; close both eyes %.1f s = pause/resume; "
            "Ctrl+C = quit.",
            cfg.blink.required_blinks,
            cfg.blink.long_close_s,
        )
        try:
            run_loop(camera, tracker, backend, pipeline, cfg, preview=preview)
        except KeyboardInterrupt:
            log.info("Interrupted by user")
        finally:
            if preview is not None:
                preview.close()
    return 0


def calibrate_only(cfg: Config) -> int:
    backend = DryRunBackend() if _no_real_mouse() else PyAutoGuiBackend()
    screen = backend.screen_size()
    with Camera(cfg.camera) as camera, FaceTracker(cfg.tracking) as tracker:
        _calibrate(cfg, camera, tracker, screen)
    return 0


def _no_real_mouse() -> bool:
    """Calibration only needs the screen size, so fall back gracefully without pyautogui."""
    try:
        import pyautogui  # noqa: F401
    except Exception:
        return True
    return False
