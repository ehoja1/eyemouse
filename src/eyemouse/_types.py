"""Shared type aliases."""

from __future__ import annotations

from typing import TypeAlias

import numpy as np
import numpy.typing as npt

#: Vectors / matrices of 64-bit floats (landmarks, features, model weights).
FloatArray: TypeAlias = npt.NDArray[np.float64]
#: One BGR camera frame as delivered by OpenCV.
Frame: TypeAlias = npt.NDArray[np.uint8]
