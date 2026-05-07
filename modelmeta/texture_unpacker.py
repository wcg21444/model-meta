"""Extract embedded GLTF/GLB textures to files."""

from __future__ import annotations

import base64
import mimetypes
from pathlib import Path
from typing import Any

from .gltf_reader import ModelDocument

# 输出格式取决于 asset_root:
#   在 asset_root 内 → "textures/image.png" (asset-relative, 无前缀)
#   不在 asset_root 内 → "file:textures/image.png" (file-relative)
def unpack_embedded_textures(
    document: ModelDocument,
    metadata_output_path: Path,
    texture_output_dir: str,
    texture_output_base: Path | None = None,
    asset_root: Path | None = None,
    unpack_policy: str = "retain",
) -> dict[int, str]:
    gltf = document.gltf
    if gltf is None:
        return {}
    images = getattr(gltf, "images", None) or []
    textures = getattr(gltf, "textures", None) or []
    if not images:
        return {}

    # Resolve target directory
    target_dir = Path(texture_output_dir)
    if not target_dir.is_absolute():
        if texture_output_base is not None:
            target_dir = texture_output_base.resolve() / target_dir
        else:
            target_dir = metadata_output_path.parent / target_dir
    target_dir.mkdir(parents=True, exist_ok=True)

    image_paths: dict[int, str] = {}
    for image_index, image in enumerate(images):
        data, ext = _image_bytes(document, image)
        if data is None:
            continue
        safe_name = _safe_stem(image.name or f"texture_{image_index}")
        file_path = _resolve_texture_path(target_dir, document, safe_name, ext, unpack_policy)
        file_path.write_bytes(data)
        image_paths[image_index] = _texture_ref_path(file_path, metadata_output_path, asset_root)

    texture_paths: dict[int, str] = {}
    for texture_index, texture in enumerate(textures):
        image_index = getattr(texture, "source", None)
        if image_index in image_paths:
            texture_paths[texture_index] = image_paths[image_index]
    return texture_paths


def _texture_ref_path(
    abs_texture: Path,
    metadata_output_path: Path,
    asset_root: Path | None,
) -> str:
    """Return the reference string for a texture in metadata.

    - Under ``asset_root`` → path relative to asset root (bare, no prefix)
    - Otherwise → ``file:<relative-to-.modelmeta.json>``
    """
    import os

    abs_texture = abs_texture.resolve()
    if asset_root is not None:
        resolved_root = asset_root.resolve()
        try:
            return abs_texture.relative_to(resolved_root).as_posix()
        except ValueError:
            pass  # not under asset_root
    rel = os.path.relpath(str(abs_texture), str(metadata_output_path.parent.resolve()))
    return f"file:{rel.replace(os.sep, '/')}"


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


def _resolve_texture_path(
    target_dir: Path,
    document: ModelDocument,
    safe_name: str,
    ext: str,
    policy: str,
) -> Path:
    """Resolve the output path for an unpacked texture.

    - ``"retain"``: skip existing files by appending a suffix (``_1``, ``_2``, ...)
    - ``"cover"``: overwrite the file at the expected path
    """
    path = target_dir / f"{document.path.stem}_{safe_name}{ext}"
    if policy == "cover":
        return path
    # retain: find a non-existing path
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
