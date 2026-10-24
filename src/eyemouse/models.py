"""Locating (and, on first run, downloading) the MediaPipe face landmark model."""

from __future__ import annotations

import hashlib
import logging
import os
import urllib.error
import urllib.request
from pathlib import Path

from .config import TrackingConfig
from .errors import ModelError
from .paths import default_model_path

log = logging.getLogger(__name__)

#: A real model is a few MB; anything tiny is an error page or a truncated download.
MIN_PLAUSIBLE_BYTES = 100_000
DOWNLOAD_TIMEOUT_S = 30


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _verify(path: Path, expected_sha256: str) -> None:
    if path.stat().st_size < MIN_PLAUSIBLE_BYTES:
        raise ModelError(f"Model file {path} is too small to be valid; delete it and retry.")
    if expected_sha256:
        actual = sha256_of(path)
        if actual.lower() != expected_sha256.lower():
            raise ModelError(
                f"SHA-256 mismatch for {path}: expected {expected_sha256}, got {actual}. "
                "The file is corrupt or not the model you pinned; delete it and retry."
            )


def _download(url: str, destination: Path) -> None:
    if not url.lower().startswith("https://"):
        raise ModelError("Refusing to download the model over an insecure or unknown scheme.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp = destination.with_suffix(destination.suffix + ".part")
    log.info("Downloading face landmark model (one time only) from %s", url)
    try:
        with (
            urllib.request.urlopen(url, timeout=DOWNLOAD_TIMEOUT_S) as response,
            tmp.open("wb") as out,
        ):
            while chunk := response.read(1 << 16):
                out.write(chunk)
        os.replace(tmp, destination)
    except (urllib.error.URLError, OSError, TimeoutError) as exc:
        tmp.unlink(missing_ok=True)
        raise ModelError(
            f"Could not download the model: {exc}\n"
            f"Download it manually from:\n  {url}\n"
            f"and either save it as {destination}\n"
            "or set  tracking.model_path  in your config file."
        ) from exc


def ensure_face_model(cfg: TrackingConfig) -> Path:
    """Return the path of a verified model file, downloading it first if necessary."""
    if cfg.model_path:
        path = Path(cfg.model_path).expanduser()
        if not path.is_file():
            raise ModelError(f"tracking.model_path does not exist: {path}")
        _verify(path, cfg.model_sha256)
        return path

    path = default_model_path()
    if not path.is_file():
        _download(cfg.model_url, path)
    _verify(path, cfg.model_sha256)
    return path
