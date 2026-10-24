# Architecture

```
camera ─▶ tracker ─▶ features ─▶ pipeline ─▶ cursor
(OpenCV)  (MediaPipe) (pure)      (pure)      (pyautogui)
                         │           ▲
                         ▼           │
                      blink ─────────┘      calibration (pure) ◀─ calibration_ui
```

| Module | Role | Hardware? |
|---|---|---|
| `camera` | Threaded capture; always returns the newest frame | yes |
| `tracker` | MediaPipe Face Landmarker → landmarks | yes |
| `features` | Landmarks → EAR (eye openness), iris ratios, head position | no |
| `blink` | State machine: triple blink = click, long close = pause | no |
| `calibration` | Ridge polynomial regression features → screen pixels | no |
| `pipeline` | Observation → actions (Move/Click/TogglePause); smoothing, freeze, click placement | no |
| `cursor` | `pyautogui` or `DryRunBackend`; hardware-mouse watcher | yes |
| `app` | Main loop wiring, driven by protocols (fully testable) | no |
| `calibration_ui`, `preview`, `doctor`, `cli` | User interface | partly |

## Key design decisions
1. **Adaptive blink threshold.** EAR is compared to a per-session baseline (ratio), so it works across eye shapes, cameras and lighting. Hysteresis avoids flicker.
2. **Freeze before the click.** Iris landmarks are unreliable while lids move. The cursor holds as EAR starts dropping, stays held 150 ms after reopening, and the click uses the position from `click_lookback_s` before the first blink began.
3. **Gaze in the eye's own frame.** The iris is projected onto the corner-to-corner axis, which is stable under head roll. The nose position is a calibration feature, which absorbs small head translation.
4. **Honest accuracy.** Calibration reports leave-one-out error, not the flattering training error.
5. **Bounded extrapolation.** Features have a minimum scale and are clipped, so unusual poses cannot throw the cursor across the screen.
6. **Safety first.** Pause gesture, hardware-mouse yielding, no pyautogui corner fail-safe surprises, and `--dry-run`.
7. **Testability.** All logic depends on small protocols; tests use synthetic signals (see `tests/helpers.py`).

## Extending
- Different click gesture: edit `blink.py` (`_on_blink_finished`) and config.
- Another cursor backend (e.g. Wayland): implement the `CursorBackend` protocol in `cursor.py`.
