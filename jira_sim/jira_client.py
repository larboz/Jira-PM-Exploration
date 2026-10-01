"""Thin wrapper over the Jira Cloud REST API v3, plus the Agile (sprint) API.

Auth is basic auth with an Atlassian account email + API token, which is how
Jira Cloud expects programmatic access:
https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/
"""
import os
import requests
from requests.auth import HTTPBasicAuth


def _flatten_adf(node):
    """Flattens an Atlassian Document Format node tree down to plain text."""
    if not node:
        return ""
    if isinstance(node, str):
        return node
    parts = [node.get("text", "")] if node.get("type") == "text" else []
    for child in node.get("content", []) or []:
        parts.append(_flatten_adf(child))
    return "".join(parts)


class JiraClient:
    def __init__(self, site=None, email=None, token=None):
        self.site = (site or os.environ["JIRA_SITE"]).rstrip("/")
        self.email = email or os.environ["JIRA_EMAIL"]
        self.token = token or os.environ["JIRA_API_TOKEN"]
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.email, self.token)
        self.session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )
        self._field_cache = None

    # --- raw HTTP: platform REST API (issues, links, search) -----------------

    def _url(self, path):
        return f"{self.site}/rest/api/3/{path.lstrip('/')}"

    def get(self, path, **kw):
        r = self.session.get(self._url(path), **kw)
        r.raise_for_status()
        return r.json() if r.text else {}

    def post(self, path, json=None, **kw):
        r = self.session.post(self._url(path), json=json, **kw)
        if not r.ok:
            raise RuntimeError(f"POST {path} failed [{r.status_code}]: {r.text}")
        return r.json() if r.text else {}

    def put(self, path, json=None, **kw):
        r = self.session.put(self._url(path), json=json, **kw)
        if not r.ok:
            raise RuntimeError(f"PUT {path} failed [{r.status_code}]: {r.text}")
        return r.json() if r.text else {}

    # --- raw HTTP: agile REST API (boards, sprints) ---------------------------

    def _agile_url(self, path):
        return f"{self.site}/rest/agile/1.0/{path.lstrip('/')}"

    def agile_get(self, path, **kw):
        r = self.session.get(self._agile_url(path), **kw)
        r.raise_for_status()
        return r.json() if r.text else {}

    def agile_post(self, path, json=None, **kw):
        r = self.session.post(self._agile_url(path), json=json, **kw)
        if not r.ok:
            raise RuntimeError(f"AGILE POST {path} failed [{r.status_code}]: {r.text}")
        return r.json() if r.text else {}

    def agile_put(self, path, json=None, **kw):
        r = self.session.put(self._agile_url(path), json=json, **kw)
        if not r.ok:
            raise RuntimeError(f"AGILE PUT {path} failed [{r.status_code}]: {r.text}")
        return r.json() if r.text else {}

    # --- issue helpers ---------------------------------------------------------

    def get_field_id(self, field_name):
        """Looks up a (possibly custom) field's id by its display name, e.g.
        "Story point estimate". Cached for the life of the client."""
        if self._field_cache is None:
            self._field_cache = {f["name"]: f["id"] for f in self.get("field")}
        return self._field_cache.get(field_name)

    def create_issue(
        self,
        project_key,
        summary,
        issue_type,
        parent_key=None,
        labels=None,
        story_points=None,
        due_date=None,
        assignee_account_id=None,
    ):
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if labels:
            fields["labels"] = labels
        if due_date:
            fields["duedate"] = due_date
        if assignee_account_id:
            fields["assignee"] = {"accountId": assignee_account_id}
        if story_points is not None:
            field_id = self.get_field_id("Story point estimate") or self.get_field_id("Story Points")
            if field_id:
                fields[field_id] = story_points
        data = self.post("issue", json={"fields": fields})
        return data["key"]

    def add_comment(self, issue_key, text):
        body = {
            "body": {
                "type": "doc",
                "version": 1,
                "content": [{"type": "paragraph", "content": [{"type": "text", "text": text}]}],
            }
        }
        self.post(f"issue/{issue_key}/comment", json=body)

    def get_latest_comment(self, issue_key):
        """Plain-text body of the most recent comment on an issue, or None."""
        data = self.get(f"issue/{issue_key}/comment", params={"orderBy": "-created", "maxResults": 1})
        comments = data.get("comments", [])
        if not comments:
            return None
        return _flatten_adf(comments[0].get("body")).strip() or None

    def set_labels(self, issue_key, labels):
        self.put(f"issue/{issue_key}", json={"fields": {"labels": labels}})

    def set_due_date(self, issue_key, due_date_iso):
        self.put(f"issue/{issue_key}", json={"fields": {"duedate": due_date_iso}})

    def link_blocks(self, blocker_key, blocked_key):
        """blocker_key 'blocks' blocked_key (blocked_key 'is blocked by' blocker_key)."""
        self.post(
            "issueLink",
            json={
                "type": {"name": "Blocks"},
                "outwardIssue": {"key": blocker_key},
                "inwardIssue": {"key": blocked_key},
            },
        )

    def get_transitions(self, issue_key):
        data = self.get(f"issue/{issue_key}/transitions")
        return data.get("transitions", [])

    def transition_to(self, issue_key, target_status_name):
        for t in self.get_transitions(issue_key):
            if t["to"]["name"].lower() == target_status_name.lower():
                self.post(f"issue/{issue_key}/transitions", json={"transition": {"id": t["id"]}})
                return True
        return False

    def search(self, jql, fields=None, max_results=100):
        # Atlassian retired /rest/api/3/search (HTTP 410) in favor of this
        # cursor-paginated endpoint: startAt/total are gone, replaced by
        # nextPageToken. See https://developer.atlassian.com/changelog/#CHANGE-2046
        fields = fields or ["summary", "status", "labels", "issuelinks"]
        results, next_token = [], None
        while True:
            body = {"jql": jql, "maxResults": max_results, "fields": fields}
            if next_token:
                body["nextPageToken"] = next_token
            data = self.post("search/jql", json=body)
            issues = data.get("issues", [])
            results.extend(issues)
            next_token = data.get("nextPageToken")
            if not issues or not next_token:
                break
        return results

    # --- sprint helpers (team-managed Scrum projects) ---------------------------

    def get_board_id(self, project_key):
        data = self.agile_get(f"board?projectKeyOrId={project_key}")
        values = data.get("values", [])
        if not values:
            raise RuntimeError(f"No board found for project {project_key}")
        return values[0]["id"]

    def get_active_sprint(self, board_id):
        data = self.agile_get(f"board/{board_id}/sprint?state=active")
        values = data.get("values", [])
        return values[0] if values else None

    def create_sprint(self, board_id, name, start_iso, end_iso, goal=None):
        body = {"name": name, "originBoardId": board_id, "startDate": start_iso, "endDate": end_iso}
        if goal:
            body["goal"] = goal
        return self.agile_post("sprint", json=body)

    def start_sprint(self, sprint_id, start_iso, end_iso):
        # Jira's sprint PUT requires "name" to be resent even when only the
        # state/dates are changing, or it rejects with "Sprint name is required".
        current = self.agile_get(f"sprint/{sprint_id}")
        self.agile_put(
            f"sprint/{sprint_id}",
            json={"name": current["name"], "state": "active", "startDate": start_iso, "endDate": end_iso},
        )

    def close_sprint(self, sprint_id, fallback_start_iso=None, fallback_end_iso=None):
        # A sprint that was auto-created but never actually started (e.g. the
        # "Sprint 1" Jira drops into a brand-new Scrum project) has no dates
        # yet, and Jira won't close it without one, so fall back to the dates
        # of the sprint replacing it.
        current = self.agile_get(f"sprint/{sprint_id}")
        self.agile_put(
            f"sprint/{sprint_id}",
            json={
                "name": current["name"],
                "state": "closed",
                "startDate": current.get("startDate") or fallback_start_iso,
                "endDate": current.get("endDate") or fallback_end_iso,
            },
        )

    def add_issues_to_sprint(self, sprint_id, issue_keys):
        if not issue_keys:
            return
        self.agile_post(f"sprint/{sprint_id}/issue", json={"issues": issue_keys})
