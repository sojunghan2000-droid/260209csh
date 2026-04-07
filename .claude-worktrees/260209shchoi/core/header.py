"""Hero header rendering."""
import streamlit as st
from supabase import Client
from config import APP_VERSION, DEFAULT_SITE_NAME
from db.models import settings_get

def ui_header(con: Client):
    """Render hero header with KPI stats."""
    # 프로젝트명 우선, 없으면 settings의 site_name 사용
    site_name = st.session_state.get("PROJECT_NAME") or settings_get(con, "site_name", DEFAULT_SITE_NAME)
    user_name = st.session_state.get("USER_NAME", "")
    user_role = st.session_state.get("USER_ROLE", "")
    is_admin = st.session_state.get("IS_ADMIN", False)
    project_id = st.session_state.get("PROJECT_ID", "")
    res = con.table("requests").select("status").eq("project_id", project_id).execute()
    rows = res.data or []
    total = len(rows)
    pending = sum(1 for r in rows if r.get("status") == "PENDING_APPROVAL")
    approved = sum(1 for r in rows if r.get("status") in ("APPROVED", "EXECUTING"))
    done = sum(1 for r in rows if r.get("status") == "DONE")
    st.markdown(f"""
    <div class="hero">
      <div class="hero-content">
        <div class="title">🏗️ {site_name}</div>
        <div class="sub">{APP_VERSION} · 현장 자재 반출입 관리 · 👤 {user_name} ({user_role}){"&nbsp;&nbsp;🔐 관리자" if is_admin else ""}</div>
        <div class="kpi" style="margin-top:8px;">
          <div class="box" style="background:#f1f5f9;border:1px solid #94a3b8;">
            <div class="n" style="color:#334155;">{total}</div><div class="l" style="color:#475569;">전체 요청</div>
          </div>
          <div class="box" style="background:#f1f5f9;border:1px solid #94a3b8;">
            <div class="n" style="color:#d97706;">{pending}</div><div class="l" style="color:#475569;">대기중</div>
          </div>
          <div class="box" style="background:#f1f5f9;border:1px solid #94a3b8;">
            <div class="n" style="color:#16a34a;">{approved}</div><div class="l" style="color:#475569;">승인됨</div>
          </div>
          <div class="box" style="background:#f1f5f9;border:1px solid #94a3b8;">
            <div class="n" style="color:#2563eb;">{done}</div><div class="l" style="color:#475569;">완료</div>
          </div>
        </div>
      </div>
    </div>
    """, unsafe_allow_html=True)
    if is_admin:
        if st.button("⚙️ 관리자 설정", key="admin_shortcut_btn"):
            st.session_state["ACTIVE_PAGE"] = "admin"
            st.rerun()
