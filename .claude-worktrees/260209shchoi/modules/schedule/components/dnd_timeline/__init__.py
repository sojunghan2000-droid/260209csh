"""Drag-and-drop timeline custom Streamlit component."""
import os
from typing import List, Dict, Any, Optional
import streamlit.components.v1 as components

_FRONTEND_DIR = os.path.join(os.path.dirname(__file__), "frontend")
_component_func = components.declare_component("dnd_timeline_v6", path=_FRONTEND_DIR)


def dnd_timeline(
    slots: List[str],
    in_schedules: List[Dict[str, Any]],
    out_schedules: List[Dict[str, Any]],
    is_admin: bool = False,
    sel_ids: Optional[List[str]] = None,
    sel_in_slots: Optional[List[str]] = None,
    sel_out_slots: Optional[List[str]] = None,
    admin_sel_kind: Optional[str] = None,
    username: str = "",
    user_sel_ids: Optional[List[str]] = None,
    key: str = None,
) -> Optional[Dict[str, Any]]:
    """Render a drag-and-drop timeline grid.

    Returns a dict {action, ts, ...} on user interaction, or None.
    Actions:
      - select:      {sched_id, kind}          — admin toggles booked slot
      - move:        {sched_id, to_slot, kind}  — admin drags booked slot
      - move_click:  {to_slot, kind}            — admin clicks 이동 target
      - toggle_book: {slot, kind}               — user toggles booking slot
      - user_select: {sched_id, kind}           — user toggles own booked slot
    """
    return _component_func(
        slots=list(slots),
        in_schedules=list(in_schedules),
        out_schedules=list(out_schedules),
        is_admin=is_admin,
        sel_ids=list(sel_ids or []),
        sel_in_slots=list(sel_in_slots or []),
        sel_out_slots=list(sel_out_slots or []),
        admin_sel_kind=admin_sel_kind,
        username=username,
        user_sel_ids=list(user_sel_ids or []),
        key=key,
        default=None,
    )
