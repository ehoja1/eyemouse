# EyeMouse

[![CI](https://github.com/ehoja1/eyemouse/actions/workflows/ci.yml/badge.svg)](https://github.com/ehoja1/eyemouse/actions/workflows/ci.yml)
![Python](https://img.shields.io/badge/python-3.10%E2%80%933.13-blue)
![License](https://img.shields.io/badge/license-MIT-green)

**Hands-free mouse control with a plain webcam.** Move the cursor with your eyes; click with **three quick blinks**.

🇧🇷 [Leia em português](docs/pt-BR/README.md)

## Features
- Gaze-driven cursor using MediaPipe iris tracking; no special hardware.
- **Triple-blink click** with an adaptive, per-user threshold. Winks, single blinks, and deliberate long closures never click.
- **Click accuracy:** the cursor freezes as your eyes start to close, and the click lands where you were looking *before* the blinks.
- Quick calibration (16 points, ~25 s) with an accuracy estimate; saved per user.
- Smooth, jitter-free movement (One Euro filter); screen-edge clamping.
- Safety: close both eyes for 2 s to **pause/resume**; moving the physical mouse pauses automatically.
- `--dry-run` mode, live `--preview`, `eyemouse doctor` diagnostics, fully configurable via TOML.
- Private: video stays on your machine and is never stored or uploaded.

## Quick start
```bash
git clone https://github.com/ehoja1/eyemouse.git && cd eyemouse
python -m venv .venv
source .venv/bin/activate            # Windows: .venv\Scripts\activate
pip install -e ".[all]"
eyemouse doctor --fetch-model        # checks everything, downloads the face model once
eyemouse run --preview               # calibrates the first time, then starts
```
Try it safely first with `eyemouse run --dry-run --preview` (the real mouse does not move).

## How to use
| Gesture | Action |
|---|---|
| Look at something | Cursor follows your gaze |
| Blink 3× quickly (within ~1.5 s) | Left click where you were looking |
| Close both eyes ≈ 2 s | Pause / resume eye control |
| `p` / `q` in the preview window | Pause / quit |
| Ctrl+C in the terminal | Quit |

Commands: `eyemouse run`, `eyemouse calibrate`, `eyemouse doctor`. See `eyemouse --help` and [`config.example.toml`](config.example.toml).

## Requirements
- Python 3.10+, a webcam, Windows 10/11, macOS, or Linux **with an X11 session** (Wayland blocks synthetic mouse control).
- Good, even lighting on your face; sit about 40–70 cm from the screen.
- macOS: allow camera access *and* Accessibility control for your terminal / VS Code.

## Limitations (please read)
Webcam gaze tracking is **approximate**: expect roughly 1–3 cm of accuracy on screen, best for large targets, accessibility use and hands-free navigation, not pixel-precise work. Glasses glare, backlighting and head movement reduce accuracy; recalibrate when you change position. This is not a medical device.

## Documentation
[Detailed guide (PT-BR)](docs/pt-BR/GUIA.md) · [Architecture](docs/ARCHITECTURE.md) · [Troubleshooting](docs/TROUBLESHOOTING.md) · [Contributing](CONTRIBUTING.md) · [Security & privacy](SECURITY.md)

## License
MIT. The MediaPipe Face Landmarker model is downloaded separately from Google under its own terms.
