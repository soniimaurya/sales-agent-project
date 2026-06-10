"""
Tool: get_user_memory(user_id)

Retrieves the user's recent conversation history from the DB and formats it
as a context string the LLM can read.

This is what enables cross-session memory:
  Session 1: user asks about Enterprise pricing → saved to DB
  Session 2: agent calls get_user_memory → retrieves that context → answers "yes SSO is included"
  Without this tool, session 2 would have no idea what was discussed in session 1.
"""
from typing import Any, Dict


# Tool definition for the Anthropic tools API
TOOL_DEFINITION = {
    "name": "get_user_memory",
    "description": (
        "Retrieve what this user has asked about or expressed interest in during "
        "past conversations. Always call this at the start of a response to "
        "personalize answers and avoid asking the user to repeat themselves."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "user_id": {
                "type": "string",
                "description": "The user's unique identifier"
            }
        },
        "required": ["user_id"]
    }
}


def get_user_memory_result(user_id: str, memory_backend) -> Dict[str, Any]:
    """
    Called by the agent loop when Claude invokes the get_user_memory tool.
    Fetches recent messages and formats them as a readable context block.

    Args:
        user_id: the user to look up
        memory_backend: the injected BaseMemory implementation (SQLite/Postgres/etc.)

    Returns a dict that gets injected into the tool_result message to Claude.
    """
    recent = memory_backend.get_recent_context(user_id, n=10)

    if not recent:
        return {
            "user_id": user_id,
            "has_history": False,
            "context": "No previous conversations found for this user.",
            "message_count": 0,
        }

    # Format the history as a readable transcript
    lines = []
    for entry in recent:
        role_label = "User" if entry.role == "user" else "Assistant"
        lines.append(f"{role_label}: {entry.content}")

    return {
        "user_id": user_id,
        "has_history": True,
        "context": "\n".join(lines),
        "message_count": len(recent),
        "sessions_represented": len(set(e.session_id for e in recent)),
    }
