"""Entrypoint for generating .modelmeta.json files from GLTF/GLB models.

All parameters are read from model_meta_configs.py (DEFAULT_CONFIG).
Edit that file to configure input, output, naming, and other options.
"""

from __future__ import annotations

import sys
from pathlib import Path

from model_meta_configs import DEFAULT_CONFIG, ModelMetaConfig
from modelmeta.gltf_reader import load_model
from modelmeta.metadata_builder import build_metadata
from modelmeta.output_writer import iter_input_files, resolve_output_path, write_metadata
from modelmeta.schema_loader import load_schema, validate_metadata
from modelmeta.texture_unpacker import unpack_embedded_textures
from symbol_map import apply_json_field_mapping


def generate_for_file(model_path: Path, is_glob: bool, config: ModelMetaConfig) -> Path:
    output_path = resolve_output_path(model_path, config.output_path, is_glob)
    document = load_model(model_path)
    texture_overrides: dict[int, str] = {}
    if config.unpack_textures:
        texture_overrides = unpack_embedded_textures(
            document, output_path, config.texture_output_dir,
            config.texture_output_base, config.asset_root,
            config.texture_unpack_policy,
        )

    metadata = build_metadata(document, config.float_precision, texture_overrides)
    mapped_metadata = apply_json_field_mapping(metadata)
    schema = load_schema(config.schema_path)
    validate_metadata(mapped_metadata, schema)
    write_metadata(mapped_metadata, output_path)
    return output_path


def main(config: ModelMetaConfig | None = None) -> int:
    if config is None:
        config = DEFAULT_CONFIG
    if not config.glob_patterns:
        print("error: glob_patterns is empty in configuration. Set it to at least one model path or glob pattern.", file=sys.stderr)
        return 1
    try:
        files, is_glob = iter_input_files(config.glob_patterns)
        outputs = [generate_for_file(path, is_glob, config) for path in files]
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())