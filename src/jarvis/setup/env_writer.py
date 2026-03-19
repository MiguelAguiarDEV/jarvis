"""Utility for reading and writing .env files."""

from __future__ import annotations

from pathlib import Path

from dotenv import dotenv_values, set_key

DEFAULT_ENV_PATH = Path(".env")


def read_env(path: Path = DEFAULT_ENV_PATH) -> dict[str, str]:
    """Read all key-value pairs from .env file.

    Returns:
        Dict of env var names to values. Missing file returns empty dict.
    """
    if not path.exists():
        return {}
    values = dotenv_values(path)
    return {k: v for k, v in values.items() if v is not None}


def update_env(key: str, value: str, path: Path = DEFAULT_ENV_PATH) -> None:
    """Set or update a single key in .env file.

    Creates the file if it doesn't exist.

    Args:
        key: Environment variable name (e.g., JARVIS_LLM_PREFERRED).
        value: Value to set.
        path: Path to .env file.
    """
    _ensure_env_file(path)
    set_key(str(path), key, value)


def write_env(config: dict[str, str], path: Path = DEFAULT_ENV_PATH) -> None:
    """Write multiple key-value pairs to .env file.

    Creates the file if it doesn't exist. Existing keys are updated,
    new keys are appended.

    Args:
        config: Dict of env var names to values.
        path: Path to .env file.
    """
    _ensure_env_file(path)
    for key, value in config.items():
        set_key(str(path), key, value)


def _ensure_env_file(path: Path) -> None:
    """Create .env file with restrictive permissions if it doesn't exist."""
    if not path.exists():
        path.touch(mode=0o600)
