"""
Conversation Memory — manages per-session chat history for the agent.
"""

from typing import Any


class ConversationMemory:
    """
    Stores and manages the conversation history for a single session.
    Automatically trims history to stay within token limits.
    """

    def __init__(self, max_turns: int = 50):
        """
        Args:
            max_turns: Maximum number of message turns to keep in memory.
                       Older messages are dropped when this limit is exceeded.
        """
        self._messages: list[dict[str, Any]] = []
        self.max_turns = max_turns

    def add_message(self, role: str, content: Any) -> None:
        """Add a message to memory. Role should be 'user' or 'assistant'."""
        self._messages.append({"role": role, "content": content})
        self._trim()

    def get_messages(self) -> list[dict[str, Any]]:
        """Return a copy of all stored messages."""
        return list(self._messages)

    def get_last_n_messages(self, n: int) -> list[dict[str, Any]]:
        """Return the last n messages from memory."""
        return list(self._messages[-n:]) if n > 0 else []

    def get_summary(self) -> str:
        """Return a human-readable summary of the current session state."""
        return f"Session has {len(self._messages)} messages"

    def clear(self) -> None:
        """Clear all messages."""
        self._messages = []

    def _trim(self) -> None:
        """Keep only the last max_turns messages to prevent context overflow."""
        if len(self._messages) > self.max_turns * 2:
            self._messages = self._messages[-(self.max_turns * 2):]

    def __len__(self) -> int:
        return len(self._messages)

    def summary(self) -> str:
        """Human-readable summary of current memory state."""
        return f"Memory: {len(self._messages)} messages stored (max {self.max_turns * 2})"