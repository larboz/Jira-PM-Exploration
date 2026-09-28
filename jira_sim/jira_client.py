"""Thin wrapper over the Jira Cloud REST API v3, plus the Agile (sprint) API.

Auth is basic auth with an Atlassian account email + API token, which is how
Jira Cloud expects programmatic access:
https://developer.atlassian.com/cloud/jira/platform/basic-auth-for-rest-apis/
"""
import os
import requests
from requests.auth import HTTPBasicAuth


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

    def create_issue(self, project_key, summary, issue_type, parent_key=None, labels=None):
        fields = {
            "project": {"key": project_key},
            "summary": summary,
            "issuetype": {"name": issue_type},
        }
        if parent_key:
            fields["parent"] = {"key": parent_key}
        if labels:
            fields["labels"] = labels
        data = self.post("issue", json={"fields": fields})
        return data["key"]

    def set_labels(self, issue_key, labels):
        self.put(f"issue/{issue_key}", json={"fields": {"labels": labels}})

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
        fields = fields or ["summary", "status", "labels", "issuelinks"]
        results, start_at = [], 0
        while True:
            data = self.post(
                "search",
                json={"jql": jql, "startAt": start_at, "maxResults": max_results, "fields": fields},
            )
            issues = data.get("issues", [])
            results.extend(issues)
            total = data.get("total", len(results))
            start_at += len(issues)
            if not issues or start_at >= total:
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
        self.agile_put(f"sprint/{sprint_id}", json={"state": "active", "startDate": start_iso, "endDate": end_iso})

    def close_sprint(self, sprint_id):
        self.agile_put(f"sprint/{sprint_id}", json={"state": "closed"})

    def add_issues_to_sprint(self, sprint_id, issue_keys):
        if not issue_keys:
            return
        self.agile_post(f"sprint/{sprint_id}/issue", json={"issues": issue_keys})
