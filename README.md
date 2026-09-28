# Jira PM Exploration

A simulated 5-team engineering program (fictional company: **Fieldstone Commerce**, an
online store with proprietary software) used to demo how Claude can act as a senior
program manager on top of Jira and Confluence: standing up realistic work, running the
day-to-day churn, and producing an executive status view.

## The company

Fieldstone Commerce is building a custom storefront platform. Five teams:

| Team | Jira project key | What they do |
|---|---|---|
| UI/UX | `UXD` | User experience journeys, wireframes, mockups, design collateral |
| Infrastructure | `INF` | AWS: environments, autoscaling, databases, Kubernetes |
| Backend | `BE` | Core services and business logic |
| API | `API` | Bridges front end and backend, exposes data to third parties |
| Front End | `FE` | HTML/CSS/JS storefront experience |

Each "cycle" (target: one calendar quarter, first one ending **2026-12-31**) picks a
handful of customer-facing features from a pool and builds an epic per team per feature,
with realistic cross-team dependencies:

```
UXD (mockups) ───────────┐
                          ▼
INF (env/db) ──► BE (services) ──► API (endpoints) ──► FE (integration)
```

A story can't be marked Done by the daily update while its upstream dependency is still
open — it gets labeled `blocked` instead, which is exactly the kind of thing a program
manager needs surfaced.

When every story in a cycle reaches Done, the next cycle is generated automatically with
a fresh (but similarly-shaped) set of features. Nothing about this depends on a chat
session being open — it all runs on GitHub Actions.

Each project is a **Team-managed Scrum** board, so each cycle also gets its own sprint
per team (named "Cycle N"), created and started automatically, with that team's stories
for the cycle added to it. Only one sprint can be active per board at a time on the free
plan, so the previous cycle's sprint is closed right before the next one starts.

## Repo layout

```
jira_sim/
  jira_client.py     thin wrapper over the Jira Cloud REST API
  templates.py        feature pool + per-team epic/story templates + dependency map
  generate_backlog.py builds one cycle's worth of epics/stories/links
  daily_update.py     advances/stalls tickets, detects cycle completion
  state.py             reads/writes state/cycle_state.json
state/
  cycle_state.json     which cycle we're on (committed back by the workflow)
.github/workflows/
  daily-update.yml     the daily cron job
```

## One-time setup (do this before the automation can run)

### 1. Create the 5 Jira projects

In your Jira Cloud site, create 5 **Team-managed** projects with the **Scrum** template
(the default 3-column workflow: To Do / In Progress / Done is exactly what the automation
expects). Use these exact keys:

- `UXD` — name it "UI/UX"
- `INF` — name it "Infrastructure"
- `BE` — name it "Backend"
- `API` — name it "API"
- `FE` — name it "Front End"

Team-managed projects use "Story" and "Epic" issue types by default with a `parent`
field linking stories to epics — that's what this code assumes.

### 2. Get a Jira API token

Go to https://id.atlassian.com/manage-profile/security/api-tokens, create a token, copy it.

### 3. Add GitHub repo secrets

In this repo: Settings → Secrets and variables → Actions → New repository secret. Add:

- `JIRA_SITE` — e.g. `https://yourdomain.atlassian.net` (no trailing slash)
- `JIRA_EMAIL` — the email on your Atlassian account
- `JIRA_API_TOKEN` — the token from step 2

### 4. Allow the workflow to push

Settings → Actions → General → Workflow permissions → select **"Read and write
permissions"**. The daily job commits the updated cycle state back to the repo, so it
needs this.

### 5. Kick off cycle 1

Go to the Actions tab → "Daily Jira Update" → "Run workflow". This bootstraps the first
cycle (creates the initial epics/stories/links) since there's no cycle yet. After that,
it runs automatically every day on the schedule in the workflow file.

## Running locally (optional, for testing)

```
pip install -r requirements.txt
export JIRA_SITE=https://yourdomain.atlassian.net
export JIRA_EMAIL=you@example.com
export JIRA_API_TOKEN=...
python -m jira_sim.daily_update
```
