"""
SessionManager — central registry of session_id → Agent instances.

All channels (Telegram, CLI, Web, etc.) and the cron scheduler go through a
single SessionManager so that session lifecycle is managed in one place.

Session ID conventions
----------------------
  telegram:{chat_id}   — one per Telegram chat
  cron:{job_id}        — one per scheduled job (persistent across runs)
  cli                  — the interactive REPL session
  web:{connection_id}  — future web channel

Factory signature
-----------------
The factory callable must accept the session_id as its first positional arg:

    def factory(session_id: str) -> Agent: ...

This lets PersistentAgent know which JSONL file to load/save.

Usage
-----
    sm = SessionManager(agent_factory, store=session_store)
    agent = sm.get_or_create("telegram:123456")
    sm.reset("telegram:123456")   # deletes JSONL, creates fresh agent
    sm.list_sessions()
"""

from __future__ import annotations

import logging
from typing import Callable, TYPE_CHECKING

if TYPE_CHECKING:
    from .core.agent import Agent
    from .core.session_store import SessionStore

logger = logging.getLogger(__name__)

# Factory receives the session_id so PersistentAgent can locate its JSONL file.
AgentFactory = Callable[[str], "Agent"]


class SessionManager:
    """
    Central registry that maps session_id strings to Agent instances.

    Channels and schedulers call get_or_create(session_id) to obtain the
    Agent for a given session.  This decouples session lifecycle from
    channel-specific code.
    """

    def __init__(
        self,
        agent_factory: AgentFactory,
        store: "SessionStore | None" = None,
    ) -> None:
        self._factory = agent_factory
        self._store = store
        self._sessions: dict[str, "Agent"] = {}

    # ── Factory ──────────────────────────────────────────────────────────────

    def set_factory(self, factory: AgentFactory) -> None:
        """Late-bind the factory (used to resolve circular dependencies in server.py)."""
        self._factory = factory

    # ── Core API ─────────────────────────────────────────────────────────────

    def get_or_create(self, session_id: str) -> "Agent":
        """Return the existing Agent for session_id, creating one if needed."""
        if session_id not in self._sessions:
            logger.info("[SessionManager] Creating session '%s'", session_id)
            self._sessions[session_id] = self._factory(session_id)
        return self._sessions[session_id]

    def reset(self, session_id: str) -> "Agent":
        """Discard the current Agent, erase persisted history, and start fresh."""
        logger.info("[SessionManager] Resetting session '%s'", session_id)
        if self._store is not None:
            self._store.delete(session_id)
        self._sessions[session_id] = self._factory(session_id)
        return self._sessions[session_id]

    def remove(self, session_id: str) -> None:
        """Remove a session from memory (JSONL file is kept unless store.delete is called)."""
        if session_id in self._sessions:
            del self._sessions[session_id]
            logger.info("[SessionManager] Removed session '%s'", session_id)

    def list_sessions(self) -> list[str]:
        """Return all active (in-memory) session IDs."""
        return list(self._sessions.keys())

    def get(self, session_id: str) -> "Agent | None":
        """Return the Agent for session_id, or None if it doesn't exist."""
        return self._sessions.get(session_id)

    def __len__(self) -> int:
        return len(self._sessions)

    def __contains__(self, session_id: str) -> bool:
        return session_id in self._sessions
