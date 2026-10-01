"""Builds the executive status dashboard as a static HTML page for GitHub Pages.

Pulls live data straight from Jira (no LLM involved), aggregates it by team,
and renders docs/index.html. Run daily, right after daily_update.py, by the
same GitHub Actions workflow.
"""
import os
from datetime import date, datetime, timedelta, timezone

from jira_sim.archive import archive_current
from jira_sim.blocking import find_blocker
from jira_sim.charts import burndown_chart, team_status_chart
from jira_sim.decisions import load_open_decisions
from jira_sim.jira_client import JiraClient
from jira_sim.milestones import milestone_status, milestones_for_cycle
from jira_sim.state import load_state
from jira_sim.status import QUARTER_END, compute_status
from jira_sim.templates import FEATURE_POOL, TEAM_ORDER

STALE_DAYS = 5  # no activity in this many days -> flagged as an "Issue"
RISK_POINTS_THRESHOLD = 5  # story points at/above this count as "big" for risk purposes
CHOKEPOINT_THRESHOLD = 2  # blocking this many other stories makes a ticket a "chokepoint" risk

TEAM_NAMES = {
    "UXD": "UI/UX",
    "INF": "Infrastructure",
    "BE": "Backend",
    "API": "API",
    "FE": "Front End",
}
OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "index.html")
JIRA_SITE = os.environ.get("JIRA_SITE", "").rstrip("/")


def _issue_url(key):
    return f"{JIRA_SITE}/browse/{key}" if JIRA_SITE else "#"


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _parse_jira_dt(s):
    # Jira Cloud returns e.g. "2026-09-28T10:15:00.000-0500"
    return datetime.strptime(s, "%Y-%m-%dT%H:%M:%S.%f%z")


def _burndown_series(issues, sp_field_id):
    """Derives a day-by-day remaining-points burndown straight from each
    story's created/resolutiondate/duedate fields -- no separate history log
    to maintain, since Jira already timestamps all of this."""
    created_dates, due_dates, completions = [], [], []
    total_points = 0
    for issue in issues:
        f = issue["fields"]
        points = (f.get(sp_field_id) or 0) if sp_field_id else 0
        total_points += points
        created_raw = f.get("created")
        if created_raw:
            created_dates.append(_parse_jira_dt(created_raw).date())
        due_raw = f.get("duedate")
        if due_raw:
            due_dates.append(datetime.strptime(due_raw, "%Y-%m-%d").date())
        resolved_raw = f.get("resolutiondate")
        if resolved_raw:
            completions.append((_parse_jira_dt(resolved_raw).date(), points))

    if not created_dates:
        return [], [], [], date.today()

    start = min(created_dates)
    target_end = max(due_dates) if due_dates else date.today()
    today = date.today()
    end = max(target_end, today)
    span_days = (end - start).days or 1
    dates = [start + timedelta(days=i) for i in range(span_days + 1)]

    # The "actual" trace only has real data through today -- extending it
    # into the future (whenever the cycle's target date hasn't arrived yet)
    # would flat-line it at today's value, which reads as "no more progress
    # expected" rather than "not known yet". Only "ideal" spans the full
    # start-to-target range, since that's a fixed reference line, not data.
    actual = []
    for d in dates:
        if d > today:
            actual.append(None)
            continue
        done_by_d = sum(p for rd, p in completions if rd <= d)
        actual.append(max(total_points - done_by_d, 0))

    ideal_span = (target_end - start).days or 1
    ideal = []
    for d in dates:
        elapsed = (d - start).days
        remaining = total_points * max(0, 1 - elapsed / ideal_span)
        ideal.append(round(remaining, 1))

    return dates, ideal, actual, target_end


