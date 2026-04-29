"""Shared JSON Schema to C++ helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from model_meta_configs import DEFAULT_CONFIG
from symbol_map import cpp_enum, cpp_member, cpp_type


@dataclass
class CppEnum:
    """A C++ enum class derived from a JSON Schema string+enum property."""
    cpp_name: str               # e.g., "ModelType"
    values: list[str]           # e.g., ["Skeletal", "Static"]


@dataclass
class CppField:
    json_name: str
    member_name: str
    cpp_type: str
    required: bool
    is_vector: bool = False
    is_enum: bool = False


@dataclass
class CppStruct:
    schema_name: str
    cpp_name: str
    fields: list[CppField] = field(default_factory=list)
    dependencies: set[str] = field(default_factory=set)
    enums: list[CppEnum] = field(default_factory=list)


def load_schema(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_structs(
    schema: dict[str, Any],
    root_name: str = DEFAULT_CONFIG.root_cpp_type,
) -> tuple[list[CppStruct], list[CppEnum]]:
    """Return (ordered structs, deduplicated enums in first-seen order)."""
    definitions = dict(schema.get("$defs", {}))
    definitions[root_name] = {
        "type": "object",
        "required": schema.get("required", []),
        "properties": schema.get("properties", {}),
    }

    enum_registry: dict[str, CppEnum] = {}  # cpp_name → CppEnum
    enum_order: list[str] = []               # cpp_names in first-seen order

    structs: dict[str, CppStruct] = {}
    for schema_name, definition in definitions.items():
        if definition.get("type") != "object":
            continue
        required = set(definition.get("required", []))
        struct = CppStruct(schema_name=schema_name, cpp_name=cpp_type(schema_name))
        for json_name, property_schema in definition.get("properties", {}).items():
            field_type, dependency, is_vector, is_enum = cpp_type_for_schema(
                property_schema, definitions
            )
            if is_enum:
                enum_cpp_name = cpp_enum(json_name)  # e.g., "model_type" → "ModelType"
                field_type = enum_cpp_name
                if enum_cpp_name not in enum_registry:
                    enum_registry[enum_cpp_name] = CppEnum(
                        cpp_name=enum_cpp_name,
                        values=property_schema["enum"],
                    )
                    enum_order.append(enum_cpp_name)
                struct.enums.append(enum_registry[enum_cpp_name])
            if dependency:
                struct.dependencies.add(dependency)
            struct.fields.append(
                CppField(
                    json_name=json_name,
                    member_name=cpp_member(json_name),
                    cpp_type=field_type,
                    required=json_name in required,
                    is_vector=is_vector,
                    is_enum=is_enum,
                )
            )
        structs[schema_name] = struct

    ordered_structs = topological_sort(structs, root_name)
    ordered_enums = [enum_registry[name] for name in enum_order]
    return ordered_structs, ordered_enums


def cpp_type_for_schema(
    schema: dict[str, Any], definitions: dict[str, Any]
) -> tuple[str, str | None, bool, bool]:
    """Return ``(cpp_type, dependency_name | None, is_vector, is_enum)``.

    When *is_enum* is ``True`` the returned *cpp_type* is ``"__ENUM__"`` –
    the caller must replace it with the real enum type name.
    """
    if "$ref" in schema:
        name = ref_name(schema["$ref"])
        definition = definitions.get(name, {})
        if definition.get("type") == "object":
            return cpp_type(name), name, False, False
        return cpp_type_for_schema(definition, definitions)

    schema_type = schema.get("type")
    if schema_type == "array":
        item_type, dependency, _, is_enum = cpp_type_for_schema(
            schema.get("items", {}), definitions
        )
        return f"std::vector<{item_type}>", dependency, True, is_enum
    if schema_type == "string":
        if "enum" in schema:
            return "__ENUM__", None, False, True
        return "std::string", None, False, False
    if schema_type == "number":
        return "float", None, False, False
    if schema_type == "integer":
        return "int", None, False, False
    if schema_type == "boolean":
        return "bool", None, False, False
    if schema_type == "object":
        return "nlohmann::json", None, False, False
    return "nlohmann::json", None, False, False


def ref_name(ref: str) -> str:
    return ref.rsplit("/", 1)[-1]


def topological_sort(structs: dict[str, CppStruct], root_name: str) -> list[CppStruct]:
    ordered: list[CppStruct] = []
    temporary: set[str] = set()
    permanent: set[str] = set()

    def visit(name: str) -> None:
        if name in permanent or name not in structs:
            return
        if name in temporary:
            raise ValueError(f"cyclic schema dependency involving {name}")
        temporary.add(name)
        for dependency in sorted(structs[name].dependencies):
            visit(dependency)
        temporary.remove(name)
        permanent.add(name)
        ordered.append(structs[name])

    for name in sorted(structs):
        if name != root_name:
            visit(name)
    visit(root_name)
    return ordered


def namespace_open(namespace: str | None) -> str:
    if not namespace:
        return ""
    return "\n".join(f"namespace {part} {{" for part in namespace.split("::")) + "\n\n"


def namespace_close(namespace: str | None) -> str:
    if not namespace:
        return ""
    return "\n".join(
        f"}} // namespace {part}" for part in reversed(namespace.split("::"))
    ) + "\n"


def sanitize_identifier(value: str) -> str:
    identifier = re.sub(r"\W+", "_", value)
    if not identifier or identifier[0].isdigit():
        identifier = f"_{identifier}"
    return identifier