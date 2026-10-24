from __future__ import annotations

from itertools import pairwise

import numpy as np
import pytest

from eyemouse.filters import OneEuroFilter, Point2DFilter


def test_constant_signal_passes_through_unchanged():
    f = OneEuroFilter(min_cutoff=1.0, beta=0.01)
    outputs = [f(i / 30, 500.0) for i in range(60)]
    assert outputs == pytest.approx([500.0] * 60)


def test_first_sample_is_returned_as_is():
    assert OneEuroFilter()(0.0, 123.0) == 123.0


def test_step_response_converges_without_overshoot():
    f = OneEuroFilter(min_cutoff=1.0, beta=0.0)
    f(0.0, 0.0)
    values = [f(i / 30, 100.0) for i in range(1, 150)]
    assert all(b >= a for a, b in pairwise(values))
    assert max(values) <= 100.0 + 1e-9
    assert values[-1] == pytest.approx(100.0, abs=1.0)


def test_jitter_is_reduced_at_rest():
    rng = np.random.default_rng(1)
    raw = 400.0 + rng.normal(0.0, 8.0, 300)
    f = OneEuroFilter(min_cutoff=1.0, beta=0.01)
    out = np.array([f(i / 30, x) for i, x in enumerate(raw)])
    assert out[30:].std() < 0.5 * raw[30:].std()


def test_higher_beta_reduces_lag_during_fast_motion():
    ramp = [(i / 30, 3000.0 * i / 30) for i in range(60)]  # 3000 px/s sweep

    def final_lag(beta: float) -> float:
        f = OneEuroFilter(min_cutoff=1.0, beta=beta)
        last = 0.0
        for t, x in ramp:
            last = f(t, x)
        return ramp[-1][1] - last

    assert final_lag(beta=0.05) < final_lag(beta=0.0)


def test_non_increasing_time_returns_previous_output():
    f = OneEuroFilter()
    f(1.0, 10.0)
    first = f(1.1, 20.0)
    assert f(1.1, 999.0) == first


def test_reset_forgets_history():
    f = OneEuroFilter()
    f(0.0, 5.0)
    f(0.1, 50.0)
    f.reset()
    assert f(0.2, 7.0) == 7.0


def test_invalid_cutoffs_are_rejected():
    with pytest.raises(ValueError):
        OneEuroFilter(min_cutoff=0.0)


def test_point_filter_handles_axes_independently():
    f = Point2DFilter()
    assert f(0.0, 10.0, 20.0) == (10.0, 20.0)
    x, y = f(0.1, 10.0, 220.0)
    assert x == pytest.approx(10.0)
    assert y > 20.0
