"""Builds a rolling weekly status page -- a Project Status Report Template
layout (banner, Project/Date meta row, a Time/Quality/Budget RAG row) with
exactly three narrative sections written in plain, executive-friendly
language: What We Achieved This Week, What's In Progress, What's Coming Up.
No ticket keys or story-point jargon in the narrative itself -- that detail
lives on the daily tracker, which this page links to.

Regenerated daily alongside the main dashboard so it always reflects a
trailing 7-day window -- no separate schedule needed.
"""
import os
from datetime import date, datetime

from jira_sim.blocking import find_blocker
from jira_sim.build_dashboard import gather as gather_dashboard_data
from jira_sim.jira_client import JiraClient
from jira_sim.milestones import milestone_status, milestones_for_cycle
from jira_sim.state import load_state
from jira_sim.status import QUARTER_END, compute_status
from jira_sim.templates import FEATURE_POOL, TEAM_ORDER
from jira_sim.weekly_snapshot import diff_and_maybe_roll

OUTPUT_PATH = os.path.join(os.path.dirname(__file__), "..", "docs", "weekly.html")
TEAM_NAMES = {
    "UXD": "UI/UX",
    "INF": "Infrastructure",
    "BE": "Backend",
    "API": "API",
    "FE": "Front End",
}
PROJECT_LIST = ", ".join(TEAM_ORDER)
MAX_LINES = 5


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _feature_for(summary):
    for f in FEATURE_POOL:
        if f in summary:
            return f
    return None


def _feature_set(issues):
    """Distinct feature names touched by a list of issues."""
    out = set()
    for issue in issues:
        feat = _feature_for(issue["fields"]["summary"])
        if feat:
            out.add(feat)
    return out


def _feature_teams(issues):
    """feature -> set of team keys touched, for naming which team's slice
    of a feature is about to start."""
    out = {}
    for issue in issues:
        f = issue["fields"]
        feat = _feature_for(f["summary"])
        if feat:
            out.setdefault(feat, set()).add(f["project"]["key"])
    return out


def _feature_progress(by_team):
    """feature -> {done, remaining} across the WHOLE cycle (not just this
    week), so we can tell whether a feature is actually fully wrapped."""
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


def _fmt_date(d):
    return datetime.strptime(d, "%Y-%m-%d").strftime("%b %-d") if isinstance(d, str) else d.strftime("%b %-d")


def _achieved_lines(completed_features, progress, milestones_by_feature, unblocked_features, total_completed_count):
    lines = []

    for feature in sorted(completed_features):
        p = progress.get(feature)
        if not p or p["remaining"] != 0:
            continue
        m = milestones_by_feature.get(feature)
        if m:
            target = date.fromisoformat(m["target_date"])
            today = date.today()
            if today <= target:
                lines.append(f'<li class="good"><strong>{_esc(m["name"])}</strong> shipped &mdash; on time for its {_fmt_date(target)} target.</li>')
            else:
                days_late = (today - target).days
                lines.append(f'<li class="warn"><strong>{_esc(m["name"])}</strong> shipped &mdash; {days_late} day{"s" if days_late != 1 else ""} after its {_fmt_date(target)} target.</li>')
        else:
            lines.append(f'<li class="good"><strong>{_esc(feature)}</strong> is complete and ready to ship.</li>')

    for feature in sorted(unblocked_features):
        if len(lines) >= MAX_LINES:
            break
        lines.append(f'<li class="good"><strong>{_esc(feature)}</strong> is moving again &mdash; a dependency that was holding it up got cleared this week.</li>')

    if not lines and total_completed_count:
        lines.append(f'<li>Steady progress across the program &mdash; {total_completed_count} items wrapped up this week.</li>')

    if not lines:
        lines.append('<li class="empty">Quiet week &mdash; nothing major closed out.</li>')

    return lines[:MAX_LINES]


def _in_progress_lines(in_progress_features, progress, milestones_by_feature, risk_features):
    lines = []
    for feature in sorted(in_progress_features):
        sentence = f'<strong>{_esc(feature)}</strong> is in active development'
        m = milestones_by_feature.get(feature)
        if m and milestone_status(m, progress.get(feature)) == "upcoming":
            sentence += f', targeting {_fmt_date(m["target_date"])}'
        sentence += "."
        cls = "warn" if feature in risk_features else ""
        if feature in risk_features:
            sentence += " The team has flagged a risk here worth watching."
        lines.append(f'<li class="{cls}">{sentence}</li>' if cls else f'<li>{sentence}</li>')

    if not lines:
        lines.append('<li class="empty">Nothing actively in motion right now.</li>')
    return lines[:MAX_LINES]


