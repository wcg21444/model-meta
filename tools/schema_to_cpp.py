#!/usr/bin/env python3
"""Schema-to-C++ exporter with libclang validation & sync.

Reads schema/modelmeta.schema.json and generates a C++17 header.
Supports:
    --sync <existing.h>   diff against existing header and rewrite

Naming conventions:
    - Struct names   : PascalCase (from Schema struct name)
    - Member variables: snake_case (from Schema field name)
    - Enum class names: PascalCase derived from field name
"""

import sys
import json
import argparse
import tempfile
import textwrap
from pathlib import Path
from typing import Dict, List, Any, Optional, Set

# ---------------------------------------------------------------------------
# libclang setup
# ---------------------------------------------------------------------------

def _find_libclang() -> Optional[str]:
    """Probe common Windows libclang.dll locations."""
    import os
    candidates = [
        r"C:\Program Files\LLVM\bin\libclang.dll",
        r"C:\Program Files (x86)\LLVM\bin\libclang.dll",
    ]
    # Also check PATH
    for name in ("libclang.dll", "libclang.so", "libclang.dylib"):
        for path_dir in os.environ.get("PATH", "").split(os.pathsep):
            cand = Path(path_dir) / name
            if cand.exists():
                return str(cand)
    for c in candidates:
        if Path(c).exists():
            return c
    return None


_LIBCLANG_CONFIGURED = False


def _configure_libclang():
    """Configure clang.cindex.Config with the shared library path (idempotent)."""
    global _LIBCLANG_CONFIGURED
    if _LIBCLANG_CONFIGURED:
        return
    try:
        import clang.cindex
    except ImportError as exc:
        print("ERROR: clang Python bindings not installed.", file=sys.stderr)
        print("  pip install libclang", file=sys.stderr)
        sys.exit(1)

    lib = _find_libclang()
    if lib and not clang.cindex.Config.loaded:
        clang.cindex.Config.set_library_file(lib)
    _LIBCLANG_CONFIGURED = True


# ---------------------------------------------------------------------------
# C++ keyword guard
# ---------------------------------------------------------------------------

_CPP_KEYWORDS: Set[str] = {
    "alignas", "alignof", "and", "and_eq", "asm", "atomic_cancel", "atomic_commit",
    "atomic_noexcept", "auto", "bitand", "bitor", "bool", "break", "case", "catch",
    "char", "char8_t", "char16_t", "char32_t", "class", "compl", "concept", "const",
    "consteval", "constexpr", "constinit", "const_cast", "continue", "co_await",
    "co_return", "co_yield", "decltype", "default", "delete", "do", "double",
    "dynamic_cast", "else", "enum", "explicit", "export", "extern", "false", "float",
    "for", "friend", "goto", "if", "inline", "int", "long", "mutable", "namespace",
    "new", "noexcept", "not", "not_eq", "nullptr", "operator", "or", "or_eq",
    "private", "protected", "public", "register", "reinterpret_cast", "requires",
    "return", "short", "signed", "sizeof", "static", "static_assert", "static_cast",
    "struct", "switch", "synchronized", "template", "this", "thread_local", "throw",
    "true", "try", "typedef", "typeid", "typename", "union", "unsigned", "using",
    "virtual", "void", "volatile", "wchar_t", "while", "xor", "xor_eq",
}


def _escape_cpp(name: str) -> str:
    """Append underscore if name is a C++ keyword."""
    return name + "_" if name in _CPP_KEYWORDS else name


def _snake_to_pascal(name: str) -> str:
    """Convert snake_case to PascalCase."""
    return "".join(word.capitalize() for word in name.split("_"))


# ---------------------------------------------------------------------------
# C++ code generation
# ---------------------------------------------------------------------------

