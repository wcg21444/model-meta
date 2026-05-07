"""Pure configuration dataclass for the model-meta toolchain.

Defines parameters for all three scripts:
  - gltf_meta_generator.py   (GLTF → .modelmeta.json)
  - schema_to_cpp.py         (JSON Schema → C++ struct/enum header)
  - cpp_json_codegen.py      (JSON Schema → C++ to_json/from_json)

This module is intentionally free of CLI logic so that downstream projects
can import ``ModelMetaConfig`` without pulling in argument‑parsing machinery.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ModelMetaConfig:
    """All configuration fields with sensible defaults."""

    # =========================================================================
    # GLTF meta generator
    # =========================================================================
    float_precision: Optional[int] = 6
    unpack_textures: bool = True
    texture_unpack_policy: str = "retain"          # "retain" = skip existing, create new; "cover" = overwrite
    texture_output_dir: str = ""
    texture_output_base: Optional[Path] = Path(
        "D:\\Codes\\vscode\\python\\directcraft_utils\\model-meta\\assets\\models\\textures"
    )  # None = relative to .modelmeta.json; Path = absolute dir
    asset_root: Optional[Path] = Path(
        "D:\\Codes\\vscode\\python\\directcraft_utils\\model-meta\\assets\\"
    )  # for normalizing output paths to asset-relative
    glob_patterns: List[str] = field(default_factory=lambda: ["assets/**/*"])
    output_path: Optional[Path] = None  # None = next to .gltf/.glb; Path = explicit output path for .modelmeta.json
    schema_path: Path = Path("schema/modelmeta.schema.json")

    # =========================================================================
    # Naming conventions (shared by all scripts)
    # =========================================================================
    namespace: Optional[str] = "GLTFModelMeta"
    type_naming: str = "BigCamel"
    member_naming: str = "snake"
    enum_naming: str = "BigCamel"
    function_naming: str = "BigCamel"

    # =========================================================================
    # C++ codegen – shared identifiers
    # =========================================================================
    root_cpp_type: str = "ModelMeta"
    parse_function: str = "Parse"

    # =========================================================================
    # cpp_json_codegen.py  (JSON Schema → C++ .cpp with to_json/from_json)
    # =========================================================================
    cpp_source_output: Path = Path("src/modelmeta.cpp")
    header_include: str = "modelmeta.h"

    # =========================================================================
    # schema_to_cpp.py  (JSON Schema → C++ struct/enum header)
    # =========================================================================
    cpp_header_output: Path = Path("include/modelmeta.h")
    pch_output: Optional[Path] = Path("include/pch.h")
    debug_yaml: Optional[Path] = None
    module_name: str = "modelmeta"
    additional_includes: List[str] = field(default_factory=list)
    pch_includes: List[str] = field(default_factory=list)
    schema_to_cpp_sync_path: Optional[Path] = None
    schema_to_cpp_skip_clang: bool = False


DEFAULT_CONFIG = ModelMetaConfig()
