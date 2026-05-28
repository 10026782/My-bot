"""
memory.py — ניהול זיכרון שיחה קשיח
Memory Length = 5 אינטראקציות (user+assistant = זוג אחד).
"""

from collections import deque
from threading import Lock


class ConversationMemory:
    def __init__(self, max_interactions: int = 5):
        self.max_interactions = max_interactions
        # כל אינטראקציה = זוג (user, assistant). שומרים עד max*2 הודעות.
        self._messages: deque = deque(maxlen=max_interactions * 2)
        self._lock = Lock()

    def add_user_message(self, text: str):
        with self._lock:
            self._messages.append({"role": "user", "content": text})

    def add_assistant_message(self, text: str):
        with self._lock:
            self._messages.append({"role": "assistant", "content": text})

    def get_messages(self) -> list:
        with self._lock:
            return list(self._messages)

    def clear(self):
        with self._lock:
            self._messages.clear()
