"""
Tool: flag_for_human(user_id, reason)   [Bonus tool]

When the agent's confidence is very low, it can call this tool to log the
conversation for human review. The frontend can then show a "talk to a human"
button or route the user to support.
"""
from typing import Dict, Any

TOOL_DEFINITION = {
    "name": "flag_for_human",
    "description": (
        "Escalate this conversation for human review when you are not confident "
        "in your answer, when the question is outside the product scope, or when "
        "the user seems frustrated. Only call this when genuinely unsure."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "user_id": {"type": "string", "description": "The user's ID"},
            "reason": {
                "type": "string",
                "description": "Why this is being flagged, e.g. 'User asked about a feature not in catalog'"
            }
        },
        "required": ["user_id", "reason"]
    }
}


def flag_for_human_result(user_id: str, reason: str,
                          session_id: str, memory_backend) -> Dict[str, Any]:
    """Writes the flag to DB and returns confirmation to the agent."""
    memory_backend.flag_conversation(user_id, session_id, reason)
    return {
        "flagged": True,
        "user_id": user_id,
        "reason": reason,
        "message": "Conversation flagged for human review. A support agent will follow up.",
    }
