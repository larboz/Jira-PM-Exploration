"""Generates one cycle's worth of epics/stories and wires cross-team dependencies.

Called directly to bootstrap cycle 1, or automatically by daily_update.py once a
cycle's stories are all Done.
"""
import random
from datetime import date

from jira_sim.jira_client import JiraClient
from jira_sim.state import load_state, save_state
from jira_sim.templates import (
    DEPENDENCIES,
    FEATURE_POOL,
    NUM_FEATURES_PER_CYCLE,
    TEAM_ORDER,
    TEAM_TEMPLATES,
)


def generate_cycle(client, cycle_num):
    features = random.sample(FEATURE_POOL, k=min(NUM_FEATURES_PER_CYCLE, len(FEATURE_POOL)))
    label = f"cycle-{cycle_num}"

    # created[(team, feature, story_id)] = issue key; "__epic__" holds the epic key
    created = {}

    for team in TEAM_ORDER:
        tpl = TEAM_TEMPLATES[team]
        for f in features:
            epic_key = client.create_issue(team, tpl["epic_name"].format(f=f), "Epic", labels=[label])
            created[(team, f, "__epic__")] = epic_key
            for story_id, story_tpl in tpl["stories"].items():
                story_key = client.create_issue(
                    team, story_tpl.format(f=f), "Story", parent_key=epic_key, labels=[label]
                )
                created[(team, f, story_id)] = story_key

    for (dep_team, dep_story), (blocker_team, blocker_story) in DEPENDENCIES:
        for f in features:
            blocked_key = created.get((dep_team, f, dep_story))
            blocker_key = created.get((blocker_team, f, blocker_story))
            if blocked_key and blocker_key:
                client.link_blocks(blocker_key, blocked_key)

    return {"cycle": cycle_num, "features": features, "issues_created": len(created)}


def main():
    client = JiraClient()
    state = load_state()
    cycle_num = state.get("current_cycle", 0) + 1
    result = generate_cycle(client, cycle_num)
    state["current_cycle"] = cycle_num
    state["cycle_started"] = date.today().isoformat()
    state.setdefault("history", []).append(result)
    save_state(state)
    print(f"Generated cycle {cycle_num}: {result}")


if __name__ == "__main__":
    main()
