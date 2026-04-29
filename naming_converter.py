"""Naming style conversion utilities.

Pipeline: raw name -> snake_case (canonical) -> target style.
"""

from __future__ import annotations

import re


def to_snake(name: str) -> str:
    """Convert any common naming style to snake_case.

    Supports BigCamel, smallCamel, snake, SCREAMING_SNAKE, kebab-case.
    """
    if not name:
        return name

    # Normalize hyphens to underscores first
    name = name.replace("-", "_")

    # If already contains underscores, treat as snake/SCREAMING structure
    if "_" in name:
        return name.lower()

    # Insert underscore before uppercase letters (except at start)
    # Handle consecutive caps correctly: URLParser -> URL_Parser
    name = re.sub(r"([A-Z]+)([A-Z][a-z])", r"\1_\2", name)
    name = re.sub(r"([a-z\d])([A-Z])", r"\1_\2", name)

    return name.lower()


def from_snake(name: str, style: str) -> str:
    """Convert snake_case to the specified naming style.

    Styles:
      - snake       : foo_bar
      - BigCamel    : FooBar
      - smallCamel  : fooBar
      - SCREAMING   : FOO_BAR
    """
    parts = [p for p in name.split("_") if p]

    if not parts:
        return name

    if style == "snake":
        return "_".join(parts).lower()
    if style == "BigCamel":
        return "".join(p.capitalize() for p in parts)
    if style == "smallCamel":
        return parts[0].lower() + "".join(p.capitalize() for p in parts[1:])
    if style == "SCREAMING":
        return "_".join(p.upper() for p in parts)

    # Unknown style: fall back to snake
    return "_".join(parts).lower()


def convert_name(name: str, style: str) -> str:
    """Normalize name to snake_case then convert to target style."""
    return from_snake(to_snake(name), style)
