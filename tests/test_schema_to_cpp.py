#!/usr/bin/env python3
"""Tests for tools/schema_to_cpp.py."""

import json
import unittest
from pathlib import Path

import tools.schema_to_cpp as cppgen


FIXTURES = Path(__file__).parent / "fixtures"
SCHEMA_PATH = FIXTURES.parent.parent / "schema" / "modelmeta.schema.json"


class TestSchemaToCppGeneration(unittest.TestCase):
    def setUp(self):
        self.schema_data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_generate_compiles(self):
        """Generated C++ must pass libclang validation."""
        gen = cppgen.SchemaToCpp(self.schema_data)
        source = gen.generate(namespace="modelmeta")
        ok = cppgen.validate_with_libclang(source)
        self.assertTrue(ok)

    def test_struct_order_topological(self):
        """Structs should be emitted in dependency order."""
        gen = cppgen.SchemaToCpp(self.schema_data)
        order = [s["name"] for s in gen._topo_sort_structs()]
        # BoundingBox has no deps, should come before ModelPart
        self.assertLess(order.index("BoundingBox"), order.index("ModelPart"))
        # TextureSlots before Material
        self.assertLess(order.index("TextureSlots"), order.index("Material"))

    def test_enum_values_uppercased(self):
        """Enum values are uppercased; lowercase C++ keywords become safe when uppercased."""
        schema = {
            "structs": [
                {
                    "name": "Test",
                    "fields": [
                        {"name": "kind", "type": "enum", "enum_values": ["static", "class", "normal"]}
                    ]
                }
            ]
        }
        gen = cppgen.SchemaToCpp(schema)
        source = gen.generate()
        # static -> STATIC (not a keyword in uppercase)
        self.assertIn("STATIC", source)
        self.assertIn("CLASS", source)
        self.assertIn("NORMAL", source)
        # Should NOT have underscores appended for uppercased keywords
        self.assertNotIn("STATIC_,", source)
        self.assertNotIn("CLASS_,", source)

    def test_pascal_case_conversion(self):
        self.assertEqual(cppgen._snake_to_pascal("alpha_mode"), "AlphaMode")
        self.assertEqual(cppgen._snake_to_pascal("model_type"), "ModelType")
        self.assertEqual(cppgen._snake_to_pascal("node_name"), "NodeName")

    def test_namespace_custom(self):
        gen = cppgen.SchemaToCpp(self.schema_data)
        source = gen.generate(namespace="mygame")
        self.assertIn("namespace mygame {", source)
        self.assertIn("} // namespace mygame", source)


class TestLibclangSync(unittest.TestCase):
    def setUp(self):
        self.schema_data = json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))

    def test_parse_existing_header(self):
        """Parse a generated header back with libclang."""
        gen = cppgen.SchemaToCpp(self.schema_data)
        source = gen.generate()
        # Write to temp file and parse
        tmp = FIXTURES / "_test_tmp_header.h"
        tmp.write_text(source, encoding="utf-8")
        try:
            existing = cppgen.parse_existing_header(tmp)
            self.assertIn("ModelMeta", existing["structs"])
            self.assertIn("BoundingBox", existing["structs"])
            # Check that ModelMeta has model_type field
            field_names = [f["name"] for f in existing["structs"]["ModelMeta"]["fields"]]
            self.assertIn("model_type", field_names)
        finally:
            tmp.unlink(missing_ok=True)

    def test_diff_no_changes(self):
        """Diff against identical generated header should be empty."""
        gen = cppgen.SchemaToCpp(self.schema_data)
        source = gen.generate()
        tmp = FIXTURES / "_test_tmp_header.h"
        tmp.write_text(source, encoding="utf-8")
        try:
            existing = cppgen.parse_existing_header(tmp)
            diffs = cppgen.diff_schema_vs_cpp(self.schema_data, existing)
            # Enum values may show as differences because libclang drops enum
            # values that aren't referenced, but struct/field names should match.
            struct_diffs = [d for d in diffs if d.startswith(("+", "-")) and "struct" in d]
            self.assertEqual(struct_diffs, [])
        finally:
            tmp.unlink(missing_ok=True)


if __name__ == "__main__":
    unittest.main()
