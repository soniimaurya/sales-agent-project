"""
Pydantic schemas — the shape of every request and response in the API.
These act as contracts between your frontend and backend.
"""
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


# ── Inbound ──────────────────────────────────────────────────────────────────

class ChatRequest(BaseModel):
    """What the frontend sends when a user types a message."""
    message: str = Field(..., min_length=1, max_length=2000,
                         description="The user's message text")
    session_id: Optional[str] = Field(
        None,
        description="Optional: resume a specific session. If omitted, a new session is started."
    )


# ── Eval block ────────────────────────────────────────────────────────────────

class EvalBlock(BaseModel):
    """
    Self-evaluation scores the agent produces for EVERY response.
    Scores are 0.0–1.0. flagged=True means a human should review this reply.
    """
    groundedness: float = Field(..., ge=0.0, le=1.0,
        description="How well the answer is grounded in catalog facts (vs hallucinated)")
    relevance: float = Field(..., ge=0.0, le=1.0,
        description="How relevant the answer is to the question asked")
    confidence: float = Field(..., ge=0.0, le=1.0,
        description="Overall confidence that the answer is correct and complete")
    flagged: bool = Field(False,
        description="True when confidence < 0.5 — escalate to a human reviewer")
    reasoning: str = Field(...,
        description="Plain-English explanation of why these scores were assigned")


# ── Outbound ──────────────────────────────────────────────────────────────────

class ChatResponse(BaseModel):
    """Everything the API returns after processing a chat message."""
    response: str
    eval: EvalBlock
    tools_called: List[str]
    session_id: str
    user_id: str


class MessageRecord(BaseModel):
    """A single message as stored in the DB, returned in history."""
    role: str                    # "user" or "assistant"
    content: str
    session_id: str
    created_at: datetime
    tools_called: Optional[List[str]] = []
    eval: Optional[EvalBlock] = None


class HistoryResponse(BaseModel):
    """Full conversation history for a user across ALL past sessions."""
    user_id: str
    total_messages: int
    sessions: List[str]          # list of distinct session UUIDs
    messages: List[MessageRecord]


class HealthResponse(BaseModel):
    status: str
    db: str
    model: str


class DeleteResponse(BaseModel):
    message: str
    user_id: str


class EvalSummary(BaseModel):
    """Aggregated eval stats — used by the bonus /evals endpoint."""
    user_id: str
    total_responses: int
    avg_groundedness: float
    avg_relevance: float
    avg_confidence: float
    flagged_count: int
    flagged_percentage: float
