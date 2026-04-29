"""Unified configuration for the model-meta toolchain.

Defines parameters for all three scripts:
  - gltf_meta_generator.py   (GLTF → .modelmeta.json)
  - cpp_json_codegen.py      (JSON schema → C++ to_json/from_json)
  - schema_to_cpp.py         (JSON/YAML schema → C++ struct/enum header)

CLI overrides::

    python gltf_model_meta.py --glob-pattern "assets/**/*.glb" \\
        --cpp-header-output include/out.h --cpp-source-output src/out.cpp

Every --option falls back to the value in DEFAULT_CONFIG (or the dataclass
default) when omitted on the command line.

CMake integration (recommended pattern)::

    set(MODELMETA_GLOB        "assets/**/*.glb")
    set(MODELMETA_HEADER      "${CMAKE_CURRENT_BINARY_DIR}/modelmeta.h")
    set(MODELMETA_SOURCE      "${CMAKE_CURRENT_BINARY_DIR}/modelmeta.cpp")

    add_custom_command(
        OUTPUT  ${MODELMETA_HEADER} ${MODELMETA_SOURCE}
        COMMAND ${Python3_EXECUTABLE} "${CMAKE_SOURCE_DIR}/gltf_model_meta.py"
                --glob-pattern       "${MODELMETA_GLOB}"
                --cpp-header-output  "${MODELMETA_HEADER}"
                --cpp-source-output  "${MODELMETA_SOURCE}"
        DEPENDS ${CMAKE_SOURCE_DIR}/schema/modelmeta.schema.json
                ${CMAKE_SOURCE_DIR}/assets/...
        COMMENT "Generating model-meta C++ sources"
    )
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class ModelMetaConfig:
    """Mutable configuration – CLI args override these defaults at runtime."""

    # =========================================================================
    # GLTF meta generator
    # =========================================================================
    float_precision: Optional[int] = 6
    unpack_textures: bool = True
    texture_output_dir: str = "textures"
    glob_pattern: Optional[str] = "assets/**/*"
    output_path: Optional[Path] = None
    schema_path: Path = Path("schema/modelmeta.schema.json")

    # =========================================================================
    # Naming conventions (shared by all scripts)
    # =========================================================================
    namespace: Optional[str] = None
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
    # cpp_json_codegen.py  (JSON schema → C++ .cpp with to_json/from_json)
    # =========================================================================
    json_schema_path: Path = Path("schema/modelmeta.schema.json")
    cpp_source_output: Path = Path("src/modelmeta.cpp")
    header_include: str = "modelmeta.h"

    # =========================================================================
    # schema_to_cpp.py  (JSON/YAML schema → C++ struct/enum header)
    # =========================================================================
    cpp_schema_path: Path = Path("schema/modelmeta.schema.json")
    cpp_header_output: Path = Path("include/modelmeta.h")
    pch_output: Optional[Path] = Path("include/pch.h")
    debug_yaml: Optional[Path] = None
    module_name: str = "modelmeta"
    additional_includes: List[str] = field(default_factory=list)
    pch_includes: List[str] = field(default_factory=list)
    schema_to_cpp_sync_path: Optional[Path] = None
    schema_to_cpp_skip_clang: bool = False


DEFAULT_CONFIG = ModelMetaConfig()


def _path_type(value: str) -> Path:
    return Path(value)


def build_argparser() -> argparse.ArgumentParser:
    """Return an ArgumentParser covering every field of ModelMetaConfig.

    Each option mirrors a config field.  When the option is omitted the
    DEFAULT_CONFIG / dataclass-default value is preserved unchanged.
    """
    parser = argparse.ArgumentParser(
        description="model-meta toolchain – GLTF → .modelmeta.json + C++ codegen",
    )
    # -- GLTF meta generator ------------------------------------------------
    parser.add_argument("--float-precision", type=int, default=None)
    parser.add_argument(
        "--unpack-textures", dest="unpack_textures",
        action="store_true", default=None,
    )
    parser.add_argument(
        "--no-unpack-textures", dest="unpack_textures",
        action="store_false",
    )
    parser.add_argument("--texture-output-dir", type=str, default=None)
    parser.add_argument("--glob-pattern", type=str, default=None)
    parser.add_argument("--output-path", type=_path_type, default=None)
    parser.add_argument("--schema-path", type=_path_type, default=None)

    # -- Naming conventions --------------------------------------------------
    parser.add_argument("--namespace", type=str, default=None)
    parser.add_argument("--type-naming", type=str, default=None)
    parser.add_argument("--member-naming", type=str, default=None)
    parser.add_argument("--enum-naming", type=str, default=None)
    parser.add_argument("--function-naming", type=str, default=None)

    # -- C++ shared identifiers ----------------------------------------------
    parser.add_argument("--root-cpp-type", type=str, default=None)
    parser.add_argument("--parse-function", type=str, default=None)

    # -- cpp_json_codegen.py ------------------------------------------------
    parser.add_argument("--json-schema-path", type=_path_type, default=None)
    parser.add_argument("--cpp-source-output", type=_path_type, default=None)
    parser.add_argument("--header-include", type=str, default=None)

    # -- schema_to_cpp.py ----------------------------------------------------
    parser.add_argument("--cpp-schema-path", type=_path_type, default=None)
    parser.add_argument("--cpp-header-output", type=_path_type, default=None)
    parser.add_argument("--pch-output", type=_path_type, default=None)
    parser.add_argument("--debug-yaml", type=_path_type, default=None)
    parser.add_argument("--module-name", type=str, default=None)
    parser.add_argument("--additional-includes", nargs="*", default=None)
    parser.add_argument("--pch-includes", nargs="*", default=None)
    parser.add_argument("--schema-to-cpp-sync-path", type=_path_type, default=None)
    parser.add_argument(
        "--skip-clang", dest="schema_to_cpp_skip_clang",
        action="store_true", default=None,
    )
    return parser


def apply_cli_args(config: ModelMetaConfig, args: argparse.Namespace) -> ModelMetaConfig:
    """Return a *new* config with CLI-supplied values overriding *config*.

    Only non-``None`` values in *args* are applied – ``None`` means the
    user did not specify that option.
    """
    overrides: dict = {}
    for attr in vars(args):
        value = getattr(args, attr)
        if value is not None:
            overrides[attr] = value
    if not overrides:
        return config
    # dataclasses.replace creates a new instance preserving frozen/non-frozen
    from dataclasses import replace
    return replace(config, **overrides)


def parse_and_apply(
    config: ModelMetaConfig | None = None,
    argv: list[str] | None = None,
) -> ModelMetaConfig:
    """Convenience: parse CLI *argv* and merge into *config*.

    Returns ``DEFAULT_CONFIG + CLI overrides`` when *config* is ``None``.
    """
    if config is None:
        config = DEFAULT_CONFIG
    parser = build_argparser()
    cli_args = parser.parse_args(argv)
    return apply_cli_args(config, cli_args)