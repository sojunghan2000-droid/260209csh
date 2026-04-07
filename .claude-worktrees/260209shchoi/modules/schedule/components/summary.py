"""Daily summary component."""
import streamlit as st
from typing import List, Dict, Any
from config import KIND_IN, KIND_OUT


def render_daily_summary(schedules: List[Dict[str, Any]]):
    """Render daily summary card with counts by kind and gate."""
    in_count = sum(1 for s in schedules if s.get("kind") == KIND_IN)
    out_count = sum(1 for s in schedules if s.get("kind") == KIND_OUT)
    gates: Dict[str, int] = {}
    for s in schedules:
        g = s.get("gate", "N/A") or "N/A"
        gates[g] = gates.get(g, 0) + 1

    gate_text = " / ".join(f"{k}: {v}건" for k, v in sorted(gates.items()))

    st.markdown(
        f"""
    <div class="card" style="margin-top:12px;">
      <h4 style="margin:0 0 8px 0;">일일 요약</h4>
      <p style="margin:0; font-size:13px;">
        반입: <strong>{in_count}건</strong> / 반출: <strong>{out_count}건</strong>
      </p>
      <p style="margin:4px 0 0 0; font-size:12px; color:var(--text-muted);">
        GATE별: {gate_text or '없음'}
      </p>
    </div>
    """,
        unsafe_allow_html=True,
    )