class SchemaToCpp:
    """Converts a Schema JSON dict to C++17 source code."""

    def __init__(self, schema_data: dict):
        self.schema = schema_data
        self.structs = {s["name"]: s for s in schema_data.get("structs", [])}
        self._enum_names: Dict[str, str] = {}  # field key -> enum class name
        self._generated_enums: Set[str] = set()

    def _cpp_type(self, field: dict, parent_struct_name: str = "") -> str:
        t = field["type"]
        if t == "string":
            base = "std::string"
        elif t == "float":
            base = "float"
        elif t == "bool":
            base = "bool"
        elif t == "int":
            base = "int"
        elif t == "float3":
            base = "std::array<float, 3>"
        elif t == "enum":
            enum_name = _snake_to_pascal(field["name"])
            key = f"{parent_struct_name}.{field['name']}"
            self._enum_names[key] = enum_name
            base = enum_name
        elif t == "array":
            item = field.get("item_type", "void")
            item_cpp = self._cpp_type_simple(item)
            base = f"std::vector<{item_cpp}>"
        else:
            # struct reference
            base = t

        if field.get("optional", False):
            # Don't wrap std::optional around already-optional-looking things?
            # In C++ we explicitly wrap everything.
            base = f"std::optional<{base}>"
        return base

    def _cpp_type_simple(self, type_name: str) -> str:
        """Resolve a plain type name (used for array items)."""
        if type_name == "string":
            return "std::string"
        if type_name == "float":
            return "float"
        if type_name == "bool":
            return "bool"
        if type_name == "int":
            return "int"
        return type_name  # struct name

    def _generate_enum(self, field: dict, struct_name: str) -> str:
        enum_name = _snake_to_pascal(field["name"])
        if enum_name in self._generated_enums:
            return ""
        self._generated_enums.add(enum_name)

        values = field.get("enum_values", [])
        lines = [f"enum class {enum_name} {{"]
        for v in values:
            lines.append(f"    {_escape_cpp(v.upper())},")
        lines.append("};")
        return "\n".join(lines) + "\n"

    def _generate_struct(self, struct: dict) -> str:
        lines = []
        if struct.get("doc"):
            lines.append(f"// {struct['doc']}")
        lines.append(f"struct {struct['name']} {{")

        for field in struct.get("fields", []):
            if field["type"] == "enum":
                enum_src = self._generate_enum(field, struct["name"])
                if enum_src:
                    lines.append(textwrap.indent(enum_src, "    ").rstrip())
                    lines.append("")

            cpp_t = self._cpp_type(field, struct["name"])
            member = _escape_cpp(field["name"])
            lines.append(f"    {cpp_t} {member};")

        lines.append("};")
        return "\n".join(lines)

    def _struct_dependencies(self, struct: dict) -> Set[str]:
        """Return the set of struct names this struct depends on."""
        deps: Set[str] = set()
        for field in struct.get("fields", []):
            t = field["type"]
            if t in self.structs and t != struct["name"]:
                deps.add(t)
            if t == "array":
                item = field.get("item_type")
                if item and item in self.structs and item != struct["name"]:
                    deps.add(item)
        return deps

    def _topo_sort_structs(self) -> List[dict]:
        """Topological sort of structs so dependencies are defined first."""
        in_degree: Dict[str, int] = {name: 0 for name in self.structs}
        adj: Dict[str, List[str]] = {name: [] for name in self.structs}

        for name, struct in self.structs.items():
            for dep in self._struct_dependencies(struct):
                adj[dep].append(name)
                in_degree[name] += 1

        queue = [name for name, deg in in_degree.items() if deg == 0]
        order: List[str] = []
        while queue:
            name = queue.pop(0)
            order.append(name)
            for neighbor in adj[name]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)

        if len(order) != len(self.structs):
            # Cyclic dependency — schema validation should catch this, but handle gracefully
            remaining = [self.structs[n] for n in self.structs if n not in order]
            return [self.structs[n] for n in order] + remaining

        return [self.structs[n] for n in order]

    def generate(self, namespace: str = "modelmeta") -> str:
        """Generate the complete C++ header source."""
        parts = [
            '#pragma once',
            '#include <string>',
            '#include <vector>',
            '#include <array>',
            '#include <optional>',
            '',
            f'namespace {namespace} {{',
            '',
        ]

        # Forward declarations for all enums
        seen_enums: Set[str] = set()
        for struct in self.schema.get("structs", []):
            for field in struct.get("fields", []):
                if field["type"] == "enum":
                    enum_name = _snake_to_pascal(field["name"])
                    if enum_name not in seen_enums:
                        seen_enums.add(enum_name)
                        parts.append(f"enum class {enum_name};")
        if seen_enums:
            parts.append("")

        for struct in self._topo_sort_structs():
            parts.append(self._generate_struct(struct))
            parts.append("")

        parts.append(f"}} // namespace {namespace}")
        parts.append("")
        return "\n".join(parts)


# ---------------------------------------------------------------------------
# libclang validation
# ---------------------------------------------------------------------------

def validate_with_libclang(source: str) -> bool:
    """Parse the generated C++ source with libclang and report diagnostics."""
    _configure_libclang()
    import clang.cindex

    with tempfile.NamedTemporaryFile(mode="w", suffix=".h", delete=False, encoding="utf-8") as f:
        f.write(source)
        tmp_path = f.name

    try:
        index = clang.cindex.Index.create()
        # We pass -x c++ -std=c++17 to ensure C++17 parsing
        tu = index.parse(
            tmp_path,
            args=["-x", "c++", "-std=c++17", "-Wno-unused-private-field"],
        )

        errors = [d for d in tu.diagnostics if d.severity >= clang.cindex.Diagnostic.Error]
        if errors:
            print("libclang validation FAILED:", file=sys.stderr)
            for d in errors:
                print(f"  {d}", file=sys.stderr)
            return False

        print("libclang validation: OK")
        return True
    finally:
        Path(tmp_path).unlink(missing_ok=True)


