#!/usr/bin/env python3
"""Unit tests for gltf_meta_generator."""

import json
import unittest
from pathlib import Path

import pygltflib
import gltf_meta_generator as gen


FIXTURES = Path(__file__).parent / "fixtures"


def _get_material(result: dict, part_index: int = 0) -> dict:
    """Look up the full Material dict for a model_part by its material name reference."""
    name = result["model_part"][part_index]["material"]
    return next(m for m in result["materials"] if m["name"] == name)


class TestStaticModel(unittest.TestCase):
    def setUp(self):
        self.result = gen.generate_meta(FIXTURES / "static_box.gltf")

    def test_model_type(self):
        self.assertEqual(self.result["model_type"], "static")

    def test_overall_bounding_box(self):
        bbox = self.result["bounding_box"]
        self.assertEqual(bbox["min"], [-0.5, -1.0, -1.5])
        self.assertEqual(bbox["max"], [0.5, 1.0, 1.5])

    def test_model_parts_count(self):
        self.assertEqual(len(self.result["model_part"]), 1)

    def test_model_part_name(self):
        self.assertEqual(self.result["model_part"][0]["name"], "geometry_0")

    def test_model_part_bbox(self):
        bbox = self.result["model_part"][0]["bounding_box"]
        self.assertEqual(bbox["min"], [-0.5, -1.0, -1.5])
        self.assertEqual(bbox["max"], [0.5, 1.0, 1.5])

    def test_material_pbr(self):
        mat = _get_material(self.result, 0)
        self.assertTrue(mat["is_pbr"])
        self.assertEqual(mat["metallic"], 0.5)
        self.assertEqual(mat["roughness"], 0.3)
        self.assertEqual(mat["alpha_mode"], "OPAQUE")

    def test_no_skeleton(self):
        self.assertEqual(self.result["skeleton"], [])


class TestSkeletalModel(unittest.TestCase):
    def setUp(self):
        self.result = gen.generate_meta(FIXTURES / "skeletal_triangle.glb")

    def test_model_type(self):
        self.assertEqual(self.result["model_type"], "skeletal")

    def test_model_part_name(self):
        self.assertEqual(self.result["model_part"][0]["name"], "skinned_mesh")

    def test_skeleton_joints(self):
        skel = self.result["skeleton"]
        names = {entry["node_name"] for entry in skel}
        self.assertEqual(names, {"hip", "knee"})

    def test_skeleton_affected_parts(self):
        for entry in self.result["skeleton"]:
            self.assertIn("skinned_mesh", entry["model_part"])


class TestTexturedModel(unittest.TestCase):
    def setUp(self):
        self.result = gen.generate_meta(FIXTURES / "textured_quad.gltf")

    def test_texture_paths(self):
        mat = _get_material(self.result, 0)
        tex = mat["textures"]
        self.assertEqual(tex["base_color"], "textures/base_color.png")
        self.assertIsNone(tex["metallic"])
        self.assertIsNone(tex["roughness"])
        self.assertIsNone(tex["normal"])

    def test_material_values(self):
        mat = _get_material(self.result, 0)
        self.assertEqual(mat["metallic"], 0.0)
        self.assertEqual(mat["roughness"], 0.5)


class TestBoundingBoxHelpers(unittest.TestCase):
    def test_compute_overall_bbox_from_parts(self):
        parts = [
            {"bounding_box": {"min": [-1, -2, -3], "max": [1, 2, 3]}},
            {"bounding_box": {"min": [0, 0, 0], "max": [5, 5, 5]}},
        ]
        bbox = gen.compute_overall_bbox_from_parts(parts)
        self.assertEqual(bbox["min"], [-1.0, -2.0, -3.0])
        self.assertEqual(bbox["max"], [5.0, 5.0, 5.0])

    def test_compute_overall_bbox_empty(self):
        bbox = gen.compute_overall_bbox_from_parts([{"name": "no_bbox"}])
        self.assertEqual(bbox["min"], [0.0, 0.0, 0.0])
        self.assertEqual(bbox["max"], [0.0, 0.0, 0.0])

    def test_is_invalid_bbox_normal(self):
        self.assertFalse(gen._is_invalid_bbox({"min": [0, 0, 0], "max": [1, 1, 1]}))

    def test_is_invalid_bbox_inverted(self):
        self.assertTrue(gen._is_invalid_bbox({"min": [1, 0, 0], "max": [0, 1, 1]}))

    def test_is_invalid_bbox_nan(self):
        self.assertTrue(gen._is_invalid_bbox({"min": [float("nan"), 0, 0], "max": [1, 1, 1]}))


class TestAlphaModeMapping(unittest.TestCase):
    def test_opaque(self):
        # Default material has no alphaMode set -> OPAQUE
        result = gen.generate_meta(FIXTURES / "static_box.gltf")
        mat = _get_material(result, 0)
        self.assertEqual(mat["alpha_mode"], "OPAQUE")


