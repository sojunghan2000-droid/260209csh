"""Timeline grid — 30-min slots, separate IN/OUT multi-select."""
import streamlit as st
from typing import List, Dict, Any
from modules.schedule.models import generate_time_slots
from config import KIND_IN, KIND_OUT

STATUS_COLORS = {
    "PENDING":   ("🟡", "#fbbf24"),
    "APPROVED":  ("🟢", "#22c55e"),
    "REJECTED":  ("🔴", "#ef4444"),
    "EXECUTING": ("🔵", "#3b82f6"),
    "DONE":      ("⚪", "#94a3b8"),
}

BLOCKING_STATUSES = {"PENDING", "APPROVED", "EXECUTING"}


def _is_blocked(items: List[Dict[str, Any]]) -> bool:
    return any(s.get("status", "PENDING") in BLOCKING_STATUSES for s in items)


def _booked_label(items: List[Dict[str, Any]]) -> str:
    """업체명 최대 4자 (초과 시 잘라서 반환, 2줄 없음)"""
    if not items:
        return ""
    name = items[0]["company_name"]
    return name[:4]


def _toggle(key: str, slot: str) -> None:
    lst = list(st.session_state.get(key, []))
    if slot in lst:
        lst.remove(slot)
    else:
        lst.append(slot)
    st.session_state[key] = sorted(lst)


def _admin_toggle(sched: Dict[str, Any], kind: str) -> None:
    """관리자 슬롯 다중 선택 토글 (같은 kind만)."""
    ids   = set(st.session_state.get("admin_sel_sched_ids", []))
    lst   = list(st.session_state.get("admin_sel_sched_list", []))
    prev_kind = st.session_state.get("admin_sel_sched_kind")

    # 다른 kind 클릭 시 기존 선택 초기화
    if prev_kind and prev_kind != kind:
        ids, lst = set(), []

    sid = sched["id"]
    if sid in ids:
        ids.discard(sid)
        lst = [s for s in lst if s["id"] != sid]
    else:
        ids.add(sid)
        lst.append(sched)

    st.session_state["admin_sel_sched_ids"]  = list(ids)
    st.session_state["admin_sel_sched_list"] = lst
    st.session_state["admin_sel_sched_kind"] = kind if ids else None


def _user_toggle(sched: Dict[str, Any]) -> None:
    """일반 사용자 본인 슬롯 선택/해제 (단일 선택)."""
    lst = list(st.session_state.get("user_sel_sched_list", []))
    sid = sched["id"]
    if any(s["id"] == sid for s in lst):
        lst = [s for s in lst if s["id"] != sid]
    else:
        lst = [sched]          # 단일 선택으로 교체
    st.session_state["user_sel_sched_list"] = lst


