from __future__ import annotations

from eyemouse.cursor import DryRunBackend, HardwareMouseWatcher


def test_dry_run_backend_tracks_a_virtual_cursor_and_records_clicks():
    backend = DryRunBackend((1280, 720))
    assert backend.screen_size() == (1280, 720)
    assert backend.position() == (640, 360)
    backend.move_to(100, 200)
    backend.click("right")
    assert backend.position() == (100, 200)
    assert backend.clicks == [(100, 200, "right")]


def test_watcher_ignores_everything_before_the_first_command():
    assert not HardwareMouseWatcher(50).hijacked((999, 999))


def test_watcher_tolerates_small_differences():
    watcher = HardwareMouseWatcher(50)
    watcher.commanded(500, 500)
    assert not watcher.hijacked((510, 505))


def test_watcher_detects_a_real_mouse_movement():
    watcher = HardwareMouseWatcher(50)
    watcher.commanded(500, 500)
    assert watcher.hijacked((700, 500))


def test_watcher_reset_forgets_the_last_command():
    watcher = HardwareMouseWatcher(50)
    watcher.commanded(500, 500)
    watcher.reset()
    assert not watcher.hijacked((900, 900))
