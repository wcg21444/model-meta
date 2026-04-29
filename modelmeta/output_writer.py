"""Input/output path handling for metadata generation."""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any


MODEL_EXTENSIONS = {".gltf", ".glb"}


def iter_input_files(input_pattern: str) -> tuple[list[Path], bool]:
    is_glob = any(token in input_pattern for token in "*?[")
    if is_glob:
        files = sorted(Path(path) for path in glob.glob(input_pattern, recursive=True))
        files = [path for path in files if path.suffix.lower() in MODEL_EXTENSIONS]
        if not files:
            raise FileNotFoundError(f"glob matched no model files: {input_pattern}")
        return files, True

    path = Path(input_pattern)
    if not path.exists():
        raise FileNotFoundError(f"input model does not exist: {path}")
    if path.suffix.lower() not in MODEL_EXTENSIONS:
        raise ValueError(f"unsupported model extension: {path.suffix}")
    return [path], False


def resolve_output_path(model_path: Path, output_arg: Path | None, is_glob: bool) -> Path:
    if output_arg is not None:
        if is_glob or output_arg.exists() and output_arg.is_dir() or str(output_arg).endswith(("/", "\\")):
            return output_arg / f"{model_path.stem}.modelmeta.json"
        return output_arg
    return model_path.with_name(f"{model_path.stem}.modelmeta.json")


def write_metadata(metadata: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
