"""Exception hierarchy for EyeMouse.

Every error that the user can reasonably fix derives from :class:`EyeMouseError`, so the
command line interface can print a short, actionable message instead of a traceback.
"""

from __future__ import annotations


class EyeMouseError(Exception):
    """Base class for all expected, user-facing errors."""


class ConfigError(EyeMouseError, ValueError):
    """Invalid or unreadable configuration."""


class MissingDependencyError(EyeMouseError):
    """An optional dependency is not installed."""

    def __init__(self, package: str, extra: str) -> None:
        super().__init__(
            f"The '{package}' package is required for this feature. "
            f'Install it with:  pip install "eyemouse[{extra}]"  '
            f'(or, from a source checkout:  pip install -e ".[{extra}]")'
        )
        self.package = package
        self.extra = extra


class CameraError(EyeMouseError):
    """The camera could not be opened or stopped delivering frames."""


class ModelError(EyeMouseError):
    """The face landmark model is missing, corrupt or could not be downloaded."""


class CalibrationError(EyeMouseError):
    """Calibration failed (not enough data, or the fitted model is unusable)."""


class CalibrationAborted(EyeMouseError):
    """The user cancelled calibration."""
