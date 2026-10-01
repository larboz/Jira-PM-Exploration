"""One-off scenario injection -- NOT part of the daily automation.

Run by hand (via the "Inject Scenario" GitHub Actions workflow,
workflow_dispatch only) when you want the dashboard to show a specific real
situation instead of waiting for one to occur naturally: a feature slipping
behind its milestone, or a capacity risk worth flagging before it becomes a
crisis. Each function makes a real, concrete edit to real Jira tickets
(a due date, a comment) so the change shows up through the normal automatic
detection on the daily tracker and weekly status page -- nothing here is
faked in the dashboard code itself.

This is meant to be edited per use: swap the ticket keys and wording below
for whatever scenario you actually want to demonstrate next time.
"""
from datetime import date, timedelta

from jira_sim.jira_client import JiraClient


def push_ticket_overdue(client, issue_key, days_overdue, reason):
    """Sets issue_key's due date to `days_overdue` days in the past and logs
    a comment explaining why. This is what makes a ticket show up in "What's
    behind" (and "High risks" if it carries enough story points) on the next
    dashboard build -- the detection is the existing automatic logic reading
    a real overdue due date, not a special case."""
    due = (date.today() - timedelta(days=days_overdue)).isoformat()
    client.set_due_date(issue_key, due)
    client.add_comment(issue_key, reason)
    print(f"{issue_key}: due date set to {due} (now overdue). Comment added: {reason}")


def flag_capacity_risk(client, issue_key, note):
    """Logs a comment documenting a forward-looking risk (one that hasn't
    broken anything yet) directly on the ticket, so it's recorded in Jira
    itself rather than only in a chat conversation. This does NOT change
    status or due date -- pair it with a config/decisions.json entry if the
    risk needs an actual decision, since "is this ticket late" is something
    the dashboard can compute but "should we change the plan because of the
    holidays" needs a human call."""
    client.add_comment(issue_key, note)
    print(f"{issue_key}: risk comment added: {note}")


def main():
    client = JiraClient()

    # Scenario 1: Checkout Redesign slips behind its Oct 15 milestone.
    # UXD-13 (the hi-fi mockup rework) already shipped by the time this was
    # re-run, so the live blocker is now BE-10 -- backend code review is
    # paused until the reworked checkout layout (driven by a late
    # payments-team fee-disclosure requirement) is confirmed to match.
    push_ticket_overdue(
        client,
        "BE-10",
        days_overdue=6,
        reason=(
            "Paused: holding backend code review until the reworked checkout layout is "
            "confirmed to match the payments team's new fee-disclosure requirement -- the "
            "hi-fi mockups were updated for it, and we don't want to sign off on backend "
            "changes that might need another pass. Expect this to land about a week later "
            "than planned, which pushes the whole Checkout Redesign timeline past the "
            "Oct 15 target."
        ),
    )

    # Scenario 2: Subscription Boxes (Dec 15 target) still has real work
    # spread across every team, and that work has to get done across
    # Thanksgiving and the December holidays, when capacity historically drops.
    flag_capacity_risk(
        client,
        "BE-18",
        note=(
            "Flagging a timeline risk, not a current blocker: Subscription Boxes still has "
            "open work in every team (design, infra, backend, API, front end), and the "
            "remaining runway to the Dec 15 target overlaps Thanksgiving week and the "
            "Christmas/New Year's stretch, when we should plan on meaningfully reduced "
            "team capacity. Recommend deciding now whether to pull the target in, add "
            "resourcing, or accept the risk and monitor -- waiting until December to "
            "notice this will be too late to do anything about it."
        ),
    )


if __name__ == "__main__":
    main()
