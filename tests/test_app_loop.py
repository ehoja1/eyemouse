"""End-to-end test of the main loop with a fake camera, tracker, preview and mouse."""

from __future__ import annotations

import numpy as np

from eyemouse.app import run_loop
from eyemouse.config import Config
from eyemouse.cursor import DryRunBackend
from eyemouse.pipeline import GazePipeline
from helpers import TRIPLE, PixelModel, scenario

SCREEN = (1920, 1080)
DT = 1.0 / 30.0


class FakeCamera:
    def __init__(self, none_first: int = 0) -> None:
        self._none = none_first

    def read(self, timeout: float = 1.0):
        if self._none > 0:
            self._none -= 1
            return None
        return np.zeros((4, 4, 3), dtype=np.uint8)


class ScriptedTracker:
    def __init__(self, frames, on_frame=None) -> None:
        self._obs = [obs for _, obs in frames]
        self._i = 0
        self._on_frame = on_frame

    def process(self, frame, t):
        i = self._i
        self._i += 1
        if self._on_frame:
            self._on_frame(i)
        return self._obs[i] if i < len(self._obs) else None


class Clock:
    def __init__(self) -> None:
        self._n = -1

    def __call__(self) -> float:
        self._n += 1
        return self._n * DT


def build(frames, on_frame=None, cfg=None, camera=None):
    cfg = cfg or Config()
    backend = DryRunBackend(SCREEN)
    pipeline = GazePipeline(PixelModel(), SCREEN, cfg)  # type: ignore[arg-type]
    tracker = ScriptedTracker(frames, on_frame)
    return cfg, backend, pipeline, tracker, camera or FakeCamera()


def test_triple_blink_performs_exactly_one_click_at_the_gaze_point():
    frames = scenario(TRIPLE)
    cfg, backend, pipeline, tracker, camera = build(frames)
    run_loop(camera, tracker, backend, pipeline, cfg, clock=Clock(), max_frames=len(frames))
    assert backend.clicks == [(800, 400, "left")]
    assert backend.position() == (800, 400)


def test_missing_camera_frames_are_skipped_not_fatal():
    frames = scenario([])
    cfg, backend, pipeline, tracker, camera = build(frames, camera=FakeCamera(none_first=3))
    done = run_loop(camera, tracker, backend, pipeline, cfg, clock=Clock(), max_frames=20)
    assert done == 20
    assert backend.position() == (800, 400)


def test_moving_the_physical_mouse_pauses_eye_control():
    frames = scenario([], tail=4.0)
    holder = {}

    def user_grabs_the_mouse(frame_index: int) -> None:
        if frame_index == 90:
            holder["backend"].move_to(100, 100)  # the real mouse is moved by hand

    cfg, backend, pipeline, tracker, camera = build(frames, on_frame=user_grabs_the_mouse)
    holder["backend"] = backend
    run_loop(camera, tracker, backend, pipeline, cfg, clock=Clock(), max_frames=len(frames))
    assert pipeline.paused
    assert backend.position() == (100, 100)  # eye control did not drag it back


def test_hardware_mouse_yielding_can_be_disabled():
    cfg = Config()
    cfg.cursor.yield_to_hardware_mouse = False
    frames = scenario([], tail=4.0)
    holder = {}

    def user_grabs_the_mouse(frame_index: int) -> None:
        if frame_index == 90:
            holder["backend"].move_to(100, 100)

    cfg, backend, pipeline, tracker, camera = build(frames, user_grabs_the_mouse, cfg)
    holder["backend"] = backend
    run_loop(camera, tracker, backend, pipeline, cfg, clock=Clock(), max_frames=len(frames))
    assert not pipeline.paused


class FakePreview:
    def __init__(self, commands) -> None:
        self._commands = list(commands)
        self.calls = 0
        self.closed = False

    def show(self, frame, obs, *, paused, frozen, fps):
        self.calls += 1
        return self._commands.pop(0) if self._commands else None

    def close(self) -> None:
        self.closed = True


def test_preview_quit_key_ends_the_loop():
    frames = scenario([], tail=4.0)
    cfg, backend, pipeline, tracker, camera = build(frames)
    preview = FakePreview([None, None, None, "quit"])
    done = run_loop(
        camera, tracker, backend, pipeline, cfg, preview=preview, clock=Clock(), max_frames=500
    )
    assert done == 4
    assert preview.calls == 4


def test_preview_pause_key_toggles_eye_control():
    frames = scenario([], tail=4.0)
    cfg, backend, pipeline, tracker, camera = build(frames)
    preview = FakePreview([None] * 100 + ["pause"])
    run_loop(
        camera, tracker, backend, pipeline, cfg, preview=preview, clock=Clock(), max_frames=101
    )
    assert pipeline.paused
