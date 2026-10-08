"""Temporary: dumps every Cycle 1 epic (key + project + summary) to
epics_dump.json so it can be read outside the GitHub Actions run (raw logs
aren't reachable from the agent's sandbox). Removed after use.
"""
import json

from jira_sim.jira_client import JiraClient
from jira_sim.state import load_state


def main():
    client = JiraClient()
    state = load_state()
    cycle_num = state.get("current_cycle", 1)
    cycle_label = f"cycle-{cycle_num}"

    jql = f'labels = "{cycle_label}" AND issuetype = Epic ORDER BY project ASC, key ASC'
    epics = client.search(jql, fields=["summary", "project"])
    data = [
        {
            "key": e["key"],
            "project": e["fields"]["project"]["key"],
            "summary": e["fields"]["summary"],
        }
        for e in epics
    ]
    with open("epics_dump.json", "w") as f:
        json.dump(data, f, indent=2)
    print(json.dumps(data, indent=2))


if __name__ == "__main__":
    main()
