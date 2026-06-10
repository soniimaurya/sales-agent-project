"""
FastAPI route handlers.
Thin layer: parse request → call service → return response.
No business logic here.
"""
import json
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.schemas import (
    ChatRequest, ChatResponse, HistoryResponse, MessageRecord,
    EvalBlock, DeleteResponse, HealthResponse, EvalSummary
)
from app.services.chat_service import ChatService
from app.memory.sqlite_memory import SQLiteMemory
from app.db.models import Message
from app.db.session import engine

import os
import sys
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))
import catalog_loader

router = APIRouter()


# ── POST /chat/{user_id} ─────────────────────────────────────────────────────

@router.post("/chat/{user_id}", response_model=ChatResponse)
def chat(user_id: str, body: ChatRequest, db: Session = Depends(get_db)):
    """
    Main chat endpoint.
    Send a message, get back a response + self-eval score + tools called.
    Memory is loaded and saved automatically — no context needed in request body.
    """
    service = ChatService(db)
    return service.handle_message(
        user_id=user_id,
        message=body.message,
        session_id=body.session_id,
    )


# ── GET /chat/{user_id}/history ───────────────────────────────────────────────

@router.get("/chat/{user_id}/history", response_model=HistoryResponse)
def get_history(user_id: str, db: Session = Depends(get_db)):
    """
    Return full conversation history across ALL sessions for a user.
    Useful for the frontend to render a chat timeline.
    """
    memory = SQLiteMemory(db)
    entries = memory.get_history(user_id, limit=200)

    if not entries:
        raise HTTPException(status_code=404, detail=f"No history found for user {user_id}")

    messages = []
    for e in entries:
        eval_block = None
        if e.eval_confidence is not None:
            # We don't store all eval fields in MemoryEntry — re-query DB for full eval
            row = db.query(Message).filter(Message.id == e.id).first()
            if row and row.eval_confidence is not None:
                eval_block = EvalBlock(
                    groundedness=row.eval_groundedness or 0,
                    relevance=row.eval_relevance or 0,
                    confidence=row.eval_confidence or 0,
                    flagged=row.eval_flagged or False,
                    reasoning=row.eval_reasoning or "",
                )
        messages.append(MessageRecord(
            role=e.role,
            content=e.content,
            session_id=e.session_id,
            created_at=e.created_at,
            tools_called=e.tools_called,
            eval=eval_block,
        ))

    sessions = list(dict.fromkeys(e.session_id for e in entries))

    return HistoryResponse(
        user_id=user_id,
        total_messages=len(messages),
        sessions=sessions,
        messages=messages,
    )


# ── DELETE /chat/{user_id}/memory ─────────────────────────────────────────────

@router.delete("/chat/{user_id}/memory", response_model=DeleteResponse)
def delete_memory(user_id: str, db: Session = Depends(get_db)):
    """
    GDPR-style memory wipe.
    Deletes ALL messages and flags for this user. Irreversible.
    """
    memory = SQLiteMemory(db)
    count = memory.delete_user_memory(user_id)
    return DeleteResponse(
        message=f"Deleted {count} message(s) for user {user_id}.",
        user_id=user_id,
    )


# ── GET /catalog ──────────────────────────────────────────────────────────────

@router.get("/catalog")
def get_catalog():
    """Returns the full product/pricing catalog the agent uses."""
    return catalog_loader.load()


# ── GET /health ───────────────────────────────────────────────────────────────

@router.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)):
    """Service health check. Verifies DB connection is alive."""
    try:
        db.execute(__import__("sqlalchemy").text("SELECT 1"))
        db_status = "ok"
    except Exception as e:
        db_status = f"error: {e}"
    return HealthResponse(
        status="ok",
        db=db_status,
        model="claude-opus-4-6",
    )


# ── GET /chat/{user_id}/evals  [BONUS] ────────────────────────────────────────

@router.get("/chat/{user_id}/evals", response_model=EvalSummary)
def get_evals(user_id: str, db: Session = Depends(get_db)):
    """
    Aggregated eval scores across all sessions for a user.
    Shows average groundedness/relevance/confidence and % of flagged responses.
    """
    memory = SQLiteMemory(db)
    summary = memory.get_eval_summary(user_id)
    if summary.get("total_responses", 0) == 0:
        raise HTTPException(status_code=404, detail="No eval data found for this user.")
    return EvalSummary(**summary)
