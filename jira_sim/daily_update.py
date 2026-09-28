"""The periodic churn: advances some stories, blocks others, and rolls the
backlog over into a new cycle once everything in the current one is Done.

Run once a week by .github/workflows/daily-update.yml (kept its original
filename/module name even though the schedule is now weekly, to avoid
touching every reference to it). Deliberately has no LLM calls in it -- it's
pure randomness over Jira's REST API, so it's cheap to run and cheap to
re-run.
"""
import random

from jira_sim.blocking import find_blocker
from jira_sim.generate_backlog import generate_cycle
from jira_sim.jira_client import JiraClient
from jira_sim.state import load_state, save_state

ADVANCE_PROBABILITY = 0.35  # chance an unblocked open story moves forward one step, per run
STATUS_ORDER = ["To Do", "In Progress", "Done"]


def daily_pass(client, cycle_label):
    jql = f'labels = "{cycle_label}" AND issuetype = Story'
    issues = client.search(jql, fields=["summary", "status", "issuelinks", "labels"])
    open_issues = [i for i in issues if i["fields"]["status"]["name"] != "Done"]
    random.shuffle(open_issues)

    advanced = blocked_count = newly_blocked = unflagged = 0

    for issue in open_issues:
        key = issue["key"]
        status = issue["fields"]["status"]["name"]
        labels = issue["fields"].get("labels", [])
        blocker_key, blocker_summary, blocker_status = find_blocker(issue)

        if blocker_key:
            if "blocked" not in labels:
                client.set_labels(key, labels + ["blocked"])
                client.add_comment(
                    key,
                    f'Blocked by {blocker_key}: "{blocker_summary}" is still {blocker_status}.',
                )
                newly_blocked += 1
            blocked_count += 1
            continue
        elif "blocked" in labels:
            client.set_labels(key, [l for l in labels if l != "blocked"])
            unflagged += 1

        if random.random() < ADVANCE_PROBABILITY:
            idx = STATUS_ORDER.index(status)
            if idx < len(STATUS_ORDER) - 1:
                if client.transition_to(key, STATUS_ORDER[idx + 1]):
                    advanced += 1

    return {
        "open_total": len(open_issues),
        "advanced": advanced,
        "blocked": blocked_count,
        "newly_blocked": newly_blocked,
        "unblocked_this_pass": unflagged,
    }


def cycle_is_complete(client, cycle_label):
    jql = f'labels = "{cycle_label}" AND issuetype = Story AND status != Done'
    remaining = client.search(jql, fields=["summary"], max_results=1)
    return len(remaining) == 0


def _recover_features(client, cycle_label):
    """Best-effort reconstruction of a cycle's feature list from Jira itself,
    for a cycle that was bootstrapped before build_requirements_doc existed
    (so it was never recorded in state['history'])."""
    from jira_sim.templates import TEAM_TEMPLATES

    suffix = TEAM_TEMPLATES["UXD"]["epic_name"].format(f="\0").replace("\0", "")
    jql = f'labels = "{cycle_label}" AND issuetype = Epic AND project = UXD'
    epics = client.search(jql, fields=["summary"])
    return [e["fields"]["summary"].replace(suffix, "") for e in epics]


def main():
    from jira_sim.build_requirements_doc import upsert_requirements_page

    client = JiraClient()
    state = load_state()
    cycle_num = state.get("current_cycle", 0)

    if cycle_num == 0:
        result = generate_cycle(client, 1)
        state["current_cycle"] = 1
        state.setdefault("history", []).append(result)
        upsert_requirements_page(state, 1, result["features"])
        save_state(state)
        print(f"Bootstrapped cycle 1: {result}")
        return

    cycle_label = f"cycle-{cycle_num}"
    summary = daily_pass(client, cycle_label)
    print(f"Cycle {cycle_num} weekly pass: {summary}")

    # Self-heal: a cycle bootstrapped before the Confluence integration
    # existed never got a requirements page. Backfill it here instead of
    # waiting for the next cycle rollover.
    if "confluence_page_url" not in state:
        history = state.get("history", [])
        features = history[-1]["features"] if history else _recover_features(client, cycle_label)
        upsert_requirements_page(state, cycle_num, features)
        save_state(state)
        print(f"Backfilled requirements doc for cycle {cycle_num}: {state['confluence_page_url']}")

    if cycle_is_complete(client, cycle_label):
        next_cycle = cycle_num + 1
        result = generate_cycle(client, next_cycle)
        state["current_cycle"] = next_cycle
        state.setdefault("history", []).append(result)
        upsert_requirements_page(state, next_cycle, result["features"])
        save_state(state)
        print(f"Cycle {cycle_num} complete -- started cycle {next_cycle}: {result}")


if __name__ == "__main__":
    main()
