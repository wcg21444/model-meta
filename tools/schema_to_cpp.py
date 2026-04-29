"""Generate C++17 structs from the model metadata JSON Schema."""

from __future__ import annotations

import argparse
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generator_configs import DEFAULT_CONFIG
from naming_converter import convert_name
from tools.cpp_schema import build_structs, load_schema, namespace_close, namespace_open


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate a C++17 header from a JSON Schema.")
    parser.add_argument("schema", help="Input JSON Schema.")
    parser.add_argument("-o", "--output", required=True, help="Output header path.")
    parser.add_argument("--namespace", default=DEFAULT_CONFIG.namespace, help="Optional C++ namespace, e.g. dc::meta.")
    parser.add_argument("--root-type", default=DEFAULT_CONFIG.root_cpp_type, help="Root C++ type name.")
    parser.add_argument("--parse-function", default=DEFAULT_CONFIG.parse_function, help="Parse function declaration name.")
    parser.add_argument("--sync", help="Existing header to sync. The output path is rewritten from schema.")
    parser.add_argument("--skip-clang", action="store_true", help="Skip optional libclang validation.")
    return parser.parse_args(argv)


def render_header(schema_path: Path, namespace: str | None, root_type: str, parse_function: str) -> str:
    root_type = convert_name(root_type, DEFAULT_CONFIG.type_naming)
    parse_function = convert_name(parse_function, DEFAULT_CONFIG.function_naming)
    schema = load_schema(schema_path)
    structs = build_structs(schema, root_type)
    lines: list[str] = [
        "#pragma once",
        "",
        "#include <string>",
        "#include <vector>",
        "",
        "#include <nlohmann/json.hpp>",
        "",
    ]
    if namespace:
        lines.append(namespace_open(namespace).rstrip())
        lines.append("")
    for struct in structs:
        lines.append(f"struct {struct.cpp_name} {{")
        if struct.fields:
            for field in struct.fields:
                lines.append(f"  {field.cpp_type} {field.member_name}{{}};")
        lines.append("};")
        lines.append("")
    lines.append(f"{root_type} {parse_function}(const std::string& jsonStr);")
    lines.append("")
    if namespace:
        lines.append(namespace_close(namespace).rstrip())
        lines.append("")
    return "\n".join(lines)


def validate_with_clang(header_path: Path) -> None:
    try:
        from clang import cindex
    except ImportError:
        print("warning: clang Python bindings are not installed; skipped libclang validation", file=sys.stderr)
        return

    try:
        index = cindex.Index.create()
        translation_unit = index.parse(
            str(header_path),
            args=["-std=c++17", "-x", "c++", "-I", str(header_path.parent)],
        )
    except Exception as exc:
        print(
            "warning: libclang is not available; skipped validation. "
            "Install libclang or configure clang.cindex.Config.set_library_file(). "
            f"Details: {exc}",
            file=sys.stderr,
        )
        return
    diagnostics = [diag for diag in translation_unit.diagnostics if diag.severity >= diag.Error]
    if diagnostics:
        message = "\n".join(str(diag) for diag in diagnostics)
        raise RuntimeError(f"libclang validation failed:\n{message}")


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output)
    try:
        header = render_header(Path(args.schema), args.namespace, args.root_type, args.parse_function)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(header, encoding="utf-8")
        if args.sync:
            sync_path = Path(args.sync)
            if sync_path.resolve() != output.resolve():
                sync_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(output, sync_path)
        if not args.skip_clang:
            with tempfile.TemporaryDirectory() as tmp:
                validation_path = Path(tmp) / output.name
                validation_path.write_text(header, encoding="utf-8")
                validate_with_clang(validation_path)
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
