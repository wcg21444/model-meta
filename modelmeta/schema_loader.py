"""JSON schema loading and validation."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_schema(path: Path | str) -> dict[str, Any]:
    schema_path = Path(path)
    if not schema_path.exists():
        raise FileNotFoundError(f"schema file does not exist: {schema_path}")
    return json.loads(schema_path.read_text(encoding="utf-8"))


def validate_metadata(metadata: dict[str, Any], schema: dict[str, Any]) -> None:
    try:
        from jsonschema import Draft202012Validator
    except ImportError as exc:
        raise RuntimeError("jsonschema is required. Install dependencies with: pip install -r requirements.txt") from exc

    validator = Draft202012Validator(schema)
    errors = sorted(validator.iter_errors(metadata), key=lambda item: list(item.path))
    if errors:
        error = errors[0]
        location = "/".join(str(part) for part in error.path) or "<root>"
        raise ValueError(f"metadata schema validation failed at {location}: {error.message}")
