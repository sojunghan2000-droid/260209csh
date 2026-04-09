"""Execution registration page."""

import json

import streamlit as st
from supabase import Client

from datetime import date
from config import CHECK_ITEMS
from modules.request.crud import req_list, req_update_status
from modules.execution.crud import execution_upsert, execution_get, required_photos_ok
from shared.helpers import req_display_id
from modules.execution.photos import ui_photo_capture_required, ui_photo_optional_upload
from modules.outputs.crud import generate_all_outputs


def page_execute(sb: Client):
    st.markdown("""
    <style>
    [data-testid="stSelectbox"] [data-testid="stWidgetLabel"],
    [data-testid="stSelectbox"] label {
        margin-bottom: -14px !important;
        padding-bottom: 0 !important;
        line-height: 1 !important;
    }
    [data-testid="stTextInput"] [data-testid="stWidgetLabel"],
    [data-testid="stTextInput"] label {
        margin-bottom: -14px !important;
        padding-bottom: 0 !important;
        line-height: 1 !important;
    }
    .st-key-exec_done_btn button {
        background: #6b7280 !important;
        border-color: #6b7280 !important;
        color: #ffffff !important;
        cursor: default !important;
    }
    .st-key-exec_done_btn button p {
        color: #ffffff !important;
    }
    .st-key-exec_done_btn button:hover {
        background: #6b7280 !important;
        transform: none !important;
        box-shadow: none !important;
    }
    .st-key-exec_reedit_btn button {
        background: #f59e0b !important;
        border-color: #f59e0b !important;
        color: #ffffff !important;
    }
    .st-key-exec_reedit_btn button p {
        color: #ffffff !important;
    }
    .st-key-exec_reedit_btn button:hover {
        background: #d97706 !important;
        border-color: #d97706 !important;
        transform: none !important;
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("### 📸 확인 등록")
    today = date.today().isoformat()
    candidates = [
        r for r in req_list(sb, None, None, 500)
        if r['status'] in ['APPROVED', 'EXECUTING', 'DONE']
        and (r.get('date') or '') >= today
    ]
    if not candidates:
        st.info("실행 등록 가능한 요청이 없습니다.")
        return
    items = [(f"{req_display_id(r)} · {r['company_name']} · {r['item_name']}", r['id']) for r in candidates]
    sel = st.selectbox("확인 대상", items, format_func=lambda x: x[0])
    rid = sel[1]
    ui_photo_capture_required(sb, rid)
    ui_photo_optional_upload(sb, rid)
    ok = required_photos_ok(sb, rid)
    exec_row = execution_get(sb, rid)
    is_done = exec_row is not None
    reedit_key = f"exec_reedit_{rid}"
    is_editing = (not is_done) or st.session_state.get(reedit_key, False)
    existing = json.loads(exec_row['check_json']) if is_done and exec_row.get('check_json') else {}
    saved_notes = (exec_row.get('notes') or "") if is_done else ""
    st.markdown("#### 3. 자재 상/하차 점검카드")
    check_json = {}
    cols = st.columns(2)
    for idx, (key, title) in enumerate(CHECK_ITEMS):
        check_json[key] = cols[idx % 2].checkbox(title, value=bool(existing.get(key, False)), disabled=not is_editing)
    notes = st.text_input("메모", value=saved_notes, disabled=not is_editing)
    st.markdown("<div style='margin-bottom:32px'></div>", unsafe_allow_html=True)
    if is_done and not st.session_state.get(reedit_key, False):
        col_done, col_reedit, col_empty = st.columns([2, 1, 1])
        with col_done:
            st.button("등록 완료", key="exec_done_btn", use_container_width=True, type="primary")
        with col_reedit:
            if st.button("재등록", key="exec_reedit_btn", use_container_width=True, type="primary"):
                st.session_state[reedit_key] = True
                st.rerun()
    else:
        if not ok:
            st.warning("필수 사진 3종이 아직 등록되지 않았습니다.")
        if st.button("확인 등록", type="primary", use_container_width=True):
            try:
                req_update_status(sb, rid, "EXECUTING")
                execution_upsert(sb, rid, st.session_state.get("USER_NAME", ""), st.session_state.get("USER_ROLE", ""), check_json, notes)
                req_update_status(sb, rid, "DONE")
            except Exception as e:
                st.error(f"저장 오류: {e}")
                st.stop()
            try:
                generate_all_outputs(sb, rid)
            except Exception:
                pass
            st.session_state.pop(reedit_key, None)
            st.toast("확인 등록 완료!", icon="✅")
            st.rerun()
