"""Tests for logging module."""

from __future__ import annotations

from jarvis.logging import (
    _add_context,
    _filter_sensitive,
    configure_logging,
    pipeline_state_var,
    request_id_var,
)


class TestFilterSensitive:
    def test_redacts_api_key(self) -> None:
        event = {"api_key": "sk-secret-123", "message": "hello"}
        result = _filter_sensitive(None, "info", event)
        assert result["api_key"] == "***REDACTED***"
        assert result["message"] == "hello"

    def test_redacts_access_token(self) -> None:
        event = {"access_token": "eyJ...", "event": "test"}
        result = _filter_sensitive(None, "info", event)
        assert result["access_token"] == "***REDACTED***"

    def test_redacts_password(self) -> None:
        event = {"password": "hunter2"}
        result = _filter_sensitive(None, "info", event)
        assert result["password"] == "***REDACTED***"

    def test_preserves_normal_fields(self) -> None:
        event = {"event": "test", "user": "jarvis", "count": 42}
        result = _filter_sensitive(None, "info", event)
        assert result == {"event": "test", "user": "jarvis", "count": 42}

    def test_redacts_long_token_like_strings(self) -> None:
        event = {"auth_token": "a" * 200}
        result = _filter_sensitive(None, "info", event)
        assert result["auth_token"] == "***REDACTED***"

    def test_does_not_redact_long_normal_strings(self) -> None:
        event = {"description": "a" * 200}
        result = _filter_sensitive(None, "info", event)
        assert result["description"] == "a" * 200


class TestAddContext:
    def test_adds_request_id(self) -> None:
        token = request_id_var.set("req_123")
        try:
            event: dict = {"event": "test"}
            result = _add_context(None, "info", event)
            assert result["request_id"] == "req_123"
        finally:
            request_id_var.reset(token)

    def test_adds_pipeline_state(self) -> None:
        token = pipeline_state_var.set("listening")
        try:
            event: dict = {"event": "test"}
            result = _add_context(None, "info", event)
            assert result["pipeline_state"] == "listening"
        finally:
            pipeline_state_var.reset(token)

    def test_skips_idle_state(self) -> None:
        token = pipeline_state_var.set("idle")
        try:
            event: dict = {"event": "test"}
            result = _add_context(None, "info", event)
            assert "pipeline_state" not in result
        finally:
            pipeline_state_var.reset(token)

    def test_skips_empty_request_id(self) -> None:
        token = request_id_var.set("")
        try:
            event: dict = {"event": "test"}
            result = _add_context(None, "info", event)
            assert "request_id" not in result
        finally:
            request_id_var.reset(token)


class TestConfigureLogging:
    def test_configure_info(self) -> None:
        """configure_logging doesn't raise."""
        configure_logging(level="INFO")

    def test_configure_debug(self) -> None:
        configure_logging(level="DEBUG")

    def test_configure_json(self) -> None:
        configure_logging(level="INFO", json_output=True)
