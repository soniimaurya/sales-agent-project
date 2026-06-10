"""
Tool: search_catalog(query)

Searches the product catalog JSON for plans/features/FAQs matching a query.
Uses simple keyword matching (no embeddings needed for a small catalog).
For a large catalog, replace the body with a vector search (pgvector, Pinecone).

Why a real function (not string-injected)?
  - Claude sees the function signature and knows WHEN to call it
  - The result is injected as a tool_result message — LLM can cite it
  - Logs which tool was called for the eval block
"""
import json
import os
from typing import List, Dict, Any


# Load the catalog once at import time — it's a static file
_CATALOG_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "catalog.json")

def _load_catalog() -> dict:
    with open(_CATALOG_PATH, "r") as f:
        return json.load(f)

CATALOG = _load_catalog()


def search_catalog(query: str) -> Dict[str, Any]:
    """
    Keyword search over plans, features, add-ons, and FAQ.

    Returns a dict with:
      - matched_plans: list of plan objects whose name/features match
      - matched_faq: list of FAQ entries whose Q or A match
      - add_ons: always included (small enough to always be relevant)
      - raw_query: the query that was searched (for debugging)
    """
    query_lower = query.lower()
    keywords = query_lower.split()

    matched_plans = []
    for plan in CATALOG.get("plans", []):
        # Score = how many keywords appear in the plan text
        plan_text = (
            plan["name"].lower() + " " +
            plan.get("ideal_for", "").lower() + " " +
            " ".join(plan.get("features", [])).lower() +
            plan.get("limitations", "").lower()
        )
        if any(kw in plan_text for kw in keywords):
            matched_plans.append(plan)

    matched_faq = []
    for item in CATALOG.get("faq", []):
        combined = (item["question"] + " " + item["answer"]).lower()
        if any(kw in combined for kw in keywords):
            matched_faq.append(item)

    # If no specific match found, return all plans (better than empty)
    if not matched_plans:
        matched_plans = CATALOG.get("plans", [])

    return {
        "matched_plans": matched_plans,
        "matched_faq": matched_faq,
        "add_ons": CATALOG.get("add_ons", []),
        "raw_query": query,
    }


# ── Claude tool definition (for the Anthropic tools API) ────────────────────

TOOL_DEFINITION = {
    "name": "search_catalog",
    "description": (
        "Search the SaaS product pricing and features catalog. "
        "Use this whenever the user asks about plans, pricing, features, "
        "limits, add-ons, trials, or anything product-related. "
        "Always call this before answering product questions — never guess."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "query": {
                "type": "string",
                "description": "The search query, e.g. 'enterprise pricing SSO' or 'webhooks'"
            }
        },
        "required": ["query"]
    }
}
