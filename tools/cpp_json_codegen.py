"""Generate nlohmann/json serialization code for model metadata structs."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from generator_configs import DEFAULT_CONFIG
from naming_converter import convert_name
from tools.cpp_schema import build_structs, load_schema, namespace_close, namespace_open


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate nlohmann/json serialization .cpp code.")
    parser.add_argument("schema", help="Input JSON Schema.")
    parser.add_argument("-o", "--output", required=True, help="Output .cpp path.")
    parser.add_argument("--header", default="modelmeta.h", help="Header include path used by generated .cpp.")
    parser.add_argument("--namespace", default=DEFAULT_CONFIG.namespace, help="Optional C++ namespace, e.g. dc::meta.")
    parser.add_argument("--root-type", default=DEFAULT_CONFIG.root_cpp_type, help="Root C++ type name.")
    parser.add_argument("--parse-function", default=DEFAULT_CONFIG.parse_function, help="Parse function name.")
    return parser.parse_args(argv)


def render_cpp(
    schema_path: Path,
    header: str,
    namespace: str | None,
    root_type: str,
    parse_function: str,
) -> str:
    root_type = convert_name(root_type, DEFAULT_CONFIG.type_naming)
    parse_function = convert_name(parse_function, DEFAULT_CONFIG.function_naming)
    schema = load_schema(schema_path)
    structs = build_structs(schema, root_type)
    lines: list[str] = [
        f'#include "{header}"',
        "",
        "#include <utility>",
        "",
    ]
    if namespace:
        lines.append(namespace_open(namespace).rstrip())
        lines.append("")
    for struct in structs:
        lines.extend(render_to_json(struct.cpp_name, struct.fields))
        lines.append("")
        lines.extend(render_from_json(struct.cpp_name, struct.fields))
        lines.append("")
    lines.extend(
        [
            f"{root_type} {parse_function}(const std::string& jsonStr) {{",
            "  return nlohmann::json::parse(jsonStr).get<" + root_type + ">();",
            "}",
            "",
        ]
    )
    if namespace:
        lines.append(namespace_close(namespace).rstrip())
        lines.append("")
    return "\n".join(lines)


def render_to_json(cpp_name: str, fields: list[object]) -> list[str]:
    lines = [
        f"void to_json(nlohmann::json& j, const {cpp_name}& value) {{",
        "  j = nlohmann::json::object();",
    ]
    for field in fields:
        lines.append(f'  j["{field.json_name}"] = value.{field.member_name};')
    lines.append("}")
    return lines


def render_from_json(cpp_name: str, fields: list[object]) -> list[str]:
    lines = [f"void from_json(const nlohmann::json& j, {cpp_name}& value) {{"]
    for field in fields:
        if field.required:
            lines.append(f'  j.at("{field.json_name}").get_to(value.{field.member_name});')
        else:
            lines.append(f'  if (j.contains("{field.json_name}") && !j.at("{field.json_name}").is_null()) {{')
            lines.append(f'    j.at("{field.json_name}").get_to(value.{field.member_name});')
            lines.append("  }")
    lines.append("}")
    return lines


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    output = Path(args.output)
    try:
        code = render_cpp(Path(args.schema), args.header, args.namespace, args.root_type, args.parse_function)
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(code, encoding="utf-8")
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
