#!/usr/bin/env python3
"""Schema loader and builder for modelmeta output format.

Provides a lightweight DSL for describing JSON output structures,
plus a SchemaBuilder that constructs dicts according to the schema.
"""

import json
from pathlib import Path
from typing import Dict, List, Any, Optional, Set


class SchemaError(Exception):
    """Raised when a schema definition is invalid or misused."""
    pass


class FieldDef:
    """Definition of a single field inside a struct."""

    def __init__(self, data: dict):
        self.name: str = data["name"]
        self.type: str = data["type"]
        self.optional: bool = data.get("optional", False)
        self.enum_values: Optional[List[str]] = data.get("enum_values")
        self.item_type: Optional[str] = data.get("item_type")
        self.doc: str = data.get("doc", "")

    def __repr__(self) -> str:
        return f"FieldDef({self.name}: {self.type})"


class StructDef:
    """Definition of a struct (composite type)."""

    def __init__(self, data: dict):
        self.name: str = data["name"]
        self.doc: str = data.get("doc", "")
        self.fields: Dict[str, FieldDef] = {}
        for f in data.get("fields", []):
            fd = FieldDef(f)
            self.fields[fd.name] = fd

    def __repr__(self) -> str:
        return f"StructDef({self.name})"


class Schema:
    """Loaded schema with all struct definitions."""

    def __init__(self, data: dict):
        self.version: str = data.get("version", "unknown")
        self.structs: Dict[str, StructDef] = {}
        for s in data.get("structs", []):
            sd = StructDef(s)
            self.structs[sd.name] = sd
        self._validate()

    def _validate(self) -> None:
        """Check for unknown types and circular references."""
        primitive_types = {"string", "float", "bool", "int", "float3", "enum", "array", "object"}

        # Collect all defined struct names
        known = set(self.structs.keys()) | primitive_types

        # Check all field types are known
        for struct in self.structs.values():
            for field in struct.fields.values():
                if field.type not in known:
                    raise SchemaError(
                        f"Struct '{struct.name}' field '{field.name}': unknown type '{field.type}'"
                    )
                if field.type == "array" and field.item_type and field.item_type not in known:
                    raise SchemaError(
                        f"Struct '{struct.name}' field '{field.name}': unknown item_type '{field.item_type}'"
                    )
                if field.type == "enum" and not field.enum_values:
                    raise SchemaError(
                        f"Struct '{struct.name}' field '{field.name}': enum type requires 'enum_values'"
                    )

        # Detect circular references (basic DFS)
        def has_cycle(struct_name: str, visiting: Set[str]) -> bool:
            if struct_name in visiting:
                return True
            if struct_name not in self.structs:
                return False
            visiting.add(struct_name)
            for field in self.structs[struct_name].fields.values():
                if field.type in self.structs:
                    if has_cycle(field.type, visiting):
                        return True
                if field.type == "array" and field.item_type in self.structs:
                    if has_cycle(field.item_type, visiting):
                        return True
            visiting.discard(struct_name)
            return False

        for name in self.structs:
            if has_cycle(name, set()):
                raise SchemaError(f"Circular reference detected involving struct '{name}'")

    def get_struct(self, name: str) -> StructDef:
        if name not in self.structs:
            raise SchemaError(f"Struct '{name}' not found in schema")
        return self.structs[name]

    @staticmethod
    def load(path: Path) -> "Schema":
        data = json.loads(path.read_text(encoding="utf-8"))
        return Schema(data)


class SchemaBuilder:
    """Builds a Python dict that conforms to a Schema struct definition."""

    def __init__(self, schema: Schema, struct_name: str):
        self._schema = schema
        self._struct = schema.get_struct(struct_name)
        self._values: Dict[str, Any] = {}

    def set(self, field_name: str, value: Any) -> "SchemaBuilder":
        """Set a field value. Validates that the field exists in the schema."""
        if field_name not in self._struct.fields:
            raise SchemaError(
                f"Field '{field_name}' not defined in struct '{self._struct.name}'"
            )
        self._values[field_name] = value
        return self

    def get(self, field_name: str) -> Any:
        """Get a previously set field value."""
        return self._values.get(field_name)

    def build(self, strict: bool = False) -> Dict[str, Any]:
        """Build and return the dict.

        If strict=True, raises SchemaError for missing required fields.
        """
        if strict:
            for name, field in self._struct.fields.items():
                if not field.optional and name not in self._values:
                    raise SchemaError(
                        f"Missing required field '{name}' in struct '{self._struct.name}'"
                    )
        return dict(self._values)

    def new_child(self, struct_name: str) -> "SchemaBuilder":
        """Create a new builder for a nested struct."""
        return SchemaBuilder(self._schema, struct_name)

    @staticmethod
    def from_dict(schema: Schema, struct_name: str, data: dict) -> "SchemaBuilder":
        """Wrap an existing dict in a builder for further modification."""
        builder = SchemaBuilder(schema, struct_name)
        for k, v in data.items():
            builder.set(k, v)
        return builder


def is_primitive_type(type_name: str) -> bool:
    """Check if a type name is a primitive (not a user-defined struct)."""
    return type_name in {"string", "float", "bool", "int", "float3", "enum", "array"}
