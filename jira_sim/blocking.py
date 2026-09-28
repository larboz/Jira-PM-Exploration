"""Shared helper for reading an issue's blocking state off its issuelinks.

Used by both daily_update.py (to label/advance stories and post a comment the
first time something becomes blocked) and build_dashboard.py (to render the
"What's Blocked" table) so the two never disagree about what "blocked" means.
"""


def find_blocker(issue):
    """Returns (key, summary, status) of the first open issue this one is
    blocked by, or (None, None, None) if it isn't blocked. Requires the issue
    to have been fetched with the "issuelinks" field."""
    for link in issue["fields"].get("issuelinks", []):
        if link.get("type", {}).get("name") == "Blocks" and "inwardIssue" in link:
            blocker = link["inwardIssue"]
            status = blocker["fields"]["status"]["name"]
            if status != "Done":
                return blocker["key"], blocker["fields"]["summary"], status
    return None, None, None


def is_blocked(issue):
    return find_blocker(issue)[0] is not None
