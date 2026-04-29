"""Generate nlohmann/json serialization code for model metadata structs.

All parameters are read from model_meta_configs.py (DEFAULT_CONFIG).
Edit that file to configure schema, output, naming, and other options.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_meta_configs import DEFAULT_CONFIG, ModelMetaConfig
from naming_converter import convert_name
from tools.cpp_schema import build_structs, load_schema, namespace_close, namespace_open


def render_cpp(config: ModelMetaConfig) -> str:
    root_type = convert_name(config.root_cpp_type, config.type_naming)
    parse_function = convert_name(config.parse_function, config.function_naming)
    schema = load_schema(config.json_schema_path)
    structs = build_structs(schema, root_type)
    lines: list[str] = [
        f'#include "{config.header_include}"',
        "",
        "#include <utility>",
        "",
    ]
    if config.namespace:
        lines.append(namespace_open(config.namespace).rstrip())
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
    if config.namespace:
        lines.append(namespace_close(config.namespace).rstrip())
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


def main(config: ModelMetaConfig | None = None) -> int:
    if config is None:
        config = DEFAULT_CONFIG
    try:
        code = render_cpp(config)
        config.cpp_source_output.parent.mkdir(parents=True, exist_ok=True)
        config.cpp_source_output.write_text(code, encoding="utf-8")
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    print(config.cpp_source_output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
