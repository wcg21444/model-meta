"""Input/output path handling for metadata generation."""

from __future__ import annotations

import glob
import json
from pathlib import Path
from typing import Any


MODEL_EXTENSIONS = {".gltf", ".glb"}


def iter_input_files(patterns: list[str]) -> tuple[list[Path], bool]:
    """Collect model files matching *patterns*.

    Each element of *patterns* may be a concrete file path, a glob
    pattern, or a semicolon‑delimited CMake list (e.g.
    ``/a/b.glb;/c/**/*.gltf``).  Semdiamonds in a single string are
    split automatically so that both ``--glob-patterns a b`` (Python
    shell) and ``--glob-patterns "a;b"`` (CMake) work.

    Returns ``(files, is_multi)`` where *is_multi* is ``True`` when
    more than one input file was resolved (so downstream logic knows
    whether ``output_path`` should be treated as a directory).
    """

    def _expand_one(raw: str) -> list[Path]:
        """Split a single raw item (possibly with semicolons), then glob."""
        collected: list[Path] = []
        for candidate in raw.split(";"):
            candidate = candidate.strip()
            if not candidate:
                continue
            is_glob = any(token in candidate for token in "*?[")
            if is_glob:
                matched = sorted(Path(p) for p in glob.glob(candidate, recursive=True))
                matched = [p for p in matched if p.suffix.lower() in MODEL_EXTENSIONS]
                collected.extend(matched)
            else:
                p = Path(candidate)
                if p.suffix.lower() not in MODEL_EXTENSIONS:
                    raise ValueError(f"unsupported model extension: {p.suffix} ({candidate})")
                if not p.exists():
                    raise FileNotFoundError(f"input model does not exist: {candidate}")
                collected.append(p)
        return collected

    all_files: list[Path] = []
    for raw in patterns:
        all_files.extend(_expand_one(raw))

    # Deduplicate while preserving order
    seen: set[Path] = set()
    unique: list[Path] = []
    for f in all_files:
        if f not in seen:
            seen.add(f)
            unique.append(f)

    if not unique:
        raise FileNotFoundError(f"no model files found for patterns: {patterns}")

    is_multi = len(unique) > 1
    return unique, is_multi


def resolve_output_path(model_path: Path, output_arg: Path | None, is_multi: bool) -> Path:
    if output_arg is not None:
        if is_multi or output_arg.exists() and output_arg.is_dir() or str(output_arg).endswith(("/", "\\")):
            return output_arg / f"{model_path.stem}.modelmeta.json"
        return output_arg
    return model_path.with_name(f"{model_path.stem}.modelmeta.json")


def write_metadata(metadata: dict[str, Any], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metadata, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")