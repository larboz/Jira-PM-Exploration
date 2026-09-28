"""Builds the executive status dashboard as a static HTML page for GitHub Pages.

Pulls live data straight from Jira (no LLM involved), aggregates it by team,
and renders docs/index.html. Run daily, right after daily_update.py, by the
same GitHub Actions workflow.
"""
import os
from datetime import date, datetime

from jira_sim.jira_client import JiraClient
from jira_sim.state import load_state
from jira_sim.templates import TEAM_ORDER

QUARTER_END = date(2026, 12, 31)
TEAM_NAMES = {
    "UXD": "UI/UX",
    "INF": "Infrastructure",
    "BE": "Backend",
    "API": "API",
    "FE": "Front End",
}
# Categorical slots 1-5 from the dataviz reference palette, fixed order per team.
TEAM_COLOR_LIGHT = {
    "UXD": "#2a78d6",
    "INF": "#eb6834",
    "BE": "#1baf7a",
    "API": "#eda100",
    "FE": "#e87ba4",
}
TEAM_COLOR_DARK = {
    "UXD": "#3987e5",
    "INF": "#d95926",
    "BE": "#199e70",
    "API": "#c98500",
    "FE": "#d55181",
}
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "index.html")


def gather(client, cycle_label):
    jql = f'labels = "{cycle_label}" AND issuetype = Story'
    issues = client.search(jql, fields=["summary", "status", "labels", "project"])
    by_team = {t: {"done": [], "in_progress": [], "todo": []} for t in TEAM_ORDER}
    blockers = []
    for issue in issues:
        team = issue["fields"]["project"]["key"]
        status = issue["fields"]["status"]["name"]
        labels = issue["fields"].get("labels", [])
        entry = {"key": issue["key"], "summary": issue["fields"]["summary"]}
        bucket = by_team.setdefault(team, {"done": [], "in_progress": [], "todo": []})
        if status == "Done":
            bucket["done"].append(entry)
        elif status == "In Progress":
            bucket["in_progress"].append(entry)
        else:
            bucket["todo"].append(entry)
        if "blocked" in labels:
            blockers.append({**entry, "team": team, "reason": "Blocked on an upstream dependency"})
        elif "at-risk" in labels:
            blockers.append({**entry, "team": team, "reason": "Stalled in progress"})
    return by_team, blockers


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _story_list(entries, empty_text):
    if not entries:
        return f'<li class="empty">{empty_text}</li>'
    return "\n".join(f'<li><span class="key">{e["key"]}</span> {_esc(e["summary"])}</li>' for e in entries)


