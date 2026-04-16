"""Configuration helpers for Neo4j-backed graph sources."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv


def _as_bool(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _find_dotenv() -> Path | None:
    candidates = []

    for base in (Path.cwd(), Path(__file__).resolve().parent):
        candidates.extend([base, *base.parents])

    seen = set()
    for directory in candidates:
        if directory in seen:
            continue
        seen.add(directory)
        dotenv_path = directory / ".env"
        if dotenv_path.is_file():
            return dotenv_path

    return None


def read_config(section: str = "neo4j") -> Dict[str, Any]:
    """
    Read connection settings for the requested config section.

    Neo4j settings are loaded from the environment after attempting to load a
    project-level ``.env`` file. The returned keys match what the Neo4j
    ``Database`` wrapper expects.
    """
    if section.lower() != "neo4j":
        raise ValueError(f"Unsupported config section: {section}")

    dotenv_path = _find_dotenv()
    if dotenv_path is not None:
        load_dotenv(dotenv_path=dotenv_path, override=False)

    return {
        "uri": os.getenv("NEO4J_URI"),
        "user": os.getenv("NEO4J_USERNAME"),
        "password": os.getenv("NEO4J_PASSWORD"),
        "database": os.getenv("NEO4J_DATABASE", "neo4j"),
        "encrypted": _as_bool(os.getenv("NEO4J_ENCRYPTED"), default=False),
    }
