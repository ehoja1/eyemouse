"""Command line interface: ``eyemouse [run|calibrate|doctor]``."""

from __future__ import annotations

import argparse
import dataclasses
import logging
import sys
from collections.abc import Sequence

from . import __version__
from .config import Config, load_config
from .errors import CalibrationAborted, EyeMouseError
from .logging_setup import setup_logging

log = logging.getLogger("eyemouse")

COMMANDS = ("run", "calibrate", "doctor")


def build_parser() -> argparse.ArgumentParser:
    common = argparse.ArgumentParser(add_help=False)
    common.add_argument("--config", metavar="FILE", help="TOML configuration file")
    common.add_argument("-v", "--verbose", action="count", default=0, help="debug logging")
    common.add_argument("--log-file", metavar="FILE", help="also write logs to this file")
    common.add_argument("--camera", type=int, metavar="N", help="camera index (default 0)")

    parser = argparse.ArgumentParser(
        prog="eyemouse",
        description="Move the mouse with your eyes; click with three quick blinks.",
        epilog="Without a command, 'run' is assumed.",
    )
    parser.add_argument("--version", action="version", version=f"eyemouse {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="{run,calibrate,doctor}")

    run = sub.add_parser("run", parents=[common], help="start eye control (default)")
    run.add_argument("--preview", action="store_true", help="show the camera preview window")
    run.add_argument(
        "--dry-run", action="store_true", help="never move the real mouse; log actions instead"
    )
    run.add_argument("--recalibrate", action="store_true", help="ignore the saved calibration")

    sub.add_parser("calibrate", parents=[common], help="(re)run the calibration and save it")

    doctor = sub.add_parser("doctor", parents=[common], help="diagnose the installation")
    doctor.add_argument("--fetch-model", action="store_true", help="download the face model now")
    doctor.add_argument("--skip-camera", action="store_true", help="do not open the camera")
    return parser


def _apply_overrides(cfg: Config, args: argparse.Namespace) -> Config:
    if getattr(args, "camera", None) is not None:
        cfg = dataclasses.replace(cfg, camera=dataclasses.replace(cfg.camera, index=args.camera))
    if getattr(args, "preview", False):
        cfg = dataclasses.replace(cfg, ui=dataclasses.replace(cfg.ui, preview=True))
    cfg.validate()
    return cfg


def main(argv: Sequence[str] | None = None) -> int:
    args_list = list(sys.argv[1:] if argv is None else argv)
    if not args_list or (
        args_list[0].startswith("-") and args_list[0] not in ("-h", "--help", "--version")
    ):
        args_list.insert(0, "run")  # bare `eyemouse` or `eyemouse --preview` means "run"

    parser = build_parser()
    args = parser.parse_args(args_list)
    setup_logging(args.verbose, args.log_file)

    try:
        cfg = _apply_overrides(load_config(args.config), args)
        if args.command == "calibrate":
            from .app import calibrate_only

            return calibrate_only(cfg)
        if args.command == "doctor":
            from .doctor import run_doctor

            return run_doctor(cfg, fetch_model=args.fetch_model, check_camera=not args.skip_camera)

        from .app import run

        return run(cfg, dry_run=args.dry_run, recalibrate=args.recalibrate)
    except CalibrationAborted as exc:
        print(str(exc), file=sys.stderr)
        return 1
    except EyeMouseError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except KeyboardInterrupt:
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
