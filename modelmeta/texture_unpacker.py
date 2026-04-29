"""Extract embedded GLTF/GLB textures to files."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from .gltf_reader import ModelDocument


def unpack_embedded_textures(document: ModelDocument, metadata_output_path: Path, texture_output_dir: str) -> dict[int, str]:
    gltf = document.gltf
    if gltf is None:
        return {}
    images = getattr(gltf, "images", None) or []
    textures = getattr(gltf, "textures", None) or []
    if not images:
        return {}

    target_dir = Path(texture_output_dir)
    if not target_dir.is_absolute():
        target_dir = metadata_output_path.parent / target_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    image_paths: dict[int, str] = {}
    for image_index, image in enumerate(images):
        data, ext = _image_bytes(document, image)
        if data is None:
            continue
        safe_name = _safe_stem(image.name or f"texture_{image_index}")
        file_path = _unique_path(target_dir / f"{document.path.stem}_{safe_name}{ext}")
        file_path.write_bytes(data)
        image_paths[image_index] = _relative_path(file_path, metadata_output_path.parent)

    texture_paths: dict[int, str] = {}
    for texture_index, texture in enumerate(textures):
        image_index = getattr(texture, "source", None)
        if image_index in image_paths:
            texture_paths[texture_index] = image_paths[image_index]
    return texture_paths


def _image_bytes(document: ModelDocument, image: Any) -> tuple[bytes | None, str]:
    uri = getattr(image, "uri", None)
    if uri:
        if uri.startswith("data:"):
            header, payload = uri.split(",", 1)
            mime = header.split(";", 1)[0].removeprefix("data:")
            ext = mimetypes.guess_extension(mime) or ".bin"
            return base64.b64decode(payload), ext
        source_path = document.path.parent / uri
        if source_path.exists():
            return source_path.read_bytes(), source_path.suffix or ".bin"
        return None, ".bin"

    buffer_view_index = getattr(image, "bufferView", None)
    if buffer_view_index is None:
        return None, ".bin"
    data = _read_buffer_view(document, buffer_view_index)
    mime = getattr(image, "mimeType", None)
    ext = mimetypes.guess_extension(mime or "") or ".bin"
    return data, ext


def _read_buffer_view(document: ModelDocument, buffer_view_index: int) -> bytes | None:
    gltf = document.gltf
    if gltf is None:
        return None
    buffer_views = getattr(gltf, "bufferViews", None) or []
    if buffer_view_index >= len(buffer_views):
        return None
    buffer_view = buffer_views[buffer_view_index]
    try:
        blob = gltf.get_data_from_buffer_uri(gltf.buffers[buffer_view.buffer].uri)
    except Exception:
        blob = getattr(gltf, "binary_blob", lambda: None)()
    if blob is None:
        return None
    start = buffer_view.byteOffset or 0
    end = start + buffer_view.byteLength
    return bytes(blob[start:end])


def _relative_path(path: Path, base: Path) -> str:
    try:
        return path.relative_to(base).as_posix()
    except ValueError:
        return path.as_posix()


def _unique_path(path: Path) -> Path:
    if not path.exists():
        return path
    for index in range(1, 10_000):
        candidate = path.with_name(f"{path.stem}_{index}{path.suffix}")
        if not candidate.exists():
            return candidate
    raise RuntimeError(f"unable to find unique texture path for {path}")


def _safe_stem(value: str) -> str:
    safe = "".join(char if char.isalnum() or char in ("-", "_") else "_" for char in value)
    return safe or "texture"