def gather(client, cycle_label):
    sp_field_id = client.get_field_id("Story point estimate") or client.get_field_id("Story Points")
    fields = ["summary", "status", "labels", "project", "issuelinks", "assignee", "duedate", "updated", "created", "resolutiondate"]
    if sp_field_id:
        fields.append(sp_field_id)

    jql = f'labels = "{cycle_label}" AND issuetype = Story'
    issues = client.search(jql, fields=fields)
    issues_by_key = {i["key"]: i for i in issues}

    by_team = {t: {"done": [], "in_progress": [], "todo": []} for t in TEAM_ORDER}
    blocked_rows = []
    behind_rows = []
    issue_rows = []
    risk_by_key = {}
    blocker_counts = {}
    today = date.today()
    now = datetime.now(timezone.utc)

    for issue in issues:
        f = issue["fields"]
        team = f["project"]["key"]
        status = f["status"]["name"]
        points = f.get(sp_field_id) if sp_field_id else None
        assignee = f.get("assignee")
        assignee_name = assignee["displayName"] if assignee else "Unassigned"
        due_raw = f.get("duedate")
        updated_raw = f.get("updated")

        entry = {"key": issue["key"], "summary": f["summary"], "points": points}
        bucket = by_team.setdefault(team, {"done": [], "in_progress": [], "todo": []})
        if status == "Done":
            bucket["done"].append(entry)
            continue
        elif status == "In Progress":
            bucket["in_progress"].append(entry)
        else:
            bucket["todo"].append(entry)

        blocker_key, blocker_summary, blocker_status = find_blocker(issue)
        is_behind = False
        if blocker_key:
            comment = client.get_latest_comment(issue["key"])
            blocked_rows.append(
                {
                    "key": issue["key"],
                    "team": team,
                    "assignee": assignee_name,
                    "comment": comment or "No comment logged yet.",
                    "summary": f["summary"],
                }
            )
            blocker_counts[blocker_key] = blocker_counts.get(blocker_key, 0) + 1
        elif due_raw:
            due = datetime.strptime(due_raw, "%Y-%m-%d").date()
            if due < today:
                is_behind = True
                behind_rows.append(
                    {
                        "key": issue["key"],
                        "team": team,
                        "assignee": assignee_name,
                        "due": due_raw,
                    }
                )

        # Issues: not blocked (that already has a known reason), not done,
        # but nobody's touched it in a while -- a stall with no explanation.
        if not blocker_key and updated_raw:
            try:
                days_stale = (now - _parse_jira_dt(updated_raw)).days
            except ValueError:
                days_stale = 0
            if days_stale >= STALE_DAYS:
                issue_rows.append(
                    {"key": issue["key"], "team": team, "assignee": assignee_name, "days": days_stale}
                )

        # High risk, criterion 1: a big story already in trouble.
        if points and points >= RISK_POINTS_THRESHOLD and (blocker_key or is_behind):
            entry = risk_by_key.setdefault(
                issue["key"],
                {"key": issue["key"], "team": team, "assignee": assignee_name, "points": points, "summary": f["summary"], "reasons": []},
            )
            entry["reasons"].append(f"{points}-pt story, {'blocked' if blocker_key else 'past due'}")

    # High risk, criterion 2: a chokepoint -- one ticket holding up several others.
    for blocker_key, count in blocker_counts.items():
        if count < CHOKEPOINT_THRESHOLD:
            continue
        blocker_issue = issues_by_key.get(blocker_key)
        if not blocker_issue:
            continue
        bf = blocker_issue["fields"]
        entry = risk_by_key.setdefault(
            blocker_key,
            {
                "key": blocker_key,
                "team": bf["project"]["key"],
                "assignee": (bf.get("assignee") or {}).get("displayName", "Unassigned"),
                "points": bf.get(sp_field_id) if sp_field_id else None,
                "summary": bf["summary"],
                "reasons": [],
            },
        )
        entry["reasons"].append(f"blocking {count} other stories")

    risk_rows = [{**v, "reason": "; ".join(v["reasons"])} for v in risk_by_key.values()]

    burndown = _burndown_series(issues, sp_field_id)

    return by_team, blocked_rows, behind_rows, risk_rows, issue_rows, burndown


def _feature_for(summary):
    for f in FEATURE_POOL:
        if f in summary:
            return f
    return None


