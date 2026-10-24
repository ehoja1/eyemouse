"""Logging configuration shared by every entry point."""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path

_FORMAT = "%(asctime)s %(levelname)-7s %(name)s: %(message)s"


def setup_logging(verbose: int = 0, log_file: str | Path | None = None) -> None:
    """Configure the root logger.

    ``verbose`` 0 = INFO, 1 or more = DEBUG. A rotating log file is added when requested.
    """
    level = logging.DEBUG if verbose >= 1 else logging.INFO
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if log_file:
        path = Path(log_file)
        path.parent.mkdir(parents=True, exist_ok=True)
        handlers.append(RotatingFileHandler(path, maxBytes=1_000_000, backupCount=3))
    logging.basicConfig(level=level, format=_FORMAT, handlers=handlers, force=True)
