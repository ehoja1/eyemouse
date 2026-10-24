from __future__ import annotations

import json

import numpy as np
import pytest

from eyemouse.calibration import (
    MIN_SCALE,
    NUM_TERMS,
    GazeModel,
    SampleCollector,
    calibration_targets,
)
from eyemouse.errors import CalibrationError

SCREEN = (1920, 1080)


def true_mapping(features: np.ndarray) -> np.ndarray:
    """A made-up but plausible ground truth: looking right => iris moves image-left."""
    gx, gy = features[:, 0], features[:, 1]
    return np.column_stack([960 - (gx - 0.5) * 5000, 540 + (gy - 0.5) * 4000])


def make_dataset(n=16, gaze_noise=0.0, seed=0):
    rng = np.random.default_rng(seed)
    gx = rng.uniform(0.38, 0.62, n)
    gy = rng.uniform(0.40, 0.60, n)
    head = 0.5 + rng.normal(0.0, 0.001, (n, 2))
    features = np.column_stack([gx, gy, head])
    targets = true_mapping(features)
    noisy = features.copy()
    noisy[:, :2] += rng.normal(0.0, gaze_noise, (n, 2))
    return noisy, targets


# --------------------------------------------------------------------- targets
def test_targets_form_a_grid_inside_the_margins():
    pts = calibration_targets(1920, 1080, grid=4, margin=0.1)
    assert len(pts) == 16
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    assert min(xs) == round(1920 * 0.1) and max(xs) == round(1920 * 0.9)
    assert min(ys) == round(1080 * 0.1) and max(ys) == round(1080 * 0.9)
    assert len(set(pts)) == 16


def test_targets_snake_so_consecutive_points_are_close():
    pts = calibration_targets(1920, 1080, grid=3, margin=0.1)
    assert pts[2][0] == pts[3][0]  # end of row 0 and start of row 1 share x
    assert pts[3][0] > pts[5][0]  # row 1 runs right-to-left


# --------------------------------------------------------------------- fitting
def test_fit_recovers_a_noise_free_mapping():
    feats, targets = make_dataset(n=16)
    model = GazeModel.fit(feats, targets, SCREEN)
    test_feats, test_targets = make_dataset(n=50, seed=7)
    errors = [
        np.hypot(*(np.array(model.predict(f)) - t))
        for f, t in zip(test_feats, test_targets, strict=True)
    ]
    assert max(errors) < 15.0
    assert model.rmse_px < 10.0


def test_noisy_data_gives_plausible_error_estimates():
    feats, targets = make_dataset(n=16, gaze_noise=0.004, seed=3)
    model = GazeModel.fit(feats, targets, SCREEN)
    assert 0.0 < model.rmse_px < model.loo_rmse_px  # leave-one-out is the honest, larger number
    assert model.loo_rmse_px < 120.0
    assert 0.0 < model.quality_fraction < 0.1


def test_head_features_that_barely_varied_cannot_blow_up_predictions():
    feats, targets = make_dataset(n=16, gaze_noise=0.003, seed=5)
    model = GazeModel.fit(feats, targets, SCREEN)
    base = np.array([0.5, 0.5, 0.5, 0.5])
    moved = base.copy()
    moved[2:] += 0.10  # the user leans a lot more than during calibration
    shift = np.hypot(*(np.array(model.predict(moved)) - np.array(model.predict(base))))
    assert shift < 400.0


def test_extreme_inputs_stay_finite_and_bounded():
    feats, targets = make_dataset()
    model = GazeModel.fit(feats, targets, SCREEN)
    x, y = model.predict([50.0, -50.0, 9.0, -9.0])
    assert np.isfinite(x) and np.isfinite(y)
    assert abs(x) < 1e5 and abs(y) < 1e5


def test_too_few_points_are_rejected():
    feats, targets = make_dataset(n=5)
    with pytest.raises(CalibrationError, match="at least 6"):
        GazeModel.fit(feats, targets, SCREEN)


def test_nan_data_is_rejected():
    feats, targets = make_dataset()
    feats[3, 0] = np.nan
    with pytest.raises(CalibrationError, match="NaN"):
        GazeModel.fit(feats, targets, SCREEN)


def test_wrong_shapes_are_rejected():
    with pytest.raises(CalibrationError, match="shape"):
        GazeModel.fit(np.zeros((10, 3)), np.zeros((10, 2)), SCREEN)


# ----------------------------------------------------------------- persistence
def test_save_and_load_roundtrip(tmp_path):
    feats, targets = make_dataset()
    model = GazeModel.fit(feats, targets, SCREEN)
    path = tmp_path / "sub" / "cal.json"
    model.save(path)
    loaded = GazeModel.load(path)
    probe = [0.45, 0.55, 0.5, 0.5]
    assert loaded.predict(probe) == pytest.approx(model.predict(probe))
    assert loaded.screen == SCREEN
    assert not list(path.parent.glob("*.tmp"))  # atomic write leaves no temp file


def test_loading_a_missing_file_fails_cleanly(tmp_path):
    with pytest.raises(CalibrationError, match="not found"):
        GazeModel.load(tmp_path / "nope.json")


def test_loading_garbage_fails_cleanly(tmp_path):
    path = tmp_path / "bad.json"
    path.write_text("{not json", encoding="utf-8")
    with pytest.raises(CalibrationError):
        GazeModel.load(path)


def test_loading_wrong_version_or_shape_fails_cleanly(tmp_path):
    feats, targets = make_dataset()
    data = GazeModel.fit(feats, targets, SCREEN).to_dict()
    for broken in ({**data, "format": 99}, {**data, "weights": [[1.0, 2.0]]}):
        path = tmp_path / "x.json"
        path.write_text(json.dumps(broken), encoding="utf-8")
        with pytest.raises(CalibrationError):
            GazeModel.load(path)
    path.write_text(json.dumps([1, 2, 3]), encoding="utf-8")
    with pytest.raises(CalibrationError):
        GazeModel.load(path)


def test_model_has_expected_number_of_terms():
    feats, targets = make_dataset()
    assert GazeModel.fit(feats, targets, SCREEN).weights.shape == (NUM_TERMS, 2)


# ------------------------------------------------------------- sample collector
def test_collector_needs_enough_samples():
    c = SampleCollector(min_samples=10)
    for _ in range(9):
        c.add(np.array([0.5, 0.5, 0.5, 0.5]))
    assert c.result() is None
    c.add(np.array([0.5, 0.5, 0.5, 0.5]))
    assert c.result() is not None


def test_collector_rejects_outliers():
    rng = np.random.default_rng(2)
    c = SampleCollector(min_samples=10)
    for _ in range(30):
        c.add(0.5 + rng.normal(0.0, 0.002, 4))
    for _ in range(3):
        c.add(np.array([0.9, 0.1, 0.5, 0.5]))  # glance away / tracking glitch
    result = c.result()
    assert result is not None
    assert result.tolist() == pytest.approx([0.5] * 4, abs=0.01)


def test_scale_of_nearly_constant_features_is_floored():
    feats, targets = make_dataset(n=16)
    model = GazeModel.fit(feats, targets, SCREEN)
    assert (model.scale >= MIN_SCALE).all()
    assert model.scale[2] == MIN_SCALE and model.scale[3] == MIN_SCALE  # head barely moved
