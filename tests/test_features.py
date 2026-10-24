from __future__ import annotations

import numpy as np
import pytest

from eyemouse.features import extract_observation
from helpers import landmarks


def obs_for(pts, w=640, h=480):
    return extract_observation(pts, w, h, t=1.0)


def test_open_eye_has_expected_ear():
    obs = obs_for(landmarks(open_h=0.012))
    assert obs.ear_left == pytest.approx(0.30, abs=0.01)
    assert obs.ear_right == pytest.approx(0.30, abs=0.01)


def test_closed_eye_has_low_ear():
    assert obs_for(landmarks(open_h=0.002)).ear < 0.07


def test_ear_uses_pixel_geometry_not_normalised_geometry():
    # The same face in a wide frame is not squashed into a different EAR.
    square = extract_observation(landmarks(), 600, 600, 0.0).ear
    wide = extract_observation(landmarks(), 600, 300, 0.0).ear
    assert wide == pytest.approx(square / 2.0, rel=0.01)


def test_centred_iris_is_half_way():
    obs = obs_for(landmarks())
    assert obs.gaze_x == pytest.approx(0.5, abs=0.01)
    assert obs.gaze_y == pytest.approx(0.5, abs=0.01)


def test_iris_moving_right_in_the_image_increases_gaze_x():
    centre = obs_for(landmarks()).gaze_x
    right = obs_for(landmarks(iris_dx=0.015)).gaze_x
    left = obs_for(landmarks(iris_dx=-0.015)).gaze_x
    assert right == pytest.approx(centre + 0.25, abs=0.02)
    assert left == pytest.approx(centre - 0.25, abs=0.02)


def test_iris_moving_down_increases_gaze_y():
    obs = obs_for(landmarks(iris_dy=0.006))
    assert obs.gaze_y == pytest.approx(0.75, abs=0.02)


def test_gaze_ratio_is_invariant_to_head_roll():
    pts = landmarks(iris_dx=0.012, iris_dy=-0.004)
    angle = np.deg2rad(12.0)
    rot = np.array([[np.cos(angle), -np.sin(angle)], [np.sin(angle), np.cos(angle)]])
    rotated = (pts - 0.5) @ rot.T + 0.5
    base = extract_observation(pts, 1000, 1000, 0.0)
    tilted = extract_observation(rotated, 1000, 1000, 0.0)
    assert tilted.gaze_x == pytest.approx(base.gaze_x, abs=0.01)
    assert tilted.gaze_y == pytest.approx(base.gaze_y, abs=0.01)
    assert tilted.ear == pytest.approx(base.ear, abs=0.01)


def test_head_position_is_the_nose_tip():
    pts = landmarks()
    pts[1] = (0.62, 0.41)
    obs = obs_for(pts)
    assert (obs.head_x, obs.head_y) == pytest.approx((0.62, 0.41))


def test_feature_vector_layout():
    obs = obs_for(landmarks())
    assert obs.feature_vector().shape == (4,)
    assert obs.feature_vector()[0] == obs.gaze_x


def test_half_closed_eye_ratios_stay_bounded():
    obs = obs_for(landmarks(open_h=0.0005, iris_dy=0.01))
    assert -0.5 <= obs.gaze_y <= 1.5


def test_points_are_only_kept_on_request():
    assert obs_for(landmarks()).points is None
    kept = extract_observation(landmarks(), 640, 480, 0.0, keep_points=True)
    assert kept.points is not None and kept.points.shape == (478, 2)


def test_landmarks_without_iris_are_rejected():
    with pytest.raises(ValueError, match="478"):
        extract_observation(landmarks()[:468], 640, 480, 0.0)
