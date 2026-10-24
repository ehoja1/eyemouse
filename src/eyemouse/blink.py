"""Blink gesture recognition: triple blink = click, long closure = pause toggle.

Pure logic driven by ``(timestamp, EAR_left, EAR_right)`` samples, so it can be tested with
synthetic signals and has no dependency on a camera.

Design notes
------------
* **Adaptive threshold.** Eye openness differs between people, cameras and lighting. The
  detector measures the open-eye EAR during a short warm-up and then expresses every
  threshold as a *ratio* of that baseline. The baseline keeps adapting slowly while the
  eyes are open.
* **Hysteresis.** Closing and re-opening use different thresholds, which stops a noisy EAR
  hovering near one threshold from producing a burst of false blinks.
* **Both eyes.** A blink is only counted when *both* eyes close (``max(left, right)`` is
  used), so winks and one-sided tracking glitches do not trigger anything.
* **Duration limits.** Natural blinks last roughly 100-400 ms. Shorter dips are sensor
  noise; longer closures are deliberate and reset the sequence.
* **Refractory period.** Right after a click further blinks are ignored, so a slow
  finish of the gesture cannot start a second click.
"""

from __future__ import annotations

import logging
import math
import statistics
from collections import deque
from dataclasses import dataclass
from typing import Literal

from .config import BlinkConfig

log = logging.getLogger(__name__)

#: Warm-up restarts if the measured open-eye EAR is implausibly low (eyes shut, bad tracking).
MIN_PLAUSIBLE_OPEN_EAR = 0.12


@dataclass(frozen=True)
class GestureEvent:
    kind: Literal["click", "toggle_pause"]
    #: Timestamp at which the gesture started (start of the first blink for a click).
    t_ref: float


class BlinkDetector:
    def __init__(self, cfg: BlinkConfig) -> None:
        self.cfg = cfg
        self.baseline: float | None = None
        self._warm: list[float] = []
        self._warm_start: float | None = None
        self._closed = False
        self._close_t = 0.0
        self._long_fired = False
        self._last_open_t = -math.inf
        self._last_ear = 1.0
        self._face_lost = False
        self._blinks: deque[tuple[float, float]] = deque()
        self._refractory_until = -math.inf

    # ------------------------------------------------------------------ state
    @property
    def ready(self) -> bool:
        """``True`` once the open-eye baseline has been measured."""
        return self.baseline is not None

    @property
    def eyes_closed(self) -> bool:
        return self._closed

    def gaze_frozen(self, t: float) -> bool:
        """Whether gaze data is unreliable right now (eyes closing, closed or just reopened).

        While the lids move, the iris landmarks jump around; the cursor must hold still or
        the click would land somewhere other than where the user was looking.
        """
        if self.baseline is None:
            return False
        if self._closed or t - self._last_open_t < self.cfg.settle_s:
            return True
        return self._last_ear < self.baseline * self.cfg.freeze_ratio

    def on_face_lost(self) -> None:
        """Call when no face is detected: drops any half-finished gesture."""
        self._closed = False
        self._long_fired = False
        self._blinks.clear()
        self._face_lost = True

    # ----------------------------------------------------------------- update
    def update(self, t: float, ear_left: float, ear_right: float) -> list[GestureEvent]:
        events: list[GestureEvent] = []
        ear = max(ear_left, ear_right)
        self._last_ear = ear

        if self._face_lost:
            # Landmarks are unreliable for a moment after the face re-appears.
            self._face_lost = False
            self._last_open_t = t

        if self.baseline is None:
            self._warm_up(t, ear)
            return events

        cfg = self.cfg
        close_thr = self.baseline * cfg.close_ratio
        open_thr = self.baseline * cfg.open_ratio

        if not self._closed:
            if ear < close_thr:
                self._closed = True
                self._close_t = t
                self._long_fired = False
            else:
                if ear >= open_thr and cfg.baseline_alpha > 0.0:
                    self.baseline += cfg.baseline_alpha * (ear - self.baseline)
                if self._blinks and t - self._blinks[-1][1] > cfg.max_gap_s:
                    self._blinks.clear()
        elif ear >= open_thr:
            duration = t - self._close_t
            self._closed = False
            self._last_open_t = t
            if not self._long_fired:
                self._on_blink_finished(self._close_t, t, duration, events)
        elif (
            cfg.long_close_s > 0.0
            and not self._long_fired
            and t - self._close_t >= cfg.long_close_s
        ):
            self._long_fired = True
            self._blinks.clear()
            events.append(GestureEvent("toggle_pause", self._close_t))
            log.info("Long eye closure detected -> toggle pause")
        return events

    # --------------------------------------------------------------- internals
    def _warm_up(self, t: float, ear: float) -> None:
        if self._warm_start is None:
            self._warm_start = t
        self._warm.append(ear)
        if t - self._warm_start < self.cfg.warmup_s or len(self._warm) < 5:
            return
        median = statistics.median(self._warm)
        if median < MIN_PLAUSIBLE_OPEN_EAR:
            log.warning("Open-eye EAR looks too low (%.3f); restarting warm-up", median)
            self._warm.clear()
            self._warm_start = None
            return
        self.baseline = median
        self._last_open_t = t
        log.info("Blink baseline measured: EAR=%.3f", median)

    def _on_blink_finished(
        self, start: float, end: float, duration: float, events: list[GestureEvent]
    ) -> None:
        cfg = self.cfg
        if end < self._refractory_until or duration < cfg.min_blink_s:
            return  # ignored: refractory period, or too short to be a real blink
        if duration > cfg.max_blink_s:
            self._blinks.clear()  # deliberate closure: breaks the sequence
            return
        if self._blinks and start - self._blinks[-1][1] > cfg.max_gap_s:
            self._blinks.clear()
        self._blinks.append((start, end))
        while len(self._blinks) > 1 and end - self._blinks[0][0] > cfg.max_sequence_s:
            self._blinks.popleft()
        if len(self._blinks) >= cfg.required_blinks:
            events.append(GestureEvent("click", self._blinks[0][0]))
            self._blinks.clear()
            self._refractory_until = end + cfg.refractory_s
