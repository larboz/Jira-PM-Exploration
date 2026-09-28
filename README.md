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

Two more things get generated automatically each cycle:

- A **requirements page in Confluence** (program overview, the teams, this cycle's
  features, the dependency chain) — created once, then updated in place each cycle.
- A **live status dashboard**, published as a static site via GitHub Pages, showing
  whether the program looks on track, the current blockers, and a done / in-progress /
  next breakdown per team. It links back to the Confluence page.

## Repo layout

```
jira_sim/
  jira_client.py          Jira Cloud REST + Agile API wrapper (issues, links, sprints)
  confluence_client.py    Confluence Cloud REST API wrapper (pages)
  templates.py            feature pool + per-team epic/story templates + dependency map
  generate_backlog.py     builds one cycle's worth of epics/stories/links/sprints
  daily_update.py         advances/stalls tickets, detects cycle completion
  build_requirements_doc.py  creates/updates the Confluence requirements page
  build_dashboard.py      renders docs/index.html, the status dashboard
  state.py                reads/writes state/cycle_state.json
state/
  cycle_state.json        which cycle we're on, Confluence page id (committed by the workflow)
docs/
  index.html              the published dashboard (GitHub Pages serves this)
.github/workflows/
  daily-update.yml        the daily cron job
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

### 3. Create a Confluence space

Any space works — Spaces → Create space. Note its space key (shown in space settings,
a short code like `GS`).

### 4. Add GitHub repo secrets

In this repo: Settings → Secrets and variables → Actions → New repository secret. Add:

- `JIRA_SITE` — e.g. `https://yourdomain.atlassian.net` (no trailing slash)
- `JIRA_EMAIL` — the email on your Atlassian account
- `JIRA_API_TOKEN` — the token from step 2
- `CONFLUENCE_SPACE_KEY` — the space key from step 3

### 5. Allow the workflow to push

Settings → Actions → General → Workflow permissions → select **"Read and write
permissions"**. The daily job commits the updated cycle state and dashboard back to the
repo, so it needs this.

### 6. Turn on GitHub Pages

Settings → Pages → Source: **Deploy from a branch** → Branch: **main**, folder **/docs**
→ Save. (The `docs/index.html` file doesn't exist until step 7 runs once, so if Pages
complains there's nothing to serve yet, that's expected — come back after step 7.)

### 7. Kick off cycle 1

Go to the Actions tab → "Daily Jira Update" → "Run workflow". This bootstraps the first
cycle (epics/stories/links/sprints), creates the Confluence requirements page, and
builds the dashboard. After that, it runs automatically every day on the schedule in
the workflow file.

## Running locally (optional, for testing)

```
pip install -r requirements.txt
export JIRA_SITE=https://yourdomain.atlassian.net
export JIRA_EMAIL=you@example.com
export JIRA_API_TOKEN=...
python -m jira_sim.daily_update
```