def _coming_up_lines(next_feature_teams, progress, milestones_by_feature, in_progress_features):
    lines = []
    covered = set(next_feature_teams)
    for feature in sorted(next_feature_teams):
        teams = ", ".join(sorted(TEAM_NAMES.get(t, t) for t in next_feature_teams[feature]))
        already_moving = feature in in_progress_features
        if already_moving:
            sentence = f'The next phase of <strong>{_esc(feature)}</strong> &mdash; {teams} &mdash; is ready to start'
        else:
            sentence = f'<strong>{_esc(feature)}</strong> is queued to start ({teams})'
        m = milestones_by_feature.get(feature)
        if m:
            sentence += f', targeting {_fmt_date(m["target_date"])}'
        sentence += "."
        lines.append(f'<li>{sentence}</li>')

    # Upcoming milestones for features not already mentioned (in progress or
    # next up) are still worth a forward-looking line of their own.
    for feature, m in sorted(milestones_by_feature.items()):
        if len(lines) >= MAX_LINES:
            break
        if feature in covered or feature in in_progress_features:
            continue
        if milestone_status(m, progress.get(feature)) == "upcoming":
            lines.append(f'<li><strong>{_esc(m["name"])}</strong> is targeted for {_fmt_date(m["target_date"])}.</li>')
            covered.add(feature)

    if not lines:
        lines.append('<li class="empty">Nothing queued to start immediately.</li>')
    return lines[:MAX_LINES]


def gather(client, cycle_num, features):
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
    next_up = [i for i in next_up if find_blocker(i)[0] is None]

    completed_features = _feature_set(completed)
    in_progress_features = _feature_set(in_progress)

    by_team, blocked_rows, behind_rows, risk_rows, issue_rows, _burndown = gather_dashboard_data(client, f"cycle-{cycle_num}")
    progress = _feature_progress(by_team)

    # Exclude only features that are fully wrapped -- not features that
    # merely had *something* completed this week, which is nearly all of
    # them. A different team's slice of an active feature can legitimately
    # still be ready to start next.
    next_feature_teams = {
        f: teams for f, teams in _feature_teams(next_up).items()
        if not (progress.get(f) and progress[f]["remaining"] == 0)
    }

    total = sum(len(b["done"]) + len(b["in_progress"]) + len(b["todo"]) for b in by_team.values())
    flagged = len(blocked_rows) + len(behind_rows)
    days_left = (QUARTER_END - date.today()).days
    status_key, status_label = compute_status(total, flagged, days_left)

    current_blocked_keys = [r["key"] for r in blocked_rows]
    unblocked_keys = diff_and_maybe_roll(current_blocked_keys)
    key_to_feature = {}
    for bucket in by_team.values():
        for status_bucket in ("done", "in_progress", "todo"):
            for entry in bucket[status_bucket]:
                feat = _feature_for(entry["summary"])
                if feat:
                    key_to_feature[entry["key"]] = feat
    unblocked_features = {key_to_feature[k] for k in unblocked_keys if k in key_to_feature}

    risk_features = {_feature_for(r["summary"]) for r in risk_rows if _feature_for(r.get("summary", ""))}

    milestones_by_feature = {m["feature"]: m for m in milestones_for_cycle(features)}

    achieved = _achieved_lines(completed_features, progress, milestones_by_feature, unblocked_features, len(completed))
    in_prog = _in_progress_lines(in_progress_features, progress, milestones_by_feature, risk_features)
    coming_up = _coming_up_lines(next_feature_teams, progress, milestones_by_feature, in_progress_features)

    return achieved, in_prog, coming_up, status_key, status_label


