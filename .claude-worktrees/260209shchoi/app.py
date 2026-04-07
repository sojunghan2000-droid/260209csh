"""자재 반출입 관리 App. v3.0.0 — Entry Point.

Modular architecture with project-based authentication
and configurable feature modules.
"""
import html
import streamlit as st

# ── Page config (must be first Streamlit call) ──
st.set_page_config(
    page_title="자재 반출입 관리",
    page_icon="🏗️",
    layout="wide",
    initial_sidebar_state="auto",
)

# ── Imports ──
from db.connection import get_supabase
from db.migrations import db_init_and_migrate
from core.css import inject_css
from core.header import ui_header
from core.nav import render_topnav
from core.sidebar import render_sidebar
from auth.session import session_has_project, session_is_authed
from auth.login import page_project_select, page_login
from modules.approval.page import page_approval
from modules.execution.page import page_execute
from modules.outputs.page import page_outputs
from modules.ledger.page import page_ledger
from modules.admin.page import page_admin
from modules.schedule.page import page_schedule


# ── Page router ──
PAGE_ROUTER = {
    "계획": page_schedule,
    "승인":      page_approval,
    "확인":      page_execute,
    "산출물":    page_outputs,
    "대장":      page_ledger,
    "관리자":    page_admin,
}


def page_home(sb):
    """Home page — imported here to avoid circular deps."""
    from modules.request.crud import req_list, req_delete
    from modules.approval.crud import approvals_inbox
    from modules.execution.crud import photos_for_req
    from config import KIND_IN
    from pathlib import Path
    from shared.helpers import today_str

    role      = st.session_state.get("USER_ROLE", "")
    is_admin  = st.session_state.get("IS_ADMIN", False)
    user_name = st.session_state.get("USER_NAME", "")

    st.markdown("""
    <style>
    :root [class*="st-key-home_del_"] button {
        background-color: #b91c1c !important;
        border-color: #b91c1c !important;
        border-radius: 4px !important;
    }
    :root [class*="st-key-home_del_"] button:hover {
        background-color: #991b1b !important;
        border-color: #991b1b !important;
    }
    :root [class*="st-key-home_del_"] button,
    :root [class*="st-key-home_del_"] button p,
    :root [class*="st-key-home_del_"] button span,
    :root [class*="st-key-home_del_"] button * {
        color: #f8f8f8 !important;
    }
    [class*="st-key-home_goto_btn_"] button {
        overflow: hidden !important;
    }
    [class*="st-key-home_goto_btn_"] button p {
        white-space: nowrap !important;
        overflow: hidden !important;
        text-overflow: ellipsis !important;
        display: block !important;
        max-width: 100% !important;
    }
    /* 항목 간 여백 */
    [class*="st-key-home_goto_"] {
        margin-bottom: 2px !important;
    }
    /* 항상 가로 배치 유지 (모바일 스택킹 방지) */
    [class*="st-key-home_goto_"] .stHorizontalBlock {
        flex-wrap: nowrap !important;
    }
    /* 메인 버튼 컬럼: 남은 공간 차지, 넘침 숨김 */
    [class*="st-key-home_goto_"] .stHorizontalBlock > div:first-child {
        flex: 1 1 auto !important;
        min-width: 0 !important;
        max-width: none !important;
    }
    /* 컬럼 간격 축소 */
    [class*="st-key-home_goto_"] .stHorizontalBlock {
        gap: 4px !important;
    }
    /* 삭제 버튼 컬럼: 고정 폭, 줄바꿈 방지 */
    [class*="st-key-home_goto_"] .stHorizontalBlock > div:last-child {
        flex: 0 0 72px !important;
        min-width: 72px !important;
        max-width: 72px !important;
    }
    [class*="st-key-home_del_"] button {
        white-space: nowrap !important;
        width: 100% !important;
    }
    [class*="st-key-home_del_"] button p {
        white-space: nowrap !important;
    }
    </style>
    """, unsafe_allow_html=True)
    inbox = approvals_inbox(sb, role, st.session_state.get("IS_ADMIN", False))
    st.markdown(f"""
    <div class="card">
      <h3 style="margin:0 0 1px 0;">🏠 홈</h3>
      <p style="margin:0 0 8px 0; color:var(--text-secondary); font-size:13px;">계획 → 승인(공사/안전) → 점검/등록 → SNS 공유</p>
      <p style="margin:0; font-size:13px;"><strong>내 승인함 :</strong> {len(inbox)}건</p>
    </div>
    """, unsafe_allow_html=True)

    # 신규 신청 버튼
    if st.button("＋ 신규 신청", key="home_new_req", type="primary", use_container_width=False):
        st.session_state["ACTIVE_PAGE"] = "계획"
        st.rerun()

    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)

    # 전체 요청 목록 (진행 중인 건 우선)
    all_reqs = req_list(sb, limit=100)
    active_reqs = [r for r in all_reqs if r.get("status") not in ("DONE",)]
    active_reqs = sorted(active_reqs, key=lambda r: r.get("created_at", ""), reverse=True)

    STATUS_LABEL = {
        "PENDING_APPROVAL": ("대기중", "status-pending"),
        "APPROVED":         ("승인됨", "status-approved"),
        "REJECTED":         ("반려됨", "status-rejected"),
        "EXECUTING":        ("실행중", "status-executing"),
        "DONE":             ("완료",   "status-done"),
    }
    PAGE_FOR_STATUS = {
        "PENDING_APPROVAL": "승인",
        "APPROVED":         "확인",
        "REJECTED":         "승인",
        "EXECUTING":        "확인",
        "DONE":             "산출물",
    }

    if not active_reqs:
        st.markdown('<div class="card" style="text-align:center;color:var(--text-muted);font-size:13px;">진행 중인 요청이 없습니다.</div>', unsafe_allow_html=True)
        return

    for r in active_reqs[:20]:
        rid = r["id"]
        kind = "반입" if r.get("kind") == KIND_IN else "반출"
        status = r.get("status", "PENDING_APPROVAL")
        slabel, _ = STATUS_LABEL.get(status, (status, "status-pending"))
        status_icon = {
            "PENDING_APPROVAL": "✍️",
            "APPROVED":         "🚛",
            "EXECUTING":        "📸",
            "DONE":             "📦",
            "REJECTED":         "❌",
        }.get(status, "📋")
        title = f"{kind} · {r.get('company_name','')} · {r.get('item_name','')}"
        sub = f"{r.get('date','')} {r.get('time_from','')}~{r.get('time_to','')} GATE:{r.get('gate','')} | {r.get('driver_name','')}"
        target_page = PAGE_FOR_STATUS.get(status, "승인")
        label = f"{status_icon} {title} · {r.get('date','')} {r.get('time_from','')}~{r.get('time_to','')} · GATE:{r.get('gate','')} · {r.get('driver_name','')} | {slabel}"

        can_delete = is_admin or (
            role == "협력사" and r.get("requester_name") == user_name
        )

        with st.container(key=f"home_goto_{rid}"):
            gcol, dcol = st.columns([9, 1])
            with gcol:
                if st.button(label, key=f"home_goto_btn_{rid}", use_container_width=True, help=label):
                    st.session_state["ACTIVE_PAGE"] = target_page
                    st.session_state["SELECTED_REQ_ID"] = rid
                    st.rerun()
            with dcol:
                if can_delete:
                    if st.button("삭제", key=f"home_del_{rid}", type="primary"):
                        req_delete(sb, rid)
                        st.toast("삭제되었습니다.", icon="🗑️")
                        st.rerun()


def main():
    """Main application entry point."""
    # ── Supabase client ──
    sb = get_supabase()
    db_init_and_migrate(sb)

    # ── CSS ──
    inject_css()

    # ── Session defaults ──
    if "AUTH_OK" not in st.session_state:
        st.session_state["AUTH_OK"] = False
    if "BASE_DIR" not in st.session_state:
        st.session_state["BASE_DIR"] = "MaterialToolShared"
    if "ACTIVE_PAGE" not in st.session_state:
        st.session_state["ACTIVE_PAGE"] = "홈"

    # ── Step 1: Project selection ──
    if not session_has_project():
        page_project_select(sb)
        return

    # ── Step 2: Authentication ──
    if not session_is_authed():
        page_login(sb)
        return

    # ── Step 3: Main app ──
    render_sidebar()
    ui_header(sb)
    render_topnav(sb)

    active_page = st.session_state.get("ACTIVE_PAGE", "홈")
    if active_page == "홈":
        page_home(sb)
    elif active_page in PAGE_ROUTER:
        PAGE_ROUTER[active_page](sb)
    else:
        st.warning(f"알 수 없는 페이지: {active_page}")


if __name__ == "__main__":
    main()
