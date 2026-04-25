#!/usr/bin/env python3
"""Tests for schema_loader.py."""

import json
import unittest
from pathlib import Path

from schema_loader import Schema, SchemaBuilder, SchemaError


FIXTURES = Path(__file__).parent / "fixtures"


class TestSchemaLoading(unittest.TestCase):
    def test_load_valid_schema(self):
        schema = Schema.load(FIXTURES.parent.parent / "schema" / "modelmeta.schema.json")
        self.assertEqual(schema.version, "1.0")
        self.assertIn("ModelMeta", schema.structs)
        self.assertIn("BoundingBox", schema.structs)

    def test_missing_struct_ref(self):
        data = {
            "structs": [
                {"name": "Foo", "fields": [{"name": "bar", "type": "NonExistent"}]}
            ]
        }
        with self.assertRaises(SchemaError):
            Schema(data)

    def test_circular_reference(self):
        data = {
            "structs": [
                {"name": "A", "fields": [{"name": "b", "type": "B"}]},
                {"name": "B", "fields": [{"name": "a", "type": "A"}]},
            ]
        }
        with self.assertRaises(SchemaError):
            Schema(data)

    def test_enum_without_values(self):
        data = {
            "structs": [
                {"name": "Bad", "fields": [{"name": "status", "type": "enum"}]}
            ]
        }
        with self.assertRaises(SchemaError):
            Schema(data)


class TestSchemaBuilder(unittest.TestCase):
    def setUp(self):
        self.schema = Schema({
            "structs": [
                {
                    "name": "Person",
                    "fields": [
                        {"name": "name", "type": "string", "optional": False},
                        {"name": "age", "type": "int", "optional": True},
                        {"name": "scores", "type": "array", "item_type": "float", "optional": False},
                    ]
                }
            ]
        })

    def test_basic_build(self):
        b = SchemaBuilder(self.schema, "Person")
        b.set("name", "Alice")
        b.set("scores", [95.0, 88.5])
        result = b.build()
        self.assertEqual(result["name"], "Alice")
        self.assertEqual(result["scores"], [95.0, 88.5])
        self.assertNotIn("age", result)

    def test_strict_build_missing_required(self):
        b = SchemaBuilder(self.schema, "Person")
        with self.assertRaises(SchemaError):
            b.build(strict=True)

    def test_invalid_field(self):
        b = SchemaBuilder(self.schema, "Person")
        with self.assertRaises(SchemaError):
            b.set("invalid_field", 123)

    def test_nested_struct(self):
        schema = Schema({
            "structs": [
                {"name": "Address", "fields": [{"name": "city", "type": "string", "optional": False}]},
                {"name": "Person", "fields": [{"name": "address", "type": "Address", "optional": False}]},
            ]
        })
        addr = SchemaBuilder(schema, "Address")
        addr.set("city", "Beijing")

        person = SchemaBuilder(schema, "Person")
        person.set("address", addr.build())
        self.assertEqual(person.build()["address"]["city"], "Beijing")

    def test_from_dict(self):
        b = SchemaBuilder.from_dict(self.schema, "Person", {"name": "Bob", "age": 30})
        b.set("scores", [1.0])
        result = b.build()
        self.assertEqual(result["name"], "Bob")
        self.assertEqual(result["age"], 30)


if __name__ == "__main__":
    unittest.main()
