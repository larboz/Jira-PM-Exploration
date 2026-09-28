"""Resolves the fictional roster (config/people.json) to real Jira accountIds.

Jira's assignee field only accepts a real Atlassian accountId -- there's no
way to fake a name on a ticket -- so the "people" on this program are real
users invited to the Jira site under Gmail "+alias" addresses (see README).
Each is looked up by email via the user-search endpoint; anyone whose invite
hasn't been accepted yet is silently skipped, so the pipeline still runs
fine before every invite lands.
"""
import json
import os

PEOPLE_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "people.json")


def load_roster(client):
    """Returns [{"name", "email", "account_id"}, ...] for every roster person
    Jira currently recognizes. Empty list if nobody's invite has been
    accepted yet -- callers should treat that as "leave tickets unassigned"."""
    with open(PEOPLE_PATH) as f:
        people = json.load(f)["people"]

    roster = []
    for person in people:
        matches = client.get("user/search", params={"query": person["email"]})
        if matches:
            roster.append({**person, "account_id": matches[0]["accountId"]})
    return roster
