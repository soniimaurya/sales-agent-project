"""Utility to load catalog.json — used by routes and tools."""
import json, os

def load() -> dict:
    path = os.path.join(os.path.dirname(__file__), "catalog.json")
    with open(path) as f:
        return json.load(f)
