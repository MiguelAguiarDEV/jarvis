"""Event bridge between JarvisPipeline and Textual UI.

Pipeline calls bridge callbacks → bridge posts Textual Messages → widgets react.
Pipeline stays unaware of Textual. Bridge is the only coupling point.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import TYPE_CHECKING, Any

from textual.message import Message

if TYPE_CHECKING:
    from textual.app import App


class StateChangedMessage(Message):
    """Posted when pipeline state transitions."""

    def __init__(
        self,
        old_state: str,
        new_state: str,
        request_id: str = "",
    ) -> None:
        super().__init__()
        self.old_state = old_state
        self.new_state = new_state
        self.request_id = request_id


class ConversationMessage(Message):
    """Posted when a full conversation turn completes."""

    def __init__(
        self,
        user_text: str,
        response_text: str,
        provider: str,
        model: str,
        elapsed_ms: float,
        tool_names: list[str],
        request_id: str = "",
    ) -> None:
        super().__init__()
        self.user_text = user_text
        self.response_text = response_text
        self.provider = provider
        self.model = model
        self.elapsed_ms = elapsed_ms
        self.tool_names = tool_names
        self.request_id = request_id
        self.timestamp = time.time()


class PipelineErrorMessage(Message):
    """Posted when pipeline encounters an error."""

    def __init__(self, error: str, stage: str) -> None:
        super().__init__()
        self.error = error
        self.stage = stage
        self.timestamp = time.time()


class InitProgressMessage(Message):
    """Posted during pipeline initialization to show loading progress."""

    def __init__(self, component: str, status: str) -> None:
        super().__init__()
        self.component = component
        self.status = status  # "loading", "ok", "failed", "skipped"


class PipelineReadyMessage(Message):
    """Posted when pipeline finishes initialization."""

    def __init__(self, provider_health: dict[str, bool], tool_count: int) -> None:
        super().__init__()
        self.provider_health = provider_health
        self.tool_count = tool_count


@dataclass
class ConversationRecord:
    """Stored record of a conversation turn for the activity log."""

    timestamp: float
    user_text: str
    response_text: str
    provider: str
    elapsed_ms: float
    tool_names: list[str] = field(default_factory=list)
    request_id: str = ""


class PipelineEventBridge:
    """Translates pipeline callbacks into Textual Messages.

    Usage:
        bridge = PipelineEventBridge(app)
        pipeline = JarvisPipeline(settings, event_callback=bridge.dispatch)
    """

    def __init__(self, app: App[Any]) -> None:
        self._app = app
        self._conversations: list[ConversationRecord] = []
        self._max_history = 100

    @property
    def conversations(self) -> list[ConversationRecord]:
        """Recent conversation history (newest first)."""
        return list(reversed(self._conversations))

    def dispatch(self, event_type: str, **kwargs: Any) -> None:
        """Main callback — called by pipeline on events.

        Args:
            event_type: One of "state_change", "conversation_complete", "error", "ready".
            **kwargs: Event-specific data.
        """
        if event_type == "state_change":
            self._app.post_message(
                StateChangedMessage(
                    old_state=str(kwargs.get("old", "")),
                    new_state=str(kwargs.get("new", "")),
                    request_id=str(kwargs.get("request_id", "")),
                )
            )

        elif event_type == "conversation_complete":
            record = ConversationRecord(
                timestamp=time.time(),
                user_text=str(kwargs.get("user_text", "")),
                response_text=str(kwargs.get("response_text", "")),
                provider=str(kwargs.get("provider", "")),
                elapsed_ms=float(kwargs.get("elapsed_ms", 0)),
                tool_names=kwargs.get("tool_names", []),
                request_id=str(kwargs.get("request_id", "")),
            )
            self._conversations.append(record)
            if len(self._conversations) > self._max_history:
                self._conversations = self._conversations[-self._max_history :]

            self._app.post_message(
                ConversationMessage(
                    user_text=record.user_text,
                    response_text=record.response_text,
                    provider=record.provider,
                    model=str(kwargs.get("model", "")),
                    elapsed_ms=record.elapsed_ms,
                    tool_names=record.tool_names,
                    request_id=record.request_id,
                )
            )

        elif event_type == "error":
            self._app.post_message(
                PipelineErrorMessage(
                    error=str(kwargs.get("error", "Unknown error")),
                    stage=str(kwargs.get("stage", "unknown")),
                )
            )

        elif event_type == "init_progress":
            self._app.post_message(
                InitProgressMessage(
                    component=str(kwargs.get("component", "")),
                    status=str(kwargs.get("status", "")),
                )
            )

        elif event_type == "ready":
            self._app.post_message(
                PipelineReadyMessage(
                    provider_health=kwargs.get("provider_health", {}),
                    tool_count=int(kwargs.get("tool_count", 0)),
                )
            )
