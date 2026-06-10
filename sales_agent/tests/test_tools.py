"""
Unit tests for the tools — no LLM calls, no DB needed.
Run with:  pytest tests/
"""
import sys, os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.tools.search_catalog import search_catalog

def test_search_finds_enterprise():
    result = search_catalog("enterprise SSO")
    names = [p["name"] for p in result["matched_plans"]]
    assert "Enterprise" in names

def test_search_finds_webhooks():
    result = search_catalog("webhooks")
    names = [p["name"] for p in result["matched_plans"]]
    assert "Growth" in names or "Enterprise" in names

def test_search_fallback_returns_all_plans():
    result = search_catalog("xyzqqqabcnotexist")
    assert len(result["matched_plans"]) == 3

def test_search_faq():
    result = search_catalog("free trial")
    assert any("trial" in faq["question"].lower() for faq in result["matched_faq"])

def test_add_ons_always_present():
    result = search_catalog("pricing")
    assert len(result["add_ons"]) > 0
