# Contributing

Thanks for helping! The project is designed so that almost everything can be tested **without a camera**.

## Setup
```bash
git clone https://github.com/ehoja1/eyemouse.git && cd eyemouse
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -e ".[all,dev]"
```

## Before opening a pull request
```bash
ruff check . && ruff format --check . && mypy && pytest
```
(In VS Code: *Terminal → Run Build Task* runs lint, types and tests.)

## Architecture rule
Pure logic (`features`, `blink`, `calibration`, `filters`, `pipeline`) must never import OpenCV, MediaPipe or pyautogui. Hardware lives in `camera`, `tracker`, `cursor`, `preview`, `calibration_ui`. See `docs/ARCHITECTURE.md`.

## Tests
- New behaviour needs a test; bug fixes need a test that fails without the fix.
- Use the synthetic signal helpers in `tests/helpers.py` instead of real cameras.

## Commit style
Short imperative subject line (`Fix blink threshold on dark skin tones`), details in the body.
