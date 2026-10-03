"""Bounded, transactional session store for a single server process."""

from contextlib import contextmanager
from copy import deepcopy
from dataclasses import dataclass, field
from threading import Lock
from time import monotonic
import secrets

from .conversation import ConversationState


class SessionNotFound(Exception):
    pass


class SessionCapacityExceeded(Exception):
    pass


@dataclass
class _Session:
    state: ConversationState = field(default_factory=ConversationState)
    lock: Lock = field(default_factory=Lock)
    last_used: float = field(default_factory=monotonic)
    active: int = 0


class SessionStore:
    def __init__(self, ttl_seconds=3600, max_sessions=500, max_history_messages=40,
                 clock=monotonic):
        if ttl_seconds <= 0 or max_sessions <= 0 or max_history_messages <= 0:
            raise ValueError("Session limits must be positive.")
        self.ttl_seconds = ttl_seconds
        self.max_sessions = max_sessions
        self.max_history_messages = max_history_messages
        self.clock = clock
        self._sessions = {}
        self._lock = Lock()

    @contextmanager
    def transaction(self, token=None):
        """Serialize one session; commit only successful turns, never evict active ones."""
        created = token is None
        with self._lock:
            now = self.clock()
            expired = [key for key, entry in self._sessions.items()
                       if entry.active == 0 and now - entry.last_used >= self.ttl_seconds]
            for key in expired:
                del self._sessions[key]
            if created:
                if len(self._sessions) >= self.max_sessions:
                    raise SessionCapacityExceeded()
                token = secrets.token_urlsafe(32)
                self._sessions[token] = _Session(last_used=now)
            entry = self._sessions.get(token)
            if entry is None:
                raise SessionNotFound()
            entry.active += 1

        succeeded = False
        try:
            with entry.lock:
                state = deepcopy(entry.state)
                yield token, state
                state.chat_history = state.chat_history[-self.max_history_messages:]
                entry.state = state
                succeeded = True
        finally:
            with self._lock:
                entry.active -= 1
                entry.last_used = self.clock()
                if created and not succeeded:
                    self._sessions.pop(token, None)
