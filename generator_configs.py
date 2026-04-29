"""Default configuration for the model metadata generator."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Optional


@dataclass(frozen=True)
class GeneratorConfig:
    namespace: Optional[str] = None
    type_naming: str = "BigCamel"
    member_naming: str = "snake"
    enum_naming: str = "BigCamel"
    function_naming: str = "BigCamel"
    float_precision: Optional[int] = 6
    unpack_textures: bool = True
    texture_output_dir: str = "textures"
    glob_pattern: Optional[str] = "assets/**/*"
    output_path: Optional[Path] = None
    schema_path: Path = Path("schema/modelmeta.schema.json")
    root_cpp_type: str = "ModelMeta"
    parse_function: str = "Parse"


DEFAULT_CONFIG = GeneratorConfig()
