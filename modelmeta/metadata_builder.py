"""Build normalized model metadata from loaded model documents."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np

from .gltf_reader import ModelDocument
from . import __version__


EMPTY_BOUNDS = {"min": [0.0, 0.0, 0.0], "max": [0.0, 0.0, 0.0]}


def build_metadata(
    document: ModelDocument,
    float_precision: int | None = 6,
    texture_overrides: dict[int, str] | None = None,
) -> dict[str, Any]:
    texture_overrides = texture_overrides or {}
    material_by_name = _collect_gltf_materials(document, texture_overrides)
    default_material = _default_material()
    model_parts, mesh_index_to_part_name = _collect_model_parts(
        document, material_by_name, default_material, float_precision
    )
    textures = _unique(
        texture
        for part in model_parts
        for texture in part.get("material", {}).get("textures", {}).values()
        if texture
    )
    materials = _unique(part.get("material", {}).get("mat_name", "") for part in model_parts if part.get("material"))
    has_skeleton = _has_skeleton(document)

    metadata: dict[str, Any] = {
        "version": __version__,
        "model_type": "Skeletal" if has_skeleton else "Static",
        "bounding_box": _bounds_to_json(_scene_bounds(document.scene), float_precision),
        "model_part": model_parts,
        "textures": textures,
        "materials": materials,
    }
    if has_skeleton:
        metadata["skeleton"] = _collect_skeleton(document, mesh_index_to_part_name)
    return metadata


def _collect_model_parts(
    document: ModelDocument,
    material_by_name: dict[str, dict[str, Any]],
    default_material: dict[str, Any],
    float_precision: int | None,
) -> tuple[list[dict[str, Any]], dict[int, str]]:
    parts: list[dict[str, Any]] = []
    scene = document.scene
    geometry = getattr(scene, "geometry", {}) or {}

    model_names = _resolve_model_names(document)
    geom_to_mesh = _map_geometry_to_mesh_index(document)
    mesh_index_to_part_name: dict[int, str] = {}

    for geom_key, mesh in geometry.items():
        mesh_index = geom_to_mesh.get(geom_key)
        if mesh_index is not None:
            name = model_names.get(mesh_index, str(geom_key))
        else:
            name = str(geom_key)

        material = _material_from_mesh(mesh, material_by_name) or default_material
        parts.append(
            {
                "model_name": name,
                "bounding_box": _bounds_to_json(getattr(mesh, "bounds", None), float_precision),
                "material": material,
                "mesh_index": mesh_index,
            }
        )

        if mesh_index is not None:
            mesh_index_to_part_name[mesh_index] = name

    if not parts:
        stem_name = document.path.stem
        parts.append({"model_name": stem_name, "bounding_box": EMPTY_BOUNDS, "material": default_material, "mesh_index": None})

    return parts, mesh_index_to_part_name


def _resolve_model_names(document: ModelDocument) -> dict[int, str]:
    """Map GLTF mesh index to a human-readable name."""
    gltf = document.gltf
    if gltf is None:
        return {}

    meshes = getattr(gltf, "meshes", None) or []
    nodes = getattr(gltf, "nodes", None) or []

    names: dict[int, str] = {}

    # # First pass: use mesh name if available
    # for i, mesh in enumerate(meshes):
    #     if mesh.name:
    #         names[i] = mesh.name

    # model part always use node name
    for node in nodes:
        node_name = node.name
        if node_name:
            names[node.mesh] = node_name

    # # Third pass: fallback to mesh_{index}
    # for i in range(len(meshes)):
    #     if i not in names:
    #         names[i] = f"mesh_{i}"

    for i in range(len(meshes)):
        if i not in names:
            raise ValueError(f"Unable to resolve a name for mesh index {i}. Consider adding names to your GLTF nodes ")

    return names


def _map_geometry_to_mesh_index(document: ModelDocument) -> dict[str, int]:
    """Map trimesh geometry keys to original GLTF mesh indices."""
    scene = document.scene
    gltf = document.gltf
    geometry = getattr(scene, "geometry", {}) or {}

    if gltf is None:
        return {k: i for i, k in enumerate(geometry.keys())}

    nodes = getattr(gltf, "nodes", None) or []

    # Build trimesh node name -> geometry key mapping from scene graph
    tm_node_to_geom: dict[str, str] = {}
    for node_name in getattr(scene.graph, "nodes", []):
        try:
            _, geom_key = scene.graph[node_name]
            if geom_key is not None:
                tm_node_to_geom[node_name] = geom_key
        except Exception:
            pass

    # Build pygltflib node name -> node indices mapping
    pg_nodes_by_name: dict[str, list[int]] = {}
    for i, node in enumerate(nodes):
        name = node.name or f"node_{i}"
        pg_nodes_by_name.setdefault(name, []).append(i)

    result: dict[str, int] = {}
    used_mesh_indices: set[int] = set()

    for tm_node, geom_key in tm_node_to_geom.items():
        for base in (tm_node, _strip_numeric_suffix(tm_node)):
            candidates = pg_nodes_by_name.get(base, [])
            found = False
            for idx in candidates:
                mesh_idx = nodes[idx].mesh
                if mesh_idx is not None and mesh_idx not in used_mesh_indices:
                    result[geom_key] = mesh_idx
                    used_mesh_indices.add(mesh_idx)
                    found = True
                    break
            if found:
                break

    # Fallback for GLTF/GLTF_N naming convention used by trimesh
    for i, geom_key in enumerate(geometry.keys()):
        if geom_key not in result:
            if geom_key == "GLTF":
                result[geom_key] = 0
            elif geom_key.startswith("GLTF_"):
                try:
                    idx = int(geom_key.split("_", 1)[1])
                    result[geom_key] = idx
                except ValueError:
                    pass

    return result


def _strip_numeric_suffix(name: str) -> str:
    m = re.match(r"(.+)_(\d+)$", name)
    return m.group(1) if m else name


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


def _format_texture_url(path: str) -> str:
    """Format a texture path with file-relative context (url-doc.md v1.1).

    The ``texture://`` root is omitted because the ``textures`` field
    already implies the resource type.  Only the context + path are stored.

    Data URIs are passed through unchanged.
    """
    if path.startswith("data:"):
        return path
    return f"file:{path}"


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
        textures[slot] = texture_overrides[texture_index]  # pre-formatted by unpacker
        return
    path = _texture_uri(gltf, texture_index)
    if path:
        textures[slot] = _format_texture_url(_normalize_texture_path(path, model_path))


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


def _collect_skeleton(document: ModelDocument, mesh_index_to_part_name: dict[int, str]) -> list[dict[str, Any]]:
    gltf = document.gltf
    if gltf is None:
        return [{"node_name": "skeleton", "model_part": list(mesh_index_to_part_name.values())}]

    nodes = getattr(gltf, "nodes", None) or []
    skins = getattr(gltf, "skins", None) or []

    if not skins:
        return [{"node_name": "skeleton", "model_part": list(mesh_index_to_part_name.values())}]

    # Build node tree
    node_children: dict[int, list[int]] = {i: [] for i in range(len(nodes))}
    for i, node in enumerate(nodes):
        for child in (node.children or []):
            node_children[i].append(child)

    # All joint node indices across all skins (for boundary detection)
    all_joint_indices: set[int] = set()
    for skin in skins:
        for j in (skin.joints or []):
            all_joint_indices.add(j)

    # Collect mesh indices in a node's subtree, stopping at child joints
    def collect_subtree_meshes(node_idx: int, visited: set[int]) -> list[int]:
        result: list[int] = []
        for child in node_children[node_idx]:
            if child in visited or child >= len(nodes):
                continue
            visited.add(child)
            child_node = nodes[child]
            # Stop recursing at child joints — their meshes belong to them
            if child in all_joint_indices:
                continue
            if child_node.mesh is not None:
                result.append(child_node.mesh)
            result.extend(collect_subtree_meshes(child, visited))
        return result

    def map_to_part_names(mesh_indices: list[int]) -> list[str]:
        parts = [mesh_index_to_part_name[m] for m in mesh_indices if m in mesh_index_to_part_name]
        return list(dict.fromkeys(parts))

    result: list[dict[str, Any]] = []
    seen: set[int] = set()

    for skin in skins:
        for joint_idx in (skin.joints or []):
            if joint_idx in seen or joint_idx >= len(nodes):
                continue
            seen.add(joint_idx)
            joint_node = nodes[joint_idx]

            mesh_indices: list[int] = []

            # 1. Direct mesh association from glTF: joint node itself carries a mesh
            if joint_node.mesh is not None:
                mesh_indices.append(joint_node.mesh)

            # 2. Subtree fallback: collect meshes from non-joint descendants only
            subtree = collect_subtree_meshes(joint_idx, {joint_idx})
            mesh_indices.extend(subtree)

            mesh_indices = list(dict.fromkeys(mesh_indices))

            part_names = map_to_part_names(mesh_indices)
            if not part_names:
                continue

            result.append({
                "node_name": joint_node.name or f"joint_{joint_idx}",
                "model_part": part_names,
            })

    return result or [{"node_name": "skeleton", "model_part": list(mesh_index_to_part_name.values())}]


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
