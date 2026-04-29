"""Model loading helpers for trimesh and optional pygltflib access."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass
class ModelDocument:
    path: Path
    scene: Any
    gltf: Any | None


def load_model(path: Path | str) -> ModelDocument:
    model_path = Path(path)
    if not model_path.exists():
        raise FileNotFoundError(f"input model does not exist: {model_path}")
    if model_path.suffix.lower() not in {".gltf", ".glb"}:
        raise ValueError(f"unsupported model extension: {model_path.suffix}")

    try:
        import trimesh
    except ImportError as exc:
        raise RuntimeError("trimesh is required. Install dependencies with: pip install -r requirements.txt") from exc

    scene = trimesh.load(model_path, force="scene")
    gltf = None
    try:
        from pygltflib import GLTF2

        gltf = GLTF2().load(str(model_path))
    except Exception:
        gltf = None
    return ModelDocument(path=model_path, scene=scene, gltf=gltf)