def render_timeline(schedules: List[Dict[str, Any]], is_admin: bool = False, user_name: str = ""):
    slots     = generate_time_slots()
    in_items  = [s for s in schedules if s.get("kind") == KIND_IN]
    out_items = [s for s in schedules if s.get("kind") == KIND_OUT]

    sel_in  = st.session_state.get("sched_sel_in_slots",  [])
    sel_out = st.session_state.get("sched_sel_out_slots", [])

    admin_sel_ids  = set(st.session_state.get("admin_sel_sched_ids", []))
    admin_sel_kind = st.session_state.get("admin_sel_sched_kind")
    user_sel_ids   = set(s["id"] for s in st.session_state.get("user_sel_sched_list", []))

    # ── CSS ──
    st.markdown("""
    <style>
    .tl-time {
      font-size:13px; font-weight:600; color:#475569;
      padding:3px 2px; text-align:center; line-height:1.4;
    }
    .st-key-tl_header {
      margin-bottom: 6px !important;
      border-bottom: 1px solid #e2e8f0;
      padding-bottom: 4px !important;
    }
    .tl-hdr-in  { font-size:13px; font-weight:700; color:#2563eb; text-align:center; padding:2px 0 8px 0; }
    .tl-hdr-out { font-size:13px; font-weight:700; color:#dc2626; text-align:center; padding:2px 0 8px 0; }
    @media (max-width: 480px) {
      .tl-time { font-size:11px !important; padding:2px 1px !important; }
      .tl-hdr-in, .tl-hdr-out { font-size:11px !important; }
      [class*="st-key-tl_row_"] button { min-height: 30px !important; font-size:11px !important; }
      [class*="st-key-tl_row_"] button p { font-size:11px !important; }
    }
    [class*="st-key-tl_row_"] { margin-bottom: 2px !important; }
    [class*="st-key-tl_row_"] [data-testid="stElementContainer"],
    [class*="st-key-tl_row_"] [data-testid="stVerticalBlock"] {
      gap: 2px !important; margin-bottom: 0 !important;
    }
    [class*="st-key-tl_row_"] [data-testid="stHorizontalBlock"],
    .st-key-tl_header [data-testid="stHorizontalBlock"] { column-gap: 8px !important; }
    [class*="st-key-tl_row_"] [data-testid="stColumn"]:not(:first-child) button {
      font-size: 14px !important; padding: 0 4px !important;
      min-height: 28px !important; display: flex !important;
      align-items: center !important; justify-content: center !important;
      overflow: hidden !important;
    }
    [class*="st-key-tl_row_"] [data-testid="stColumn"]:not(:first-child) button p {
      font-size: 14px !important; line-height: 1 !important; margin: 0 !important;
      white-space: nowrap !important; overflow: hidden !important;
      text-overflow: clip !important; max-width: 100% !important;
    }
    /* 미선택 슬롯 테두리 */
    [class*="st-key-tl_row_"] [data-testid="stColumn"]:not(:first-child) [data-testid="stBaseButton-secondary"] {
      border: 1px solid #cbd5e1 !important; border-radius: 6px !important;
    }
    /* 비관리자 예약 슬롯: 회색 */
    [class*="st-key-tl_row_"] [data-testid="stColumn"]:not(:first-child) button:disabled {
      background-color: #a6a6a6 !important; color: #ffffff !important;
      opacity: 1 !important; border-color: #8c8c8c !important;
    }
    [class*="st-key-tl_row_"] [data-testid="stColumn"]:not(:first-child) button:disabled p {
      color: #ffffff !important;
    }
    /* 관리자 예약 슬롯 (클릭 가능, 회색) */
    [class*="st-key-ta_in_"] button, [class*="st-key-ta_out_"] button {
      background-color: #a6a6a6 !important; color: #ffffff !important;
      border-color: #8c8c8c !important;
    }
    [class*="st-key-ta_in_"] button p, [class*="st-key-ta_out_"] button p {
      color: #ffffff !important;
    }
    /* 관리자 이동 슬롯 (점선 오렌지) */
    [class*="st-key-tm_in_"] button, [class*="st-key-tm_out_"] button {
      border: 2px dashed #ED7D31 !important; color: #ED7D31 !important;
      background-color: #fff8f4 !important;
    }
    [class*="st-key-tm_in_"] button p, [class*="st-key-tm_out_"] button p {
      color: #ED7D31 !important;
    }
    /* 내 예약 PENDING (노랑) */
    [class*="st-key-tu_p_in_"] button, [class*="st-key-tu_p_out_"] button {
      background-color: #fbbf24 !important; color: #ffffff !important;
      border-color: #f59e0b !important; border-radius: 6px !important;
    }
    [class*="st-key-tu_p_in_"] button p, [class*="st-key-tu_p_out_"] button p {
      color: #ffffff !important;
    }
    /* 내 예약 APPROVED (초록) */
    [class*="st-key-tu_a_in_"] button, [class*="st-key-tu_a_out_"] button {
      background-color: #22c55e !important; color: #ffffff !important;
      border-color: #16a34a !important; border-radius: 6px !important;
    }
    [class*="st-key-tu_a_in_"] button p, [class*="st-key-tu_a_out_"] button p {
      color: #ffffff !important;
    }
    </style>
    """, unsafe_allow_html=True)

    # ── Header ──
    with st.container(key="tl_header"):
        hc1, hc2, hc3 = st.columns([0.55, 1.2, 1.2])
        with hc1:
            st.markdown('<div class="tl-hdr-in" style="color:#64748b;text-align:center;">시 간</div>', unsafe_allow_html=True)
        with hc2:
            st.markdown('<div class="tl-hdr-in">반 입</div>', unsafe_allow_html=True)
        with hc3:
            st.markdown('<div class="tl-hdr-out">반 출</div>', unsafe_allow_html=True)

    # ── Slot rows ──
    for slot in slots:
        slot_in  = [s for s in in_items  if s["time_from"] <= slot < s["time_to"]]
        slot_out = [s for s in out_items if s["time_from"] <= slot < s["time_to"]]

        blk_in  = _is_blocked(slot_in)
        blk_out = _is_blocked(slot_out)
        sel_in_here  = slot in sel_in
        sel_out_here = slot in sel_out

        with st.container(key=f"tl_row_{slot}"):
            c1, c2, c3 = st.columns([0.55, 1.2, 1.2])

            with c1:
                st.markdown(f'<div class="tl-time">{slot}</div>', unsafe_allow_html=True)

            # ── IN cell ──
            with c2:
                if blk_in:
                    sched  = slot_in[0]
                    label  = _booked_label(slot_in) or "예약"
                    is_sel = is_admin and sched["id"] in admin_sel_ids
                    is_own = (not is_admin) and bool(user_name) and sched.get("requester_name") == user_name
                    is_own_sel = is_own and sched["id"] in user_sel_ids
                    if is_admin:
                        btn_label = f"✓ {label}" if is_sel else label
                        btn_type  = "primary" if is_sel else "secondary"
                        key_      = f"ti_{slot}" if is_sel else f"ta_in_{slot}"
                        if st.button(btn_label, key=key_, type=btn_type, use_container_width=True):
                            _admin_toggle(sched, KIND_IN)
                            st.rerun()
                    elif is_own:
                        sk        = "a" if sched.get("status") == "APPROVED" else "p"
                        btn_label = f"✓ {label}" if is_own_sel else label
                        btn_type  = "primary" if is_own_sel else "secondary"
                        key_      = f"tu_{sk}_in_sel_{slot}" if is_own_sel else f"tu_{sk}_in_{slot}"
                        if st.button(btn_label, key=key_, type=btn_type, use_container_width=True):
                            _user_toggle(sched)
                            st.rerun()
                    else:
                        st.button(label, key=f"ti_{slot}", disabled=True, use_container_width=True)
                elif is_admin and admin_sel_ids and admin_sel_kind == KIND_IN:
                    if st.button("→ 이동", key=f"tm_in_{slot}", use_container_width=True):
                        st.session_state["admin_move_slot"] = slot
                        st.session_state["admin_move_kind"] = KIND_IN
                        st.rerun()
                elif sel_in_here:
                    if st.button("✓ 선택", key=f"ti_{slot}", type="primary", use_container_width=True):
                        _toggle("sched_sel_in_slots", slot)
                        st.session_state["sched_last_kind"] = "반입"
                        st.rerun()
                else:
                    lbl = (_booked_label(slot_in) or "+") if slot_in else "+"
                    if st.button(lbl, key=f"ti_{slot}", use_container_width=True):
                        _toggle("sched_sel_in_slots", slot)
                        st.session_state["sched_last_kind"] = "반입"
                        st.rerun()

            # ── OUT cell ──
            with c3:
                if blk_out:
                    sched  = slot_out[0]
                    label  = _booked_label(slot_out) or "예약"
                    is_sel = is_admin and sched["id"] in admin_sel_ids
                    is_own = (not is_admin) and bool(user_name) and sched.get("requester_name") == user_name
                    is_own_sel = is_own and sched["id"] in user_sel_ids
                    if is_admin:
                        btn_label = f"✓ {label}" if is_sel else label
                        btn_type  = "primary" if is_sel else "secondary"
                        key_      = f"to_{slot}" if is_sel else f"ta_out_{slot}"
                        if st.button(btn_label, key=key_, type=btn_type, use_container_width=True):
                            _admin_toggle(sched, KIND_OUT)
                            st.rerun()
                    elif is_own:
                        sk        = "a" if sched.get("status") == "APPROVED" else "p"
                        btn_label = f"✓ {label}" if is_own_sel else label
                        btn_type  = "primary" if is_own_sel else "secondary"
                        key_      = f"tu_{sk}_out_sel_{slot}" if is_own_sel else f"tu_{sk}_out_{slot}"
                        if st.button(btn_label, key=key_, type=btn_type, use_container_width=True):
                            _user_toggle(sched)
                            st.rerun()
                    else:
                        st.button(label, key=f"to_{slot}", disabled=True, use_container_width=True)
                elif is_admin and admin_sel_ids and admin_sel_kind == KIND_OUT:
                    if st.button("→ 이동", key=f"tm_out_{slot}", use_container_width=True):
                        st.session_state["admin_move_slot"] = slot
                        st.session_state["admin_move_kind"] = KIND_OUT
                        st.rerun()
                elif sel_out_here:
                    if st.button("✓ 선택", key=f"to_{slot}", type="primary", use_container_width=True):
                        _toggle("sched_sel_out_slots", slot)
                        st.session_state["sched_last_kind"] = "반출"
                        st.rerun()
                else:
                    lbl = (_booked_label(slot_out) or "+") if slot_out else "+"
                    if st.button(lbl, key=f"to_{slot}", use_container_width=True):
                        _toggle("sched_sel_out_slots", slot)
                        st.session_state["sched_last_kind"] = "반출"
                        st.rerun()
