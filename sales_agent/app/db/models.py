"""
SQLAlchemy ORM models — defines what the database tables look like.
We use SQLite locally (one file, zero setup). On Railway, point DATABASE_URL
at a Postgres instance and nothing else changes.
"""
from sqlalchemy import Column, String, Float, Boolean, DateTime, Text, JSON
from sqlalchemy.ext.declarative import declarative_base
from datetime import datetime, timezone
import uuid

Base = declarative_base()


def new_uuid() -> str:
    return str(uuid.uuid4())


class Message(Base):
    """
    Every message (user or assistant) is stored here.
    This is the source of truth for cross-session memory.
    """
    __tablename__ = "messages"

    id          = Column(String, primary_key=True, default=new_uuid)
    user_id     = Column(String, nullable=False, index=True)
    session_id  = Column(String, nullable=False, index=True)
    role        = Column(String, nullable=False)        # "user" | "assistant"
    content     = Column(Text, nullable=False)
    tools_called = Column(JSON, default=list)           # ["search_catalog", ...]
    created_at  = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    # Eval scores (only populated for assistant messages)
    eval_groundedness = Column(Float, nullable=True)
    eval_relevance    = Column(Float, nullable=True)
    eval_confidence   = Column(Float, nullable=True)
    eval_flagged      = Column(Boolean, nullable=True)
    eval_reasoning    = Column(Text, nullable=True)

    def __repr__(self):
        return f"<Message {self.role} user={self.user_id} session={self.session_id[:8]}>"


class FlaggedConversation(Base):
    """
    Bonus: when eval.flagged=True, we write a row here so a human reviewer
    endpoint can query all conversations that need attention.
    """
    __tablename__ = "flagged_conversations"

    id         = Column(String, primary_key=True, default=new_uuid)
    user_id    = Column(String, nullable=False, index=True)
    session_id = Column(String, nullable=False)
    reason     = Column(Text)
    resolved   = Column(Boolean, default=False)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
