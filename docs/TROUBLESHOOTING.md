# Troubleshooting

Always start with `eyemouse doctor`.

| Problem | Fix |
|---|---|
| `Could not open camera 0` | Close Zoom/Teams/browser tabs using the camera; try `--camera 1`; check OS camera privacy settings. |
| macOS: black frames or no permission | System Settings → Privacy & Security → **Camera** and **Accessibility**: enable your terminal / VS Code, then restart it. |
| Cursor does not move (Linux) | Wayland is not supported for mouse control. Log in with an *X11/Xorg* session. |
| Could not download the model | Download the file from the URL printed in the error, save it as the path shown (or set `tracking.model_path`). |
| Cursor is jittery | Lower `cursor.min_cutoff` (e.g. 0.6) or raise `cursor.deadzone_px`. Improve lighting. |
| Cursor lags | Raise `cursor.beta` (e.g. 0.03) and `cursor.min_cutoff`. |
| Accuracy is poor | Recalibrate (`eyemouse run --recalibrate`): better front light, no window behind you, head still, look at each dot until it vanishes. Camera at eye level, centred on the screen. |
| Clicks never trigger | Run with `--preview` and watch the EAR values. Blink a little firmer and faster; raise `blink.close_ratio` to 0.75 or `blink.max_gap_s` to 0.6. |
| Accidental clicks | Lower `blink.close_ratio` (0.65) or `blink.max_sequence_s` (1.5). |
| Glasses cause problems | Reduce screen glare on the lenses; tilt the camera slightly; recalibrate while wearing them. |
| Everything is paused | You closed your eyes ≥ 2 s or moved the real mouse. Close your eyes 2 s again (or press `p` in the preview). |
| Calibration says "poor" | Repeat it; if still poor, check lighting and camera position. |

Logs: `eyemouse run -v --log-file eyemouse.log`.
