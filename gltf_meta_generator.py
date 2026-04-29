"""CLI entrypoint for generating .modelmeta.json files from GLTF/GLB models."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from generator_configs import DEFAULT_CONFIG, GeneratorConfig
from modelmeta.gltf_reader import load_model
from modelmeta.metadata_builder import build_metadata
from modelmeta.output_writer import iter_input_files, resolve_output_path, write_metadata
from modelmeta.schema_loader import load_schema, validate_metadata
from modelmeta.texture_unpacker import unpack_embedded_textures
from symbol_map import apply_json_field_mapping


_NAMING_CHOICES = ["BigCamel", "smallCamel", "snake", "SCREAMING"]


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate model metadata JSON from GLTF/GLB files.")
    parser.add_argument("input", help="Input .gltf/.glb file or glob pattern.")
    parser.add_argument("-o", "--output", help="Output JSON file or output directory for glob mode.")
    parser.add_argument("--schema", default=str(DEFAULT_CONFIG.schema_path), help="JSON schema path.")
    parser.add_argument("--unpack", action="store_true", help="Extract embedded textures.")
    parser.add_argument("--texture-output", help="Directory for unpacked textures.")
    parser.add_argument(
        "--float-precision",
        type=int,
        default=DEFAULT_CONFIG.float_precision,
        help="Number of digits used for floating point rounding. Use -1 to disable.",
    )
    parser.add_argument("--namespace", default=DEFAULT_CONFIG.namespace, help="Optional C++ namespace.")
    parser.add_argument(
        "--type-naming", default=DEFAULT_CONFIG.type_naming, choices=_NAMING_CHOICES, help="C++ struct naming style."
    )
    parser.add_argument(
        "--member-naming", default=DEFAULT_CONFIG.member_naming, choices=_NAMING_CHOICES, help="C++ member naming style."
    )
    parser.add_argument(
        "--enum-naming", default=DEFAULT_CONFIG.enum_naming, choices=_NAMING_CHOICES, help="C++ enum naming style."
    )
    parser.add_argument(
        "--function-naming",
        default=DEFAULT_CONFIG.function_naming,
        choices=_NAMING_CHOICES,
        help="C++ function naming style.",
    )
    parser.add_argument("--root-type", default=DEFAULT_CONFIG.root_cpp_type, help="Root C++ type name.")
    parser.add_argument("--parse-function", default=DEFAULT_CONFIG.parse_function, help="Parse function name.")
    return parser.parse_args(argv)


def config_from_args(args: argparse.Namespace) -> GeneratorConfig:
    precision = None if args.float_precision is not None and args.float_precision < 0 else args.float_precision
    return GeneratorConfig(
        namespace=args.namespace,
        type_naming=args.type_naming,
        member_naming=args.member_naming,
        enum_naming=args.enum_naming,
        function_naming=args.function_naming,
        float_precision=precision,
        unpack_textures=args.unpack,
        texture_output_dir=args.texture_output or DEFAULT_CONFIG.texture_output_dir,
        output_path=Path(args.output) if args.output else None,
        schema_path=Path(args.schema),
        root_cpp_type=args.root_type,
        parse_function=args.parse_function,
    )


def generate_for_file(model_path: Path, output_arg: Path | None, is_glob: bool, config: GeneratorConfig) -> Path:
    output_path = resolve_output_path(model_path, output_arg, is_glob)
    document = load_model(model_path)
    texture_overrides = {}
    if config.unpack_textures:
        texture_overrides = unpack_embedded_textures(document, output_path, config.texture_output_dir)

    metadata = build_metadata(document, config.float_precision, texture_overrides)
    mapped_metadata = apply_json_field_mapping(metadata)
    schema = load_schema(config.schema_path)
    validate_metadata(mapped_metadata, schema)
    write_metadata(mapped_metadata, output_path)
    return output_path


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    config = config_from_args(args)
    try:
        files, is_glob = iter_input_files(args.input)
        outputs = [generate_for_file(path, config.output_path, is_glob, config) for path in files]
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1

    for output in outputs:
        print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
