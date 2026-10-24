"""Synthetic signal generators shared by the tests (no camera or screen needed)."""

from __future__ import annotations

from collections.abc import Callable, Sequence

import numpy as np

from eyemouse.features import Observation

FPS = 30.0
OPEN_EAR = 0.30
CLOSED_EAR = 0.05

Closure = tuple[float, float]  # (offset_s after the lead-in, duration_s)


def closed_at(closures: Sequence[Closure], t: float, lead: float) -> bool:
    return any(lead + start <= t < lead + start + dur for start, dur in closures)


def ear_series(
    closures: Sequence[Closure],
    *,
    fps: float = FPS,
    open_ear: float = OPEN_EAR,
    closed_ear: float = CLOSED_EAR,
    lead: float = 2.0,
    tail: float = 2.0,
) -> list[tuple[float, float]]:
    """EAR samples: open except during the given closures (offsets measured after ``lead``)."""
    last = max((s + d for s, d in closures), default=0.0)
    count = int((lead + last + tail) * fps)
    series = []
    for i in range(count):
        t = i / fps
        series.append((t, closed_ear if closed_at(closures, t, lead) else open_ear))
    return series


def drive(detector, series):  # type: ignore[no-untyped-def]
    events = []
    for t, ear in series:
        events += detector.update(t, ear, ear)
    return events


def landmarks(open_h: float = 0.012, iris_dx: float = 0.0, iris_dy: float = 0.0) -> np.ndarray:
    """A 478-point landmark array with just the points EyeMouse reads, placed sensibly.

    Eye width is 0.06 (normalised), ``open_h`` is the half-height of the eye opening.
    """
    pts = np.full((478, 2), 0.5)
    cy = 0.40
    h = open_h
    # Right eye (subject's right = image left)
    pts[33], pts[133] = (0.40, cy), (0.46, cy)
    pts[160], pts[144] = (0.42, cy - h), (0.42, cy + h)
    pts[158], pts[153] = (0.44, cy - h), (0.44, cy + h)
    pts[159], pts[145] = (0.43, cy - h), (0.43, cy + h)
    pts[468] = (0.43 + iris_dx, cy + iris_dy)
    # Left eye
    pts[362], pts[263] = (0.54, cy), (0.60, cy)
    pts[385], pts[380] = (0.56, cy - h), (0.56, cy + h)
    pts[387], pts[373] = (0.58, cy - h), (0.58, cy + h)
    pts[386], pts[374] = (0.57, cy - h), (0.57, cy + h)
    pts[473] = (0.57 + iris_dx, cy + iris_dy)
    pts[1] = (0.5, 0.5)  # nose tip
    return pts


class PixelModel:
    """Stand-in for GazeModel: the 'features' are already screen pixels."""

    def predict(self, feature: np.ndarray) -> tuple[float, float]:
        return float(feature[0]), float(feature[1])


def make_obs(t: float, ear: float, gx: float, gy: float) -> Observation:
    return Observation(
        t=t, ear_left=ear, ear_right=ear, gaze_x=gx, gaze_y=gy, head_x=0.5, head_y=0.5
    )


def scenario(
    closures: Sequence[Closure],
    *,
    gaze_fn: Callable[[float], tuple[float, float]] = lambda t: (800.0, 400.0),
    garbage: tuple[float, float] = (10.0, 10.0),
    lead: float = 2.0,
    tail: float = 1.0,
    fps: float = FPS,
) -> list[tuple[float, Observation]]:
    """Observation stream. While the eyes are closed the 'gaze' is garbage, like real data."""
    out = []
    for t, ear in ear_series(closures, fps=fps, lead=lead, tail=tail):
        gx, gy = garbage if ear == CLOSED_EAR else gaze_fn(t)
        out.append((t, make_obs(t, ear, gx, gy)))
    return out


TRIPLE: list[Closure] = [(0.0, 0.12), (0.3, 0.12), (0.6, 0.12)]
