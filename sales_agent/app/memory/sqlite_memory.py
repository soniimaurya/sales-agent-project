"""
SQLite (and Postgres-compatible) implementation of BaseMemory.
Uses the same SQLAlchemy session as the rest of the app.

To swap to Postgres: change DATABASE_URL env var. Done.
To swap to Mem0:     create mem0_memory.py implementing BaseMemory. Done.
"""
from typing import List, Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from app.memory.base import BaseMemory, MemoryEntry
from app.db.models import Message, FlaggedConversation
import uuid


class SQLiteMemory(BaseMemory):
    """
    Concrete memory backend backed by SQLAlchemy.
    Works with SQLite locally and Postgres in production with zero code changes.
    """

    def __init__(self, db: Session):
        # We receive the DB session from FastAPI's dependency injection
        self.db = db

    def save_message(self, user_id: str, session_id: str, role: str,
                     content: str, tools_called: List[str] = None,
                     eval_data: dict = None) -> MemoryEntry:
        """
        Write one message to the DB.
        eval_data is only set for assistant messages.
        """
        msg = Message(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            role=role,
            content=content,
            tools_called=tools_called or [],
        )
        if eval_data:
            msg.eval_groundedness = eval_data.get("groundedness")
            msg.eval_relevance    = eval_data.get("relevance")
            msg.eval_confidence   = eval_data.get("confidence")
            msg.eval_flagged      = eval_data.get("flagged")
            msg.eval_reasoning    = eval_data.get("reasoning")

        self.db.add(msg)
        self.db.commit()
        self.db.refresh(msg)
        return self._to_entry(msg)

    def get_history(self, user_id: str, limit: int = 100) -> List[MemoryEntry]:
        """All messages for a user, oldest first, capped at limit."""
        rows = (
            self.db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.asc())
            .limit(limit)
            .all()
        )
        return [self._to_entry(r) for r in rows]

    def get_recent_context(self, user_id: str, n: int = 10) -> List[MemoryEntry]:
        """
        Last N messages — injected into the LLM prompt as conversation history.
        We fetch in DESC order then reverse so the LLM sees them oldest→newest.
        """
        rows = (
            self.db.query(Message)
            .filter(Message.user_id == user_id)
            .order_by(Message.created_at.desc())
            .limit(n)
            .all()
        )
        rows.reverse()
        return [self._to_entry(r) for r in rows]

    def delete_user_memory(self, user_id: str) -> int:
        """GDPR-style wipe. Returns how many rows were deleted."""
        count = self.db.query(Message).filter(Message.user_id == user_id).count()
        self.db.query(Message).filter(Message.user_id == user_id).delete()
        self.db.query(FlaggedConversation).filter(
            FlaggedConversation.user_id == user_id
        ).delete()
        self.db.commit()
        return count

    def get_eval_summary(self, user_id: str) -> dict:
        """Aggregate eval scores across all assistant messages for the user."""
        rows = (
            self.db.query(Message)
            .filter(Message.user_id == user_id, Message.role == "assistant",
                    Message.eval_confidence.isnot(None))
            .all()
        )
        if not rows:
            return {"user_id": user_id, "total_responses": 0}

        total = len(rows)
        return {
            "user_id": user_id,
            "total_responses": total,
            "avg_groundedness": round(sum(r.eval_groundedness or 0 for r in rows) / total, 3),
            "avg_relevance":    round(sum(r.eval_relevance    or 0 for r in rows) / total, 3),
            "avg_confidence":   round(sum(r.eval_confidence   or 0 for r in rows) / total, 3),
            "flagged_count":    sum(1 for r in rows if r.eval_flagged),
            "flagged_percentage": round(sum(1 for r in rows if r.eval_flagged) / total * 100, 1),
        }

    def flag_conversation(self, user_id: str, session_id: str, reason: str):
        """Write a flag record that a human reviewer can query."""
        flag = FlaggedConversation(
            id=str(uuid.uuid4()),
            user_id=user_id,
            session_id=session_id,
            reason=reason,
        )
        self.db.add(flag)
        self.db.commit()

    # ── helper ────────────────────────────────────────────────────────────────

    @staticmethod
    def _to_entry(msg: Message) -> MemoryEntry:
        return MemoryEntry(
            id=msg.id,
            user_id=msg.user_id,
            session_id=msg.session_id,
            role=msg.role,
            content=msg.content,
            created_at=msg.created_at,
            tools_called=msg.tools_called or [],
            eval_confidence=msg.eval_confidence,
            eval_flagged=msg.eval_flagged,
        )