# ---------------------------------------------------------------------------
# libclang sync / diff
# ---------------------------------------------------------------------------

def parse_existing_header(path: Path) -> Dict[str, Any]:
    """Use libclang to parse an existing C++ header and extract struct/field info."""
    _configure_libclang()
    import clang.cindex

    index = clang.cindex.Index.create()
    abs_path = str(path.resolve())
    tu = index.parse(
        abs_path,
        args=["-x", "c++", "-std=c++17", "-Wno-unused-private-field"],
    )

    existing: Dict[str, Any] = {"structs": {}, "enums": {}}
    target_path = str(path.resolve())

    def _is_in_target(node) -> bool:
        loc = node.location
        if not loc.file:
            return False
        return str(loc.file) == target_path

    def visit(node, parent_struct=None):
        try:
            kind = node.kind
        except ValueError:
            # libclang binding too old for this cursor kind — recurse anyway
            for child in node.get_children():
                visit(child, parent_struct)
            return

        if kind == clang.cindex.CursorKind.STRUCT_DECL and node.spelling and _is_in_target(node):
            existing["structs"][node.spelling] = {"fields": []}
            for child in node.get_children():
                visit(child, node.spelling)
        elif kind == clang.cindex.CursorKind.FIELD_DECL and parent_struct and _is_in_target(node):
            field_type = node.type.spelling
            existing["structs"][parent_struct]["fields"].append({
                "name": node.spelling,
                "type": field_type,
            })
        elif kind == clang.cindex.CursorKind.ENUM_DECL and node.spelling and _is_in_target(node):
            values = []
            for c in node.get_children():
                try:
                    if c.kind == clang.cindex.CursorKind.ENUM_CONSTANT_DECL:
                        values.append(c.spelling)
                except ValueError:
                    pass
            existing["enums"][node.spelling] = values
        else:
            for child in node.get_children():
                visit(child, parent_struct)

    visit(tu.cursor)
    return existing


def diff_schema_vs_cpp(schema_data: dict, existing: Dict[str, Any]) -> List[str]:
    """Compare Schema definitions with existing C++ definitions. Returns human-readable diff lines."""
    diffs: List[str] = []
    structs = {s["name"]: s for s in schema_data.get("structs", [])}

    # Check structs present in schema but missing in C++
    for name, sdef in structs.items():
        if name not in existing["structs"]:
            diffs.append(f"+ struct {name} (new)")
            continue

        cpp_fields = {f["name"]: f["type"] for f in existing["structs"][name]["fields"]}
        for field in sdef.get("fields", []):
            fname = _escape_cpp(field["name"])
            if fname not in cpp_fields:
                diffs.append(f"+ {name}::{fname} (new field)")
            # Note: type diffing is tricky due to optional/vector/array wrappers;
            # we report name-level differences for now.

        cpp_field_names = set(cpp_fields.keys())
        schema_field_names = {_escape_cpp(f["name"]) for f in sdef.get("fields", [])}
        for extra in cpp_field_names - schema_field_names:
            diffs.append(f"- {name}::{extra} (removed)")

    # Check structs present in C++ but missing in schema
    for name in existing["structs"]:
        if name not in structs:
            diffs.append(f"- struct {name} (removed)")

    return diffs


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Export Schema to C++17 struct header.")
    parser.add_argument("schema", help="Path to schema JSON")
    parser.add_argument("-o", "--output", required=True, help="Output C++ header path")
    parser.add_argument("--namespace", default="modelmeta", help="C++ namespace (default: modelmeta)")
    parser.add_argument("--sync", help="Existing header to diff against before overwriting")
    parser.add_argument("--no-validate", action="store_true", help="Skip libclang validation")
    args = parser.parse_args()

    schema_data = json.loads(Path(args.schema).read_text(encoding="utf-8"))

    gen = SchemaToCpp(schema_data)
    source = gen.generate(namespace=args.namespace)

    # Validation
    if not args.no_validate:
        _configure_libclang()
        try:
            ok = validate_with_libclang(source)
            if not ok:
                sys.exit(1)
        except Exception as exc:
            print(f"libclang validation error: {exc}", file=sys.stderr)
            print("(Use --no-validate to skip)", file=sys.stderr)
            sys.exit(1)

    # Sync / diff
    if args.sync:
        _configure_libclang()
        try:
            existing = parse_existing_header(Path(args.sync))
            diffs = diff_schema_vs_cpp(schema_data, existing)
            if diffs:
                print(f"Sync differences ({len(diffs)} items):")
                for d in diffs:
                    print(f"  {d}")
            else:
                print("Sync: no differences detected.")
        except Exception as exc:
            print(f"Sync parse error: {exc}", file=sys.stderr)

    # Write output
    out_path = Path(args.output)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(source, encoding="utf-8")
    print(f"C++ header written to: {out_path}")


if __name__ == "__main__":
    main()
