from __future__ import annotations

import pytest

from eyemouse import __version__
from eyemouse.cli import build_parser, main


def test_version_flag_exits_cleanly():
    with pytest.raises(SystemExit) as info:
        main(["--version"])
    assert info.value.code == 0
    assert __version__


def test_run_options_are_parsed():
    args = build_parser().parse_args(
        ["run", "--preview", "--dry-run", "--recalibrate", "--camera", "2", "-vv"]
    )
    assert (args.command, args.preview, args.dry_run, args.recalibrate) == ("run", True, True, True)
    assert args.camera == 2
    assert args.verbose == 2


def test_doctor_options_are_parsed():
    args = build_parser().parse_args(["doctor", "--fetch-model", "--skip-camera"])
    assert args.command == "doctor" and args.fetch_model and args.skip_camera


def test_bad_config_path_returns_error_code_2_without_touching_hardware(tmp_path):
    missing = str(tmp_path / "missing.toml")
    assert main(["run", "--config", missing]) == 2
    assert main(["--config", missing]) == 2  # bare invocation defaults to "run"
    assert main(["calibrate", "--config", missing]) == 2
    assert main(["doctor", "--config", missing]) == 2


def test_invalid_config_value_returns_error_code_2(tmp_path):
    path = tmp_path / "bad.toml"
    path.write_text("[blink]\nrequired_blinks = 1\n", encoding="utf-8")
    assert main(["run", "--config", str(path)]) == 2
