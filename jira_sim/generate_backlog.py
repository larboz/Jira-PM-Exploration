"""Generates one cycle's worth of epics/stories, starts a fresh sprint per team,
and wires the cross-team dependencies.

Called directly to bootstrap cycle 1, or automatically by daily_update.py once a
cycle's stories are all Done.

Each of the 5 team-managed Scrum projects gets its own sprint per cycle (named
"Cycle N"). Only one sprint can be active per board on the free plan, so before
starting a new one we close whatever is currently active.
"""
import random
from datetime import date, datetime, timedelta

from jira_sim.jira_client import JiraClient
from jira_sim.people import load_roster
from jira_sim.state import load_state, save_state
from jira_sim.templates import (
    DEPENDENCIES,
    FEATURE_POOL,
    NUM_FEATURES_PER_CYCLE,
    TEAM_ORDER,
    TEAM_TEMPLATES,
)

SPRINT_LENGTH_DAYS = 21  # informational only; sprints are actually closed when a cycle completes

STORY_POINTS_POOL = [1, 2, 3, 5, 8]
# Due dates are staggered to follow the same pipeline as DEPENDENCIES, so
# "behind" tickets show up first in upstream teams, same as in real life.
TEAM_DUE_OFFSET_DAYS = {"UXD": 7, "INF": 7, "BE": 12, "API": 17, "FE": 22}


def _due_date_for(team):
    base = TEAM_DUE_OFFSET_DAYS.get(team, 14)
    offset = base + random.randint(-2, 3)
    return (date.today() + timedelta(days=offset)).isoformat()


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%S.000Z")


def start_new_sprints(client, cycle_num):
    """Close each team's active sprint (if any) and start a fresh 'Cycle N' sprint."""
    start_iso = _iso(datetime.utcnow())
    end_iso = _iso(datetime.utcnow() + timedelta(days=SPRINT_LENGTH_DAYS))
    sprint_ids = {}
    for team in TEAM_ORDER:
        board_id = client.get_board_id(team)
        active = client.get_active_sprint(board_id)
        if active:
            client.close_sprint(active["id"], fallback_start_iso=start_iso, fallback_end_iso=start_iso)
        sprint = client.create_sprint(board_id, f"Cycle {cycle_num}", start_iso, end_iso)
        client.start_sprint(sprint["id"], start_iso, end_iso)
        sprint_ids[team] = sprint["id"]
    return sprint_ids


def generate_cycle(client, cycle_num):
    features = random.sample(FEATURE_POOL, k=min(NUM_FEATURES_PER_CYCLE, len(FEATURE_POOL)))
    label = f"cycle-{cycle_num}"

    sprint_ids = start_new_sprints(client, cycle_num)

    roster = load_roster(client)
    if not roster:
        print("No roster members found yet (invites not accepted) -- tickets will be unassigned.")

    # created[(team, feature, story_id)] = issue key; "__epic__" holds the epic key
    created = {}
    stories_by_team = {team: [] for team in TEAM_ORDER}

    for team in TEAM_ORDER:
        tpl = TEAM_TEMPLATES[team]
        for f in features:
            epic_key = client.create_issue(team, tpl["epic_name"].format(f=f), "Epic", labels=[label])
            created[(team, f, "__epic__")] = epic_key
            for story_id, story_tpl in tpl["stories"].items():
                assignee = random.choice(roster) if roster else None
                story_key = client.create_issue(
                    team,
                    story_tpl.format(f=f),
                    "Story",
                    parent_key=epic_key,
                    labels=[label],
                    story_points=random.choice(STORY_POINTS_POOL),
                    due_date=_due_date_for(team),
                    assignee_account_id=assignee["account_id"] if assignee else None,
                )
                created[(team, f, story_id)] = story_key
                stories_by_team[team].append(story_key)

    for team, keys in stories_by_team.items():
        client.add_issues_to_sprint(sprint_ids[team], keys)

    for (dep_team, dep_story), (blocker_team, blocker_story) in DEPENDENCIES:
        for f in features:
            blocked_key = created.get((dep_team, f, dep_story))
            blocker_key = created.get((blocker_team, f, blocker_story))
            if blocked_key and blocker_key:
                client.link_blocks(blocker_key, blocked_key)

    return {
        "cycle": cycle_num,
        "features": features,
        "issues_created": len(created),
        "sprint_ids": sprint_ids,
    }


def main():
    from jira_sim.build_requirements_doc import upsert_requirements_page

    client = JiraClient()
    state = load_state()
    cycle_num = state.get("current_cycle", 0) + 1
    result = generate_cycle(client, cycle_num)
    state["current_cycle"] = cycle_num
    state["cycle_started"] = date.today().isoformat()
    state.setdefault("history", []).append(result)
    upsert_requirements_page(state, cycle_num, result["features"])
    save_state(state)
    print(f"Generated cycle {cycle_num}: {result}")


if __name__ == "__main__":
    main()
