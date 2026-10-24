"""Signal smoothing: the One Euro filter (Casiez, Roussel & Vogel, CHI 2012).

The filter smooths heavily when the signal is nearly still (removing jitter) and relaxes
when it moves fast (removing lag), which is exactly what gaze-driven cursors need.
"""

from __future__ import annotations

import math


def _alpha(dt: float, cutoff: float) -> float:
    tau = 1.0 / (2.0 * math.pi * cutoff)
    return 1.0 / (1.0 + tau / dt)


class OneEuroFilter:
    """One Euro filter for a scalar signal sampled at irregular times."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0, d_cutoff: float = 1.0) -> None:
        if min_cutoff <= 0 or d_cutoff <= 0:
            raise ValueError("cutoff frequencies must be positive")
        self.min_cutoff = min_cutoff
        self.beta = beta
        self.d_cutoff = d_cutoff
        self.reset()

    def reset(self) -> None:
        self._t: float | None = None
        self._x_hat = 0.0
        self._dx_hat = 0.0

    def __call__(self, t: float, x: float) -> float:
        if self._t is None:
            self._t, self._x_hat, self._dx_hat = t, x, 0.0
            return x
        dt = t - self._t
        if dt <= 0.0:
            return self._x_hat
        dx = (x - self._x_hat) / dt
        self._dx_hat += _alpha(dt, self.d_cutoff) * (dx - self._dx_hat)
        cutoff = self.min_cutoff + self.beta * abs(self._dx_hat)
        self._x_hat += _alpha(dt, cutoff) * (x - self._x_hat)
        self._t = t
        return self._x_hat


class Point2DFilter:
    """Two independent One Euro filters, one per axis."""

    def __init__(self, min_cutoff: float = 1.0, beta: float = 0.0, d_cutoff: float = 1.0) -> None:
        self._fx = OneEuroFilter(min_cutoff, beta, d_cutoff)
        self._fy = OneEuroFilter(min_cutoff, beta, d_cutoff)

    def reset(self) -> None:
        self._fx.reset()
        self._fy.reset()

    def __call__(self, t: float, x: float, y: float) -> tuple[float, float]:
        return self._fx(t, x), self._fy(t, y)
