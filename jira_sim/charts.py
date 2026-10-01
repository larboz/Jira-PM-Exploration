"""Inline SVG chart helpers for the dashboard.

No JS, no charting library -- server-rendered <svg> markup that references
the page's own CSS custom properties (the --stage-*/--status-* tokens
defined in build_dashboard.py's <style> block), so one static chart
re-themes automatically with the page's existing light/dark CSS instead of
needing two renders.
"""


def _esc(s):
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# --- Team status: horizontal stacked bar, one per team --------------------
# Done / In progress / Not started are stages of one measure (completion),
# not unrelated categories, so this uses a single-hue ordinal ramp (light
# -> dark = less done -> more done) rather than categorical color.

def team_status_chart(by_team, team_order, team_names):
    totals = {}
    for team in team_order:
        b = by_team.get(team, {"done": [], "in_progress": [], "todo": []})
        totals[team] = (len(b["done"]), len(b["in_progress"]), len(b["todo"]))

    max_total = max((sum(v) for v in totals.values()), default=0)
    if max_total == 0:
        return '<p class="empty">No stories yet this cycle.</p>'

    label_w = 108
    plot_w = 380
    chart_w = label_w + plot_w + 56  # room for the total-count label at the tip
    bar_h = 20
    row_gap = 16
    seg_gap = 2

    bars = []
    y = 8
    for team in team_order:
        done, prog, todo = totals[team]
        total = done + prog + todo
        segs = [
            ("done", done, "var(--stage-done)"),
            ("prog", prog, "var(--stage-progress)"),
            ("todo", todo, "var(--stage-todo)"),
        ]
        present = [s for s in segs if s[1] > 0]
        x = label_w
        seg_markup = []
        for i, (name, n, color) in enumerate(present):
            w = (n / max_total) * plot_w
            is_last = i == len(present) - 1
            draw_w = max(w - (seg_gap if not is_last else 0), 1)
            rx = 4 if is_last else 0
            label = {"done": "Done", "prog": "In progress", "todo": "Not started"}[name]
            seg_markup.append(
                f'<rect x="{x:.1f}" y="{y}" width="{draw_w:.1f}" height="{bar_h}" rx="{rx}" '
                f'fill="{color}"><title>{team_names.get(team, team)}: {n} {label.lower()}</title></rect>'
            )
            x += w
        bars.append(
            f'<text x="{label_w - 10}" y="{y + bar_h / 2 + 4}" text-anchor="end" '
            f'class="chart-label">{_esc(team_names.get(team, team))}</text>'
            + "".join(seg_markup)
            + f'<text x="{label_w + plot_w + 10}" y="{y + bar_h / 2 + 4}" class="chart-value">{total}</text>'
        )
        y += bar_h + row_gap

    chart_h = y - row_gap + 8

    legend = (
        '<span class="chart-legend-item"><span class="swatch" style="background:var(--stage-done)"></span>Done</span>'
        '<span class="chart-legend-item"><span class="swatch" style="background:var(--stage-progress)"></span>In progress</span>'
        '<span class="chart-legend-item"><span class="swatch" style="background:var(--stage-todo)"></span>Not started</span>'
    )

    svg = (
        f'<svg viewBox="0 0 {chart_w} {chart_h}" class="chart-svg" role="img" '
        f'aria-label="Story status by team">{"".join(bars)}</svg>'
    )
    return f'<div class="chart-wrap">{svg}<div class="chart-legend">{legend}</div></div>'


# --- Burndown: ideal pace (dashed, muted) vs actual remaining (solid) -----

def burndown_chart(dates, ideal, actual, target_end, status_key):
    if not dates:
        return '<p class="empty">Not enough data yet to draw a burndown.</p>'

    chart_w = 640
    chart_h = 220
    pad_l, pad_r, pad_t, pad_b = 44, 12, 12, 28
    plot_w = chart_w - pad_l - pad_r
    plot_h = chart_h - pad_t - pad_b

    actual_known = [(i, v) for i, v in enumerate(actual) if v is not None]
    max_y = max([*ideal, *(v for _, v in actual_known), 1])
    n = len(dates)
    span = max(n - 1, 1)

    def xy(i, v):
        px = pad_l + (i / span) * plot_w
        py = pad_t + plot_h - (v / max_y) * plot_h
        return px, py

    def path(points):
        return "M " + " L ".join(f"{x:.1f} {y:.1f}" for x, y in points)

    ideal_path = path([xy(i, v) for i, v in enumerate(ideal)])
    actual_path = path([xy(i, v) for i, v in actual_known])

    # Gridlines + y ticks at 0 and the rounded max.
    y0_px = pad_t + plot_h
    ytop_px = pad_t
    gridlines = (
        f'<line x1="{pad_l}" y1="{y0_px}" x2="{chart_w - pad_r}" y2="{y0_px}" class="chart-axis"/>'
        f'<text x="{pad_l - 8}" y="{y0_px + 4}" text-anchor="end" class="chart-label">0</text>'
        f'<text x="{pad_l - 8}" y="{ytop_px + 4}" text-anchor="end" class="chart-label">{round(max_y)}</text>'
    )

    # X labels: start date and today.
    x_start, y_start = xy(0, ideal[0])
    x_end, y_end = xy(span, ideal[-1])
    x_labels = (
        f'<text x="{pad_l}" y="{chart_h - 6}" text-anchor="start" class="chart-label">{dates[0].isoformat()}</text>'
        f'<text x="{chart_w - pad_r}" y="{chart_h - 6}" text-anchor="end" class="chart-label">{dates[-1].isoformat()}</text>'
    )

    last_actual_i, last_actual_v = actual_known[-1]
    ax, ay = xy(last_actual_i, last_actual_v)
    ix, iy = xy(span, ideal[-1])

    status_var = {"good": "var(--good)", "warning": "var(--warning)", "critical": "var(--critical)"}[status_key]

    end_markers = (
        f'<circle cx="{ix:.1f}" cy="{iy:.1f}" r="4" fill="var(--surface)" stroke="var(--muted)" stroke-width="2">'
        f'<title>Ideal pace: {round(ideal[-1])} pts remaining on {dates[-1].isoformat()}</title></circle>'
        f'<circle cx="{ax:.1f}" cy="{ay:.1f}" r="5" fill="{status_var}" stroke="var(--surface)" stroke-width="2">'
        f'<title>Actual: {round(last_actual_v)} pts remaining on {dates[last_actual_i].isoformat()}</title></circle>'
    )

    svg = f"""<svg viewBox="0 0 {chart_w} {chart_h}" class="chart-svg" role="img" aria-label="Burndown: remaining story points over time">
      {gridlines}
      <path d="{ideal_path}" fill="none" stroke="var(--muted)" stroke-width="2" stroke-dasharray="5 4"/>
      <path d="{actual_path}" fill="none" stroke="{status_var}" stroke-width="2"/>
      {end_markers}
      {x_labels}
    </svg>"""

    legend = (
        '<span class="chart-legend-item"><span class="swatch dash" style="border-color:var(--muted)"></span>Ideal pace</span>'
        f'<span class="chart-legend-item"><span class="swatch" style="background:{status_var}"></span>Actual remaining</span>'
    )

    caption = (
        f'{round(last_actual_v)} pts remaining of {round(ideal[0])} &middot; '
        f"target {target_end.isoformat()}"
    )

    return (
        f'<div class="chart-wrap">{svg}<div class="chart-legend">{legend}</div>'
        f'<p class="chart-caption">{caption}</p></div>'
    )
