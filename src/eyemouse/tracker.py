"""MediaPipe Face Landmarker wrapper: camera frame in, :class:`Observation` out."""

from __future__ import annotations

import logging
from types import TracebackType
from typing import Any

import numpy as np

from ._types import Frame
from .config import TrackingConfig
from .errors import MissingDependencyError, ModelError
from .features import Observation, extract_observation
from .models import ensure_face_model

log = logging.getLogger(__name__)


class FaceTracker:
    """Detects one face and derives eye/iris features (see :mod:`eyemouse.features`)."""

    def __init__(self, cfg: TrackingConfig, keep_points: bool = False) -> None:
        try:
            import cv2
            import mediapipe as mp
            from mediapipe.tasks import python as mp_python
            from mediapipe.tasks.python import vision
        except ImportError as exc:
            raise MissingDependencyError("mediapipe and opencv-python", "vision") from exc

        self._cv2: Any = cv2
        self._mp: Any = mp
        self.keep_points = keep_points
        self._last_ts_ms = -1
        self._warned_shape = False

        model_path = ensure_face_model(cfg)
        # Passing the model as bytes (not a path) keeps non-ASCII user folders working on
        # Windows, e.g. C:\Users\João\...
        model_bytes = model_path.read_bytes()
        options = vision.FaceLandmarkerOptions(
            base_options=mp_python.BaseOptions(model_asset_buffer=model_bytes),
            running_mode=vision.RunningMode.VIDEO,
            num_faces=1,
            min_face_detection_confidence=cfg.min_detection_confidence,
            min_face_presence_confidence=cfg.min_presence_confidence,
            min_tracking_confidence=cfg.min_tracking_confidence,
            output_face_blendshapes=False,
            output_facial_transformation_matrixes=False,
        )
        try:
            self._landmarker: Any = vision.FaceLandmarker.create_from_options(options)
        except Exception as exc:  # MediaPipe raises bare RuntimeError / ValueError
            raise ModelError(
                f"MediaPipe could not load the face model ({model_path}): {exc}. "
                "Delete that file and run again to download it afresh."
            ) from exc

    def process(self, frame_bgr: Frame, t: float) -> Observation | None:
        """Analyse one BGR frame captured at monotonic time ``t`` (seconds)."""
        height, width = frame_bgr.shape[:2]
        rgb = self._cv2.cvtColor(frame_bgr, self._cv2.COLOR_BGR2RGB)
        image = self._mp.Image(image_format=self._mp.ImageFormat.SRGB, data=rgb)
        # MediaPipe requires strictly increasing integer millisecond timestamps.
        ts_ms = max(int(t * 1000.0), self._last_ts_ms + 1)
        self._last_ts_ms = ts_ms
        result = self._landmarker.detect_for_video(image, ts_ms)
        if not result.face_landmarks:
            return None
        landmarks = np.array([(p.x, p.y) for p in result.face_landmarks[0]], dtype=np.float64)
        try:
            return extract_observation(landmarks, width, height, t, keep_points=self.keep_points)
        except ValueError as exc:
            if not self._warned_shape:
                log.error("Unusable landmark output (is the model iris-enabled?): %s", exc)
                self._warned_shape = True
            return None

    def close(self) -> None:
        self._landmarker.close()

    def __enter__(self) -> FaceTracker:
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: TracebackType | None,
    ) -> None:
        self.close()
