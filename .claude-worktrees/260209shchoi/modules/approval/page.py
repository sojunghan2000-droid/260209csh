"""Approval (signature) page."""

import streamlit as st
from supabase import Client

from modules.approval.crud import approvals_inbox, approval_mark
from modules.request.crud import req_get
from modules.outputs.crud import generate_all_outputs
from shared.signature import ui_signature_block
from shared.helpers import req_display_id


def _pending_my_requests(sb: Client, project_id: str, user_name: str):
    """협력사 사용자가 등록한 요청 중 승인 대기 중인 건 조회."""
    res = (sb.table("requests").select("*")
           .eq("project_id", project_id)
           .eq("requester_name", user_name)
           .eq("status", "PENDING_APPROVAL")
           .order("created_at", desc=True)
           .execute())
    reqs = res.data or []
    if not reqs:
        return []
    req_ids = [r["id"] for r in reqs]
    ap_res = (sb.table("approvals").select("req_id,role_required,status,step_no")
              .in_("req_id", req_ids).eq("status", "PENDING")
              .order("step_no").execute())
    ap_map = {}
    for ap in (ap_res.data or []):
        ap_map.setdefault(ap["req_id"], ap)
    result = []
    for r in reqs:
        ap = ap_map.get(r["id"], {})
        result.append({**r, "role_required": ap.get("role_required"), "ap_status": ap.get("status"), "step_no": ap.get("step_no")})
    return result


def page_approval(sb: Client):
    st.markdown("### ✍️ 승인(서명)")

    user_role = st.session_state.get("USER_ROLE", "")
    is_admin  = st.session_state.get("IS_ADMIN", False)
    user_name = st.session_state.get("USER_NAME", "")
    project_id = st.session_state.get("PROJECT_ID", "")

    inbox = approvals_inbox(sb, user_role, is_admin)

    # ── 협력사: 서명 권한 없음 → 본인 요청의 대기 현황만 표시 ──────────────
    if not inbox and user_role == "협력사":
        pending = _pending_my_requests(sb, project_id, user_name)
        if not pending:
            st.info("대기 중인 승인 건이 없습니다.")
            return

        st.caption("📋 내가 등록한 요청 중 승인 대기 중인 건")
        KIND_LABEL = {"IN": "반입", "OUT": "반출"}
        STATUS_COLOR = {"PENDING_APPROVAL": "#f59e0b"}

        for r in pending:
            kind_lbl = KIND_LABEL.get(r.get("kind", ""), r.get("kind", ""))
            role_req  = r.get("role_required") or "-"
            step_no   = r.get("step_no") or "-"
            st.markdown(
                f"<div style='background:#fffbeb;border:1px solid #fcd34d;border-radius:8px;"
                f"padding:10px 14px;margin-bottom:8px;'>"
                f"<div style='font-weight:600;font-size:14px;margin-bottom:4px'>"
                f"{r['company_name']} &nbsp;·&nbsp; {r['item_name']}</div>"
                f"<div style='font-size:12px;color:#64748b;display:flex;gap:12px;flex-wrap:wrap'>"
                f"<span>📦 {kind_lbl}</span>"
                f"<span>📅 {r.get('date','')} {r.get('time_from','')}~{r.get('time_to','')}</span>"
                f"<span>📍 {r.get('gate','')}</span>"
                f"</div>"
                f"<div style='margin-top:6px;font-size:12px;color:#92400e'>"
                f"⏳ {step_no}단계 승인 대기 중 &nbsp;→&nbsp; <b>{role_req}</b> 서명 필요</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
        return

    # ── 승인 권한 있는 계정 ───────────────────────────────────────────────
    if not inbox:
        st.info("대기 중인 승인 건이 없습니다.")
        return

    items = [(f"[{i['role_required']}] {i['company_name']} / {i['item_name']}", i["id"]) for i in inbox]
    sel = st.selectbox("승인 대상", items, format_func=lambda x: x[0])
    approval_id = sel[1]
    target = next((x for x in inbox if x["id"] == approval_id), None)
    rid = target["req_id"]
    req = req_get(sb, rid)
    st.markdown(f"**{req_display_id(req)}** / {req.get('company_name')} / {req.get('item_name')}")
    st.markdown("""
    <style>
    [data-testid="stTextArea"] [data-testid="stWidgetLabel"],
    [data-testid="stTextArea"] label {
        margin-bottom: -14px !important;
        padding-bottom: 0 !important;
        line-height: 1 !important;
    }
    </style>
    """, unsafe_allow_html=True)
    sign_path, stamp_path = ui_signature_block(rid, "서명 입력", key_prefix=f"ap_{approval_id}")
    reject_reason = st.text_area("반려 사유(반려 시)", height=60)
    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
    c1, c2 = st.columns(2)
    with c1:
        if st.button("승인", type="primary", use_container_width=True):
            if not sign_path:
                st.error("서명이 필요합니다.")
            else:
                rid2, msg = approval_mark(sb, approval_id, "APPROVE", user_name, user_role, sign_path, stamp_path, "")
                if req_get(sb, rid2).get("status") == "APPROVED":
                    with st.spinner("⏳ 산출물 생성 중... (잠시 기다려 주세요)"):
                        generate_all_outputs(sb, rid2)
                    st.success("✅ " + msg + " · 산출물 생성 완료")
                else:
                    st.success(msg)
                st.rerun()
    with c2:
        if st.button("반려", use_container_width=True):
            if not reject_reason.strip():
                st.error("사유 필수")
            else:
                rid2, msg = approval_mark(sb, approval_id, "REJECT", user_name, user_role, None, None, reject_reason.strip())
                st.success(msg)
                st.rerun()
