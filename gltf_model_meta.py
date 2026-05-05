"""gltf_model_meta.py — Main entry point for the model-meta toolchain.

Runs all three code‑generation steps in order:
  1. gltf_meta_generator.py   – GLTF/GLB → .modelmeta.json
  2. schema_to_cpp.py         – JSON Schema → C++ struct/enum header
  3. cpp_json_codegen.py      – JSON Schema → C++ to_json/from_json

All parameters are read from model_meta_configs.py (DEFAULT_CONFIG).
CLI arguments (e.g. --glob-pattern, --cpp-header-output, --cpp-source-output)
override the corresponding config values.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from model_meta_configs import DEFAULT_CONFIG, ModelMetaConfig, parse_and_apply  # noqa: E402

import gltf_meta_generator  # noqa: E402
import tools.cpp_json_codegen as cpp_json_codegen  # noqa: E402
import tools.schema_to_cpp as schema_to_cpp  # noqa: E402


def step_gltf(config: ModelMetaConfig) -> int:
    print("=== gltf_meta_generator ===", flush=True)
    return gltf_meta_generator.main(config)


def step_schema_to_cpp(config: ModelMetaConfig) -> int:
    print("=== schema_to_cpp ===", flush=True)
    return schema_to_cpp.main(config)


def step_cpp_json_codegen(config: ModelMetaConfig) -> int:
    print("=== cpp_json_codegen ===", flush=True)
    return cpp_json_codegen.main(config)


STEPS = [
    ("gltf_meta_generator", step_gltf),
    ("schema_to_cpp", step_schema_to_cpp),
    ("cpp_json_codegen", step_cpp_json_codegen),
]


def main(argv: list[str] | None = None) -> int:
    config = parse_and_apply(DEFAULT_CONFIG, argv)

    for name, step in STEPS:
        print(f"\n> {name}", flush=True)
        rc = step(config)
        if rc != 0:
            print(f"x {name} failed (exit {rc})", file=sys.stderr)
            return rc
        print(f"+ {name} OK", flush=True)

    print("\nAll steps completed successfully.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())