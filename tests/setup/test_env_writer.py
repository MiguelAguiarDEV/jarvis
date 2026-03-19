"""Tests for env_writer utility."""

from __future__ import annotations

from typing import TYPE_CHECKING

from jarvis.setup.env_writer import read_env, update_env, write_env

if TYPE_CHECKING:
    from pathlib import Path


class TestEnvWriter:
    def test_read_nonexistent_returns_empty(self, tmp_path: Path) -> None:
        result = read_env(tmp_path / ".env")
        assert result == {}

    def test_write_and_read(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        write_env({"KEY1": "value1", "KEY2": "value2"}, env_path)

        result = read_env(env_path)
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"

    def test_update_existing_key(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        write_env({"KEY1": "old_value"}, env_path)
        update_env("KEY1", "new_value", env_path)

        result = read_env(env_path)
        assert result["KEY1"] == "new_value"

    def test_update_creates_file(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        assert not env_path.exists()

        update_env("NEW_KEY", "new_value", env_path)

        assert env_path.exists()
        result = read_env(env_path)
        assert result["NEW_KEY"] == "new_value"

    def test_write_creates_file(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        assert not env_path.exists()

        write_env({"KEY": "value"}, env_path)

        assert env_path.exists()

    def test_write_preserves_existing_keys(self, tmp_path: Path) -> None:
        env_path = tmp_path / ".env"
        write_env({"KEY1": "value1"}, env_path)
        write_env({"KEY2": "value2"}, env_path)

        result = read_env(env_path)
        assert result["KEY1"] == "value1"
        assert result["KEY2"] == "value2"