def _feature_progress(by_team):
    """feature -> {done, remaining} across the whole cycle, so milestone
    status (upcoming vs. missed vs. achieved) can be computed per feature."""
    progress = {}
    for bucket in by_team.values():
        for status_key in ("done", "in_progress", "todo"):
            for entry in bucket[status_key]:
                feature = _feature_for(entry["summary"])
                if not feature:
                    continue
                p = progress.setdefault(feature, {"done": 0, "remaining": 0})
                if status_key == "done":
                    p["done"] += 1
                else:
                    p["remaining"] += 1
    return progress


def _upcoming_milestone_rows(features, by_team):
    """Milestones not yet wrapped up -- upcoming or already past their
    target -- sorted soonest-first. Achieved and not-in-cycle milestones
    aren't news, so they're left off."""
    progress = _feature_progress(by_team)
    rows = []
    for m in milestones_for_cycle(features):
        p = progress.get(m["feature"])
        status = milestone_status(m, p)
        if status not in ("upcoming", "missed"):
            continue
        total = (p["done"] + p["remaining"]) if p else 0
        pct = round(100 * p["done"] / total) if total else 0
        rows.append({**m, "status": status, "pct": pct})
    rows.sort(key=lambda m: m["target_date"])
    return rows


def _points_sum(entries):
    return sum(e.get("points") or 0 for e in entries)


