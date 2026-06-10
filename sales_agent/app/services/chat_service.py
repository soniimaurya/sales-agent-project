"""
ChatService — orchestrates memory + agent + eval for a single /chat request.

Why a service layer?
  Routes should be thin (just parse HTTP, call service, return response).
  Business logic lives here so it's testable without HTTP overhead.
"""
import uuid
from sqlalchemy.orm import Session

from app.memory.sqlite_memory import SQLiteMemory
from app.agents.sales_agent import run_agent, self_evaluate
from app.models.schemas import ChatResponse, EvalBlock


class ChatService:
    def __init__(self, db: Session):
        self.memory = SQLiteMemory(db)

    def handle_message(self, user_id: str, message: str,
                       session_id: str = None) -> ChatResponse:
        """
        Full pipeline for one user message:
          1. Assign/reuse session_id
          2. Save the user's message
          3. Run the agent (may call tools)
          4. Self-evaluate the response
          5. Save the assistant response + eval
          6. Flag if needed
          7. Return structured ChatResponse
        """
        # Step 1: session management
        if not session_id:
            session_id = str(uuid.uuid4())

        # Step 2: persist user message
        self.memory.save_message(
            user_id=user_id,
            session_id=session_id,
            role="user",
            content=message,
        )

        # Step 3: run agent loop
        response_text, tools_called, human_flagged = run_agent(
            user_id=user_id,
            session_id=session_id,
            user_message=message,
            memory=self.memory,
        )

        # Step 4: self-evaluation
        eval_scores = self_evaluate(message, response_text, tools_called)

        # Respect the agent's flag_for_human call
        if human_flagged:
            eval_scores["flagged"] = True

        eval_block = EvalBlock(**eval_scores)

        # Step 5: persist assistant message + eval
        self.memory.save_message(
            user_id=user_id,
            session_id=session_id,
            role="assistant",
            content=response_text,
            tools_called=tools_called,
            eval_data=eval_scores,
        )

        # Step 6: write flag record if needed
        if eval_block.flagged:
            self.memory.flag_conversation(
                user_id=user_id,
                session_id=session_id,
                reason=eval_scores.get("reasoning", "Low confidence response"),
            )

        return ChatResponse(
            response=response_text,
            eval=eval_block,
            tools_called=tools_called,
            session_id=session_id,
            user_id=user_id,
        )
