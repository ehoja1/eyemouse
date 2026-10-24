"""Optional live preview window with eye landmarks, EAR values and status."""

from __future__ import annotations

from typing import Any

from ._types import Frame
from .errors import MissingDependencyError
from .features import (
    LEFT_EYE_EAR,
    LEFT_IRIS_CENTER,
    RIGHT_EYE_EAR,
    RIGHT_IRIS_CENTER,
    Observation,
)

WINDOW_NAME = "EyeMouse preview  (q = quit, p = pause)"
GREEN = (80, 220, 80)
RED = (60, 60, 240)
YELLOW = (0, 220, 240)
WHITE = (255, 255, 255)


class PreviewWindow:
    def __init__(self, mirror: bool = True) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise MissingDependencyError("opencv-python", "vision") from exc
        self._cv2: Any = cv2
        self.mirror = mirror
        cv2.namedWindow(WINDOW_NAME, cv2.WINDOW_NORMAL)

    def show(
        self,
        frame: Frame,
        obs: Observation | None,
        *,
        paused: bool,
        frozen: bool,
        fps: float,
    ) -> str | None:
        """Draw one frame. Returns ``"quit"``, ``"pause"`` or ``None`` (key presses)."""
        cv2 = self._cv2
        canvas = cv2.flip(frame, 1) if self.mirror else frame.copy()
        width = canvas.shape[1]

        if obs is not None and obs.points is not None:
            for idx in (*RIGHT_EYE_EAR, *LEFT_EYE_EAR):
                x, y = obs.points[idx]
                cx = int(width - 1 - x) if self.mirror else int(x)
                cv2.circle(canvas, (cx, int(y)), 2, GREEN, -1)
            for idx in (RIGHT_IRIS_CENTER, LEFT_IRIS_CENTER):
                x, y = obs.points[idx]
                cx = int(width - 1 - x) if self.mirror else int(x)
                cv2.circle(canvas, (cx, int(y)), 3, RED, -1)

        status = "PAUSED" if paused else ("HOLD (blink)" if frozen else "ACTIVE")
        lines = [f"{status}   {fps:4.1f} fps"]
        if obs is None:
            lines.append("no face detected")
        else:
            lines.append(f"EAR  L {obs.ear_left:.2f}  R {obs.ear_right:.2f}")
        color = YELLOW if paused else (WHITE if not frozen else RED)
        for i, text in enumerate(lines):
            cv2.putText(canvas, text, (10, 24 + 22 * i), cv2.FONT_HERSHEY_SIMPLEX, 0.6, color, 2)
        cv2.imshow(WINDOW_NAME, canvas)

        key = cv2.waitKey(1) & 0xFF
        if key in (ord("q"), 27):
            return "quit"
        if key == ord("p"):
            return "pause"
        if cv2.getWindowProperty(WINDOW_NAME, cv2.WND_PROP_VISIBLE) < 1:
            return "quit"  # the user closed the window with its [x] button
        return None

    def close(self) -> None:
        self._cv2.destroyWindow(WINDOW_NAME)
