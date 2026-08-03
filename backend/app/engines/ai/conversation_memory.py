# file_name: conversation_memory.py

"""Conversation memory.

``docs/08_ai/44_CONVERSATION_MEMORY.md``: memory is scoped to one user and one
conversation, preserves message order, and is pruned to a configured window
before prompt construction. Section 12 restricts it to conversational content
only, so no landmarks, frames or detector output are ever stored here.

``docs/04_backend/29_DOMAIN_MODEL.md`` defines no Conversation or Message
entity, so there is no table to persist to. Memory is therefore held in the
process behind an interface: conversations are lost on restart, and a shared
store is required before running several replicas. Recorded in PROJECT_STATUS.
"""

import logging
from abc import ABC, abstractmethod
from collections import OrderedDict
from dataclasses import dataclass
from datetime import datetime
from uuid import UUID

from app.domain.entities.user import utc_now

logger = logging.getLogger(__name__)

USER_ROLE = "user"
ASSISTANT_ROLE = "assistant"

DEFAULT_WINDOW_MESSAGES = 10
"""Turns kept in the prompt window. Older turns are pruned from the prompt."""

DEFAULT_MAX_CONVERSATIONS = 500
"""Conversations retained in memory before the least recent is evicted."""

MAX_MESSAGES_PER_CONVERSATION = 100
"""Hard cap per conversation, so one session cannot grow without bound."""


@dataclass(frozen=True, slots=True)
class StoredMessage:
    """One stored conversational turn."""

    conversation_id: str
    user_id: UUID
    role: str
    content: str
    created_at: datetime


class ConversationMemory(ABC):
    """Stores and recalls conversational turns."""

    @abstractmethod
    def append(
        self, conversation_id: str, user_id: UUID, role: str, content: str
    ) -> StoredMessage:
        """Record one turn."""

    @abstractmethod
    def window(
        self, conversation_id: str, user_id: UUID, limit: int
    ) -> tuple[StoredMessage, ...]:
        """Return the most recent turns of a conversation, oldest first."""

    @abstractmethod
    def clear(self, conversation_id: str, user_id: UUID) -> None:
        """Forget a conversation."""


class InMemoryConversationMemory(ConversationMemory):
    """Keeps conversations in the process, with bounded size."""

    def __init__(
        self,
        max_conversations: int = DEFAULT_MAX_CONVERSATIONS,
        max_messages: int = MAX_MESSAGES_PER_CONVERSATION,
    ) -> None:
        self._max_conversations = max_conversations
        self._max_messages = max_messages
        self._store: OrderedDict[tuple[str, UUID], list[StoredMessage]] = OrderedDict()

    def append(
        self, conversation_id: str, user_id: UUID, role: str, content: str
    ) -> StoredMessage:
        """Record one turn, evicting the least recent conversation if needed."""
        key = self._key(conversation_id, user_id)
        message = StoredMessage(
            conversation_id=conversation_id,
            user_id=user_id,
            role=role,
            content=content,
            created_at=utc_now(),
        )

        messages = self._store.setdefault(key, [])
        messages.append(message)

        if len(messages) > self._max_messages:
            del messages[: len(messages) - self._max_messages]

        self._store.move_to_end(key)
        while len(self._store) > self._max_conversations:
            evicted, _ = self._store.popitem(last=False)
            logger.info("Evicted the least recently used conversation.")

        return message

    def window(
        self, conversation_id: str, user_id: UUID, limit: int = DEFAULT_WINDOW_MESSAGES
    ) -> tuple[StoredMessage, ...]:
        """Return the most recent turns, oldest first.

        Keyed by conversation *and* user, so one user can never read another's
        conversation even if they guess the identifier. This is the session
        isolation required by section 11.
        """
        messages = self._store.get(self._key(conversation_id, user_id), [])
        if limit <= 0:
            return ()
        return tuple(messages[-limit:])

    def clear(self, conversation_id: str, user_id: UUID) -> None:
        """Forget a conversation."""
        self._store.pop(self._key(conversation_id, user_id), None)

    def conversation_count(self) -> int:
        """Return how many conversations are held."""
        return len(self._store)

    @staticmethod
    def _key(conversation_id: str, user_id: UUID) -> tuple[str, UUID]:
        return (conversation_id, user_id)
