"""Turn raw face landmarks into the few numbers the rest of the system needs.

This module is pure NumPy: no camera, no MediaPipe, no screen. That keeps it fast to test.

Conventions
-----------
* Landmark indices follow the MediaPipe Face Mesh topology with iris refinement
  (478 points: 468 face points + 5 per iris).
* "left" and "right" are the *subject's* anatomical eyes, not the image sides.
* Landmark coordinates arrive normalised to [0, 1]; geometry is computed in pixels so
  that distances are not distorted by the image aspect ratio.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt

from ._types import FloatArray

NUM_LANDMARKS_WITH_IRIS = 478

# EAR points in the order p1..p6 used by Soukupova & Cech (2016):
# outer corner, upper-1, upper-2, inner corner, lower-2, lower-1.
RIGHT_EYE_EAR = (33, 160, 158, 133, 153, 144)
LEFT_EYE_EAR = (362, 385, 387, 263, 373, 380)

RIGHT_IRIS_CENTER = 468
LEFT_IRIS_CENTER = 473
# Corners ordered so that the first one has the smaller x in an un-mirrored camera image.
RIGHT_EYE_CORNERS = (33, 133)
LEFT_EYE_CORNERS = (362, 263)
# (upper lid, lower lid) mid-points.
RIGHT_EYE_LIDS = (159, 145)
LEFT_EYE_LIDS = (386, 374)
NOSE_TIP = 1

#: Number of features in :meth:`Observation.feature_vector`.
FEATURE_DIM = 4


@dataclass(frozen=True, eq=False)
class Observation:
    """Everything derived from one video frame."""

    t: float
    ear_left: float
    ear_right: float
    #: Horizontal iris position within the eye, averaged over both eyes (0..1, image x).
    gaze_x: float
    #: Vertical iris position between the lids, averaged over both eyes (0..1).
    gaze_y: float
    #: Nose-tip position in the frame (0..1); lets calibration absorb head movement.
    head_x: float
    head_y: float
    #: Landmarks in pixel coordinates, kept only for the optional preview window.
    points: FloatArray | None = None

    @property
    def ear(self) -> float:
        return (self.ear_left + self.ear_right) / 2.0

    def feature_vector(self) -> FloatArray:
        return np.array([self.gaze_x, self.gaze_y, self.head_x, self.head_y], dtype=np.float64)


def eye_aspect_ratio(points: FloatArray, idx: Sequence[int]) -> float:
    """Eye Aspect Ratio: ~0.25-0.35 when open, drops toward 0 when closed."""
    p1, p2, p3, p4, p5, p6 = (points[i] for i in idx)
    horizontal = float(np.linalg.norm(p1 - p4))
    if horizontal < 1e-9:
        return 0.0
    vertical = float(np.linalg.norm(p2 - p6) + np.linalg.norm(p3 - p5))
    return vertical / (2.0 * horizontal)


def iris_ratios(
    points: FloatArray,
    iris: int,
    corners: tuple[int, int],
    lids: tuple[int, int],
) -> tuple[float, float]:
    """Iris centre expressed in the eye's own coordinate frame.

    Projecting onto the corner-to-corner axis (and the lid-to-lid axis) keeps the values
    stable when the head rolls. Results are clipped to a sane range because a half-closed
    eye can push the vertical ratio far outside [0, 1].
    """
    centre = points[iris]
    a, b = points[corners[0]], points[corners[1]]
    axis = b - a
    axis_len2 = float(axis @ axis)
    x_ratio = float((centre - a) @ axis) / axis_len2 if axis_len2 > 1e-9 else 0.5

    upper, lower = points[lids[0]], points[lids[1]]
    vaxis = lower - upper
    vaxis_len2 = float(vaxis @ vaxis)
    y_ratio = float((centre - upper) @ vaxis) / vaxis_len2 if vaxis_len2 > 1e-9 else 0.5
    return float(np.clip(x_ratio, -0.5, 1.5)), float(np.clip(y_ratio, -0.5, 1.5))


def extract_observation(
    landmarks: npt.ArrayLike, frame_w: int, frame_h: int, t: float, keep_points: bool = False
) -> Observation:
    """Compute an :class:`Observation` from normalised landmarks of a single face."""
    lm = np.asarray(landmarks, dtype=np.float64)
    if lm.ndim != 2 or lm.shape[1] < 2 or lm.shape[0] < NUM_LANDMARKS_WITH_IRIS:
        raise ValueError(
            f"expected at least {NUM_LANDMARKS_WITH_IRIS} landmarks with iris refinement, "
            f"got array of shape {lm.shape}"
        )
    pts = lm[:, :2] * np.array([frame_w, frame_h], dtype=np.float64)

    ear_right = eye_aspect_ratio(pts, RIGHT_EYE_EAR)
    ear_left = eye_aspect_ratio(pts, LEFT_EYE_EAR)
    rx, ry = iris_ratios(pts, RIGHT_IRIS_CENTER, RIGHT_EYE_CORNERS, RIGHT_EYE_LIDS)
    lx, ly = iris_ratios(pts, LEFT_IRIS_CENTER, LEFT_EYE_CORNERS, LEFT_EYE_LIDS)
    return Observation(
        t=t,
        ear_left=ear_left,
        ear_right=ear_right,
        gaze_x=(rx + lx) / 2.0,
        gaze_y=(ry + ly) / 2.0,
        head_x=float(lm[NOSE_TIP, 0]),
        head_y=float(lm[NOSE_TIP, 1]),
        points=pts if keep_points else None,
    )