class TestTexturePathEdgeCases(unittest.TestCase):
    def test_data_uri_returns_none(self):
        """Data URIs (base64 embedded images) must not leak as paths."""
        gltf = pygltflib.GLTF2()
        gltf.images = [
            pygltflib.Image(uri="data:image/png;base64,iVBORw0KGgo=")
        ]
        gltf.textures = [pygltflib.Texture(source=0)]
        self.assertIsNone(gen.resolve_texture_path(gltf, 0))

    def test_percent_encoded_path(self):
        """Percent-encoded characters should be decoded."""
        gltf = pygltflib.GLTF2()
        gltf.images = [
            pygltflib.Image(uri="textures/my%20texture.png")
        ]
        gltf.textures = [pygltflib.Texture(source=0)]
        self.assertEqual(gen.resolve_texture_path(gltf, 0), "textures/my texture.png")


class TestUnpackFeature(unittest.TestCase):
    def tearDown(self):
        # Clean up extracted textures
        import shutil
        tex_dir = FIXTURES / "textures"
        if tex_dir.exists():
            shutil.rmtree(tex_dir)
        for f in FIXTURES.glob("*.modelmeta.json"):
            f.unlink()

    def test_unpack_data_uri(self):
        import subprocess
        subprocess.run(
            ["python", str(Path(__file__).parent.parent / "gltf_meta_generator.py"),
             str(FIXTURES / "embedded_texture.gltf"), "--unpack"],
            check=True,
        )
        meta_path = FIXTURES / "embedded_texture.modelmeta.json"
        self.assertTrue(meta_path.exists())
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        mat = _get_material(data, 0)
        self.assertEqual(mat["textures"]["base_color"], "textures/embedded_texture_texture_0.png")
        self.assertTrue((FIXTURES / "textures" / "embedded_texture_texture_0.png").exists())

    def test_unpack_buffer_view(self):
        import subprocess
        subprocess.run(
            ["python", str(Path(__file__).parent.parent / "gltf_meta_generator.py"),
             str(FIXTURES / "glb_embedded_image.glb"), "--unpack"],
            check=True,
        )
        meta_path = FIXTURES / "glb_embedded_image.modelmeta.json"
        self.assertTrue(meta_path.exists())
        data = json.loads(meta_path.read_text(encoding="utf-8"))
        mat = _get_material(data, 0)
        self.assertEqual(mat["textures"]["base_color"], "textures/glb_embedded_image_texture_0.png")
        tex_path = FIXTURES / "textures" / "glb_embedded_image_texture_0.png"
        self.assertTrue(tex_path.exists())
        # Verify it's a valid PNG
        self.assertEqual(tex_path.read_bytes()[:8], b"\x89PNG\r\n\x1a\n")

    def test_no_unpack_returns_null_for_embedded(self):
        result = gen.generate_meta(FIXTURES / "embedded_texture.gltf")
        mat = _get_material(result, 0)
        self.assertIsNone(mat["textures"]["base_color"])


class TestGlobMode(unittest.TestCase):
    def test_glob_batch_processing(self):
        import subprocess
        import tempfile
        import os
        with tempfile.TemporaryDirectory() as tmpdir:
            pattern = str(FIXTURES / "*.gltf")
            subprocess.run(
                ["python", str(Path(__file__).parent.parent / "gltf_meta_generator.py"), pattern, "-o", tmpdir + "/"],
                check=True,
            )
            # Should have generated metadata for all .gltf files
            names = {p.name.replace(".modelmeta.json", "") for p in Path(tmpdir).glob("*.modelmeta.json")}
            self.assertIn("static_box", names)
            self.assertIn("textured_quad", names)
            self.assertIn("embedded_texture", names)

    def test_glob_no_match(self):
        import subprocess
        import tempfile
        with tempfile.TemporaryDirectory() as tmpdir:
            result = subprocess.run(
                ["python", str(Path(__file__).parent.parent / "gltf_meta_generator.py"), str(FIXTURES / "*.nonexistent"), "-o", tmpdir + "/"],
            )
            self.assertNotEqual(result.returncode, 0)


class TestCLIOutput(unittest.TestCase):
    def test_output_written(self):
        import subprocess
        out_path = FIXTURES / "static_box_cli.modelmeta.json"
        if out_path.exists():
            out_path.unlink()
        subprocess.run(
            ["python", str(Path(__file__).parent.parent / "gltf_meta_generator.py"), str(FIXTURES / "static_box.gltf"), "-o", str(out_path)],
            check=True,
        )
        self.assertTrue(out_path.exists())
        data = json.loads(out_path.read_text(encoding="utf-8"))
        self.assertEqual(data["model_type"], "static")
        out_path.unlink()


if __name__ == "__main__":
    unittest.main()
