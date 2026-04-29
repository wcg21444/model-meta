"""Symbol mapping used by JSON output and C++ code generation.

Users may edit this file to rename output JSON fields or generated C++
symbols without changing metadata collection logic.
"""

from __future__ import annotations

from typing import Any

from model_meta_configs import DEFAULT_CONFIG
from naming_converter import convert_name


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
    """JSON output field names are not affected by C++ naming styles."""
    return JSON_FIELD_MAP.get(name, name)


def cpp_type(name: str) -> str:
    """Resolve C++ struct name: symbol map -> snake canonical -> type_naming."""
    mapped = CPP_TYPE_NAME_MAP.get(name, name)
    return convert_name(mapped, DEFAULT_CONFIG.type_naming)


def cpp_member(name: str) -> str:
    """Resolve C++ member name: symbol map -> snake canonical -> member_naming."""
    mapped = CPP_MEMBER_NAME_MAP.get(name, name)
    return convert_name(mapped, DEFAULT_CONFIG.member_naming)


def cpp_function(name: str) -> str:
    """Resolve C++ function name: snake canonical -> function_naming."""
    return convert_name(name, DEFAULT_CONFIG.function_naming)


def cpp_enum(name: str) -> str:
    """Resolve C++ enum name: symbol map -> snake canonical -> enum_naming."""
    mapped = CPP_TYPE_NAME_MAP.get(name, name)
    return convert_name(mapped, DEFAULT_CONFIG.enum_naming)


def apply_json_field_mapping(value: Any) -> Any:
    if isinstance(value, dict):
        return {json_field(key): apply_json_field_mapping(item) for key, item in value.items()}
    if isinstance(value, list):
        return [apply_json_field_mapping(item) for item in value]
    return value
