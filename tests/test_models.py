from __future__ import annotations

import hashlib

import pytest

from eyemouse.config import TrackingConfig
from eyemouse.errors import ModelError
from eyemouse.models import _download, ensure_face_model, sha256_of

PAYLOAD = b"x" * 200_000


def cfg_for(path, sha: str = "") -> TrackingConfig:
    return TrackingConfig(model_path=str(path), model_sha256=sha)


def test_existing_model_file_is_accepted(tmp_path):
    model = tmp_path / "m.task"
    model.write_bytes(PAYLOAD)
    assert ensure_face_model(cfg_for(model)) == model


def test_matching_sha256_is_accepted(tmp_path):
    model = tmp_path / "m.task"
    model.write_bytes(PAYLOAD)
    digest = hashlib.sha256(PAYLOAD).hexdigest()
    assert sha256_of(model) == digest
    assert ensure_face_model(cfg_for(model, digest.upper())) == model


def test_mismatching_sha256_is_rejected(tmp_path):
    model = tmp_path / "m.task"
    model.write_bytes(PAYLOAD)
    with pytest.raises(ModelError, match="mismatch"):
        ensure_face_model(cfg_for(model, "0" * 64))


def test_missing_model_path_is_rejected(tmp_path):
    with pytest.raises(ModelError, match="does not exist"):
        ensure_face_model(cfg_for(tmp_path / "nope.task"))


def test_tiny_file_is_rejected_as_corrupt(tmp_path):
    model = tmp_path / "m.task"
    model.write_bytes(b"<html>error page</html>")
    with pytest.raises(ModelError, match="too small"):
        ensure_face_model(cfg_for(model))


def test_insecure_download_urls_are_refused(tmp_path):
    for url in ("http://example.com/m.task", "file:///etc/passwd", "ftp://example.com/m.task"):
        with pytest.raises(ModelError, match="insecure"):
            _download(url, tmp_path / "m.task")