def render(achieved, in_progress, coming_up, status_key, status_label, cycle_num):
    achieved_html = "\n".join(achieved)
    in_progress_html = "\n".join(in_progress)
    coming_up_html = "\n".join(coming_up)
    generated_full = datetime.utcnow().strftime("%Y-%m-%d %H:%M UTC")
    today_str = date.today().isoformat()

    na_box = '<div class="rag-box rag-na"><div class="rag-label">Not tracked</div></div>'
    time_box = f'<div class="rag-box rag-{status_key}"><div class="rag-label">{status_label}</div></div>'

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
    --border: rgba(11,11,11,0.10); --grid: #e1e0d9; --label-bg: #eceae4;
    --banner: #16365c; --banner-ink: #ffffff;
    --good: #0ca30c; --warning: #fab219; --critical: #d03b3b; --na: #c7c5bd;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      color-scheme: dark;
      --surface: #1a1a19; --page: #0d0d0d; --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
      --border: rgba(255,255,255,0.10); --grid: #2c2c2a; --label-bg: #232320;
      --banner: #0d2742; --banner-ink: #ffffff;
      --na: #3a3a37;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 0 0 56px; background: var(--page); color: var(--ink);
    font-family: system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  .wrap {{ max-width: 760px; margin: 0 auto; padding: 0 16px; }}
  .banner {{ background: var(--banner); color: var(--banner-ink); padding: 22px 16px; text-align: center; margin-bottom: 20px; }}
  .banner h1 {{ margin: 0; font-size: 1.6rem; letter-spacing: .01em; }}
  .banner .sub {{ margin: 6px 0 0; font-size: 0.9rem; opacity: 0.85; }}
  .top-links {{ display: flex; justify-content: flex-end; gap: 14px; font-size: 0.9rem; margin-bottom: 14px; }}
  a {{ color: var(--ink); }}
  table.meta {{ width: 100%; border-collapse: collapse; margin-bottom: 28px; border: 1px solid var(--border); }}
  table.meta th, table.meta td {{ border: 1px solid var(--border); padding: 10px 14px; text-align: left; vertical-align: middle; font-size: 0.92rem; }}
  table.meta th {{ background: var(--label-bg); font-weight: 700; width: 180px; white-space: nowrap; }}
  .rag-row td {{ padding: 10px; }}
  .rag-group {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 2px; }}
  .rag-box {{ padding: 14px 8px; text-align: center; }}
  .rag-box .rag-label {{ font-weight: 700; font-size: 0.85rem; color: #1a1a1a; }}
  .rag-good {{ background: var(--good); }}
  .rag-warning {{ background: var(--warning); }}
  .rag-critical {{ background: var(--critical); color: #fff; }}
  .rag-critical .rag-label {{ color: #fff; }}
  .rag-na {{ background: var(--na); }}
  .rag-na .rag-label {{ color: var(--ink-2); font-weight: 600; }}
  .rag-names {{ display: grid; grid-template-columns: repeat(3, 1fr); gap: 2px; margin-bottom: 2px; }}
  .rag-names span {{ text-align: center; font-size: 0.72rem; text-transform: uppercase; letter-spacing: .04em; color: var(--ink-2); }}
  h2 {{ font-size: 1.05rem; border-bottom: 1px solid var(--grid); padding-bottom: 6px; margin-top: 30px; }}
  ul {{ padding-left: 20px; margin: 10px 0; list-style: none; }}
  li {{ margin-bottom: 10px; line-height: 1.45; padding-left: 20px; position: relative; }}
  li::before {{ content: "\\2022"; position: absolute; left: 4px; color: var(--muted); }}
  li.good::before {{ content: "\\2713"; color: var(--good); }}
  li.warn::before {{ content: "\\26A0"; color: var(--warning); }}
  li.empty {{ font-style: italic; color: var(--muted); }}
  li.empty::before {{ content: ""; }}
  footer {{ margin-top: 40px; color: var(--muted); font-size: 0.82rem; }}
</style>
</head>
<body>
<div class="banner">
  <h1>Fieldstone Commerce &mdash; Weekly Status</h1>
  <p class="sub">Rolling 7-day view, across the whole program</p>
</div>
<div class="wrap">
  <div class="top-links"><a href="index.html">Daily tracker &#8594;</a></div>

  <table class="meta">
    <tr><th>Project Name</th><td>Fieldstone Commerce (Cycle {cycle_num})</td></tr>
    <tr><th>Date</th><td>{today_str}</td></tr>
    <tr><th>Created By</th><td>Auto-generated &middot; updated {generated_full}</td></tr>
    <tr class="rag-row"><th>Status RAG</th><td>
      <div class="rag-names"><span>Time</span><span>Quality</span><span>Budget</span></div>
      <div class="rag-group">{time_box}{na_box}{na_box}</div>
    </td></tr>
  </table>

  <h2>What We Achieved This Week</h2>
  <ul>{achieved_html}</ul>

  <h2>What's In Progress</h2>
  <ul>{in_progress_html}</ul>

  <h2>What's Coming Up</h2>
  <ul>{coming_up_html}</ul>

  <footer>Generated {generated_full} &middot; <a href="https://github.com/larboz/Jira-PM-Exploration">source</a></footer>
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

    if cycle_num == 0:
        achieved, in_progress, coming_up, status_key, status_label = [], [], [], "good", "ON TRACK"
    else:
        achieved, in_progress, coming_up, status_key, status_label = gather(client, cycle_num, features)

    html = render(achieved, in_progress, coming_up, status_key, status_label, cycle_num)
    os.makedirs(os.path.dirname(OUTPUT_PATH), exist_ok=True)
    with open(OUTPUT_PATH, "w") as f:
        f.write(html)
    print(f"Wrote weekly status to {OUTPUT_PATH}")


if __name__ == "__main__":
    main()
