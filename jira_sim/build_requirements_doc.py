"""Creates/updates the Confluence requirements page for the current cycle.

Called once per cycle (from generate_backlog.py, right after the new cycle's
Jira content exists) so the page always reflects the current cycle's scope.
The page id is stored in state so later cycles update the same page instead
of creating a new one each time.
"""
import os

from jira_sim.confluence_client import ConfluenceClient
from jira_sim.templates import DEPENDENCIES, TEAM_ORDER, TEAM_TEMPLATES

TEAM_NAMES = {
    "UXD": "UI/UX",
    "INF": "Infrastructure",
    "BE": "Backend",
    "API": "API",
    "FE": "Front End",
}

QUARTER_END = "2026-12-31"
PAGE_TITLE = "Fieldstone Commerce — Program Requirements"


def _dependency_rows():
    rows = []
    for (dep_team, dep_story), (blocker_team, blocker_story) in DEPENDENCIES:
        dep_label = TEAM_TEMPLATES[dep_team]["stories"][dep_story]
        blocker_label = TEAM_TEMPLATES[blocker_team]["stories"][blocker_story]
        rows.append(
            f"<tr><td>{TEAM_NAMES[blocker_team]}</td><td>{blocker_label}</td>"
            f"<td>&#8594;</td>"
            f"<td>{TEAM_NAMES[dep_team]}</td><td>{dep_label}</td></tr>"
        )
    return "\n".join(rows)


def render_body(cycle_num, features):
    team_rows = "\n".join(
        f"<tr><td><code>{key}</code></td><td>{TEAM_NAMES[key]}</td>"
        f"<td>{TEAM_TEMPLATES[key]['epic_name'].format(f='(feature)')}</td></tr>"
        for key in TEAM_ORDER
    )
    feature_items = "\n".join(f"<li>{f}</li>" for f in features)
    dependency_rows = _dependency_rows()

    return f"""
<h1>Fieldstone Commerce</h1>
<p>A custom-built online storefront platform. Five teams own the build end to
end, from design through infrastructure. Target: an end-of-quarter release,
<strong>{QUARTER_END}</strong>.</p>

<h2>Teams</h2>
<table>
<thead><tr><th>Key</th><th>Team</th><th>Epic pattern this cycle</th></tr></thead>
<tbody>
{team_rows}
</tbody>
</table>

<h2>Current cycle: Cycle {cycle_num}</h2>
<p>This cycle covers the following customer-facing features, each built as a
coordinated epic across all five teams:</p>
<ul>
{feature_items}
</ul>

<h2>Cross-team dependency chain</h2>
<p>Work flows UX/Infra &#8594; Backend &#8594; API &#8594; Front End. A story can't be
completed while its upstream dependency is still open, it shows up flagged as
<code>blocked</code> on the status dashboard instead.</p>
<table>
<thead><tr><th>Upstream (blocks)</th><th></th><th></th><th>Downstream (blocked by)</th><th></th></tr></thead>
<tbody>
{dependency_rows}
</tbody>
</table>

<h2>How this is generated</h2>
<p>This page and the live status dashboard are both generated automatically by
a daily job. See the <a href="https://github.com/larboz/Jira-PM-Exploration">
Jira-PM-Exploration</a> repo for how it works.</p>
""".strip()


def upsert_requirements_page(state, cycle_num, features):
    space_key = os.environ["CONFLUENCE_SPACE_KEY"]
    client = ConfluenceClient()
    html_body = render_body(cycle_num, features)

    page_id = state.get("confluence_page_id")
    if page_id:
        client.update_page(page_id, PAGE_TITLE, html_body)
    else:
        space_id = client.get_space_id(space_key)
        page = client.create_page(space_id, PAGE_TITLE, html_body)
        page_id = page["id"]
        state["confluence_page_id"] = page_id

    state["confluence_page_url"] = client.page_url(page_id)
    return state["confluence_page_url"]
