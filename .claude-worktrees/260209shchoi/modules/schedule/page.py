"""Unified 계획 page — schedule timeline + request form side by side."""
import streamlit as st
from datetime import date, timedelta

from modules.schedule.crud import schedule_list_by_date, schedule_sync_from_requests
from modules.schedule.components.timeline import render_timeline, BLOCKING_STATUSES
from modules.schedule.components.dnd_timeline import dnd_timeline
from modules.schedule.components.summary import render_daily_summary
from modules.schedule.css.schedule import get_schedule_css
from modules.request.crud import req_insert, req_update_time, req_get
from modules.approval.crud import approvals_create_default
from modules.schedule.crud import schedule_delete, schedule_update
from shared.helpers import now_str, req_display_id
from config import KIND_IN, KIND_OUT, VEHICLE_TONS, GATE_ZONES, TIME_SLOTS


def _consecutive_toggle(slots: list, new_slot: str) -> list:
    """슬롯 선택/해제 — 항상 연속 구간 유지.
    - 미선택 슬롯 클릭: 기존 범위와 새 슬롯 사이를 모두 채워 확장
    - 경계(첫/마지막) 슬롯 클릭: 한 칸 축소
    - 중간 슬롯 클릭: 해당 슬롯으로 초기화
    - 단일 선택 슬롯 클릭: 전체 해제
    """
    if new_slot not in slots:
        if not slots:
            return [new_slot]
        try:
            new_idx = TIME_SLOTS.index(new_slot)
            lo = min(TIME_SLOTS.index(x) for x in slots)
            hi = max(TIME_SLOTS.index(x) for x in slots)
            lo, hi = min(lo, new_idx), max(hi, new_idx)
            return [TIME_SLOTS[i] for i in range(lo, hi + 1)]
        except ValueError:
            return [new_slot]
    else:
        s = sorted(slots)
        if len(s) == 1:
            return []
        if new_slot == s[0] or new_slot == s[-1]:
            return [x for x in s if x != new_slot]
        return [new_slot]


def _slot_range(slots: list) -> tuple[str, str]:
    """정렬된 슬롯 리스트에서 time_from, time_to 계산 (폼 제출용)."""
    if not slots:
        return "08:00", "08:30"
    s = sorted(slots)
    t_from = s[0]
    last_idx = TIME_SLOTS.index(s[-1]) if s[-1] in TIME_SLOTS else 4
    t_to = TIME_SLOTS[min(last_idx + 1, len(TIME_SLOTS) - 1)]
    return t_from, t_to


def _format_slot_ranges(slots: list) -> str:
    """슬롯 리스트를 연속 구간으로 묶어 표시. 예) 09:00~09:30, 10:00~11:00"""
    if not slots:
        return "미선택"
    s = sorted(slots)
    groups, group = [], [s[0]]
    for slot in s[1:]:
        try:
            prev_i = TIME_SLOTS.index(group[-1])
            curr_i = TIME_SLOTS.index(slot)
            if curr_i == prev_i + 1:
                group.append(slot)
                continue
        except ValueError:
            pass
        groups.append(group)
        group = [slot]
    groups.append(group)

    parts = []
    for grp in groups:
        t_from = grp[0]
        try:
            last_i = TIME_SLOTS.index(grp[-1])
            t_to   = TIME_SLOTS[min(last_i + 1, len(TIME_SLOTS) - 1)]
        except ValueError:
            t_to = t_from
        parts.append(f"{t_from}~{t_to}")
    return ", ".join(parts)


def _has_conflict(slots: list, schedules: list, kind_val: str) -> bool:
    """선택된 슬롯 중 이미 예약된 슬롯이 있으면 True."""
    booked = [
        s for s in schedules
        if s.get("kind") == kind_val and s.get("status") in BLOCKING_STATUSES
    ]
    for slot in slots:
        if any(b["time_from"] <= slot < b["time_to"] for b in booked):
            return True
    return False


