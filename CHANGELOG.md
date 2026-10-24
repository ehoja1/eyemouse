# Changelog

Format based on [Keep a Changelog](https://keepachangelog.com/); versioning follows [SemVer](https://semver.org/).

## [0.1.0] - 2026-10-24

### Added
- Cursor control from iris position using MediaPipe Face Landmarker (478 landmarks).
- Triple-blink click with adaptive per-user threshold, hysteresis and refractory period.
- Gaze is frozen while the eyes close, so the click lands where you were looking.
- 16-point polynomial calibration with leave-one-out accuracy estimate; saved per user.
- One Euro filter smoothing, dead zone and screen clamping.
- Long eye closure (2 s) toggles pause; moving the physical mouse pauses automatically.
- `eyemouse run | calibrate | doctor`, `--dry-run`, `--preview`, TOML configuration.
- Test suite, strict typing, CI on Windows / macOS / Linux.