def render(cycle_num, features, by_team, blockers, requirements_url):
    total = sum(len(b["done"]) + len(b["in_progress"]) + len(b["todo"]) for b in by_team.values())
    done = sum(len(b["done"]) for b in by_team.values())
    in_progress = sum(len(b["in_progress"]) for b in by_team.values())
    todo = sum(len(b["todo"]) for b in by_team.values())
    pct = round(100 * done / total) if total else 0
    days_left = (QUARTER_END - date.today()).days
    blocked_ratio = (len(blockers) / total) if total else 0

    if days_left < 0:
        status_key, status_label = "critical", "PAST TARGET DATE"
    elif blocked_ratio >= 0.3:
        status_key, status_label = "critical", "BEHIND"
    elif blocked_ratio >= 0.15:
        status_key, status_label = "warning", "AT RISK"
    else:
        status_key, status_label = "good", "ON TRACK"

    team_sections = []
    for key in TEAM_ORDER:
        b = by_team.get(key, {"done": [], "in_progress": [], "todo": []})
        team_sections.append(f"""
      <section class="team-card" style="--team-color:{TEAM_COLOR_LIGHT[key]};--team-color-dark:{TEAM_COLOR_DARK[key]}">
        <h3>{TEAM_NAMES[key]} <span class="muted">{key}</span></h3>
        <div class="team-cols">
          <div><h4>Done ({len(b['done'])})</h4><ul>{_story_list(b['done'], 'Nothing done yet')}</ul></div>
          <div><h4>In progress ({len(b['in_progress'])})</h4><ul>{_story_list(b['in_progress'], 'Nothing in progress')}</ul></div>
          <div><h4>Next ({len(b['todo'])})</h4><ul>{_story_list(b['todo'], 'Backlog clear')}</ul></div>
        </div>
      </section>""")

    if blockers:
        blocker_rows = "\n".join(
            f'<tr><td><span class="key">{b["key"]}</span></td><td>{TEAM_NAMES.get(b["team"], b["team"])}</td>'
            f'<td>{_esc(b["summary"])}</td><td>{b["reason"]}</td></tr>'
            for b in blockers
        )
    else:
        blocker_rows = '<tr><td colspan="4" class="empty">No blockers right now.</td></tr>'

    features_html = "".join(f"<li>{_esc(f)}</li>" for f in features)
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    req_link = (
        f'<a href="{requirements_url}">Requirements doc &#8594;</a>'
        if requirements_url
        else '<span class="muted">Requirements doc not generated yet</span>'
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fieldstone Commerce — Program Status</title>
<style>
  :root {{
    color-scheme: light;
    --surface: #fcfcfb; --page: #f9f9f7; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
    --border: rgba(11,11,11,0.10); --grid: #e1e0d9;
    --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
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
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  header {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 20px; }}
  h1 {{ font-size: 1.4rem; margin: 0; }}
  .muted {{ color: var(--muted); font-weight: normal; }}
  a {{ color: var(--ink); }}
  .status-row {{ display: flex; flex-wrap: wrap; gap: 12px; margin-bottom: 20px; }}
  .badge {{ display: inline-flex; align-items: center; gap: 8px; padding: 10px 16px; border-radius: 8px; font-weight: 600; border: 1px solid var(--border); background: var(--surface); }}
  .badge .dot {{ width: 10px; height: 10px; border-radius: 50%; }}
  .badge.good .dot {{ background: var(--good); }} .badge.warning .dot {{ background: var(--warning); }} .badge.critical .dot {{ background: var(--critical); }}
  .stat-tiles {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(120px, 1fr)); gap: 12px; margin-bottom: 28px; }}
  .tile {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }}
  .tile .value {{ font-size: 1.6rem; font-weight: 700; }}
  .tile .label {{ color: var(--ink-2); font-size: 0.85rem; }}
  h2 {{ font-size: 1.1rem; border-bottom: 1px solid var(--grid); padding-bottom: 6px; margin-top: 32px; }}
  table {{ width: 100%; border-collapse: collapse; margin-top: 8px; }}
  th, td {{ text-align: left; padding: 8px 10px; border-bottom: 1px solid var(--grid); font-size: 0.9rem; vertical-align: top; }}
  th {{ color: var(--ink-2); font-weight: 600; font-size: 0.8rem; text-transform: uppercase; letter-spacing: .03em; }}
  .key {{ font-family: ui-monospace, monospace; color: var(--ink-2); font-size: 0.82rem; white-space: nowrap; }}
  .empty {{ color: var(--muted); font-style: italic; }}
  .team-card {{ background: var(--surface); border: 1px solid var(--border); border-left: 4px solid var(--team-color); border-radius: 8px; padding: 14px 18px; margin-top: 14px; }}
  @media (prefers-color-scheme: dark) {{ .team-card {{ border-left-color: var(--team-color-dark); }} }}
  .team-card h3 {{ margin: 0 0 10px; }}
  .team-cols {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(180px, 1fr)); gap: 16px; }}
  .team-cols h4 {{ margin: 0 0 6px; font-size: 0.8rem; color: var(--ink-2); text-transform: uppercase; letter-spacing: .03em; }}
  .team-cols ul {{ margin: 0; padding-left: 18px; font-size: 0.88rem; }}
  .team-cols li {{ margin-bottom: 4px; }}
  footer {{ margin-top: 40px; color: var(--muted); font-size: 0.82rem; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Fieldstone Commerce <span class="muted">Program Status</span></h1>
    <div>{req_link}</div>
  </header>

  <div class="status-row">
    <div class="badge {status_key}"><span class="dot"></span>{status_label}</div>
    <div class="badge"><strong>{pct}%</strong>&nbsp;of Cycle {cycle_num} done</div>
    <div class="badge"><strong>{days_left if days_left >= 0 else 0}</strong>&nbsp;days to {QUARTER_END.isoformat()}</div>
  </div>

  <div class="stat-tiles">
    <div class="tile"><div class="value">{total}</div><div class="label">Total stories</div></div>
    <div class="tile"><div class="value">{done}</div><div class="label">Done</div></div>
    <div class="tile"><div class="value">{in_progress}</div><div class="label">In progress</div></div>
    <div class="tile"><div class="value">{todo}</div><div class="label">Not started</div></div>
    <div class="tile"><div class="value">{len(blockers)}</div><div class="label">Blockers</div></div>
  </div>

  <h2>Blockers needing a look</h2>
  <table>
    <thead><tr><th>Ticket</th><th>Team</th><th>Summary</th><th>Why it's flagged</th></tr></thead>
    <tbody>{blocker_rows}</tbody>
  </table>

  <h2>This cycle's features</h2>
  <ul>{features_html}</ul>

  <h2>By team</h2>
  {"".join(team_sections)}

  <footer>Cycle {cycle_num} &middot; generated {generated} &middot; <a href="https://github.com/larboz/Jira-PM-Exploration">source</a></footer>
</div>
</body>
</html>
"""


def main():
    client = JiraClient()
    state = load_state()
    cycle_num = state.get("current_cycle", 0)
    history = state.get("history", [])
    features = history[-1]["features"] if history else []
    requirements_url = state.get("confluence_page_url")

    if cycle_num == 0:
        by_team, blockers = {t: {"done": [], "in_progress": [], "todo": []} for t in TEAM_ORDER}, []
    else:
        by_team, blockers = gather(client, f"cycle-{cycle_num}")

    html = render(cycle_num, features, by_team, blockers, requirements_url)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote dashboard for cycle {cycle_num} to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
