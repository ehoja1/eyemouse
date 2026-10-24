"""Gaze calibration: learn the mapping from eye/head features to screen coordinates.

Webcam gaze estimation cannot rely on a universal formula: every face, camera position and
sitting distance is different. During calibration the user looks at known points on the
screen; we then fit a small ridge-regularised polynomial model

    screen = W^T [1, gx, gy, hx, hy, gx^2, gy^2, gx*gy]

where ``gx, gy`` are iris positions inside the eyes and ``hx, hy`` is the nose position
(so moderate head movement is compensated rather than ignored). Everything here is pure
NumPy and unit-tested; the on-screen UI lives in :mod:`eyemouse.calibration_ui`.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
import numpy.typing as npt

from ._types import FloatArray
from .errors import CalibrationError
from .features import FEATURE_DIM

FORMAT_VERSION = 1
#: Minimum feature scale. Features that barely vary during calibration (typically the head
#: position) would otherwise be amplified into noise at run time.
MIN_SCALE = 0.03
#: Standardised features are clipped to +/- this, which bounds extrapolation of the model.
Z_CLIP = 4.0
NUM_TERMS = 8


def calibration_targets(width: int, height: int, grid: int, margin: float) -> list[tuple[int, int]]:
    """Calibration points on a ``grid x grid`` lattice, visited in a snaking order."""
    xs = np.linspace(width * margin, width * (1.0 - margin), grid)
    ys = np.linspace(height * margin, height * (1.0 - margin), grid)
    points: list[tuple[int, int]] = []
    for row, y in enumerate(ys):
        row_xs = xs if row % 2 == 0 else xs[::-1]
        points.extend((round(x), round(y)) for x in row_xs)
    return points


class SampleCollector:
    """Collects feature vectors for one calibration target and returns a robust average."""

    def __init__(self, min_samples: int) -> None:
        self.min_samples = min_samples
        self._samples: list[FloatArray] = []

    def add(self, feature: FloatArray) -> None:
        self._samples.append(np.asarray(feature, dtype=np.float64))

    def __len__(self) -> int:
        return len(self._samples)

    def result(self) -> FloatArray | None:
        """Mean of the samples after rejecting outliers, or ``None`` if too few samples."""
        if len(self._samples) < self.min_samples:
            return None
        data = np.vstack(self._samples)
        median = np.median(data, axis=0)
        deviation = np.abs(data - median)
        mad = np.median(deviation, axis=0) * 1.4826 + 1e-9
        keep = np.all(deviation <= 3.0 * mad, axis=1)
        if int(keep.sum()) < max(3, self.min_samples // 2):
            keep = np.ones(len(data), dtype=bool)
        return np.asarray(data[keep].mean(axis=0), dtype=np.float64)


def _design(z: FloatArray) -> FloatArray:
    """Polynomial design matrix for standardised features ``z`` of shape (n, 4)."""
    gx, gy, hx, hy = z[:, 0], z[:, 1], z[:, 2], z[:, 3]
    return np.column_stack([np.ones(len(z)), gx, gy, hx, hy, gx**2, gy**2, gx * gy])


@dataclass
class GazeModel:
    mean: FloatArray
    scale: FloatArray
    weights: FloatArray  # (NUM_TERMS, 2)
    screen: tuple[int, int]
    rmse_px: float
    loo_rmse_px: float
    n_points: int
    created: str

    # ------------------------------------------------------------------ fitting
    @classmethod
    def fit(
        cls,
        features: npt.ArrayLike,
        targets: npt.ArrayLike,
        screen: tuple[int, int],
        ridge: float = 0.1,
    ) -> GazeModel:
        x = np.asarray(features, dtype=np.float64)
        y = np.asarray(targets, dtype=np.float64)
        if x.ndim != 2 or x.shape[1] != FEATURE_DIM or y.shape != (x.shape[0], 2):
            raise CalibrationError(
                f"bad calibration data shapes: features {x.shape}, targets {y.shape}"
            )
        if x.shape[0] < 6:
            raise CalibrationError("at least 6 calibration points are required")
        if not (np.all(np.isfinite(x)) and np.all(np.isfinite(y))):
            raise CalibrationError("calibration data contains NaN or infinite values")

        mean = x.mean(axis=0)
        scale = np.maximum(x.std(axis=0), MIN_SCALE)
        design = _design((x - mean) / scale)

        penalty = ridge * np.eye(NUM_TERMS)
        penalty[0, 0] = 0.0  # never shrink the intercept
        gram = design.T @ design + penalty
        try:
            weights = np.linalg.solve(gram, design.T @ y)
            hat_diag = np.einsum("ij,ji->i", design, np.linalg.solve(gram, design.T))
        except np.linalg.LinAlgError as exc:
            raise CalibrationError("calibration data is degenerate; look at every target") from exc

        residual = y - design @ weights
        rmse = math.sqrt(float(np.mean(np.sum(residual**2, axis=1))))
        loo_residual = residual / np.maximum(1.0 - hat_diag, 1e-3)[:, None]
        loo_rmse = math.sqrt(float(np.mean(np.sum(loo_residual**2, axis=1))))

        return cls(
            mean=mean,
            scale=scale,
            weights=weights,
            screen=(int(screen[0]), int(screen[1])),
            rmse_px=rmse,
            loo_rmse_px=loo_rmse,
            n_points=int(x.shape[0]),
            created=datetime.now(timezone.utc).isoformat(timespec="seconds"),
        )

    # --------------------------------------------------------------- prediction
    def predict(self, feature: npt.ArrayLike) -> tuple[float, float]:
        z = np.clip(
            (np.asarray(feature, dtype=np.float64) - self.mean) / self.scale, -Z_CLIP, Z_CLIP
        )
        out = _design(z[None, :]) @ self.weights
        return float(out[0, 0]), float(out[0, 1])

    @property
    def quality_fraction(self) -> float:
        """Leave-one-out error as a fraction of the screen diagonal (lower is better)."""
        return self.loo_rmse_px / math.hypot(*self.screen)

    # -------------------------------------------------------------- persistence
    def to_dict(self) -> dict[str, Any]:
        return {
            "format": FORMAT_VERSION,
            "created": self.created,
            "screen": list(self.screen),
            "n_points": self.n_points,
            "rmse_px": self.rmse_px,
            "loo_rmse_px": self.loo_rmse_px,
            "mean": self.mean.tolist(),
            "scale": self.scale.tolist(),
            "weights": self.weights.tolist(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> GazeModel:
        try:
            if data["format"] != FORMAT_VERSION:
                raise CalibrationError(f"unsupported calibration format {data['format']!r}")
            mean = np.asarray(data["mean"], dtype=np.float64)
            scale = np.asarray(data["scale"], dtype=np.float64)
            weights = np.asarray(data["weights"], dtype=np.float64)
            screen = (int(data["screen"][0]), int(data["screen"][1]))
            if mean.shape != (FEATURE_DIM,) or scale.shape != (FEATURE_DIM,):
                raise CalibrationError("calibration feature statistics have the wrong shape")
            if weights.shape != (NUM_TERMS, 2):
                raise CalibrationError("calibration weights have the wrong shape")
            if not (np.all(np.isfinite(weights)) and np.all(scale > 0)):
                raise CalibrationError("calibration file contains invalid numbers")
            return cls(
                mean=mean,
                scale=scale,
                weights=weights,
                screen=screen,
                rmse_px=float(data["rmse_px"]),
                loo_rmse_px=float(data["loo_rmse_px"]),
                n_points=int(data["n_points"]),
                created=str(data["created"]),
            )
        except (KeyError, TypeError, ValueError, IndexError) as exc:
            raise CalibrationError(f"corrupt calibration file: {exc}") from exc

    def save(self, path: str | Path) -> None:
        target = Path(path)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(target.suffix + ".tmp")
        tmp.write_text(json.dumps(self.to_dict(), indent=2), encoding="utf-8")
        tmp.replace(target)  # atomic: never leaves a half-written calibration behind

    @classmethod
    def load(cls, path: str | Path) -> GazeModel:
        try:
            data = json.loads(Path(path).read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise CalibrationError(f"calibration file not found: {path}") from exc
        except (OSError, json.JSONDecodeError) as exc:
            raise CalibrationError(f"cannot read calibration file {path}: {exc}") from exc
        if not isinstance(data, dict):
            raise CalibrationError("corrupt calibration file: expected a JSON object")
        return cls.from_dict(data)
