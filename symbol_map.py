"""Symbol mapping used by JSON output and C++ code generation.

Users may edit this file to rename output JSON fields or generated C++
symbols without changing metadata collection logic.
"""

from __future__ import annotations

from typing import Any


JSON_FIELD_MAP: dict[str, str] = {
    "model_type": "model_type",
    "bounding_box": "bounding_box",
    "min": "min",
    "max": "max",
    "model_part": "model_part",
    "model_name": "model_name",
    "material": "material",
    "mat_name": "mat_name",
    "is_pbr": "is_pbr",
    "textures": "textures",
    "alpha_mode": "alpha_mode",
    "roughness": "roughness",
    "metallic": "metallic",
    "skeleton": "skeleton",
    "node_name": "node_name",
}

CPP_TYPE_NAME_MAP: dict[str, str] = {
    "ModelMeta": "ModelMeta",
    "BoundingBox": "BoundingBox",
    "ModelPart": "ModelPart",
    "Material": "Material",
    "SkeletonNode": "SkeletonNode",
    "TextureSlots": "TextureSlots",
}

CPP_MEMBER_NAME_MAP: dict[str, str] = {
    "model_type": "model_type",
    "bounding_box": "bounding_box",
    "min": "min",
    "max": "max",
    "model_part": "model_part",
    "model_name": "model_name",
    "material": "material",
    "mat_name": "mat_name",
    "is_pbr": "is_pbr",
    "textures": "textures",
    "base_color": "base_color",
    "metallic": "metallic",
    "roughness": "roughness",
    "normal": "normal",
    "alpha_mode": "alpha_mode",
    "skeleton": "skeleton",
    "node_name": "node_name",
}


def json_field(name: str) -> str:
    return JSON_FIELD_MAP.get(name, name)


def cpp_type(name: str) -> str:
    return CPP_TYPE_NAME_MAP.get(name, name)


def cpp_member(name: str) -> str:
    return CPP_MEMBER_NAME_MAP.get(name, name)


def apply_json_field_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {json_field(key): apply_json_field_mapping(item) for key, item in value.items()}
    if isinstance(value, list):
        return [apply_json_field_mapping(item) for item in value]
    return value
