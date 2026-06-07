"""DuckDB catalog helpers."""

from __future__ import annotations

from pathlib import Path


def database_exists(path: Path) -> bool:
    """Return whether a local DuckDB database exists."""

    return path.exists() and path.is_file()
