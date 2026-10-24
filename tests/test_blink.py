from __future__ import annotations

import pytest

from eyemouse.blink import BlinkDetector
from eyemouse.config import BlinkConfig
from helpers import CLOSED_EAR, FPS, OPEN_EAR, TRIPLE, drive, ear_series


def clicks(events):
    return [e for e in events if e.kind == "click"]


def pauses(events):
    return [e for e in events if e.kind == "toggle_pause"]


def test_three_quick_blinks_make_one_click():
    events = drive(BlinkDetector(BlinkConfig()), ear_series(TRIPLE))
    assert len(clicks(events)) == 1
    assert not pauses(events)


def test_click_reference_time_is_start_of_first_blink():
    events = drive(BlinkDetector(BlinkConfig()), ear_series(TRIPLE, lead=2.0))
    assert 2.0 <= clicks(events)[0].t_ref <= 2.1


def test_two_blinks_do_nothing():
    events = drive(BlinkDetector(BlinkConfig()), ear_series(TRIPLE[:2]))
    assert events == []


def test_slow_blinks_do_nothing():
    slow = [(0.0, 0.12), (1.0, 0.12), (2.0, 0.12)]  # gaps far above max_gap_s
    assert drive(BlinkDetector(BlinkConfig()), ear_series(slow)) == []


def test_sequence_too_long_does_nothing():
    cfg = BlinkConfig(max_sequence_s=0.6)
    assert drive(BlinkDetector(cfg), ear_series(TRIPLE)) == []


def test_double_blink_can_be_configured():
    cfg = BlinkConfig(required_blinks=2)
    events = drive(BlinkDetector(cfg), ear_series(TRIPLE[:2]))
    assert len(clicks(events)) == 1


def test_extra_blinks_after_a_click_do_not_click_again():
    # An immediate second triple blink lands inside / right after the refractory period.
    twice = [*TRIPLE, (1.0, 0.12), (1.3, 0.12), (1.6, 0.12)]
    events = drive(BlinkDetector(BlinkConfig()), ear_series(twice))
    assert len(clicks(events)) == 1


def test_a_later_triple_blink_clicks_again():
    twice = [*TRIPLE, (3.0, 0.12), (3.3, 0.12), (3.6, 0.12)]
    events = drive(BlinkDetector(BlinkConfig()), ear_series(twice))
    assert len(clicks(events)) == 2


def test_deliberate_long_closure_breaks_the_sequence():
    series = ear_series([(0.0, 0.12), (0.3, 0.12), (0.6, 0.6), (1.5, 0.12)])
    assert drive(BlinkDetector(BlinkConfig()), series) == []


def test_long_closure_toggles_pause_without_clicking():
    events = drive(BlinkDetector(BlinkConfig()), ear_series([(0.0, 2.6)]))
    assert [e.kind for e in events] == ["toggle_pause"]


def test_long_closure_gesture_can_be_disabled():
    cfg = BlinkConfig(long_close_s=0.0)
    assert drive(BlinkDetector(cfg), ear_series([(0.0, 3.0)])) == []


def test_winking_one_eye_does_not_count():
    detector = BlinkDetector(BlinkConfig())
    events = []
    for t, ear in ear_series(TRIPLE):
        right = ear if ear == OPEN_EAR else OPEN_EAR  # right eye never closes
        events += detector.update(t, ear, right)
    assert events == []


def test_single_frame_sensor_glitches_are_ignored():
    # At 100 fps a 10 ms dip is shorter than min_blink_s: pure noise.
    glitches = [(0.0, 0.01), (0.2, 0.01), (0.4, 0.01)]
    series = ear_series(glitches, fps=100.0)
    assert drive(BlinkDetector(BlinkConfig()), series) == []


@pytest.mark.parametrize("open_ear", [0.18, 0.25, 0.30, 0.40])
def test_threshold_adapts_to_different_eyes(open_ear):
    series = ear_series(TRIPLE, open_ear=open_ear, closed_ear=open_ear * 0.15)
    events = drive(BlinkDetector(BlinkConfig()), series)
    assert len(clicks(events)) == 1


def test_no_events_and_not_ready_during_warmup():
    detector = BlinkDetector(BlinkConfig(warmup_s=1.5))
    assert not detector.ready
    events = []
    for t, ear in ear_series(TRIPLE, lead=0.5)[: int(1.0 * FPS)]:
        events += detector.update(t, ear, ear)
    assert events == []
    assert not detector.ready


def test_baseline_matches_open_eye_level():
    detector = BlinkDetector(BlinkConfig())
    drive(detector, ear_series([], lead=3.0, tail=0.0))
    assert detector.ready
    assert detector.baseline == pytest.approx(OPEN_EAR, abs=0.005)


def test_warmup_restarts_if_eyes_were_shut_at_start():
    detector = BlinkDetector(BlinkConfig())
    series = ear_series([(-2.0, 3.0)], lead=2.0, tail=3.0)  # shut for the first second
    drive(detector, series)
    assert detector.ready
    assert detector.baseline == pytest.approx(OPEN_EAR, abs=0.01)


def test_gaze_is_frozen_while_blinking_and_briefly_after():
    cfg = BlinkConfig()
    detector = BlinkDetector(cfg)
    frozen_during = frozen_settling = frozen_later = None
    for t, ear in ear_series([(0.0, 0.3)], lead=2.0, tail=1.0):
        detector.update(t, ear, ear)
        if abs(t - 2.1) < 1e-6:
            frozen_during = detector.gaze_frozen(t)
        if abs(t - (2.3 + 1 / FPS)) < 1e-6:
            frozen_settling = detector.gaze_frozen(t)
        if abs(t - 2.9) < 1e-6:
            frozen_later = detector.gaze_frozen(t)
    assert frozen_during is True
    assert frozen_settling is True
    assert frozen_later is False


def test_losing_the_face_cancels_a_half_finished_gesture():
    detector = BlinkDetector(BlinkConfig())
    events = []
    for t, ear in ear_series(TRIPLE[:2]):
        events += detector.update(t, ear, ear)
    detector.on_face_lost()
    for t, ear in ear_series([(0.0, 0.12)], lead=0.0, tail=0.0):
        events += detector.update(4.0 + t, ear, ear)  # a third blink after the interruption
    assert clicks(events) == []


def test_closed_ear_constant_is_below_open_threshold():
    cfg = BlinkConfig()
    assert OPEN_EAR * cfg.close_ratio > CLOSED_EAR
