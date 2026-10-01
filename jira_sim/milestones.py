"""Loads the hand-maintained milestone list (config/milestones.json) and
works out each one's live status against the feature's actual completion
state. Larry sets the name and target date by hand -- same spirit as
config/decisions.json -- and the code figures out whether it was hit,
missed, or is still upcoming, since "is this feature actually done" is
objective and doesn't need a human call the way a real decision does.
"""
import json
import os
from datetime import date

MILESTONES_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "milestones.json")


def load_milestones():
    if not os.path.exists(MILESTONES_PATH):
        return []
    with open(MILESTONES_PATH) as f:
        return json.load(f).get("milestones", [])


def milestone_status(milestone, feature_progress):
    """feature_progress: the {"done": n, "remaining": n} dict for this
    milestone's feature (see build_weekly_status._feature_progress), or
    None if that feature isn't part of the current cycle at all.

    Returns one of: not_in_cycle, achieved_on_time, achieved_late, missed,
    upcoming.
    """
    if not feature_progress or feature_progress["done"] + feature_progress["remaining"] == 0:
        return "not_in_cycle"

    target = date.fromisoformat(milestone["target_date"])
    today = date.today()
    fully_done = feature_progress["remaining"] == 0 and feature_progress["done"] > 0

    if fully_done:
        return "achieved_on_time" if today <= target else "achieved_late"
    return "missed" if today > target else "upcoming"


def milestones_for_cycle(features):
    """Only the milestones whose feature is actually part of this cycle,
    with status attached."""
    out = []
    for m in load_milestones():
        if m.get("feature") in features:
            out.append(m)
    return out
