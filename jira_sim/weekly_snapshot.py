"""Tracks which stories were blocked as of the start of the current rolling
week, so the weekly page can report what got unblocked. A live Jira query
alone can't tell you this -- once a blocker resolves, the story just quietly
disappears from the "currently blocked" list with no trace of having been
there.
"""
import json
import os
from datetime import date

SNAPSHOT_PATH = os.path.join(os.path.dirname(__file__), "..", "state", "weekly_snapshot.json")


def _load():
    if not os.path.exists(SNAPSHOT_PATH):
        return {"blocked_keys": [], "as_of": date.today().isoformat()}
    with open(SNAPSHOT_PATH) as f:
        return json.load(f)


def diff_and_maybe_roll(current_blocked_keys):
    """Returns the keys blocked as of the last baseline that aren't blocked
    now. Only moves the baseline forward once 7+ days have passed, so the
    diff covers a real week rather than resetting every time the dashboard
    happens to run."""
    snap = _load()
    prev_keys = set(snap.get("blocked_keys", []))
    unblocked = sorted(prev_keys - set(current_blocked_keys))

    as_of_str = snap.get("as_of")
    as_of = date.fromisoformat(as_of_str) if as_of_str else date.today()
    should_roll = not os.path.exists(SNAPSHOT_PATH) or (date.today() - as_of).days >= 7

    if should_roll:
        os.makedirs(os.path.dirname(SNAPSHOT_PATH), exist_ok=True)
        with open(SNAPSHOT_PATH, "w") as f:
            json.dump({"blocked_keys": sorted(current_blocked_keys), "as_of": date.today().isoformat()}, f, indent=2)

    return unblocked
