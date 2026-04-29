"""Shared JSON Schema to C++ helpers."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from model_meta_configs import DEFAULT_CONFIG
from symbol_map import cpp_member, cpp_type


@dataclass
class CppField:
    json_name: str
    member_name: str
    cpp_type: str
    required: bool
    is_vector: bool = False


@dataclass
class CppStruct:
    schema_name: str
    cpp_name: str
    fields: list[CppField] = field(default_factory=list)
    dependencies: set[str] = field(default_factory=set)


def load_schema(path: Path | str) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def build_structs(schema: dict[str, Any], root_name: str = DEFAULT_CONFIG.root_cpp_type) -> list[CppStruct]:
    definitions = dict(schema.get("$defs", {}))
    definitions[root_name] = {
        "type": "object",
        "required": schema.get("required", []),
        "properties": schema.get("properties", {}),
    }

    structs: dict[str, CppStruct] = {}
    for schema_name, definition in definitions.items():
        if definition.get("type") != "object":
            continue
        required = set(definition.get("required", []))
        struct = CppStruct(schema_name=schema_name, cpp_name=cpp_type(schema_name))
        for json_name, property_schema in definition.get("properties", {}).items():
            field_type, dependency, is_vector = cpp_type_for_schema(property_schema, definitions)
            if dependency:
                struct.dependencies.add(dependency)
            struct.fields.append(
                CppField(
                    json_name=json_name,
                    member_name=cpp_member(json_name),
                    cpp_type=field_type,
                    required=json_name in required,
                    is_vector=is_vector,
                )
            )
        structs[schema_name] = struct

    return topological_sort(structs, root_name)


def cpp_type_for_schema(schema: dict[str, Any], definitions: dict[str, Any]) -> tuple[str, str | None, bool]:
    if "$ref" in schema:
        name = ref_name(schema["$ref"])
        definition = definitions.get(name, {})
        if definition.get("type") == "object":
            return cpp_type(name), name, False
        return cpp_type_for_schema(definition, definitions)

    schema_type = schema.get("type")
    if schema_type == "array":
        item_type, dependency, _ = cpp_type_for_schema(schema.get("items", {}), definitions)
        return f"std::vector<{item_type}>", dependency, True
    if schema_type == "string":
        return "std::string", None, False
    if schema_type == "number":
        return "float", None, False
    if schema_type == "integer":
        return "int", None, False
    if schema_type == "boolean":
        return "bool", None, False
    if schema_type == "object":
        return "nlohmann::json", None, False
    return "nlohmann::json", None, False


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
    return "\n".join(f"}} // namespace {part}" for part in reversed(namespace.split("::"))) + "\n"


def sanitize_identifier(value: str) -> str:
    identifier = re.sub(r"\W+", "_", value)
    if not identifier or identifier[0].isdigit():
        identifier = f"_{identifier}"
    return identifier
