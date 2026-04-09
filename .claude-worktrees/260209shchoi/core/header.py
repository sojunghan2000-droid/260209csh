"""Hero header rendering."""
import streamlit as st
from datetime import date
from supabase import Client
from config import APP_VERSION, DEFAULT_SITE_NAME
from db.models import settings_get

def ui_header(con: Client):
    """Render hero header with KPI stats (당일 기준)."""
    site_name = st.session_state.get("PROJECT_NAME") or settings_get(con, "site_name", DEFAULT_SITE_NAME)
    user_name = st.session_state.get("USER_NAME", "")
    user_role = st.session_state.get("USER_ROLE", "")
    is_admin  = st.session_state.get("IS_ADMIN", False)
    project_id = st.session_state.get("PROJECT_ID", "")
    today = date.today().isoformat()

    # 당일 요청만 집계 (전체 대신 당일 KPI)
    res = con.table("requests").select("status,vehicle_count") \
        .eq("project_id", project_id).eq("date", today).execute()
    rows = res.data or []
    total      = len(rows)
    pending    = sum(1 for r in rows if r.get("status") == "PENDING_APPROVAL")
    approved   = sum(1 for r in rows if r.get("status") in ("APPROVED", "EXECUTING"))
    done       = sum(1 for r in rows if r.get("status") == "DONE")
    total_v    = sum((r.get("vehicle_count") or 0) for r in rows)
    pending_v  = sum((r.get("vehicle_count") or 0) for r in rows if r.get("status") == "PENDING_APPROVAL")
    approved_v = sum((r.get("vehicle_count") or 0) for r in rows if r.get("status") in ("APPROVED", "EXECUTING"))
    done_v     = sum((r.get("vehicle_count") or 0) for r in rows if r.get("status") == "DONE")

    st.markdown(f"""
    <div class="hero">
      <div class="hero-content">
        <div class="title">🏗️ {site_name}</div>
        <div class="sub">{APP_VERSION} · 현장 자재 반출입 관리 · 👤 {user_name} ({user_role}){"&nbsp;&nbsp;🔐 관리자" if is_admin else ""}</div>
        <div class="kpi" style="margin-top:8px;">
          <div class="box" style="background:#f1f5f9;border:1px solid #94a3b8;display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <div style="display:flex;align-items:center;gap:4px;">
              <span style="font-size:1.3em;font-weight:700;color:#334155;">{total}</span>
              <span style="color:#cbd5e1;font-size:1em;line-height:1;">|</span>
              <span style="font-size:0.85em;font-weight:400;color:#94a3b8;">{total_v}대</span>
            </div>
            <div style="font-size:11px;color:#475569;margin-top:2px;">전체 요청</div>
          </div>
          <div class="box" style="background:#f1f5f9;border:1px solid #94a3b8;display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <div style="display:flex;align-items:center;gap:4px;">
              <span style="font-size:1.3em;font-weight:700;color:#d97706;">{pending}</span>
              <span style="color:#cbd5e1;font-size:1em;line-height:1;">|</span>
              <span style="font-size:0.85em;font-weight:400;color:#94a3b8;">{pending_v}대</span>
            </div>
            <div style="font-size:11px;color:#475569;margin-top:2px;">대기중</div>
          </div>
          <div class="box" style="background:#f1f5f9;border:1px solid #94a3b8;display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <div style="display:flex;align-items:center;gap:4px;">
              <span style="font-size:1.3em;font-weight:700;color:#16a34a;">{approved}</span>
              <span style="color:#cbd5e1;font-size:1em;line-height:1;">|</span>
              <span style="font-size:0.85em;font-weight:400;color:#94a3b8;">{approved_v}대</span>
            </div>
            <div style="font-size:11px;color:#475569;margin-top:2px;">승인됨</div>
          </div>
          <div class="box" style="background:#f1f5f9;border:1px solid #94a3b8;display:flex;flex-direction:column;align-items:center;justify-content:center;">
            <div style="display:flex;align-items:center;gap:4px;">
              <span style="font-size:1.3em;font-weight:700;color:#2563eb;">{done}</span>
              <span style="color:#cbd5e1;font-size:1em;line-height:1;">|</span>
              <span style="font-size:0.85em;font-weight:400;color:#94a3b8;">{done_v}대</span>
            </div>
            <div style="font-size:11px;color:#475569;margin-top:2px;">완료</div>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    if is_admin:
        if st.button("⚙️ 관리자 설정", key="admin_shortcut_btn"):
            st.session_state["ACTIVE_PAGE"] = "admin"
            st.rerun()
