"""Build normalized model metadata from loaded model documents."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np

from .gltf_reader import ModelDocument


EMPTY_BOUNDS = {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}


def build_metadata(
    document: ModelDocument,
    float_precision: int | None = 6,
    texture_overrides: dict[int, str] | None = None,
) -> dict[str, Any]:
    texture_overrides = texture_overrides or {}
    material_by_name = _collect_gltf_materials(document, texture_overrides)
    default_material = _default_material()
    model_parts = _collect_model_parts(document, material_by_name, default_material, float_precision)
    textures = _unique(
        texture
        for part in model_parts
        for texture in part.get("material", {}).get("textures", {}).values()
        if texture
    )
    materials = _unique(part.get("material", {}).get("mat_name", "") for part in model_parts if part.get("material"))
    has_skeleton = _has_skeleton(document)

    metadata: dict[str, Any] = {
        "model_type": "Skeletal" if has_skeleton else "Static",
        "bounding_box": _bounds_to_json(_scene_bounds(document.scene), float_precision),
        "model_part": model_parts,
        "textures": textures,
        "material": materials,
    }
    if has_skeleton:
        metadata["skeleton"] = _collect_skeleton(document, [part["model_name"] for part in model_parts])
    return metadata


def _collect_model_parts(
    document: ModelDocument,
    material_by_name: dict[str, dict[str, Any]],
    default_material: dict[str, Any],
    float_precision: int | None,
) -> list[dict[str, Any]]:
    parts: list[dict[str, Any]] = []
    scene = document.scene
    geometry = getattr(scene, "geometry", {}) or {}
    for index, (geometry_name, mesh) in enumerate(geometry.items()):
        material = _material_from_mesh(mesh, material_by_name) or default_material
        name = str(geometry_name or f"mesh_{index}")
        parts.append(
            {
                "model_name": name,
                "bounding_box": _bounds_to_json(getattr(mesh, "bounds", None), float_precision),
                "material": material,
            }
        )
    if not parts:
        parts.append({"model_name": document.path.stem, "bounding_box": EMPTY_BOUNDS, "material": default_material})
    return parts


def _material_from_mesh(mesh: Any, material_by_name: dict[str, dict[str, Any]]) -> dict[str, Any] | None:
    visual = getattr(mesh, "visual", None)
    material = getattr(visual, "material", None)
    if material is None:
        return None
    name = getattr(material, "name", None)
    if name and name in material_by_name:
        return material_by_name[name]
    if len(material_by_name) == 1:
        return next(iter(material_by_name.values()))

    result = _default_material(name or "material")
    roughness = getattr(material, "roughnessFactor", None)
    metallic = getattr(material, "metallicFactor", None)
    if roughness is not None:
        result["roughness"] = float(roughness)
    if metallic is not None:
        result["metallic"] = float(metallic)
    return result


def _collect_gltf_materials(document: ModelDocument, texture_overrides: dict[int, str]) -> dict[str, dict[str, Any]]:
    gltf = document.gltf
    if gltf is None or not getattr(gltf, "materials", None):
        return {}

    materials: dict[str, dict[str, Any]] = {}
    for index, material in enumerate(gltf.materials or []):
        name = material.name or f"material_{index}"
        pbr = getattr(material, "pbrMetallicRoughness", None)
        textures: dict[str, str] = {}
        roughness = 0.8
        metallic = 0.0
        is_pbr = pbr is not None
        if pbr is not None:
            roughness = _optional_float(getattr(pbr, "roughnessFactor", None), 0.8)
            metallic = _optional_float(getattr(pbr, "metallicFactor", None), 0.0)
            _add_texture(textures, "base_color", getattr(pbr, "baseColorTexture", None), document.path, gltf, texture_overrides)
            _add_texture(textures, "metallic", getattr(pbr, "metallicRoughnessTexture", None), document.path, gltf, texture_overrides)
            _add_texture(textures, "roughness", getattr(pbr, "metallicRoughnessTexture", None), document.path, gltf, texture_overrides)
        _add_texture(textures, "normal", getattr(material, "normalTexture", None), document.path, gltf, texture_overrides)
        materials[name] = {
            "mat_name": name,
            "is_pbr": is_pbr,
            "textures": textures,
            "alpha_mode": _alpha_mode(getattr(material, "alphaMode", None)),
            "roughness": roughness,
            "metallic": metallic,
        }
    return materials


def _add_texture(
    textures: dict[str, str],
    slot: str,
    texture_info: Any,
    model_path: Path,
    gltf: Any,
    texture_overrides: dict[int, str],
) -> None:
    texture_index = getattr(texture_info, "index", None)
    if texture_index is None:
        return
    if texture_index in texture_overrides:
        textures[slot] = texture_overrides[texture_index]
        return
    path = _texture_uri(gltf, texture_index)
    if path:
        textures[slot] = _normalize_texture_path(path, model_path)


def _texture_uri(gltf: Any, texture_index: int) -> str | None:
    textures = getattr(gltf, "textures", None) or []
    images = getattr(gltf, "images", None) or []
    if texture_index >= len(textures):
        return None
    image_index = getattr(textures[texture_index], "source", None)
    if image_index is None or image_index >= len(images):
        return None
    return getattr(images[image_index], "uri", None)


def _normalize_texture_path(uri: str, model_path: Path) -> str:
    if uri.startswith("data:"):
        return uri
    path = Path(uri)
    if path.is_absolute():
        try:
            return path.relative_to(model_path.parent).as_posix()
        except ValueError:
            return path.as_posix()
    return path.as_posix()


def _has_skeleton(document: ModelDocument) -> bool:
    gltf = document.gltf
    if gltf is not None and getattr(gltf, "skins", None):
        return bool(gltf.skins)
    metadata = getattr(document.scene, "metadata", {}) or {}
    return bool(metadata.get("skins") or metadata.get("joints") or metadata.get("bones"))


def _collect_skeleton(document: ModelDocument, model_part_names: list[str]) -> list[dict[str, Any]]:
    gltf = document.gltf
    if gltf is None:
        return [{"node_name": "skeleton", "model_part": model_part_names}]
    nodes = getattr(gltf, "nodes", None) or []
    result: list[dict[str, Any]] = []
    seen: set[int] = set()
    for skin in getattr(gltf, "skins", None) or []:
        for joint_index in getattr(skin, "joints", None) or []:
            if joint_index in seen or joint_index >= len(nodes):
                continue
            seen.add(joint_index)
            node = nodes[joint_index]
            result.append({"node_name": node.name or f"joint_{joint_index}", "model_part": model_part_names})
    return result or [{"node_name": "skeleton", "model_part": model_part_names}]


def _scene_bounds(scene: Any) -> Any:
    bounds = getattr(scene, "bounds", None)
    if bounds is not None:
        return bounds
    geometry = getattr(scene, "geometry", {}) or {}
    meshes = [getattr(mesh, "bounds", None) for mesh in geometry.values() if getattr(mesh, "bounds", None) is not None]
    if not meshes:
        return None
    mins = np.array([bounds[0] for bounds in meshes], dtype=float)
    maxs = np.array([bounds[1] for bounds in meshes], dtype=float)
    return np.array([mins.min(axis=0), maxs.max(axis=0)])


def _bounds_to_json(bounds: Any, precision: int | None) -> dict[str, list[float]]:
    if bounds is None:
        return EMPTY_BOUNDS
    array = np.asarray(bounds, dtype=float)
    if array.shape != (2, 3) or not np.isfinite(array).all():
        return EMPTY_BOUNDS
    return {"min": _float3(array[0], precision), "max": _float3(array[1], precision)}


def _float3(values: Any, precision: int | None) -> list[float]:
    output = [float(value) for value in values]
    if precision is not None:
        output = [round(value, precision) for value in output]
    return output


def _default_material(name: str = "material") -> dict[str, Any]:
    return {
        "mat_name": name,
        "is_pbr": False,
        "textures": {},
        "alpha_mode": "Opaque",
        "roughness": 0.8,
        "metallic": 0.0,
    }


def _alpha_mode(value: str | None) -> str:
    if value == "MASK":
        return "Cutout"
    if value == "BLEND":
        return "Transparent"
    return "Opaque"


def _optional_float(value: Any, default: float) -> float:
    return default if value is None else float(value)


def _unique(values: Any) -> list[Any]:
    result = []
    seen = set()
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        result.append(value)
    return result
