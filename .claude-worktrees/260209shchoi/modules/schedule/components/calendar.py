"""Date navigation component for schedule."""
import streamlit as st
from datetime import date, timedelta


def render_date_nav(current_date: date) -> date:
    """Render a date navigation bar with previous/next day buttons.

    Layout: [< 전일] [date picker] [익일 >]
    Returns the selected date.
    """
    c1, c2, c3 = st.columns([1, 3, 1])
    with c1:
        if st.button("◀", key="sched_prev"):
            return current_date - timedelta(days=1)
    with c2:
        selected = st.date_input(
            "날짜",
            value=current_date,
            key="sched_date",
            label_visibility="collapsed",
        )
        return selected
    with c3:
        if st.button("▶", key="sched_next"):
            return current_date + timedelta(days=1)
    return current_date
