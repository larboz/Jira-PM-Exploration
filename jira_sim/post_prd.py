"""One-off: re-posts the Cycle 1 program PRD (now with epic keys/links) to
the existing Confluence page
https://larboz13.atlassian.net/wiki/spaces/GS/pages/5701639/Online+Store+PRD

Temporary script -- run once via the post-prd workflow, then removed.
"""
from jira_sim.confluence_client import ConfluenceClient

PAGE_ID = "5701639"
PAGE_TITLE = "Online Store PRD"
JIRA_SITE = "https://larboz13.atlassian.net"


def epic(key):
    return f'<a href="{JIRA_SITE}/browse/{key}">{key}</a>'


HTML_BODY = f"""
<h1>Fieldstone Commerce -- Cycle 1 PRD</h1>
<p><em>Generated 2026-10-08</em></p>

<h2>Overview</h2>
<p>Fieldstone Commerce is building a custom storefront platform across five teams -- UI/UX, Infrastructure, Backend, API, and Front End -- that hand work off in a fixed pipeline: UX produces mockups, Infrastructure provisions the environment, Backend builds the services, API exposes them, and Front End wires up the storefront experience.</p>
<p>Cycle 1 (target: 2026-12-31) bundles four customer-facing features being built in parallel across all five teams: <strong>Checkout Redesign</strong>, <strong>Multi-Currency Support</strong>, <strong>Subscription Boxes</strong>, and <strong>Wishlist Sync</strong>. Each feature gets its own epic per team, so the cycle totals 20 epics and 76 stories. As of today the cycle is 97% complete -- 74 of 76 stories done, with 2 not started (one in Infrastructure, one in API).</p>
<p>This document captures what each feature needs from every team, how the work sequences across the pipeline, and the risks and open decisions currently logged against the cycle.</p>

<h2>Goals and success metrics</h2>
<ul>
<li><strong>Ship all four features inside the Cycle 1 window</strong> (closing 2026-12-31), each against its own target launch date, without carrying stories past that window into Cycle 2.</li>
<li><strong>Keep the cross-team pipeline moving in order</strong> -- UX mockups feeding Front End, Infrastructure provisioning feeding Backend, Backend services feeding API contracts -- so no team is left idle waiting on an upstream handoff for more than a few days at a time.</li>
<li><strong>Surface risk early rather than discover it at launch.</strong> Every story that slips its due date or gets blocked should show up on the weekly status view the same week it happens, not after the fact.</li>
<li><strong>Close out open decisions before they become launch blockers</strong> -- in particular, the scope/schedule tradeoff for Checkout Redesign and the holiday-capacity question for Subscription Boxes (see Risks and open decisions below).</li>
</ul>
<p>Success for the cycle is simple to state: all 76 stories across the 20 epics reach Done, each feature hits its target date (or the date is consciously revised, not quietly missed), and nothing blocked sits unresolved for more than a week.</p>

<h2>Scope</h2>
<p><strong>In scope for Cycle 1:</strong></p>
<ul>
<li>Checkout Redesign, Multi-Currency Support, Subscription Boxes, and Wishlist Sync -- each built end-to-end across UX, Infrastructure, Backend, API, and Front End.</li>
<li>For every feature: UX flows/wireframes/mockups/design QA, infrastructure provisioning/autoscaling/DB capacity, backend data model/core service/unit tests/code review, API contract/endpoints/integration tests/docs, and front-end components/integration/cross-browser QA/accessibility.</li>
</ul>
<p><strong>Out of scope for Cycle 1</strong> (deferred to the feature pool for a future cycle):</p>
<ul>
<li>Loyalty Program, Product Recommendations, Guest Checkout, Order Tracking Timeline, Seller Storefronts, One-Click Reorder, Gift Card Wallet, and Live Inventory Alerts. These remain in the feature pool and are picked up automatically once Cycle 1 closes out.</li>
<li>Any rework triggered by a decision not yet made -- for example, if Checkout Redesign's scope or date changes per the open decision below, that change is handled as a cycle amendment, not assumed here.</li>
</ul>

<h2>Checkout Redesign</h2>
<p>Target launch: <strong>2026-10-15</strong>. This is the furthest-along feature in the cycle and the first one due.</p>
<table>
<thead><tr><th>Team</th><th>Epic</th><th>Stories</th></tr></thead>
<tbody>
<tr><td>UI/UX</td><td>{epic("UXD-10")} Checkout Redesign -- UX Design</td><td>User flow mapping, wireframes, hi-fi mockups, design QA pass</td></tr>
<tr><td>Infrastructure</td><td>{epic("INF-5")} Checkout Redesign -- Infrastructure Readiness</td><td>Provision environment &amp; resources, autoscaling policy, DB schema &amp; capacity planning</td></tr>
<tr><td>Backend</td><td>{epic("BE-6")} Checkout Redesign -- Backend Services</td><td>Data model design, core service implementation, unit tests, backend code review</td></tr>
<tr><td>API</td><td>{epic("API-6")} Checkout Redesign -- API Layer</td><td>Define API contract, implement endpoints, integration tests, publish docs</td></tr>
<tr><td>Front End</td><td>{epic("FE-6")} Checkout Redesign -- Front End Build</td><td>Build UI components, wire up API integration, cross-browser QA, accessibility pass</td></tr>
</tbody>
</table>
<p><strong>Known risk:</strong> Backend code review (BE-10) is paused -- the hi-fi mockups were reworked for a late payments-team fee-disclosure requirement, and review is held until the backend is confirmed to match. This puts the Oct 15 target at risk; see Risks below.</p>

<h2>Multi-Currency Support</h2>
<p>Target GA: <strong>2026-11-19</strong>.</p>
<table>
<thead><tr><th>Team</th><th>Epic</th><th>Stories</th></tr></thead>
<tbody>
<tr><td>UI/UX</td><td>{epic("UXD-5")} Multi-Currency Support -- UX Design</td><td>User flow mapping, wireframes, hi-fi mockups, design QA pass</td></tr>
<tr><td>Infrastructure</td><td>{epic("INF-1")} Multi-Currency Support -- Infrastructure Readiness</td><td>Provision environment &amp; resources, autoscaling policy, DB schema &amp; capacity planning</td></tr>
<tr><td>Backend</td><td>{epic("BE-1")} Multi-Currency Support -- Backend Services</td><td>Data model design, core service implementation, unit tests, backend code review</td></tr>
<tr><td>API</td><td>{epic("API-1")} Multi-Currency Support -- API Layer</td><td>Define API contract, implement endpoints, integration tests, publish docs</td></tr>
<tr><td>Front End</td><td>{epic("FE-1")} Multi-Currency Support -- Front End Build</td><td>Build UI components, wire up API integration, cross-browser QA, accessibility pass</td></tr>
</tbody>
</table>
<p>No open risks or blockers logged against this feature as of today -- it's tracking normally through the pipeline.</p>

<h2>Subscription Boxes</h2>
<p>Target beta: <strong>2026-12-15</strong>. This is the last feature due in the cycle, and the only one whose remaining runway crosses the Thanksgiving and December holidays.</p>
<table>
<thead><tr><th>Team</th><th>Epic</th><th>Stories</th></tr></thead>
<tbody>
<tr><td>UI/UX</td><td>{epic("UXD-20")} Subscription Boxes -- UX Design</td><td>User flow mapping, wireframes, hi-fi mockups, design QA pass</td></tr>
<tr><td>Infrastructure</td><td>{epic("INF-13")} Subscription Boxes -- Infrastructure Readiness</td><td>Provision environment &amp; resources, autoscaling policy, DB schema &amp; capacity planning</td></tr>
<tr><td>Backend</td><td>{epic("BE-16")} Subscription Boxes -- Backend Services</td><td>Data model design, core service implementation, unit tests, backend code review</td></tr>
<tr><td>API</td><td>{epic("API-16")} Subscription Boxes -- API Layer</td><td>Define API contract, implement endpoints, integration tests, publish docs</td></tr>
<tr><td>Front End</td><td>{epic("FE-16")} Subscription Boxes -- Front End Build</td><td>Build UI components, wire up API integration, cross-browser QA, accessibility pass</td></tr>
</tbody>
</table>
<p><strong>Known risk:</strong> open work remains in every team, and the final stretch overlaps the holidays when capacity typically drops. See Risks below.</p>

<h2>Wishlist Sync</h2>
<p>Target launch: <strong>2026-11-12</strong>.</p>
<table>
<thead><tr><th>Team</th><th>Epic</th><th>Stories</th></tr></thead>
<tbody>
<tr><td>UI/UX</td><td>{epic("UXD-15")} Wishlist Sync -- UX Design</td><td>User flow mapping, wireframes, hi-fi mockups, design QA pass</td></tr>
<tr><td>Infrastructure</td><td>{epic("INF-9")} Wishlist Sync -- Infrastructure Readiness</td><td>Provision environment &amp; resources, autoscaling policy, DB schema &amp; capacity planning</td></tr>
<tr><td>Backend</td><td>{epic("BE-11")} Wishlist Sync -- Backend Services</td><td>Data model design, core service implementation, unit tests, backend code review</td></tr>
<tr><td>API</td><td>{epic("API-11")} Wishlist Sync -- API Layer</td><td>Define API contract, implement endpoints, integration tests, publish docs</td></tr>
<tr><td>Front End</td><td>{epic("FE-11")} Wishlist Sync -- Front End Build</td><td>Build UI components, wire up API integration, cross-browser QA, accessibility pass</td></tr>
</tbody>
</table>
<p>No open risks or blockers logged against this feature as of today -- it's tracking normally through the pipeline.</p>

<h2>Cross-team dependencies and sequencing</h2>
<p>Every feature follows the same pipeline, so the same four handoffs repeat across all four features:</p>
<ol>
<li><strong>Infrastructure to Backend:</strong> Backend's data-model work can't start until Infrastructure has provisioned the environment and resources.</li>
<li><strong>Backend to API:</strong> API's contract definition can't start until Backend's core service implementation is in place.</li>
<li><strong>API to Front End:</strong> Front End's integration work can't start until API's endpoints are implemented.</li>
<li><strong>UX to Front End:</strong> Front End's component build can't start until UX's hi-fi mockups are ready.</li>
</ol>
<p>UX and Infrastructure are the two upstream starting points -- neither depends on another team -- while Front End is the downstream team with the most dependencies, needing both API and UX to finish first. A story that's ready to start but whose upstream dependency is still open gets labeled <code>blocked</code> automatically and surfaced on the weekly status view rather than silently stalling.</p>
<p>As of today this pipeline is running cleanly: nothing is currently blocked across any of the four features. The one exception is Checkout Redesign's backend code review (BE-10), which isn't blocked by another team's story but is deliberately paused pending confirmation that the backend matches a reworked requirement (see Risks below).</p>

<h2>Milestones and target dates</h2>
<table>
<thead><tr><th>Milestone</th><th>Feature</th><th>Target date</th></tr></thead>
<tbody>
<tr><td>Checkout Redesign launch</td><td>Checkout Redesign</td><td>2026-10-15</td></tr>
<tr><td>Wishlist Sync launch</td><td>Wishlist Sync</td><td>2026-11-12</td></tr>
<tr><td>Multi-Currency Support GA</td><td>Multi-Currency Support</td><td>2026-11-19</td></tr>
<tr><td>Subscription Boxes beta</td><td>Subscription Boxes</td><td>2026-12-15</td></tr>
</tbody>
</table>
<p>Checkout Redesign is first to launch, and it's also the one feature currently carrying an open schedule risk.</p>

<h2>Risks and open decisions</h2>
<ul>
<li><strong>No standing policy for a slipping feature</strong> (raised 2026-09-28): if a feature won't make its cycle deadline, there's no agreed default -- cut scope or push the date. Worth deciding before it's forced by a real deadline.</li>
<li><strong>Checkout Redesign's Oct 15 target is at risk</strong> (raised 2026-10-01): backend code review (BE-10) is paused because the hi-fi mockups were reworked for a late payments-team fee-disclosure requirement, and review is held until the backend is confirmed to match. Options are to push the date, cut scope, or pull in help to catch up.</li>
<li><strong>Subscription Boxes' Dec 15 target crosses the holidays</strong> (raised 2026-10-01): open work remains in every team, and the remaining runway crosses Thanksgiving and the December holidays, when capacity typically drops. Options are to pull the target in now, add resourcing, or accept the risk and monitor.</li>
</ul>
<p>As of today, nothing is blocked or past due across any of the four features -- the pipeline is clean. One stalled item is worth watching: INF-14 (Infrastructure) has had no movement in 7 days. None of these have an owner or decision recorded yet; that's the main open-items work for this cycle.</p>

<hr/>
<p><em>Generated from live Jira data and config/decisions.json. Full version with milestone diagram: <a href="https://claude.ai/artifact/PGJqk9AMmNNKn8Mbef1qk6">Fieldstone Commerce Cycle 1 PRD</a> (Claude Docs).</em></p>
""".strip()


def main():
    client = ConfluenceClient()
    client.update_page(PAGE_ID, PAGE_TITLE, HTML_BODY)
    print(f"Updated: {client.page_url(PAGE_ID)}")


if __name__ == "__main__":
    main()
