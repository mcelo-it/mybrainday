"""Conversation data, deliberately separate from the shared retrieval index."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ConversationState:
    chat_history: list[dict[str, str]] = field(default_factory=list)
    last_retrieved_chunks: list[dict[str, Any]] = field(default_factory=list)
    pending_clarification: dict[str, Any] | None = None
    last_user_query: str | None = None
    last_effective_query: str | None = None
    last_answer_type: str | None = None
    last_selected_chunks: list[dict[str, Any]] = field(default_factory=list)
    last_citations: list[dict[str, Any]] = field(default_factory=list)
    last_topic_summary: str | None = None
