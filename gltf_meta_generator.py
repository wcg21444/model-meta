#!/usr/bin/env python3
"""GLTF/GLB Model Metadata Generator

Parses GLTF files and generates `.modelmeta.json` containing:
- model type (static / skeletal)
- overall bounding box
- per-part geometry and PBR material info
- skeleton node hierarchy (for skeletal models)
"""

import sys
import math
import json
import base64
import argparse
import glob as glob_module
from pathlib import Path
from typing import Dict, List, Any, Optional, Tuple
from urllib.parse import unquote

import trimesh
import pygltflib


def load_gltf(filepath: Path) -> Tuple[pygltflib.GLTF2, Optional[trimesh.Scene]]:
    """Load a GLTF/GLB file with both pygltflib (spec) and trimesh (geometry)."""
    gltf = pygltflib.GLTF2.load(str(filepath))

    scene = None
    try:
        tm = trimesh.load(str(filepath), force="scene")
        scene = tm if isinstance(tm, trimesh.Scene) else trimesh.Scene(tm)
    except Exception:
        pass

    return gltf, scene


def get_overall_bounding_box(scene: Optional[trimesh.Scene]) -> Optional[Dict[str, List[float]]]:
    """Compute overall bounding box from a trimesh scene."""
    if scene is None:
        return None
    bounds = scene.bounds  # shape (2, 3)
    return {
        "min": [float(bounds[0][0]), float(bounds[0][1]), float(bounds[0][2])],
        "max": [float(bounds[1][0]), float(bounds[1][1]), float(bounds[1][2])],
    }


def get_accessor_min_max(gltf: pygltflib.GLTF2, accessor_index: int) -> Optional[Tuple[List[float], List[float]]]:
    """Return (min, max) from an accessor, if present."""
    if accessor_index is None or accessor_index < 0 or accessor_index >= len(gltf.accessors):
        return None
    acc = gltf.accessors[accessor_index]
    if acc.min is None or acc.max is None:
        return None
    return list(acc.min), list(acc.max)


def get_mesh_bounding_box(gltf: pygltflib.GLTF2, mesh) -> Optional[Dict[str, List[float]]]:
    """Aggregate bounding box from all POSITION accessors in a mesh's primitives."""
    global_min = [float("inf"), float("inf"), float("inf")]
    global_max = [float("-inf"), float("-inf"), float("-inf")]
    has_any = False

    for prim in mesh.primitives:
        pos_idx = prim.attributes.POSITION if hasattr(prim.attributes, "POSITION") else None
        if pos_idx is None:
            continue
        result = get_accessor_min_max(gltf, pos_idx)
        if result is None:
            continue
        has_any = True
        mn, mx = result
        for i in range(3):
            global_min[i] = min(global_min[i], mn[i])
            global_max[i] = max(global_max[i], mx[i])

    if not has_any:
        return None

    return {
        "min": [float(global_min[0]), float(global_min[1]), float(global_min[2])],
        "max": [float(global_max[0]), float(global_max[1]), float(global_max[2])],
    }


def _is_invalid_bbox(bbox: Dict[str, List[float]]) -> bool:
    """Check if a bounding box contains NaN, Inf, or inverted axes."""
    for i in range(3):
        mn = bbox["min"][i]
        mx = bbox["max"][i]
        if math.isnan(mn) or math.isnan(mx) or math.isinf(mn) or math.isinf(mx) or mn > mx:
            return True
    return False


def compute_overall_bbox_from_parts(parts: List[Dict[str, Any]]) -> Dict[str, List[float]]:
    """Fallback: merge per-part bounding boxes into an overall box."""
    global_min = [float("inf"), float("inf"), float("inf")]
    global_max = [float("-inf"), float("-inf"), float("-inf")]
    has_any = False

    for part in parts:
        bbox = part.get("bounding_box")
        if bbox is None:
            continue
        has_any = True
        for i in range(3):
            global_min[i] = min(global_min[i], bbox["min"][i])
            global_max[i] = max(global_max[i], bbox["max"][i])

    if not has_any:
        return {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}

    return {
        "min": [float(global_min[0]), float(global_min[1]), float(global_min[2])],
        "max": [float(global_max[0]), float(global_max[1]), float(global_max[2])],
    }


