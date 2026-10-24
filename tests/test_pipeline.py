from __future__ import annotations

import pytest

from eyemouse.config import Config
from eyemouse.pipeline import Click, GazePipeline, Move, TogglePause
from helpers import TRIPLE, PixelModel, scenario

SCREEN = (1920, 1080)


def make_pipeline(cfg: Config | None = None) -> GazePipeline:
    return GazePipeline(PixelModel(), SCREEN, cfg or Config())  # type: ignore[arg-type]


def run(pipeline: GazePipeline, frames):
    actions = []
    for t, obs in frames:
        actions += pipeline.step(obs, t)
    return actions


def of_type(actions, kind):
    return [a for a in actions if isinstance(a, kind)]


def test_cursor_goes_to_where_the_user_looks():
    actions = run(make_pipeline(), scenario([], tail=1.0))
    moves = of_type(actions, Move)
    assert moves and (moves[-1].x, moves[-1].y) == (800, 400)


def test_triple_blink_clicks_where_the_user_was_looking():
    actions = run(make_pipeline(), scenario(TRIPLE))
    clicks = of_type(actions, Click)
    assert clicks == [Click(800, 400, "left")]


def test_garbage_gaze_during_blinks_never_moves_the_cursor():
    actions = run(make_pipeline(), scenario(TRIPLE))
    for move in of_type(actions, Move):
        assert move.x > 700 and move.y > 300  # never dragged toward the (10, 10) garbage


def test_click_lands_on_the_pre_blink_target_even_if_gaze_drifts_just_before():
    # Gaze leaves A for B only 0.1 s before the first blink; the click should still hit A.
    t_blink = 2.0

    def drifting(t: float) -> tuple[float, float]:
        return (800.0, 400.0) if t < t_blink - 0.1 else (1500.0, 800.0)

    actions = run(make_pipeline(), scenario(TRIPLE, gaze_fn=drifting))
    assert of_type(actions, Click) == [Click(800, 400, "left")]


def test_click_button_is_configurable():
    cfg = Config()
    cfg.cursor.button = "right"
    actions = run(make_pipeline(cfg), scenario(TRIPLE))
    assert of_type(actions, Click) == [Click(800, 400, "right")]


def test_cursor_is_clamped_to_the_screen():
    frames = scenario([], gaze_fn=lambda t: (5000.0, -300.0))
    moves = of_type(run(make_pipeline(), frames), Move)
    assert all(0 <= m.x <= SCREEN[0] - 1 and 0 <= m.y <= SCREEN[1] - 1 for m in moves)
    assert (moves[-1].x, moves[-1].y) == (SCREEN[0] - 1, 0)


def test_small_jitter_is_suppressed_by_the_deadzone():
    frames = scenario([], gaze_fn=lambda t: (800.0 + 2.0 * ((int(t * 30) % 2) - 0.5), 400.0))
    moves = of_type(run(make_pipeline(), frames), Move)
    assert len({(m.x, m.y) for m in moves}) == 1


def test_no_face_means_no_actions():
    pipeline = make_pipeline()
    assert pipeline.step(None, 0.0) == []


def test_long_closure_pauses_and_resumes():
    pipeline = make_pipeline()
    frames = scenario(
        [(0.0, 2.6), (4.0, 2.6)],
        gaze_fn=lambda t: (800.0, 400.0) if t < 5.0 else (1200.0, 700.0),
        tail=2.0,
    )
    actions = run(pipeline, frames)
    toggles = of_type(actions, TogglePause)
    assert toggles == [TogglePause(True), TogglePause(False)]
    moves_after_resume = [m for m in of_type(actions, Move) if m.x > 1000]
    assert moves_after_resume  # control really came back


def test_nothing_moves_or_clicks_while_paused():
    pipeline = make_pipeline()
    frames = scenario(
        [(0.0, 2.6), *[(4.0 + s, d) for s, d in TRIPLE]],
        gaze_fn=lambda t: (800.0, 400.0) if t < 5.0 else (1200.0, 700.0),
    )
    actions = run(pipeline, frames)
    assert of_type(actions, TogglePause) == [TogglePause(True)]
    assert of_type(actions, Click) == []
    assert not [m for m in of_type(actions, Move) if m.x > 1000]


def test_clicks_are_suppressed_while_externally_paused():
    pipeline = make_pipeline()
    pipeline.set_paused(True)
    assert run(pipeline, scenario(TRIPLE)) == []


@pytest.mark.parametrize("blinks", [1, 2])
def test_fewer_than_three_blinks_never_click(blinks):
    actions = run(make_pipeline(), scenario(TRIPLE[:blinks]))
    assert of_type(actions, Click) == []
