"""
The Agent Loop — the heart of the system.

Flow for each user message:
  1. Build system prompt (who the agent is)
  2. Inject recent memory as conversation history
  3. Send to Claude with tool definitions
  4. Claude may call tools (search_catalog, get_user_memory, flag_for_human)
  5. Execute each tool and send results back to Claude
  6. Claude produces final text response
  7. Separately prompt Claude to self-evaluate the response
  8. Return response + eval block + list of tools called
"""
import os
import json
import anthropic
from typing import List, Dict, Any, Tuple

from app.tools.search_catalog import search_catalog, TOOL_DEFINITION as CATALOG_TOOL
from app.tools.get_user_memory import get_user_memory_result, TOOL_DEFINITION as MEMORY_TOOL
from app.tools.flag_for_human import flag_for_human_result, TOOL_DEFINITION as FLAG_TOOL
from app.memory.base import BaseMemory

# ── Anthropic client (reads ANTHROPIC_API_KEY from environment) ───────────────
client = anthropic.Anthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
MODEL = "claude-opus-4-6"   # Use latest available model

TOOLS = [CATALOG_TOOL, MEMORY_TOOL, FLAG_TOOL]

SYSTEM_PROMPT = """You are a knowledgeable and friendly sales assistant for a B2B SaaS company.
Your job is to help potential customers understand our product plans, pricing, and features.

Rules:
- ALWAYS call get_user_memory first to understand this user's history before answering.
- ALWAYS call search_catalog when the user asks anything about plans, pricing, or features.
- Never guess or hallucinate product details — only answer from tool results.
- Be concise but complete. Match the user's tone (casual vs. formal).
- If you are genuinely uncertain, call flag_for_human and tell the user a specialist will follow up.
- Do not make up discounts, promises, or features not in the catalog.
"""


def run_agent(user_id: str, session_id: str, user_message: str,
              memory: BaseMemory) -> Tuple[str, List[str], bool]:
    """
    Run the full agent loop for one user message.

    Returns:
        (response_text, tools_called_list, human_flagged)
    """
    tools_called = []
    human_flagged = False

    # ── Build initial messages ────────────────────────────────────────────────
    messages: List[Dict[str, Any]] = [
        {"role": "user", "content": user_message}
    ]

    # ── Agentic loop: keep going until Claude stops calling tools ─────────────
    while True:
        response = client.messages.create(
            model=MODEL,
            max_tokens=1024,
            system=SYSTEM_PROMPT,
            tools=TOOLS,
            messages=messages,
        )

        # Append Claude's full response to the conversation
        messages.append({"role": "assistant", "content": response.content})

        # If Claude is done (no more tool calls), extract text and break
        if response.stop_reason == "end_turn":
            final_text = _extract_text(response.content)
            break

        # If Claude wants to use tools, execute them all
        if response.stop_reason == "tool_use":
            tool_results = []

            for block in response.content:
                if block.type != "tool_use":
                    continue

                tool_name = block.name
                tool_input = block.input
                tools_called.append(tool_name)

                # ── Dispatch to the right function ────────────────────────
                if tool_name == "search_catalog":
                    result = search_catalog(tool_input["query"])

                elif tool_name == "get_user_memory":
                    result = get_user_memory_result(tool_input["user_id"], memory)

                elif tool_name == "flag_for_human":
                    result = flag_for_human_result(
                        tool_input["user_id"], tool_input["reason"],
                        session_id, memory
                    )
                    human_flagged = True

                else:
                    result = {"error": f"Unknown tool: {tool_name}"}

                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(result),
                })

            # Send all tool results back to Claude in one message
            messages.append({"role": "user", "content": tool_results})

        else:
            # Unexpected stop reason — just extract whatever text exists
            final_text = _extract_text(response.content)
            break

    return final_text, list(dict.fromkeys(tools_called)), human_flagged


def self_evaluate(user_message: str, agent_response: str,
                  tools_called: List[str]) -> Dict[str, Any]:
    """
    Ask Claude to score its own response.

    This is a separate API call so it doesn't interfere with the main response.
    The prompt forces JSON output so we can parse it reliably.

    In production you'd replace this with a dedicated eval model or
    a framework like RAGAS for more objective scoring.
    """
    eval_prompt = f"""You are an evaluation assistant. Score the sales agent response below.

USER QUESTION:
{user_message}

AGENT RESPONSE:
{agent_response}

TOOLS USED: {', '.join(tools_called) if tools_called else 'none'}

Score the response and reply with ONLY valid JSON (no markdown, no explanation outside JSON):
{{
  "groundedness": <0.0-1.0, how well grounded in product catalog facts>,
  "relevance": <0.0-1.0, how directly it answers the question>,
  "confidence": <0.0-1.0, overall quality and correctness>,
  "flagged": <true if confidence < 0.5, else false>,
  "reasoning": "<one sentence explaining the scores>"
}}"""

    eval_resp = client.messages.create(
        model=MODEL,
        max_tokens=300,
        messages=[{"role": "user", "content": eval_prompt}],
    )

    raw = _extract_text(eval_resp.content)

    try:
        # Strip any accidental markdown fences
        clean = raw.strip().strip("```json").strip("```").strip()
        return json.loads(clean)
    except json.JSONDecodeError:
        # Safe fallback — never crash because of eval parsing
        return {
            "groundedness": 0.5,
            "relevance": 0.5,
            "confidence": 0.5,
            "flagged": False,
            "reasoning": "Eval parsing failed — default scores assigned.",
        }


def _extract_text(content_blocks) -> str:
    """Pull all TextBlock strings out of a response content list."""
    parts = []
    for block in content_blocks:
        if hasattr(block, "text"):
            parts.append(block.text)
    return " ".join(parts).strip()