def resolve_texture_path(gltf: pygltflib.GLTF2, texture_index: Optional[int], unpacked_images: Optional[Dict[int, str]] = None) -> Optional[str]:
    """Map a texture index to its image URI (relative path)."""
    if texture_index is None or texture_index < 0 or texture_index >= len(gltf.textures):
        return None
    texture = gltf.textures[texture_index]

    source_idx = texture.source
    # Handle common extensions that redirect the image source
    if source_idx is None and texture.extensions:
        for ext_name in ("KHR_texture_basisu", "EXT_texture_webp"):
            ext = texture.extensions.get(ext_name)
            if ext:
                source_idx = ext.get("source")
                break

    if source_idx is None or source_idx < 0 or source_idx >= len(gltf.images):
        return None

    image = gltf.images[source_idx]

    if unpacked_images and source_idx in unpacked_images:
        return unpacked_images[source_idx]

    if image.uri is None:
        return None  # embedded image in GLB buffer

    uri = image.uri
    # Skip data URIs (base64 embedded images) — they are not file paths
    if uri.startswith("data:"):
        return None

    # Decode percent-encoded characters (e.g., %20 -> space)
    uri = unquote(uri)

    # Normalize to forward slashes for cross-platform consistency
    return str(Path(uri).as_posix())


def detect_image_extension(data: bytes) -> str:
    """Detect image format from magic bytes and return a file extension."""
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return ".png"
    if data.startswith(b"\xff\xd8\xff"):
        return ".jpg"
    if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WEBP":
        return ".webp"
    if data.startswith(b"BM"):
        return ".bmp"
    if data[:4] in (b"GIF8", b"GIF9"):
        return ".gif"
    return ".bin"


def decode_data_uri(uri: str) -> Tuple[bytes, str]:
    """Decode a data URI and return (binary_data, file_extension)."""
    header, encoded = uri.split(",", 1)
    mime = "application/octet-stream"
    if ";" in header:
        mime = header[5:].split(";")[0]
    elif header.startswith("data:"):
        mime = header[5:]

    ext_map = {
        "image/png": ".png",
        "image/jpeg": ".jpg",
        "image/jpg": ".jpg",
        "image/webp": ".webp",
        "image/bmp": ".bmp",
        "image/gif": ".gif",
    }
    ext = ext_map.get(mime, ".bin")
    data = base64.b64decode(encoded)
    return data, ext


def get_buffer_view_data(gltf: pygltflib.GLTF2, buffer_view_index: int) -> bytes:
    """Read raw bytes from a GLTF bufferView."""
    bv = gltf.bufferViews[buffer_view_index]
    buffer = gltf.buffers[bv.buffer]

    if buffer.uri:
        buffer_data = gltf.get_data_from_buffer_uri(buffer.uri)
    else:
        buffer_data = gltf.binary_blob()

    start = bv.byteOffset or 0
    end = start + bv.byteLength
    return buffer_data[start:end]


def extract_embedded_textures(gltf: pygltflib.GLTF2, output_dir: Path, prefix: str = "") -> Dict[int, str]:
    """Extract embedded images (data URI or bufferView) to files.

    Args:
        prefix: Filename prefix to avoid collisions when multiple models share
                the same textures directory. e.g. "character" -> "character_texture_0.png"

    Returns a mapping: {image_index: relative_path}
    """
    output_dir.mkdir(parents=True, exist_ok=True)
    mapping: Dict[int, str] = {}
    name_prefix = f"{prefix}_" if prefix else ""

    for i, image in enumerate(gltf.images):
        if image.uri and image.uri.startswith("data:"):
            data, ext = decode_data_uri(image.uri)
            filename = f"{name_prefix}texture_{i}{ext}"
            (output_dir / filename).write_bytes(data)
            mapping[i] = str((Path(output_dir.name) / filename).as_posix())
        elif image.bufferView is not None:
            data = get_buffer_view_data(gltf, image.bufferView)
            ext = detect_image_extension(data)
            filename = f"{name_prefix}texture_{i}{ext}"
            (output_dir / filename).write_bytes(data)
            mapping[i] = str((Path(output_dir.name) / filename).as_posix())

    return mapping


