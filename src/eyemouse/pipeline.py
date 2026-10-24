"""The hardware-free core: observations in, cursor actions out.

``GazePipeline.step`` receives what the tracker saw in one frame and returns the actions the
application should perform. Because it never touches a camera, a screen or a mouse, the
whole behaviour (smoothing, freezing during blinks, click placement, pause) is covered by
fast deterministic tests.
"""

from __future__ import annotations

import logging
import math
from collections import deque
from dataclasses import dataclass

from .blink import BlinkDetector
from .calibration import GazeModel
from .config import Config
from .features import Observation
from .filters import Point2DFilter

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Move:
    x: int
    y: int


@dataclass(frozen=True)
class Click:
    x: int
    y: int
    button: str


@dataclass(frozen=True)
class TogglePause:
    paused: bool


Action = Move | Click | TogglePause


class GazePipeline:
    def __init__(self, model: GazeModel, screen: tuple[int, int], cfg: Config) -> None:
        self.model = model
        self.screen = screen
        self.cfg = cfg
        self.detector = BlinkDetector(cfg.blink)
        self._filter = Point2DFilter(cfg.cursor.min_cutoff, cfg.cursor.beta, cfg.cursor.d_cutoff)
        self._history: deque[tuple[float, int, int]] = deque(maxlen=512)
        self._last_pos: tuple[float, float] | None = None
        self.paused = False

    # ------------------------------------------------------------------ control
    def set_paused(self, paused: bool) -> None:
        self.paused = paused

    def is_gaze_frozen(self, t: float) -> bool:
        return self.detector.gaze_frozen(t)

    # --------------------------------------------------------------------- step
    def step(self, obs: Observation | None, t: float) -> list[Action]:
        actions: list[Action] = []
        if obs is None:
            self.detector.on_face_lost()
            return actions

        events = self.detector.update(t, obs.ear_left, obs.ear_right)

        if not self.paused and not self.detector.gaze_frozen(t):
            move = self._track(obs, t)
            if move is not None:
                actions.append(move)

        for event in events:
            if event.kind == "toggle_pause":
                self.paused = not self.paused
                actions.append(TogglePause(self.paused))
            elif event.kind == "click" and not self.paused:
                target = self._position_at(event.t_ref - self.cfg.cursor.click_lookback_s)
                if target is None:
                    log.debug("Click ignored: no cursor position known yet")
                    continue
                actions.append(Move(*target))
                actions.append(Click(*target, self.cfg.cursor.button))
        return actions

    # ---------------------------------------------------------------- internals
    def _track(self, obs: Observation, t: float) -> Move | None:
        raw_x, raw_y = self.model.predict(obs.feature_vector())
        x, y = self._filter(t, raw_x, raw_y)
        x = min(max(x, 0.0), self.screen[0] - 1.0)
        y = min(max(y, 0.0), self.screen[1] - 1.0)
        if self._last_pos is not None and (
            math.hypot(x - self._last_pos[0], y - self._last_pos[1]) < self.cfg.cursor.deadzone_px
        ):
            x, y = self._last_pos
        else:
            self._last_pos = (x, y)
        pos = (round(x), round(y))
        self._history.append((t, *pos))
        return Move(*pos)

    def _position_at(self, t: float) -> tuple[int, int] | None:
        """Cursor position at (or just before) time ``t``; oldest known if ``t`` predates it."""
        if not self._history:
            return None
        chosen = self._history[0]
        for entry in self._history:
            if entry[0] > t:
                break
            chosen = entry
        return chosen[1], chosen[2]
