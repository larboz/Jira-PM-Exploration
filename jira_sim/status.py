"""Shared "is the program on track" logic, used by both the daily tracker
and the weekly status page so the Time status always agrees between them.
"""
from datetime import date

QUARTER_END = date(2026, 12, 31)


def compute_status(total, flagged, days_left):
    """total: all stories in the cycle. flagged: how many are blocked or
    behind. days_left: days until QUARTER_END (can be negative)."""
    flagged_ratio = (flagged / total) if total else 0
    if days_left < 0:
        return "critical", "PAST TARGET DATE"
    elif flagged_ratio >= 0.3:
        return "critical", "BEHIND"
    elif flagged_ratio >= 0.15:
        return "warning", "AT RISK"
    else:
        return "good", "ON TRACK"