def extract_material(gltf: pygltflib.GLTF2, material_index: Optional[int], unpacked_images: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """Build a material descriptor from a GLTF material index."""
    default = {
        "is_pbr": False,
        "textures": {
            "base_color": None,
            "metallic": None,
            "roughness": None,
            "normal": None,
        },
        "alpha_mode": "OPAQUE",
        "roughness": 0.8,
        "metallic": 0.0,
    }

    if material_index is None or material_index < 0 or material_index >= len(gltf.materials):
        return default

    mat = gltf.materials[material_index]
    result = dict(default)
    result["is_pbr"] = True  # GLTF 2.0 core materials are PBR-based
    alpha = mat.alphaMode if mat.alphaMode is not None else "OPAQUE"
    # Map GLTF spec values to the output schema
    alpha_map = {"OPAQUE": "OPAQUE", "MASK": "CUTOUT", "BLEND": "TRANSPARENT"}
    result["alpha_mode"] = alpha_map.get(alpha, alpha)

    pbr = mat.pbrMetallicRoughness
    if pbr is not None:
        result["metallic"] = float(pbr.metallicFactor) if pbr.metallicFactor is not None else 0.0
        result["roughness"] = float(pbr.roughnessFactor) if pbr.roughnessFactor is not None else 0.8

        if pbr.baseColorTexture is not None:
            result["textures"]["base_color"] = resolve_texture_path(gltf, pbr.baseColorTexture.index, unpacked_images)

        # GLTF stores metallic & roughness in a single combined texture
        if pbr.metallicRoughnessTexture is not None:
            tex_path = resolve_texture_path(gltf, pbr.metallicRoughnessTexture.index, unpacked_images)
            result["textures"]["metallic"] = tex_path
            result["textures"]["roughness"] = tex_path
    else:
        result["metallic"] = 0.0
        result["roughness"] = 0.8

    if mat.normalTexture is not None:
        result["textures"]["normal"] = resolve_texture_path(gltf, mat.normalTexture.index, unpacked_images)

    return result


def extract_model_parts(gltf: pygltflib.GLTF2, unpacked_images: Optional[Dict[int, str]] = None) -> List[Dict[str, Any]]:
    """Extract one model_part per GLTF mesh."""
    parts = []
    for mesh_idx, mesh in enumerate(gltf.meshes):
        mesh_name = mesh.name if mesh.name else f"mesh_{mesh_idx}"
        bbox = get_mesh_bounding_box(gltf, mesh)

        # Use the first primitive's material as the mesh material
        material = None
        for prim in mesh.primitives:
            if prim.material is not None:
                material = extract_material(gltf, prim.material, unpacked_images)
                break
        if material is None:
            material = {
                "is_pbr": False,
                "textures": {"base_color": None, "metallic": None, "roughness": None, "normal": None},
                "alpha_mode": "OPAQUE",
                "roughness": 0.8,
                "metallic": 0.0,
            }

        parts.append({"name": mesh_name, "bounding_box": bbox, "material": material})
    return parts


def extract_skeleton(gltf: pygltflib.GLTF2, model_parts: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Build skeleton entries mapping each joint node to the model parts it influences."""
    if not gltf.skins:
        return []

    mesh_index_to_name = {i: part["name"] for i, part in enumerate(model_parts)}

    # joint_index -> set(mesh_indices)
    joint_to_meshes: Dict[int, set] = {}
    for skin_idx, skin in enumerate(gltf.skins):
        affected = set()
        for node in gltf.nodes:
            if node.skin == skin_idx and node.mesh is not None:
                affected.add(node.mesh)
        for joint_idx in skin.joints:
            joint_to_meshes.setdefault(joint_idx, set()).update(affected)

    skeleton = []
    for joint_idx, affected in joint_to_meshes.items():
        if joint_idx < 0 or joint_idx >= len(gltf.nodes):
            continue
        node = gltf.nodes[joint_idx]
        node_name = node.name if node.name else f"joint_{joint_idx}"
        part_names = [mesh_index_to_name[m] for m in affected if m in mesh_index_to_name]
        skeleton.append({"node_name": node_name, "model_part": part_names})

    return skeleton


def generate_meta(input_path: Path, unpacked_images: Optional[Dict[int, str]] = None) -> Dict[str, Any]:
    """Generate the complete metadata dictionary for a GLTF/GLB file."""
    input_path = input_path.resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"File not found: {input_path}")

    gltf, scene = load_gltf(input_path)

    model_type = "skeletal" if gltf.skins and len(gltf.skins) > 0 else "static"
    model_parts = extract_model_parts(gltf, unpacked_images)

    # Prefer part-based overall bounds (reliable via accessor min/max);
    # use trimesh only as a fallback.
    bbox = compute_overall_bbox_from_parts(model_parts)
    if bbox is None or _is_invalid_bbox(bbox):
        bbox = get_overall_bounding_box(scene)
    if bbox is None or _is_invalid_bbox(bbox):
        bbox = {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}

    skeleton = extract_skeleton(gltf, model_parts)

    return {
        "model_type": model_type,
        "bounding_box": bbox,
        "model_part": model_parts,
        "skeleton": skeleton,
    }


def _is_glob_pattern(path: str) -> bool:
    """Check if a path string contains glob wildcards."""
    return any(ch in path for ch in "*?[")


def main():
    parser = argparse.ArgumentParser(description="Generate .modelmeta.json from a GLTF/GLB file.")
    parser.add_argument("input", help="Path to .gltf or .glb file (supports glob patterns)")
    parser.add_argument("-o", "--output", help="Output path (default: <input>.modelmeta.json). Must be a directory when input is a glob pattern.")
    parser.add_argument("--unpack", action="store_true", help="Extract embedded textures to files")
    args = parser.parse_args()

    # Glob mode
    if _is_glob_pattern(args.input):
        if not args.output:
            parser.error("--output directory is required when input is a glob pattern")
        out_dir = Path(args.output)
        if not (args.output.endswith("/") or args.output.endswith("\\") or (out_dir.exists() and out_dir.is_dir())):
            parser.error("--output must be a directory path (end with / or \\) when input is a glob pattern")
        out_dir.mkdir(parents=True, exist_ok=True)

        matched = glob_module.glob(args.input, recursive=True)
        files = [Path(p) for p in matched if Path(p).suffix.lower() in (".gltf", ".glb")]

        if not files:
            print(f"No .gltf or .glb files matched pattern: {args.input}", file=sys.stderr)
            sys.exit(1)

        for in_path in files:
            in_path = in_path.resolve()
            gltf, scene = load_gltf(in_path)

            unpacked_images = None
            if args.unpack:
                texture_dir = in_path.parent / "textures"
                unpacked_images = extract_embedded_textures(gltf, texture_dir, prefix=in_path.stem)

            result = generate_meta(in_path, unpacked_images)
            out_path = out_dir / f"{in_path.stem}.modelmeta.json"
            out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"Metadata written to: {out_path}")
        return

    # Single-file mode
    in_path = Path(args.input).resolve()

    gltf, scene = load_gltf(in_path)

    unpacked_images = None
    if args.unpack:
        texture_dir = in_path.parent / "textures"
        unpacked_images = extract_embedded_textures(gltf, texture_dir, prefix=in_path.stem)

    result = generate_meta(in_path, unpacked_images)

    out_path = Path(args.output) if args.output else in_path.parent / f"{in_path.stem}.modelmeta.json"
    out_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"Metadata written to: {out_path}")


if __name__ == "__main__":
    main()
