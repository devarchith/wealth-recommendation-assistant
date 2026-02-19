"""
Conversational Memory Management
Per-session ConversationBufferWindowMemory with a configurable exchange window.
"""

from __future__ import annotations

import logging
import os
import time
from typing import Dict, Optional

from langchain.memory import ConversationBufferWindowMemory

logger = logging.getLogger(__name__)

# Number of human/AI exchange pairs to retain (configurable via env)
MEMORY_WINDOW_SIZE: int = int(os.environ.get("MEMORY_WINDOW_SIZE", "5"))

# In-memory session store: session_id -> MemoryEntry
_sessions: Dict[str, "MemoryEntry"] = {}


class MemoryEntry:
    """Wraps a LangChain memory object with session metadata."""

    def __init__(self, session_id: str, window_size: int = MEMORY_WINDOW_SIZE):
        self.session_id = session_id
        self.window_size = window_size
        self.created_at = time.time()
        self.last_accessed = time.time()
        self.memory = ConversationBufferWindowMemory(
            k=window_size,
            memory_key="chat_history",
            return_messages=True,
            output_key="answer",
            input_key="question",
        )

    def touch(self) -> None:
        """Update the last-accessed timestamp."""
        self.last_accessed = time.time()

    def age_seconds(self) -> float:
        return time.time() - self.last_accessed

    def to_dict(self) -> dict:
        messages = self.memory.chat_memory.messages
        return {
            "session_id": self.session_id,
            "window_size": self.window_size,
            "message_count": len(messages),
            "last_accessed": self.last_accessed,
            "age_seconds": round(self.age_seconds(), 1),
        }


# ---------------------------------------------------------------------------
# Session management API
# ---------------------------------------------------------------------------

def get_memory(
    session_id: str,
    window_size: int = MEMORY_WINDOW_SIZE,
) -> ConversationBufferWindowMemory:
    """
    Return the ConversationBufferWindowMemory for a given session.
    Creates a new session entry if one does not already exist.

    The window retains the last `window_size` human/AI exchanges (default 5),
    providing contextual continuity without unbounded token growth.
    """
    if session_id not in _sessions:
        _sessions[session_id] = MemoryEntry(session_id, window_size)
        logger.info(
            "New session created: id=%s window=%d", session_id, window_size
        )
    entry = _sessions[session_id]
    entry.touch()
    return entry.memory


def clear_session(session_id: str) -> bool:
    """Remove a session's memory. Returns True if the session existed."""
    if session_id in _sessions:
        del _sessions[session_id]
        logger.info("Session cleared: id=%s", session_id)
        return True
    return False


def get_session_info(session_id: str) -> Optional[dict]:
    """Return metadata for a session, or None if it does not exist."""
    entry = _sessions.get(session_id)
    return entry.to_dict() if entry else None


def evict_stale_sessions(max_age_seconds: float = 3600.0) -> int:
    """
    Remove sessions that have not been accessed within `max_age_seconds`.
    Called periodically to prevent unbounded memory growth.
    Returns the number of sessions evicted.
    """
    stale = [
        sid for sid, entry in _sessions.items()
        if entry.age_seconds() > max_age_seconds
    ]
    for sid in stale:
        del _sessions[sid]
    if stale:
        logger.info("Evicted %d stale sessions", len(stale))
    return len(stale)


def active_session_count() -> int:
    """Return the number of active (non-evicted) sessions."""
    return len(_sessions)
