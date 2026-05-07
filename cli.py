"""CLI argument parsing and config resolution for the model-meta toolchain.

Kept separate from ``model_meta_configs.py`` so that the dataclass module
remains pure and safe for external config files to import.
"""

from __future__ import annotations

import argparse
import importlib.util
import sys
from dataclasses import replace
from pathlib import Path
from typing import Any

from model_meta_configs import DEFAULT_CONFIG, ModelMetaConfig


def _path_type(value: str) -> Path:
    return Path(value)


def build_argparser() -> argparse.ArgumentParser:
    """Return an ArgumentParser covering every field of :class:`ModelMetaConfig`.

    Each option mirrors a config field.  When the option is omitted the
    ``DEFAULT_CONFIG`` / dataclass-default value is preserved unchanged.
    """
    parser = argparse.ArgumentParser(
        description="model-meta toolchain - GLTF -> .modelmeta.json + C++ codegen",
    )
    # -- External config injection ------------------------------------------
    parser.add_argument(
        "--configs", type=_path_type, default=None,
        help="Path to an external Python module exporting CONFIG "
             "(ModelMetaConfig instance or dict of overrides). "
             "When provided, this replaces the built-in DEFAULT_CONFIG as the base configuration.",
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
    parser.add_argument(
        "--texture-unpack-policy", type=str, default=None,
        choices=["retain", "cover"],
        help="Unpack policy: 'retain' skips existing texture files; 'cover' overwrites them.",
    )
    parser.add_argument("--texture-output-dir", type=str, default=None)
    parser.add_argument("--texture-output-base", type=_path_type, default=None)
    parser.add_argument("--asset-root", type=_path_type, default=None)
    parser.add_argument("--glob-patterns", type=str, nargs="+", default=None)
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
    parser.add_argument("--cpp-source-output", type=_path_type, default=None)
    parser.add_argument("--header-include", type=str, default=None)

    # -- schema_to_cpp.py ----------------------------------------------------
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

    Only non-``None`` values in *args* are applied -- ``None`` means the
    user did not specify that option.
    """
    overrides: dict = {}
    for attr in vars(args):
        if attr == "configs":
            continue  # handled earlier by _extract_configs_path / load_external_config
        value = getattr(args, attr)
        if value is not None:
            overrides[attr] = value
    if not overrides:
        return config
    return replace(config, **overrides)


def _extract_configs_path(argv: list[str] | None) -> Path | None:
    """Extract --configs value from raw argv before full arg parsing."""
    if argv is None:
        argv = sys.argv[1:]
    if not argv:
        return None
    for i, arg in enumerate(argv):
        if arg == "--configs" and i + 1 < len(argv):
            return Path(argv[i + 1])
        if arg.startswith("--configs="):
            return Path(arg.split("=", 1)[1])
    return None


def load_external_config(path: Path) -> ModelMetaConfig:
    """Dynamically load a :class:`ModelMetaConfig` from an external Python module.

    The module must export a ``CONFIG`` or ``DEFAULT_CONFIG`` attribute, which can be:

    - A :class:`ModelMetaConfig` instance (used directly)
    - A ``dict`` of keyword overrides (applied on top of ``DEFAULT_CONFIG``)
    """
    resolved = path.resolve()
    if not resolved.is_file():
        raise FileNotFoundError(f"Config file not found: {resolved}")

    spec = importlib.util.spec_from_file_location("_external_model_meta_config", str(resolved))
    if spec is None or spec.loader is None:
        raise ImportError(f"Cannot load config module from: {resolved}")
    module = importlib.util.module_from_spec(spec)
    sys.modules["_external_model_meta_config"] = module
    spec.loader.exec_module(module)

    external: Any = getattr(module, "CONFIG", None) or getattr(module, "DEFAULT_CONFIG", None)
    if external is None:
        raise ValueError(
            f"Config file {resolved} must export CONFIG or DEFAULT_CONFIG "
            f"(a ModelMetaConfig instance or a dict of overrides)"
        )

    if isinstance(external, ModelMetaConfig):
        return external
    if isinstance(external, dict):
        return replace(DEFAULT_CONFIG, **external)
    # Handle dataclass instances from a different module (same class name, different identity)
    try:
        from dataclasses import asdict
        return replace(DEFAULT_CONFIG, **asdict(external))
    except (TypeError, AttributeError):
        raise TypeError(
            f"CONFIG must be a ModelMetaConfig, dict, or dataclass, got {type(external).__name__}"
        ) from None


def parse_and_apply(
    config: ModelMetaConfig | None = None,
    argv: list[str] | None = None,
) -> ModelMetaConfig:
    """Parse CLI *argv* and merge into *config*.

    1. If ``--configs <path>`` is provided, the external module's ``CONFIG``
       replaces ``DEFAULT_CONFIG`` as the base.
    2. Remaining CLI flags override the base config.
    """
    if config is None:
        external_path = _extract_configs_path(argv)
        if external_path:
            config = load_external_config(external_path)
        else:
            config = DEFAULT_CONFIG
    parser = build_argparser()
    cli_args = parser.parse_args(argv)
    return apply_cli_args(config, cli_args)
