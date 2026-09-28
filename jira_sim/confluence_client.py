"""Thin wrapper over the Confluence Cloud REST API v2.

Uses the same Atlassian account email + API token as Jira (they're the same
account, Confluence is just a different product on the same site).
"""
import os
import requests
from requests.auth import HTTPBasicAuth


class ConfluenceClient:
    def __init__(self, site=None, email=None, token=None):
        self.site = (site or os.environ["JIRA_SITE"]).rstrip("/")
        self.email = email or os.environ["JIRA_EMAIL"]
        self.token = token or os.environ["JIRA_API_TOKEN"]
        self.session = requests.Session()
        self.session.auth = HTTPBasicAuth(self.email, self.token)
        self.session.headers.update(
            {"Accept": "application/json", "Content-Type": "application/json"}
        )

    def _url(self, path):
        return f"{self.site}/wiki/api/v2/{path.lstrip('/')}"

    def get(self, path, **kw):
        r = self.session.get(self._url(path), **kw)
        r.raise_for_status()
        return r.json() if r.text else {}

    def post(self, path, json=None, **kw):
        r = self.session.post(self._url(path), json=json, **kw)
        if not r.ok:
            raise RuntimeError(f"CONFLUENCE POST {path} failed [{r.status_code}]: {r.text}")
        return r.json() if r.text else {}

    def put(self, path, json=None, **kw):
        r = self.session.put(self._url(path), json=json, **kw)
        if not r.ok:
            raise RuntimeError(f"CONFLUENCE PUT {path} failed [{r.status_code}]: {r.text}")
        return r.json() if r.text else {}

    def get_space_id(self, space_key):
        data = self.get(f"spaces?keys={space_key}")
        results = data.get("results", [])
        if not results:
            raise RuntimeError(f"No Confluence space found for key '{space_key}'")
        return results[0]["id"]

    def create_page(self, space_id, title, html_body):
        body = {
            "spaceId": space_id,
            "status": "current",
            "title": title,
            "body": {"representation": "storage", "value": html_body},
        }
        return self.post("pages", json=body)

    def get_page(self, page_id):
        return self.get(f"pages/{page_id}")

    def update_page(self, page_id, title, html_body):
        current = self.get_page(page_id)
        next_version = current["version"]["number"] + 1
        body = {
            "id": page_id,
            "status": "current",
            "title": title,
            "body": {"representation": "storage", "value": html_body},
            "version": {"number": next_version},
        }
        return self.put(f"pages/{page_id}", json=body)

    def page_url(self, page_id):
        # This classic URL form always resolves regardless of space key or title slug.
        return f"{self.site}/wiki/pages/viewpage.action?pageId={page_id}"
