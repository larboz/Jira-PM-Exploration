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
- A **live status dashboard**, published as a static site via GitHub Pages. It's split
  into two pages:
  - `index.html` — the **daily tracker**: a "status by team" chart and a program-wide
    burndown chart, then five tables — **What's blocked**, **What's behind**,
    **High risks**, **Issues**, and **Unlogged decisions** (see below for how each is
    computed) — plus a done / in-progress / next breakdown per team. Links to the
    Confluence page and to the weekly status page.
  - `weekly.html` — a rolling 7-day **weekly status**: What we completed this week /
    What's in progress / What's coming next, condensed to a handful of lines per
    section across the whole program (not broken out by team). Rebuilt daily so it's
    always current, even though it's framed as "this week."

### How the daily tracker's tables are computed

- **What's blocked** / **What's behind** — straight from ticket state: a story is
  blocked if its dependency link says so, behind if it's past its due date and not
  Done.
- **High risks** — automatic, from ticket data. A story counts as a high risk if
  either: (a) it's a big story (5+ points) that's also blocked or behind, or (b) it's
  blocking 2 or more other stories (a chokepoint). The "why it's risky" column says
  which.
- **Issues** — automatic: any unblocked, not-done story that hasn't been touched in
  5+ days (stalled).
- **Unlogged decisions** — the one thing that *isn't* computed from Jira. A real
  decision needs a real decision-maker, so this is a small hand-maintained list in
  `config/decisions.json`. To log a new open question, or close one out, edit that
  file directly — even via GitHub's web editor, no local setup needed:

  ```json
  {
    "id": "d2",
    "question": "Do we cut scope or push the date?",
    "raised": "2026-09-28",
    "status": "open",
    "decision": null,
    "decided_date": null
  }
  ```

  The dashboard only ever shows entries with `"status": "open"`. Once a decision is
  made, set `"status": "closed"` (and fill in `decision`/`decided_date` for your own
  record) and it drops off the dashboard on the next run.

Every story gets story points (1/2/3/5/8), a due date, and a real assignee, drawn
from a small fictional roster (`config/people.json`). Jira's assignee field only
accepts a real Atlassian account, so those "people" are real users invited to your
Jira site under email aliases — see step 7 below. Anyone not yet invited is just
left unassigned until they are; nothing breaks in the meantime.

## Repo layout

```
jira_sim/
  jira_client.py          Jira Cloud REST + Agile API wrapper (issues, links, sprints, comments)
  confluence_client.py    Confluence Cloud REST API wrapper (pages)
  templates.py            feature pool + per-team epic/story templates + dependency map
  people.py               resolves config/people.json emails to real Jira accountIds
  blocking.py             shared "is this issue blocked, and by what" helper
  generate_backlog.py     builds one cycle's worth of epics/stories/links/sprints
  daily_update.py         advances/blocks tickets (posts a comment when newly blocked), detects cycle completion
  build_requirements_doc.py  creates/updates the Confluence requirements page
  build_dashboard.py      renders docs/index.html, the daily tracker (blocked/behind/risks/issues/decisions + charts)
  build_weekly_status.py  renders docs/weekly.html, the rolling weekly status page
  charts.py               inline-SVG chart helpers (status-by-team bar, burndown) used by build_dashboard.py
  decisions.py            loads the open entries from config/decisions.json
  state.py                reads/writes state/cycle_state.json
config/
  teams.json              company/teams config
  people.json             the fictional roster (name + email alias per person)
  decisions.json          hand-maintained decision log -- edit this yourself to log/close a decision
state/
  cycle_state.json        which cycle we're on, Confluence page id (committed by the workflow)
docs/
  index.html              the published daily tracker (GitHub Pages serves this)
  weekly.html             the published weekly status page
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
→ Save. (The `docs/index.html` file doesn't exist until step 8 runs once, so if Pages
complains there's nothing to serve yet, that's expected — come back after step 8.)

### 7. Invite the fictional roster as real Jira users

Jira won't let you assign a ticket to a name that isn't a real Atlassian account, so
the 5 fictional people in `config/people.json` need to actually exist as users on your
Jira site. The easiest way: use Gmail "+alias" addresses of your own inbox — mail to
`you+jordan@gmail.com` still lands in your normal inbox, but Jira treats it as a
separate account.

In Jira: **Settings (gear icon) → System → Invite user** (or **User management**),
and invite exactly these 5 addresses:

- `larboz+jordan@gmail.com` — Jordan Lee
- `larboz+priya@gmail.com` — Priya Nair
- `larboz+marcus@gmail.com` — Marcus Webb
- `larboz+casey@gmail.com` — Casey Alvarez
- `larboz+devon@gmail.com` — Devon Park

Each invite email lands in your normal Gmail inbox — open each one and accept it (you
may need to set a name/password for that "account" the first time). Anyone whose
invite you haven't accepted yet is simply left unassigned on tickets until you do —
nothing else breaks, so you can do this before or after step 8.

### 8. Kick off cycle 1

Go to the Actions tab → "Daily Jira Update" → "Run workflow". This bootstraps the first
cycle (epics/stories/links/sprints, with story points/due dates/assignees), creates the
Confluence requirements page, and builds the dashboard. After that, it runs
automatically every day on the schedule in the workflow file.

## Running locally (optional, for testing)

```
pip install -r requirements.txt
export JIRA_SITE=https://yourdomain.atlassian.net
export JIRA_EMAIL=you@example.com
export JIRA_API_TOKEN=...
python -m jira_sim.daily_update
```