def page_schedule(con):
    """Unified schedule calendar + request registration — single screen."""
    st.markdown(f"<style>{get_schedule_css()}</style>", unsafe_allow_html=True)

    project_id = st.session_state.get("PROJECT_ID", "default")
    is_admin   = st.session_state.get("IS_ADMIN", False)
    user_name  = st.session_state.get("USER_NAME", "")

    # ── 작업 처리 세션 키 ─────────────────────────────────────────────────────
    _ADMIN_KEYS = ("admin_sel_sched_ids", "admin_sel_sched_list", "admin_sel_sched_kind")
    _USER_KEYS  = ("user_sel_sched_list",)

    # DnD 컴포넌트 단일 슬롯 이동 처리
    if "admin_dnd_move" in st.session_state:
        mv = st.session_state.pop("admin_dnd_move")
        try:
            fi = TIME_SLOTS.index(mv["to_slot"])
        except ValueError:
            fi = 0
        nf = TIME_SLOTS[fi]
        nt = TIME_SLOTS[min(fi + 1, len(TIME_SLOTS) - 1)]
        schedule_update(con, mv["sched_id"], time_from=nf, time_to=nt)
        st.rerun()

    if "admin_del_sched" in st.session_state:
        for sid in st.session_state.pop("admin_del_sched"):
            schedule_delete(con, sid)
        for k in _ADMIN_KEYS:
            st.session_state.pop(k, None)
        st.rerun()

    if "admin_move_slot" in st.session_state:
        move_slot = st.session_state.pop("admin_move_slot")
        st.session_state.pop("admin_move_kind", None)
        sel_list  = sorted(st.session_state.get("admin_sel_sched_list", []),
                           key=lambda s: s.get("time_from", ""))
        try:
            start_fi = TIME_SLOTS.index(move_slot)
        except ValueError:
            start_fi = 0
        for i, sched in enumerate(sel_list):
            nfi = start_fi + i
            if nfi + 1 >= len(TIME_SLOTS):
                break
            nf = TIME_SLOTS[nfi]
            nt = TIME_SLOTS[nfi + 1]
            schedule_update(con, sched["id"], time_from=nf, time_to=nt)
        for k in _ADMIN_KEYS:
            st.session_state.pop(k, None)
        st.rerun()

    # 세션 초기화
    for key, default in [
        ("sched_current_date",   date.today()),
        ("sched_sel_in_slots",   []),
        ("sched_sel_out_slots",  []),
        ("sched_last_kind",      "반입"),
        ("user_sel_sched_list",  []),
    ]:
        if key not in st.session_state:
            st.session_state[key] = default

    # 전일/익일 버튼 클릭으로 예약된 날짜를 위젯 렌더 전에 반영
    if "sched_pending_date" in st.session_state:
        st.session_state["sched_date_pick"] = st.session_state.pop("sched_pending_date")

    current_date = st.session_state["sched_current_date"]
    schedule_sync_from_requests(con, project_id)

    col_left, col_right = st.columns([3, 2], gap="large")

    # ── LEFT: 날짜 네비 + 타임라인 ───────────────────────────────────────────
    with col_left:
        st.markdown("#### 📅 일정 현황")

        with st.container(key="sched_nav_row"):
            nav1, nav2, nav3 = st.columns([1, 1.75, 1])
            with nav1:
                if st.button("‹ 전일", key="sched_prev", use_container_width=True,
                             disabled=(current_date <= date.today())):
                    new_date = current_date - timedelta(days=1)
                    st.session_state["sched_current_date"]  = new_date
                    st.session_state["sched_pending_date"]  = new_date
                    st.session_state["sched_sel_in_slots"]  = []
                    st.session_state["sched_sel_out_slots"] = []
                    st.session_state["user_sel_sched_list"] = []
                    st.rerun()
            with nav2:
                today = date.today()
                picked = st.date_input(
                    "날짜", value=current_date,
                    min_value=today,
                    max_value=today + timedelta(days=2),
                    key="sched_date_pick", label_visibility="collapsed",
                )
                if picked != current_date:
                    st.session_state["sched_current_date"]  = picked
                    st.session_state["sched_sel_in_slots"]  = []
                    st.session_state["sched_sel_out_slots"] = []
                    st.session_state["user_sel_sched_list"] = []
                    st.rerun()
            with nav3:
                if st.button("익일 ›", key="sched_next", use_container_width=True,
                             disabled=(current_date >= date.today() + timedelta(days=2))):
                    new_date = current_date + timedelta(days=1)
                    st.session_state["sched_current_date"]  = new_date
                    st.session_state["sched_pending_date"]  = new_date
                    st.session_state["sched_sel_in_slots"]  = []
                    st.session_state["sched_sel_out_slots"] = []
                    st.session_state["user_sel_sched_list"] = []
                    st.rerun()

        date_str  = current_date.isoformat()
        schedules = schedule_list_by_date(con, project_id, date_str)

        # schedules에 requester_name 첨부 (본인 예약 식별용)
        _req_ids = [s["req_id"] for s in schedules if s.get("req_id")]
        if _req_ids:
            _res = con.table("requests").select("id,requester_name").in_("id", _req_ids).execute()
            _rmap = {r["id"]: (r.get("requester_name") or "") for r in (_res.data or [])}
        else:
            _rmap = {}
        for s in schedules:
            s["requester_name"] = _rmap.get(s.get("req_id", ""), "")

        if is_admin:
            in_items  = [s for s in schedules if s.get("kind") == KIND_IN]
            out_items = [s for s in schedules if s.get("kind") == KIND_OUT]
            dnd_result = dnd_timeline(
                slots=TIME_SLOTS,
                in_schedules=in_items,
                out_schedules=out_items,
                is_admin=True,
                sel_ids=list(st.session_state.get("admin_sel_sched_ids", [])),
                sel_in_slots=st.session_state.get("sched_sel_in_slots", []),
                sel_out_slots=st.session_state.get("sched_sel_out_slots", []),
                admin_sel_kind=st.session_state.get("admin_sel_sched_kind"),
                key="admin_dnd",
            )
            # 새 이벤트인지 확인 (ts 기반 중복 방지)
            if dnd_result and dnd_result.get("ts") != st.session_state.get("_dnd_ts"):
                st.session_state["_dnd_ts"] = dnd_result["ts"]
                action = dnd_result.get("action")

                if action == "select":
                    # 관리자 슬롯 선택/해제
                    sid   = dnd_result["sched_id"]
                    kind_ = dnd_result["kind"]
                    sched_ = next((s for s in schedules if s["id"] == sid), None)
                    if sched_:
                        ids  = set(st.session_state.get("admin_sel_sched_ids", []))
                        lst  = list(st.session_state.get("admin_sel_sched_list", []))
                        prev = st.session_state.get("admin_sel_sched_kind")
                        if prev and prev != kind_:
                            ids, lst = set(), []
                        if sid in ids:
                            ids.discard(sid)
                            lst = [s for s in lst if s["id"] != sid]
                        else:
                            ids.add(sid)
                            lst.append(sched_)
                        st.session_state["admin_sel_sched_ids"]  = list(ids)
                        st.session_state["admin_sel_sched_list"] = lst
                        st.session_state["admin_sel_sched_kind"] = kind_ if ids else None
                    st.rerun()

                elif action == "move":
                    # 드래그로 단일 슬롯 이동
                    st.session_state["admin_dnd_move"] = {
                        "sched_id": dnd_result["sched_id"],
                        "to_slot":  dnd_result["to_slot"],
                    }
                    st.rerun()

                elif action == "move_click":
                    # 이동 버튼 클릭 → 선택된 모든 슬롯 이동
                    st.session_state["admin_move_slot"] = dnd_result["to_slot"]
                    st.session_state["admin_move_kind"] = dnd_result.get("kind")
                    st.rerun()

                elif action == "toggle_book":
                    key_ = "sched_sel_in_slots" if dnd_result["kind"] == KIND_IN else "sched_sel_out_slots"
                    lst  = list(st.session_state.get(key_, []))
                    st.session_state[key_] = _consecutive_toggle(lst, dnd_result["slot"])
                    st.session_state["sched_last_kind"] = "반입" if dnd_result["kind"] == KIND_IN else "반출"
                    st.rerun()
        else:
            user_sel_ids_cur = [s["id"] for s in st.session_state.get("user_sel_sched_list", [])]
            user_dnd = dnd_timeline(
                slots=TIME_SLOTS,
                in_schedules=[s for s in schedules if s.get("kind") == KIND_IN],
                out_schedules=[s for s in schedules if s.get("kind") == KIND_OUT],
                is_admin=False,
                sel_in_slots=st.session_state.get("sched_sel_in_slots", []),
                sel_out_slots=st.session_state.get("sched_sel_out_slots", []),
                username=user_name,
                user_sel_ids=user_sel_ids_cur,
                key="user_dnd",
            )
            if user_dnd and user_dnd.get("ts") != st.session_state.get("_user_dnd_ts"):
                st.session_state["_user_dnd_ts"] = user_dnd["ts"]
                action = user_dnd.get("action")
                if action == "toggle_book":
                    key_ = "sched_sel_in_slots" if user_dnd["kind"] == KIND_IN else "sched_sel_out_slots"
                    lst  = list(st.session_state.get(key_, []))
                    st.session_state[key_] = _consecutive_toggle(lst, user_dnd["slot"])
                    st.session_state["sched_last_kind"] = "반입" if user_dnd["kind"] == KIND_IN else "반출"
                    st.rerun()
                elif action == "user_select":
                    sid   = user_dnd["sched_id"]
                    sched_ = next((s for s in schedules if s["id"] == sid), None)
                    if sched_:
                        lst = list(st.session_state.get("user_sel_sched_list", []))
                        if any(s["id"] == sid for s in lst):
                            lst = [s for s in lst if s["id"] != sid]
                        else:
                            lst = [sched_]  # 단일 선택
                        st.session_state["user_sel_sched_list"] = lst
                    st.rerun()

        render_daily_summary(schedules)

    # ── RIGHT: 반입·반출 예약 신청 (슬롯 선택 시 기존 정보 자동 입력) ────────
    with col_right:
        admin_sel_list = st.session_state.get("admin_sel_sched_list", [])
        user_sel_list  = st.session_state.get("user_sel_sched_list", []) if not is_admin else []
        is_admin_edit  = is_admin and bool(admin_sel_list)
        is_user_edit   = not is_admin and bool(user_sel_list)
        is_edit        = is_admin_edit or is_user_edit
        sel_list       = admin_sel_list if is_admin_edit else user_sel_list

        st.markdown("#### 📝 반입·반출 예약 신청")

        # ── 슬롯 선택 시: 기존 예약 정보 로드 ────────────────────────────
        if is_edit:
            n   = len(sel_list)
            ref = sel_list[0]
            req = (req_get(con, ref["req_id"]) or {}) if ref.get("req_id") else {}
            times = sorted(s.get("time_from", "") for s in sel_list)
            can_delete = is_admin_edit or ref.get("status") == "PENDING"
            if is_admin_edit:
                st.caption("⬅️ 타임라인 [→ 이동]: 시간 이동 | 아래 폼: 내용 수정 후 저장")
            else:
                st.caption("✏️ 내 예약 수정 | 승인 전(대기중)만 삭제 가능")
            st.markdown(
                f'<div style="font-size:12px;background:#fff8f4;border:1px solid #ED7D31;'
                f'border-radius:6px;padding:6px 10px;margin-bottom:8px;">'
                f'선택된 예약: <b>{times[0]} ~ {times[-1]}</b> ({n}개 슬롯)</div>',
                unsafe_allow_html=True,
            )
            def_company = req.get("company_name", ref.get("company_name", ""))
            def_item    = req.get("item_name", "")
            def_kind_i  = 0 if ref.get("kind") == KIND_IN else 1
            def_gate_i  = GATE_ZONES.index(req.get("gate", GATE_ZONES[0])) \
                          if req.get("gate") in GATE_ZONES else 0
            def_ton_i   = VEHICLE_TONS.index(req.get("vehicle_ton", VEHICLE_TONS[0])) \
                          if req.get("vehicle_ton") in VEHICLE_TONS else 0
            def_count   = int(req.get("vehicle_count", 1))
            def_driver  = req.get("driver_name", "")
            def_phone   = req.get("driver_phone", "")
            def_notes   = req.get("notes", "")
            form_key    = f"slot_edit_{ref['id'][:8]}"
            conflict    = False
        else:
            # ── 선택 없음: 시간 선택 배지 ─────────────────────────────────
            sel_in    = sorted(st.session_state.get("sched_sel_in_slots",  []))
            sel_out   = sorted(st.session_state.get("sched_sel_out_slots", []))
            last_kind = st.session_state.get("sched_last_kind", "반입")

            def _badge(slots, kind_label, color, bg, border):
                if not slots:
                    return (
                        f'<div style="font-size:12px;color:{color};background:{bg};'
                        f'border:1px solid {border};border-radius:6px;padding:4px 10px;'
                        f'margin-bottom:4px;">{kind_label}: '
                        f'<span style="color:#94a3b8;">미선택</span></div>'
                    )
                return (
                    f'<div style="font-size:12px;color:{color};background:{bg};'
                    f'border:1px solid {border};border-radius:6px;padding:4px 10px;'
                    f'margin-bottom:4px;">{kind_label}: '
                    f'<b>{_format_slot_ranges(slots)}</b></div>'
                )
            st.markdown(
                _badge(sel_in,  "➡️ 반입", "#2563eb", "#eff6ff", "#bfdbfe") +
                _badge(sel_out, "⬅️ 반출", "#dc2626", "#fff1f2", "#fecaca"),
                unsafe_allow_html=True,
            )

            if last_kind == "반입" and sel_in:
                sel_from, sel_to = _slot_range(sel_in)
                conflict = _has_conflict(sel_in, schedules, KIND_IN)
            elif last_kind == "반출" and sel_out:
                sel_from, sel_to = _slot_range(sel_out)
                conflict = _has_conflict(sel_out, schedules, KIND_OUT)
            else:
                sel_from, sel_to = "08:00", "08:30"
                conflict = False

            if conflict and not is_admin:
                st.markdown(
                    f'<div style="font-size:12px;color:#dc2626;background:#fff1f2;'
                    f'border:1px solid #fecaca;border-radius:6px;padding:4px 10px;'
                    f'margin-bottom:6px;">🔒 선택된 시간대에 이미 예약이 있습니다. 다른 슬롯을 선택하세요.</div>',
                    unsafe_allow_html=True,
                )

            def_company = ""
            def_item    = ""
            def_kind_i  = 0 if last_kind == "반입" else 1
            def_gate_i  = 0
            def_ton_i   = 0
            def_count   = 1
            def_driver  = ""
            def_phone   = ""
            def_notes   = ""
            # 슬롯 선택이 바뀌면 폼 위젯 기본값도 갱신되도록 key에 시간 포함
            form_key    = f"req_unified_form_{sel_from}_{sel_to}"

        # ── 통합 폼 ───────────────────────────────────────────────────────
        with st.form(form_key, clear_on_submit=not is_edit):
            company_name = st.text_input("협력업체명 *", value=def_company,
                                         placeholder="예) OO내장, OO설비")
            item_name    = st.text_input("반입 자재명 *", value=def_item,
                                         placeholder="예) 백관, 석고보드, 시멘트")
            st.markdown("---")

            if is_admin_edit:
                eb1, eb2 = st.columns(2)
                with eb1:
                    new_kind = st.selectbox("구분 *", ["반입", "반출"], index=def_kind_i)
                with eb2:
                    gate = st.selectbox("하차 위치 *", GATE_ZONES, index=def_gate_i)
            elif is_edit:
                # 일반 사용자 수정: 구분 변경 불가, gate만 수정 가능
                gate = st.selectbox("하차 위치 *", GATE_ZONES, index=def_gate_i)
            else:
                # 신규 신청
                if is_admin:
                    # 관리자: 구분·시간은 타임라인 선택값 자동 사용, 위치만 입력
                    new_kind = last_kind
                    gate = st.selectbox("하차 위치 (Zone) *", GATE_ZONES, index=def_gate_i)
                    st.markdown(
                        f"<div style='font-size:12px;color:#64748b;margin:-4px 0 4px 0'>"
                        f"📅 일자: <b>{current_date.strftime('%Y/%m/%d')}</b>"
                        f"&nbsp;&nbsp;⏱ 시간: <b>{sel_from} ~ {sel_to}</b></div>",
                        unsafe_allow_html=True,
                    )
                    admin_req_date = current_date
                    admin_tf = sel_from
                    admin_tt = sel_to
                else:
                    # 일반 사용자: 구분 + 위치 선택
                    nf1, nf2 = st.columns(2)
                    with nf1:
                        new_kind = st.selectbox("구분 *", ["반입", "반출"], index=def_kind_i)
                    with nf2:
                        gate = st.selectbox("하차 위치 (Zone) *", GATE_ZONES, index=def_gate_i)

            fv1, fv2 = st.columns(2)
            with fv1:
                vehicle_ton = st.selectbox("차량 규격 *", VEHICLE_TONS, index=def_ton_i)
            with fv2:
                vehicle_count = st.number_input("차량 대수 *", min_value=1, max_value=50,
                                                value=def_count, step=1)

            vehicle_ton_custom = ""
            if vehicle_ton == "직접입력":
                vehicle_ton_custom = st.text_input("톤수 직접 입력", placeholder="예) 18톤")

            st.markdown("---")
            driver_name  = st.text_input("운전원 이름 *", value=def_driver)
            driver_phone = st.text_input("연락처", value=def_phone, placeholder="010-0000-0000")
            notes        = st.text_input("비고", value=def_notes,
                                         placeholder="예) 파레트 타입 포장, 지게차 양중 시 주의")

            if is_edit:
                ca, cb = st.columns(2)
                with ca:
                    save = st.form_submit_button("✅ 저장", type="primary", use_container_width=True)
                with cb:
                    if can_delete:
                        delete = st.form_submit_button("🗑️ 삭제", use_container_width=True)
                    else:
                        delete = False
                        st.markdown(
                            '<div style="font-size:11px;color:#94a3b8;text-align:center;padding-top:10px;">승인됨 — 삭제 불가</div>',
                            unsafe_allow_html=True,
                        )
                submitted = False
            else:
                st.markdown("---")
                submitted = st.form_submit_button("📋 예약 신청", type="primary",
                                                  use_container_width=True)
                save = delete = False

        # ── 수정 저장 ─────────────────────────────────────────────────────
        if is_edit and save:
            final_ton = vehicle_ton_custom.strip() if vehicle_ton == "직접입력" else vehicle_ton
            if is_admin_edit:
                new_kind_val = KIND_IN if new_kind == "반입" else KIND_OUT
                for sched in sel_list:
                    schedule_update(con, sched["id"],
                                    company_name=company_name.strip(),
                                    kind=new_kind_val, gate=gate)
                updated_req_ids = set()
                for sched in sel_list:
                    rid = sched.get("req_id")
                    if rid and rid not in updated_req_ids:
                        updated_req_ids.add(rid)
                        con.table("requests").update({
                            "company_name": company_name.strip(),
                            "item_name": item_name.strip(),
                            "kind": new_kind_val,
                            "gate": gate,
                            "vehicle_ton": final_ton,
                            "vehicle_count": int(vehicle_count),
                            "driver_name": driver_name.strip(),
                            "driver_phone": driver_phone.strip(),
                            "notes": notes.strip(),
                            "updated_at": now_str(),
                        }).eq("id", rid).execute()
                for k in _ADMIN_KEYS:
                    st.session_state.pop(k, None)
                st.success(f"✅ {n}개 슬롯이 수정되었습니다.")
            else:
                # 일반 사용자 — 본인 예약만 수정 (requester_name 조건)
                rid = ref.get("req_id")
                schedule_update(con, ref["id"], company_name=company_name.strip(), gate=gate)
                if rid:
                    con.table("requests").update({
                        "company_name": company_name.strip(),
                        "item_name": item_name.strip(),
                        "gate": gate,
                        "vehicle_ton": final_ton,
                        "vehicle_count": int(vehicle_count),
                        "driver_name": driver_name.strip(),
                        "driver_phone": driver_phone.strip(),
                        "notes": notes.strip(),
                        "updated_at": now_str(),
                    }).eq("id", rid).eq("requester_name", user_name).execute()
                for k in _USER_KEYS:
                    st.session_state.pop(k, None)
                st.success("✅ 예약이 수정되었습니다.")
            st.rerun()

        # ── 삭제 ─────────────────────────────────────────────────────────
        if is_edit and delete:
            if is_admin_edit:
                st.session_state["admin_del_sched"] = [s["id"] for s in sel_list]
            else:
                # 일반 사용자 — 본인 PENDING 예약만 삭제
                from modules.schedule.crud import schedule_delete as _sdel
                _sdel(con, ref["id"])
                rid = ref.get("req_id")
                if rid:
                    con.table("requests").delete().eq("id", rid).eq("requester_name", user_name).execute()
                for k in _USER_KEYS:
                    st.session_state.pop(k, None)
                st.success("✅ 예약이 취소되었습니다.")
            st.rerun()

        # ── 예약 신청 ─────────────────────────────────────────────────────
        if not is_edit and submitted:
            if conflict and not is_admin:
                st.error("⛔ 선택된 시간대에 이미 예약이 있습니다. 좌측 타임라인에서 빈 슬롯을 선택하세요.")
                st.stop()

            errors = []
            if not company_name.strip():  errors.append("협력업체명")
            if not item_name.strip():     errors.append("반입 자재명")
            if not driver_name.strip():   errors.append("운전원 이름")
            if vehicle_ton == "직접입력" and not vehicle_ton_custom.strip():
                errors.append("톤수 (직접 입력)")

            if errors:
                st.error(f"필수 입력 항목을 확인하세요: {', '.join(errors)}")
            else:
                final_ton = vehicle_ton_custom.strip() if vehicle_ton == "직접입력" else vehicle_ton
                kind_val  = KIND_IN if new_kind == "반입" else KIND_OUT
                if is_admin:
                    req_date = str(admin_req_date)
                    req_from = admin_tf
                    req_to   = admin_tt
                else:
                    req_date = str(current_date)
                    req_from = sel_from
                    req_to   = sel_to
                rid = req_insert(con, dict(
                    project_id=project_id,
                    kind=kind_val,
                    company_name=company_name.strip(),
                    item_name=item_name.strip(),
                    item_type="", work_type="",
                    date=req_date,
                    time_from=req_from, time_to=req_to,
                    gate=gate,
                    vehicle_type="", vehicle_ton=final_ton,
                    vehicle_count=int(vehicle_count),
                    driver_name=driver_name.strip(),
                    driver_phone=driver_phone.strip(),
                    notes=notes.strip(),
                    requester_name=st.session_state.get("USER_NAME", ""),
                    requester_role=st.session_state.get("USER_ROLE", ""),
                    risk_level="MID", sic_training_url="",
                ))
                approvals_create_default(con, rid, kind_val)
                disp = req_display_id(req_get(con, rid) or {"id": rid})
                st.success(f"✅ 예약 신청 완료 ({disp}) — {req_date} {req_from}~{req_to} / {gate}")
                if kind_val == KIND_IN:
                    st.session_state["sched_sel_in_slots"] = []
                else:
                    st.session_state["sched_sel_out_slots"] = []
                st.session_state["sched_current_date"] = current_date
                st.rerun()
