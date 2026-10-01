"""Builds a rolling weekly status page: what got done, what's moving, and
what's queued next, condensed to about one line per feature across the
whole program (not broken out by team). Regenerated daily alongside the
main dashboard so it always reflects a trailing 7-day window -- no separate
schedule needed.
"""
import os
from datetime import datetime

from jira_sim.blocking import find_blocker
from jira_sim.jira_client import JiraClient
from jira_sim.state import load_state
from jira_sim.templates import FEATURE_POOL, TEAM_ORDER

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "weekly.html")
TEAM_NAMES = {
    "UXD": "UI/UX",
    "INF": "Infrastructure",
    "BE": "Backend",
    "API": "API",
    "FE": "Front End",
}
PROJECT_LIST = ", ".join(TEAM_ORDER)


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _feature_for(summary):
    for f in FEATURE_POOL:
        if f in summary:
            return f
    return None


def _group_by_feature(issues):
    groups = {}
    for issue in issues:
        f = issue["fields"]
        feature = _feature_for(f["summary"])
        if not feature:
            continue
        groups.setdefault(feature, []).append(f["project"]["key"])
    return groups


def _lines(groups, verb):
    lines = []
    for feature, teams in groups.items():
        team_names = ", ".join(sorted({TEAM_NAMES.get(t, t) for t in teams}))
        n = len(teams)
        lines.append(
            f'<li><strong>{_esc(feature)}</strong> &mdash; {n} stor{"y" if n == 1 else "ies"} {verb} ({team_names})</li>'
        )
    return lines


def gather(client):
    completed = client.search(
        f"issuetype = Story AND status = Done AND resolutiondate >= -7d AND project in ({PROJECT_LIST})",
        fields=["summary", "project"],
    )
    in_progress = client.search(
        f'issuetype = Story AND status = "In Progress" AND project in ({PROJECT_LIST})',
        fields=["summary", "project"],
    )
    next_up = client.search(
        f'issuetype = Story AND status = "To Do" AND project in ({PROJECT_LIST})',
        fields=["summary", "project", "issuelinks"],
    )
    # Only count "next" stories that are actually ready to start -- otherwise
    # "coming next" is misleading about what's really about to move.
    next_up = [i for i in next_up if find_blocker(i)[0] is None]

    return _group_by_feature(completed), _group_by_feature(in_progress), _group_by_feature(next_up)


def render(completed, in_progress, next_up):
    completed_html = "\n".join(_lines(completed, "completed this week")) or '<li class="empty">Nothing completed in the last 7 days.</li>'
    progress_html = "\n".join(_lines(in_progress, "in progress")) or '<li class="empty">Nothing actively in progress.</li>'
    next_html = "\n".join(_lines(next_up, "queued and ready to start")) or '<li class="empty">Nothing ready to start right now.</li>'
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fieldstone Commerce - Weekly Status</title>
<style>
  :root {{
    color-scheme: light;
    --surface: #fcfcfb; --page: #f9f9f7; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
    --border: rgba(11,11,11,0.10); --grid: #e1e0d9;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --surface: #1a1a19; --page: #0d0d0d; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
      --border: rgba(255,255,255,0.10); --grid: #2c2c2a;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 16px 64px; background: var(--page); color: var(--ink);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  .wrap {{ max-width: 720px; margin: 0 auto; }}
  header {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 6px; }}
  h1 {{ font-size: 1.4rem; margin: 0; }}
  .muted {{ color: var(--muted); font-weight: normal; }}
  a {{ color: var(--ink); }}
  .subtitle {{ color: var(--muted); font-size: 0.9rem; margin: 0 0 20px; }}
  h2 {{ font-size: 1.05rem; border-bottom: 1px solid var(--grid); padding-bottom: 6px; margin-top: 30px; }}
  ul {{ padding-left: 20px; }}
  li {{ margin-bottom: 8px; line-height: 1.4; }}
  .empty {{ color: var(--muted); font-style: italic; }}
  footer {{ margin-top: 40px; color: var(--muted); font-size: 0.82rem; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Fieldstone Commerce <span class="muted">Weekly Status</span></h1>
    <div><a href="index.html">Daily tracker &#8594;</a></div>
  </header>
  <p class="subtitle">Rolling 7-day view, across the whole program &middot; updated {generated}</p>

  <h2>What we completed this week</h2>
  <ul>{completed_html}</ul>

  <h2>What's in progress</h2>
  <ul>{progress_html}</ul>

  <h2>What's coming next</h2>
  <ul>{next_html}</ul>

  <footer>Generated {generated} &middot; <a href="https://github.com/larboz/Jira-PM-Exploration">source</a></footer>
</div>
</body>
</html>
"""


def main():
    client = JiraClient()
    state = load_state()
    if state.get("current_cycle", 0) == 0:
        completed, in_progress, next_up = {}, {}, {}
    else:
        completed, in_progress, next_up = gather(client)
    html = render(completed, in_progress, next_up)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote weekly status to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
