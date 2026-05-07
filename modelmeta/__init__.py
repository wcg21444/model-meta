"""Model metadata generator package."""

from __future__ import annotations

from pathlib import Path

__all__ = ["__version__"]

_VERSION_PATH = Path(__file__).resolve().parents[1] / "VERSION"


def _read() -> str:
    if _VERSION_PATH.is_file():
        return _VERSION_PATH.read_text(encoding="utf-8").strip()
    return "0.0.0"


__version__ = _read()
