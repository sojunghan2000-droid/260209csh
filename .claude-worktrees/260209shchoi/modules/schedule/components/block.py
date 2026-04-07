"""Schedule block rendering utility."""

STATUS_COLORS = {
    "PENDING": ("🟡", "#fbbf24"),
    "APPROVED": ("🟢", "#22c55e"),
    "REJECTED": ("🔴", "#ef4444"),
    "EXECUTING": ("🔵", "#3b82f6"),
    "DONE": ("⚪", "#94a3b8"),
}


def render_block_html(schedule_item: dict) -> str:
    """Render a single schedule block as HTML.

    Returns an HTML string representing the schedule item with
    status icon, color coding, company name, vehicle info, and time range.
    """
    status = schedule_item.get("status", "PENDING")
    icon, color = STATUS_COLORS.get(status, ("🟡", "#fbbf24"))
    company = schedule_item.get("company_name", "")
    vehicle = schedule_item.get("vehicle_info", "")
    time_from = schedule_item.get("time_from", "")
    time_to = schedule_item.get("time_to", "")
    title = schedule_item.get("title", "")
    gate = schedule_item.get("gate", "")

    return (
        f'<div class="sched-block" style="border-left:3px solid {color}; '
        f'background:var(--bg-hover); border-radius:4px; padding:4px 8px; margin:2px 0;">'
        f'<div style="font-size:12px; font-weight:600;">{icon} {title}</div>'
        f'<div style="font-size:11px; color:var(--text-muted);">'
        f"{time_from}~{time_to} | {company} {vehicle}"
        f"{f' | {gate}' if gate else ''}"
        f"</div>"
        f"</div>"
    )