def render(cycle_num, features, by_team, blocked_rows, behind_rows, risk_rows, issue_rows, decisions, burndown, requirements_url, latest_archive_date=None):
    total = sum(len(b["done"]) + len(b["in_progress"]) + len(b["todo"]) for b in by_team.values())
    done = sum(len(b["done"]) for b in by_team.values())
    in_progress = sum(len(b["in_progress"]) for b in by_team.values())
    todo = sum(len(b["todo"]) for b in by_team.values())
    pct = round(100 * done / total) if total else 0
    days_left = (QUARTER_END - date.today()).days

    total_points = sum(_points_sum(b["done"]) + _points_sum(b["in_progress"]) + _points_sum(b["todo"]) for b in by_team.values())
    done_points = sum(_points_sum(b["done"]) for b in by_team.values())

    flagged = len(blocked_rows) + len(behind_rows)
    status_key, status_label = compute_status(total, flagged, days_left)

    if blocked_rows:
        blocked_html = "\n".join(
            f'<tr><td><a href="{_issue_url(r["key"])}"><span class="key">{r["key"]}</span></a></td>'
            f'<td>{TEAM_NAMES.get(r["team"], r["team"])}</td>'
            f'<td>{_esc(r["assignee"])}</td><td>{_esc(r["comment"])}</td></tr>'
            for r in blocked_rows
        )
    else:
        blocked_html = '<tr><td colspan="4" class="empty">Nothing blocked right now.</td></tr>'

    if behind_rows:
        behind_html = "\n".join(
            f'<tr><td><a href="{_issue_url(r["key"])}"><span class="key">{r["key"]}</span></a></td>'
            f'<td>{TEAM_NAMES.get(r["team"], r["team"])}</td>'
            f'<td>{_esc(r["assignee"])}</td><td>{r["due"]}</td></tr>'
            for r in behind_rows
        )
    else:
        behind_html = '<tr><td colspan="4" class="empty">Nothing past its due date right now.</td></tr>'

    if risk_rows:
        risk_html = "\n".join(
            f'<tr><td><a href="{_issue_url(r["key"])}"><span class="key">{r["key"]}</span></a></td>'
            f'<td>{TEAM_NAMES.get(r["team"], r["team"])}</td>'
            f'<td>{_esc(r["assignee"])}</td><td>{_esc(r["reason"])}</td></tr>'
            for r in risk_rows
        )
    else:
        risk_html = '<tr><td colspan="4" class="empty">No standout risks right now.</td></tr>'

    if issue_rows:
        issue_html = "\n".join(
            f'<tr><td><a href="{_issue_url(r["key"])}"><span class="key">{r["key"]}</span></a></td>'
            f'<td>{TEAM_NAMES.get(r["team"], r["team"])}</td>'
            f'<td>{_esc(r["assignee"])}</td><td>{r["days"]} days</td></tr>'
            for r in issue_rows
        )
    else:
        issue_html = '<tr><td colspan="4" class="empty">Nothing stalled right now.</td></tr>'

    if decisions:
        decisions_html = "\n".join(
            f'<tr><td>{_esc(d.get("question", ""))}</td><td>{_esc(d.get("raised", ""))}</td></tr>' for d in decisions
        )
    else:
        decisions_html = '<tr><td colspan="2" class="empty">No open decisions logged.</td></tr>'

    milestone_rows = _upcoming_milestone_rows(features, by_team)
    if milestone_rows:
        milestone_html = "\n".join(
            f'<tr><td>{_esc(m["name"])}</td><td>{_esc(m["feature"])}</td>'
            f'<td>{m["target_date"]}</td><td>{m["pct"]}%</td>'
            f'<td><span class="ms-tag ms-{"warning" if m["status"] == "missed" else "good"}">'
            f'{"Behind schedule" if m["status"] == "missed" else "Upcoming"}</span></td></tr>'
            for m in milestone_rows
        )
    else:
        milestone_html = '<tr><td colspan="5" class="empty">No upcoming milestones this cycle.</td></tr>'
    generated = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    today_str = date.today().isoformat()
    req_link = (
        f'<a href="{requirements_url}">Requirements doc &#8594;</a>'
        if requirements_url
        else '<span class="muted">Requirements doc not generated yet</span>'
    )
    prev_day_link = (
        f'<a href="history/{latest_archive_date}.html">&larr; Previous day</a>' if latest_archive_date else ""
    )

    team_chart_html = team_status_chart(by_team, TEAM_ORDER, TEAM_NAMES)
    dates, ideal, actual, target_end = burndown
    burndown_html = burndown_chart(dates, ideal, actual, target_end, status_key) if dates else '<p class="empty">Not enough data yet to draw a burndown.</p>'

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<meta name="dashboard-generated-date" content="{today_str}">
<title>Fieldstone Commerce - Program Status</title>
<style>
  :root {{
    color-scheme: light;
    --surface: #fcfcfb; --page: #f9f9f7; --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
    --border: rgba(11,11,11,0.10); --grid: #e1e0d9;
    --good: #0ca30c; --warning: #fab219; --serious: #ec835a; --critical: #d03b3b;
    --stage-todo: #86b6ef; --stage-progress: #3987e5; --stage-done: #1c5cab;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --surface: #1a1a19; --page: #0d0d0d; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
      --border: rgba(255,255,255,0.10); --grid: #2c2c2a;
      --stage-todo: #6da7ec; --stage-progress: #2a78d6; --stage-done: #184f95;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 24px 16px 64px; background: var(--page); color: var(--ink);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  .wrap {{ max-width: 960px; margin: 0 auto; }}
  header {{ display: flex; flex-wrap: wrap; justify-content: space-between; align-items: baseline; gap: 8px; margin-bottom: 20px; }}
  .header-links {{ display: flex; gap: 14px; }}
  .history-nav {{ display: flex; justify-content: space-between; gap: 12px; margin: -10px 0 18px; font-size: 0.85rem; }}
  .history-nav a {{ color: var(--ink-2); }}
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
  .pts {{ font-size: 0.75rem; color: var(--muted); border: 1px solid var(--border); border-radius: 4px; padding: 0 4px; margin-left: 2px; }}
  .empty {{ color: var(--muted); font-style: italic; }}
  .ms-tag {{ display: inline-block; padding: 2px 8px; border-radius: 10px; font-size: 0.78rem; font-weight: 600; }}
  .ms-tag.ms-good {{ background: rgba(12,163,12,0.15); color: var(--good); }}
  .ms-tag.ms-warning {{ background: rgba(250,178,25,0.18); color: var(--warning); }}
  .charts-row {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(320px, 1fr)); gap: 20px; margin-top: 12px; }}
  .chart-wrap {{ background: var(--surface); border: 1px solid var(--border); border-radius: 8px; padding: 14px 16px; }}
  .chart-svg {{ width: 100%; height: auto; display: block; }}
  .chart-label {{ font-size: 11px; fill: var(--ink-2); }}
  .chart-value {{ font-size: 11px; fill: var(--ink-2); font-variant-numeric: tabular-nums; }}
  .chart-axis {{ stroke: var(--grid); stroke-width: 1; }}
  .chart-legend {{ display: flex; flex-wrap: wrap; gap: 14px; margin-top: 10px; font-size: 0.82rem; color: var(--ink-2); }}
  .chart-legend-item {{ display: inline-flex; align-items: center; gap: 6px; }}
  .chart-legend .swatch {{ width: 12px; height: 12px; border-radius: 3px; display: inline-block; }}
  .chart-legend .swatch.dash {{ width: 14px; height: 0; border-top: 2px dashed; border-radius: 0; background: none; }}
  .chart-caption {{ margin: 8px 0 0; font-size: 0.85rem; color: var(--ink-2); }}
  footer {{ margin-top: 40px; color: var(--muted); font-size: 0.82rem; }}
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Fieldstone Commerce <span class="muted">Program Status</span></h1>
    <div class="header-links">
      {prev_day_link}
      <a href="weekly.html">Weekly status &#8594;</a>
      {req_link}
    </div>
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
    <div class="tile"><div class="value">{done_points}/{total_points}</div><div class="label">Story points done</div></div>
  </div>

  <div class="charts-row">
    <div>
      <h2>Status by team</h2>
      {team_chart_html}
    </div>
    <div>
      <h2>Burndown</h2>
      {burndown_html}
    </div>
  </div>

  <h2>What's blocked ({len(blocked_rows)})</h2>
  <table>
    <thead><tr><th>Ticket</th><th>Team</th><th>Assignee</th><th>Why it's blocked</th></tr></thead>
    <tbody>{blocked_html}</tbody>
  </table>

  <h2>What's behind ({len(behind_rows)})</h2>
  <table>
    <thead><tr><th>Ticket</th><th>Team</th><th>Assignee</th><th>Due date</th></tr></thead>
    <tbody>{behind_html}</tbody>
  </table>

  <h2>High risks ({len(risk_rows)})</h2>
  <table>
    <thead><tr><th>Ticket</th><th>Team</th><th>Assignee</th><th>Why it's risky</th></tr></thead>
    <tbody>{risk_html}</tbody>
  </table>

  <h2>Issues ({len(issue_rows)})</h2>
  <table>
    <thead><tr><th>Ticket</th><th>Team</th><th>Assignee</th><th>Stalled for</th></tr></thead>
    <tbody>{issue_html}</tbody>
  </table>

  <h2>Unlogged decisions ({len(decisions)})</h2>
  <table>
    <thead><tr><th>Question</th><th>Raised</th></tr></thead>
    <tbody>{decisions_html}</tbody>
  </table>

  <h2>Upcoming milestones</h2>
  <table>
    <thead><tr><th>Milestone</th><th>Feature</th><th>Target date</th><th>% Complete</th><th>Status</th></tr></thead>
    <tbody>{milestone_html}</tbody>
  </table>

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
    decisions = load_open_decisions()

    if cycle_num == 0:
        by_team = {t: {"done": [], "in_progress": [], "todo": []} for t in TEAM_ORDER}
        blocked_rows, behind_rows, risk_rows, issue_rows = [], [], [], []
        burndown = ([], [], [], date.today())
    else:
        by_team, blocked_rows, behind_rows, risk_rows, issue_rows, burndown = gather(client, f"cycle-{cycle_num}")

    docs_dir = os.path.dirname(OUTPUT_PATH)
    latest_archive_date = archive_current(docs_dir)

    html = render(
        cycle_num, features, by_team, blocked_rows, behind_rows, risk_rows, issue_rows, decisions, burndown,
        requirements_url, latest_archive_date=latest_archive_date,
    )
    os.makedirs(docs_dir, exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote dashboard for cycle {cycle_num} to {OUTPUT_PATH}")
    if latest_archive_date:
        print(f"Archived prior page as docs/history/{latest_archive_date}.html")


if __name__ == "__main__":
    main()
