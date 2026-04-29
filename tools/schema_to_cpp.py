"""Generate C++17 structs from the model metadata JSON Schema.

All parameters are read from model_meta_configs.py (DEFAULT_CONFIG).
Edit that file to configure schema, output, naming, and other options.
"""

from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_meta_configs import DEFAULT_CONFIG, ModelMetaConfig
from naming_converter import convert_name
from tools.cpp_schema import (
    CppEnum,
    CppStruct,
    build_structs,
    load_schema,
    namespace_close,
    namespace_open,
)


def render_enum(enum: CppEnum) -> str:
    """Render a single enum class with NLOHMANN_JSON_SERIALIZE_ENUM."""
    lines = [f"enum class {enum.cpp_name} {{"]
    for value in enum.values:
        lines.append(f"  {value},")
    lines.append("};")
    # nlohmann macro requires {EnumValue, "json_string"} pairs
    pairs = [f"{{{enum.cpp_name}::{v}, \"{v}\"}}" for v in enum.values]
    lines.append(
        f"NLOHMANN_JSON_SERIALIZE_ENUM({enum.cpp_name}, {{\n    {', '.join(pairs)}\n}})"
    )
    lines.append("")
    return "\n".join(lines)


def render_header(config: ModelMetaConfig) -> str:
    root_type = convert_name(config.root_cpp_type, config.type_naming)
    parse_function = convert_name(config.parse_function, config.function_naming)
    schema = load_schema(config.schema_path)
    structs, enums = build_structs(schema, root_type)

    lines: list[str] = [
        "#pragma once",
        "",
        "#include <string>",
        "#include <vector>",
        "",
        "#include <nlohmann/json.hpp>",
        "",
    ]
    if config.namespace:
        lines.append(namespace_open(config.namespace).rstrip())
        lines.append("")

    # Render enums first (before structs that reference them)
    for enum in enums:
        lines.append(render_enum(enum))

    for struct in structs:
        lines.append(f"struct {struct.cpp_name} {{")
        if struct.fields:
            for field in struct.fields:
                lines.append(f"  {field.cpp_type} {field.member_name}{{}};")
        lines.append("};")
        lines.append("")

    lines.append(f"{root_type} {parse_function}(const std::string& jsonStr);")
    lines.append("")
    if config.namespace:
        lines.append(namespace_close(config.namespace).rstrip())
        lines.append("")
    return "\n".join(lines)


def validate_with_clang(header_path: Path) -> None:
    try:
        from clang import cindex
    except ImportError:
        print(
            "warning: clang Python bindings are not installed; skipped libclang validation",
            file=sys.stderr,
        )
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
    diagnostics = [
        diag for diag in translation_unit.diagnostics if diag.severity >= diag.Error
    ]
    if diagnostics:
        message = "\n".join(str(diag) for diag in diagnostics)
        raise RuntimeError(f"libclang validation failed:\n{message}")


def main(config: ModelMetaConfig | None = None) -> int:
    if config is None:
        config = DEFAULT_CONFIG
    output = config.cpp_header_output
    try:
        header = render_header(config)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(header, encoding="utf-8")
        if config.schema_to_cpp_sync_path:
            sync_path = config.schema_to_cpp_sync_path
            if sync_path.resolve() != output.resolve():
                sync_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copyfile(output, sync_path)
        if not config.schema_to_cpp_skip_clang:
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