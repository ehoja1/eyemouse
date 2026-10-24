"""Threaded webcam capture that always hands out the newest frame.

Reading frames on a background thread avoids the classic webcam problem where a slow
processing step lets old frames pile up in the driver's buffer and the cursor ends up
following where you looked a second ago.
"""

from __future__ import annotations

import logging
import sys
import threading
import time
from types import TracebackType
from typing import Any

from ._types import Frame
from .config import CameraConfig
from .errors import CameraError, MissingDependencyError

log = logging.getLogger(__name__)


#: Consecutive failed reads before the camera is declared dead.
MAX_READ_FAILURES = 60
#: How long to wait for the first frame (macOS may show a permission dialog).
FIRST_FRAME_TIMEOUT_S = 15.0


class Camera:
    def __init__(self, cfg: CameraConfig) -> None:
        self.cfg = cfg
        self._cap: Any = None
        self._thread: threading.Thread | None = None
        self._stop = threading.Event()
        self._cond = threading.Condition()
        self._frame: Frame | None = None
        self._seq = 0
        self._last_returned = 0
        self._error: str | None = None

    # ----------------------------------------------------------------- lifecycle
    def open(self) -> None:
        try:
            import cv2
        except ImportError as exc:
            raise MissingDependencyError("opencv-python", "vision") from exc

        backends = [cv2.CAP_DSHOW, cv2.CAP_ANY] if sys.platform == "win32" else [cv2.CAP_ANY]
        cap = None
        for backend in backends:
            candidate = cv2.VideoCapture(self.cfg.index, backend)
            if candidate.isOpened():
                cap = candidate
                break
            candidate.release()
        if cap is None:
            raise CameraError(
                f"Could not open camera {self.cfg.index}. Is it in use by another program, "
                "or blocked by the operating system's camera privacy settings? "
                "Try --camera 1 for a different device."
            )
        cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cfg.width)
        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cfg.height)
        cap.set(cv2.CAP_PROP_FPS, self.cfg.fps)
        cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
        self._cap = cap
        self._stop.clear()
        self._thread = threading.Thread(target=self._capture_loop, name="camera", daemon=True)
        self._thread.start()

        if self.read(timeout=FIRST_FRAME_TIMEOUT_S) is None:
            self.close()
            raise CameraError(
                "The camera opened but delivered no frames. Check the camera permission for "
                "your terminal / VS Code and close other apps that use the camera."
            )
        log.info(
            "Camera %d open at %dx%d",
            self.cfg.index,
            int(cap.get(cv2.CAP_PROP_FRAME_WIDTH)),
            int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT)),
        )

    def close(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=2.0)
            self._thread = None
        if self._cap is not None:
            self._cap.release()
            self._cap = None

    def __enter__(self) -> Camera:
        self.open()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()

    # --------------------------------------------------------------------- frames
    def read(self, timeout: float = 1.0) -> Frame | None:
        """Return the next *new* frame, or ``None`` if none arrived within ``timeout``."""
        deadline = time.monotonic() + timeout
        with self._cond:
            while self._seq == self._last_returned and self._error is None:
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    return None
                self._cond.wait(remaining)
            if self._error is not None:
                raise CameraError(self._error)
            self._last_returned = self._seq
            return self._frame

    def _capture_loop(self) -> None:
        failures = 0
        while not self._stop.is_set():
            cap = self._cap
            if cap is None:
                return
            ok, frame = cap.read()
            if not ok or frame is None:
                failures += 1
                if failures >= MAX_READ_FAILURES:
                    with self._cond:
                        self._error = "The camera stopped delivering frames (unplugged?)."
                        self._cond.notify_all()
                    return
                time.sleep(0.01)
                continue
            failures = 0
            with self._cond:
                self._frame = frame
                self._seq += 1
                self._cond.notify_all()
