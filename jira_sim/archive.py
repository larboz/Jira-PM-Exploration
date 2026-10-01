"""Archives the previous day's rendered dashboard page before a new one is
written, so you can click back through history.

Each archived page is a frozen snapshot -- its data never changes once
written. Only the prev/next navigation at the top gets patched as newer days
get archived, so the chain always lines up:

    2026-09-28  <->  2026-09-29  <->  2026-09-30  <->  index.html (today)

Nothing here talks to Jira; it only moves and lightly rewrites the HTML
build_dashboard.py already produced.
"""
import os
import re
from datetime import datetime, timezone

HISTORY_NAV_RE = re.compile(r"<!-- HISTORY_NAV_START -->.*?<!-- HISTORY_NAV_END -->", re.DOTALL)
DATE_META_RE = re.compile(r'<meta name="dashboard-generated-date" content="([0-9-]+)">')


def _nav_block(prev_href, prev_label, next_href, next_label):
    prev_html = f'<a href="{prev_href}">&larr; {prev_label}</a>' if prev_href else "<span></span>"
    next_html = f'<a href="{next_href}">{next_label} &rarr;</a>' if next_href else "<span></span>"
    return f"<!-- HISTORY_NAV_START --><div class=\"history-nav\">{prev_html}{next_html}</div><!-- HISTORY_NAV_END -->"


def _patch_nav(content, prev_href, prev_label, next_href, next_label):
    nav = _nav_block(prev_href, prev_label, next_href, next_label)
    if HISTORY_NAV_RE.search(content):
        return HISTORY_NAV_RE.sub(nav, content)
    return content.replace("</header>", f"</header>\n{nav}", 1)


def archive_current(docs_dir):
    """If docs/index.html already exists, move it into docs/history/<date>.html
    before the caller overwrites index.html with today's page. Returns the
    date string (YYYY-MM-DD) of the archive, or None if there was nothing to
    archive yet (first-ever run)."""
    live_path = os.path.join(docs_dir, "index.html")
    if not os.path.exists(live_path):
        return None

    with open(live_path) as f:
        content = f.read()

    m = DATE_META_RE.search(content)
    if m:
        page_date = m.group(1)
    else:
        # Bootstrapping: a page built before this meta tag existed. Fall back
        # to its file mtime so the very first archive still gets a sane name.
        mtime = os.path.getmtime(live_path)
        page_date = datetime.fromtimestamp(mtime, tz=timezone.utc).strftime("%Y-%m-%d")

    history_dir = os.path.join(docs_dir, "history")
    os.makedirs(history_dir, exist_ok=True)
    archive_path = os.path.join(history_dir, f"{page_date}.html")

    if os.path.exists(archive_path):
        # Already archived today (e.g. workflow re-dispatched) -- don't
        # re-chain and don't clobber an already-correct archive.
        return page_date

    existing_dates = sorted(fn[:-5] for fn in os.listdir(history_dir) if fn.endswith(".html"))
    prev_date = existing_dates[-1] if existing_dates else None
    prev_prev_date = existing_dates[-2] if len(existing_dates) >= 2 else None

    # The only internal relative link in the page ("weekly.html") only
    # resolves correctly from docs/, not from docs/history/.
    archived_content = content.replace('href="weekly.html"', 'href="../weekly.html"')
    # Until a newer day is archived, this one is the most recent, so "next"
    # always leads to today's live page.
    archived_content = _patch_nav(
        archived_content,
        prev_href=f"{prev_date}.html" if prev_date else None,
        prev_label=prev_date,
        next_href="../index.html",
        next_label="Today",
    )
    with open(archive_path, "w") as f:
        f.write(archived_content)

    # The previously-latest archive used to point its "next" straight at the
    # live page. Now that this new archive exists, it must point here
    # instead, or clicking "next" from it would skip a day.
    if prev_date:
        prev_path = os.path.join(history_dir, f"{prev_date}.html")
        with open(prev_path) as f:
            prev_content = f.read()
        prev_content = _patch_nav(
            prev_content,
            prev_href=f"{prev_prev_date}.html" if prev_prev_date else None,
            prev_label=prev_prev_date,
            next_href=f"{page_date}.html",
            next_label=page_date,
        )
        with open(prev_path, "w") as f:
            f.write(prev_content)

    return page_date
