"""Context manager for Agent conversations."""

from dataclasses import dataclass, field
from typing import Dict, List, Optional


@dataclass
class Message:
    """Conversation message."""

    role: str  # "user", "assistant", "system"
    content: str
    metadata: Dict = field(default_factory=dict)


class ContextManager:
    """Manage conversation context for Agent."""

    def __init__(self, max_tokens: int = 4000) -> None:
        """Initialize context manager.

        Args:
            max_tokens: Maximum tokens to keep in context
        """
        self.max_tokens = max_tokens
        self.messages: List[Message] = []
        self.user_preferences: Dict = {}
        self.session_data: Dict = {}

    def add_message(self, role: str, content: str, metadata: Optional[Dict] = None) -> None:
        """Add a message to the conversation."""
        self.messages.append(Message(
            role=role,
            content=content,
            metadata=metadata or {}
        ))

        # Trim old messages if context gets too long
        self._trim_context()

    def get_context(self, n_recent: Optional[int] = None) -> List[Dict]:
        """Get conversation context as list of dicts.

        Args:
            n_recent: Number of recent messages to return (None for all)

        Returns:
            List of message dicts for LLM API
        """
        messages = self.messages
        if n_recent:
            messages = messages[-n_recent:]

        return [
            {"role": msg.role, "content": msg.content}
            for msg in messages
        ]

    def get_last_message(self) -> Optional[Message]:
        """Get the last message."""
        if self.messages:
            return self.messages[-1]
        return None

    def set_preference(self, key: str, value: any) -> None:
        """Set a user preference."""
        self.user_preferences[key] = value

    def get_preference(self, key: str, default: any = None) -> any:
        """Get a user preference."""
        return self.user_preferences.get(key, default)

    def set_session_data(self, key: str, value: any) -> None:
        """Set session-specific data."""
        self.session_data[key] = value

    def get_session_data(self, key: str, default: any = None) -> any:
        """Get session-specific data."""
        return self.session_data.get(key, default)

    def clear(self) -> None:
        """Clear all context."""
        self.messages = []
        self.session_data = {}

    def _trim_context(self) -> None:
        """Trim old messages to stay within token limit."""
        # Simple estimation: 1 token ≈ 4 characters
        total_chars = sum(len(msg.content) for msg in self.messages)
        estimated_tokens = total_chars // 4

        while estimated_tokens > self.max_tokens and len(self.messages) > 2:
            # Remove oldest non-system message
            for i, msg in enumerate(self.messages):
                if msg.role != "system":
                    removed = self.messages.pop(i)
                    estimated_tokens -= len(removed.content) // 4
                    break

    def __len__(self) -> int:
        """Return number of messages."""
        return len(self.messages)
