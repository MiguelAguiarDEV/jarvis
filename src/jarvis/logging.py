"""Structured logging configuration for JARVIS.

Provides:
- JSON output for production (machine-parseable)
- Pretty console output for development (human-readable)
- Request/pipeline correlation via context vars
- Performance timing for every pipeline stage
- Sensitive data filtering (never log credentials)
"""

from __future__ import annotations

import logging
import sys
import time
from contextvars import ContextVar
from typing import Any

import structlog

# Context variables for request correlation
request_id_var: ContextVar[str] = ContextVar("request_id", default="")
pipeline_state_var: ContextVar[str] = ContextVar("pipeline_state", default="idle")

# Fields that should NEVER appear in logs
SENSITIVE_FIELDS = frozenset(
    {
        "api_key",
        "access_token",
        "refresh_token",
        "token",
        "password",
        "secret",
        "authorization",
        "claude_token",
        "openai_access_token",
        "openai_refresh_token",
    }
)


def _filter_sensitive(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Remove sensitive fields from log events."""
    for key in list(event_dict.keys()):
        if key.lower() in SENSITIVE_FIELDS or (
            isinstance(event_dict[key], str)
            and len(event_dict[key]) > 100
            and any(s in key.lower() for s in ("key", "token", "secret", "auth"))
        ):
            event_dict[key] = "***REDACTED***"
    return event_dict


def _add_context(logger: Any, method_name: str, event_dict: dict[str, Any]) -> dict[str, Any]:
    """Add request correlation context to log events."""
    rid = request_id_var.get()
    if rid:
        event_dict["request_id"] = rid
    state = pipeline_state_var.get()
    if state and state != "idle":
        event_dict["pipeline_state"] = state
    return event_dict


def configure_logging(level: str = "INFO", json_output: bool = False) -> None:
    """Configure structured logging for JARVIS.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL).
        json_output: If True, output JSON lines. If False, pretty console output.
    """
    log_level = getattr(logging, level.upper(), logging.INFO)

    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        _filter_sensitive,  # type: ignore[list-item]
        _add_context,  # type: ignore[list-item]
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer(
            colors=sys.stderr.isatty(),
            pad_event_to=40,
        )

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(log_level),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )


class PipelineTimer:
    """Context manager for timing pipeline stages with structured logging.

    Usage:
        async with PipelineTimer("stt.transcribe", audio_samples=16000):
            result = await stt.transcribe(audio)
    """

    def __init__(self, stage: str, **extra: Any) -> None:
        self._stage = stage
        self._extra = extra
        self._start: float = 0.0
        self._log = structlog.get_logger()

    async def __aenter__(self) -> PipelineTimer:
        self._start = time.perf_counter()
        await self._log.adebug(f"{self._stage}.start", **self._extra)
        return self

    async def __aexit__(self, *exc: object) -> None:
        elapsed = time.perf_counter() - self._start
        if exc[0] is not None:
            await self._log.aerror(
                f"{self._stage}.error",
                elapsed_ms=round(elapsed * 1000, 1),
                error_type=getattr(exc[0], "__name__", str(exc[0])) if exc[0] else None,
                **self._extra,
            )
        else:
            await self._log.ainfo(
                f"{self._stage}.done",
                elapsed_ms=round(elapsed * 1000, 1),
                **self._extra,
            )

    @property
    def elapsed_ms(self) -> float:
        return round((time.perf_counter() - self._start) * 1000, 1)
