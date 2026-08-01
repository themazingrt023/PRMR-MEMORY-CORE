"""Bounded path validation and atomic artifact writing."""

from __future__ import annotations

import os
from pathlib import Path
import tempfile
from typing import Any


class UnsafePathError(ValueError):
    code = "UNSAFE_PATH_REFUSED"


def normalise_output_path(value: str | Path, *, allowed_root: str | Path | None = None) -> Path:
    path = Path(value).expanduser().resolve()
    if allowed_root is not None:
        root = Path(allowed_root).expanduser().resolve()
        try:
            path.relative_to(root)
        except ValueError as exc:
            raise UnsafePathError("Output path is outside the allowed root.") from exc
    if path == Path(path.anchor):
        raise UnsafePathError("Filesystem root cannot be used as an output path.")
    return path


def atomic_write_bytes(path: Path, payload: bytes, *, overwrite: bool = False) -> None:
    target = path.resolve()
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists() and not overwrite:
        raise FileExistsError("Output already exists; use the explicit overwrite option.")
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{target.name}.", dir=target.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        try:
            os.chmod(temporary, 0o600)
        except OSError:
            pass
        os.replace(temporary, target)
    finally:
        if temporary.exists():
            temporary.unlink()


__all__ = ["UnsafePathError", "atomic_write_bytes", "normalise_output_path"]
