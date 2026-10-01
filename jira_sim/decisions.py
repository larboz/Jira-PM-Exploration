"""Loads the manually-maintained decision log (config/decisions.json).

Unlike the other config files, this one is meant to be hand-edited -- by
Larry, straight in the repo (even via GitHub's web editor, no tooling
needed) -- whenever a real decision needs to be tracked. The dashboard just
surfaces whatever's still marked "open"; nothing here is auto-generated.
"""
import json
import os

DECISIONS_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "decisions.json")


def load_open_decisions():
    if not os.path.exists(DECISIONS_PATH):
        return []
    with open(DECISIONS_PATH) as f:
        data = json.load(f)
    return [d for d in data.get("decisions", []) if d.get("status") == "open"]
