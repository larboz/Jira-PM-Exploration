"""Backlog content templates.

Each cycle picks a handful of customer-facing "features" from FEATURE_POOL and
generates one epic per team per feature, using TEAM_TEMPLATES. This keeps every
cycle "fresh but similar" without needing an LLM call to invent content — it's
pure templating + randomness, so it costs nothing to regenerate.

DEPENDENCIES encodes the cross-team pipeline: a (team, story_id) pair is
blocked by another (team, story_id) pair, for every feature in the cycle.
"""

FEATURE_POOL = [
    "Checkout Redesign",
    "Loyalty Program",
    "Product Recommendations",
    "Guest Checkout",
    "Wishlist Sync",
    "Order Tracking Timeline",
    "Multi-Currency Support",
    "Seller Storefronts",
    "Subscription Boxes",
    "One-Click Reorder",
    "Gift Card Wallet",
    "Live Inventory Alerts",
]

NUM_FEATURES_PER_CYCLE = 4

# Order matters: upstream teams are generated first so downstream teams can
# link against issue keys that already exist.
TEAM_ORDER = ["UXD", "INF", "BE", "API", "FE"]

TEAM_TEMPLATES = {
    "UXD": {
        "epic_name": "{f} – UX Design",
        "stories": {
            "flows": "User flow mapping for {f}",
            "wireframes": "Wireframes for {f}",
            "mockups": "Hi-fi mockups for {f}",
            "design_qa": "Design QA pass for {f}",
        },
    },
    "INF": {
        "epic_name": "{f} – Infrastructure Readiness",
        "stories": {
            "provision": "Provision environment & resources for {f}",
            "autoscale": "Autoscaling policy for {f}",
            "db_capacity": "DB schema & capacity planning for {f}",
        },
    },
    "BE": {
        "epic_name": "{f} – Backend Services",
        "stories": {
            "data_model": "Data model design for {f}",
            "core_service": "Core service implementation for {f}",
            "unit_tests": "Unit tests for {f} service",
            "code_review": "Backend code review for {f}",
        },
    },
    "API": {
        "epic_name": "{f} – API Layer",
        "stories": {
            "contract": "Define API contract for {f}",
            "endpoints": "Implement API endpoints for {f}",
            "integration_tests": "API integration tests for {f}",
            "docs": "Publish API docs for {f}",
        },
    },
    "FE": {
        "epic_name": "{f} – Front End Build",
        "stories": {
            "components": "Build UI components for {f}",
            "integration": "Wire up API integration for {f}",
            "cross_browser": "Cross-browser QA for {f}",
            "a11y": "Accessibility pass for {f}",
        },
    },
}

# (downstream team, story_id) is blocked by (upstream team, story_id)
DEPENDENCIES = [
    (("BE", "data_model"), ("INF", "provision")),
    (("API", "contract"), ("BE", "core_service")),
    (("FE", "integration"), ("API", "endpoints")),
    (("FE", "components"), ("UXD", "mockups")),
]
