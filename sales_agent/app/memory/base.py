"""
Abstract memory interface.
Any memory backend (SQLite, Postgres, Mem0, Redis) must implement these methods.
Swapping backends = change ONE file (the concrete implementation), not ten.
"""
from abc import ABC, abstractmethod
from typing import List, Optional
from dataclasses import dataclass, field
from datetime import datetime


@dataclass
class MemoryEntry:
    id: str
    user_id: str
    session_id: str
    role: str
    content: str
    created_at: datetime
    tools_called: List[str] = field(default_factory=list)
    eval_confidence: Optional[float] = None
    eval_flagged: Optional[bool] = None


class BaseMemory(ABC):

    @abstractmethod
    def save_message(self, user_id: str, session_id: str, role: str,
                     content: str, tools_called: List[str] = None,
                     eval_data: dict = None) -> MemoryEntry:
        ...

    @abstractmethod
    def get_history(self, user_id: str, limit: int = 50) -> List[MemoryEntry]:
        ...

    @abstractmethod
    def get_recent_context(self, user_id: str, n: int = 10) -> List[MemoryEntry]:
        ...

    @abstractmethod
    def delete_user_memory(self, user_id: str) -> int:
        ...

    @abstractmethod
    def get_eval_summary(self, user_id: str) -> dict:
        ...

    @abstractmethod
    def flag_conversation(self, user_id: str, session_id: str, reason: str):
        ...
