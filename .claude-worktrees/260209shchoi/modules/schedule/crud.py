"""Schedule CRUD operations (Supabase)."""
from typing import List, Dict, Any, Optional, Tuple
import streamlit as st
from supabase import Client
from shared.helpers import now_str, new_id


def schedule_insert(sb: Client, project_id: str, data: dict) -> str:
    sid = new_id()
    sb.table("schedules").insert({
        "id":            sid,
        "project_id":    project_id,
        "req_id":        data.get("req_id") or None,
        "title":         data["title"],
        "schedule_date": data["schedule_date"],
        "time_from":     data["time_from"],
        "time_to":       data["time_to"],
        "kind":          data.get("kind", "IN"),
        "gate":          data.get("gate", ""),
        "company_name":  data.get("company_name", ""),
        "vehicle_info":  data.get("vehicle_info", ""),
        "status":        data.get("status", "PENDING"),
        "color":         data.get("color", "#fbbf24"),
        "created_by":    data.get("created_by", ""),
        "created_at":    now_str(),
    }).execute()
    schedule_list_by_date.clear()   # ③ 삽입 즉시 타임라인 반영
    return sid


@st.cache_data(ttl=5)
def schedule_list_by_date(_sb: Client, project_id: str, schedule_date: str) -> List[Dict[str, Any]]:
    """② 5초 캐시 — 슬롯 클릭 등 일반 인터랙션 시 DB 조회 생략."""
    res = (_sb.table("schedules").select("*")
           .eq("project_id", project_id).eq("schedule_date", schedule_date)
           .order("time_from").execute())
    return res.data or []


@st.cache_data(ttl=5)
def schedule_requester_names(_sb: Client, req_ids_tuple: Tuple[str, ...]) -> Dict[str, str]:
    """④ requester_name 캐시 함수 — 타임라인 소유자 식별용."""
    if not req_ids_tuple:
        return {}
    res = _sb.table("requests").select("id,requester_name").in_("id", list(req_ids_tuple)).execute()
    return {r["id"]: (r.get("requester_name") or "") for r in (res.data or [])}


def schedule_update(sb: Client, sid: str, **kwargs) -> None:
    allowed = {
        "title", "schedule_date", "time_from", "time_to", "kind", "gate",
        "company_name", "vehicle_info", "status", "color", "req_id",
    }
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    if filtered:
        sb.table("schedules").update(filtered).eq("id", sid).execute()
        schedule_list_by_date.clear()   # ③ 수정 즉시 타임라인 반영


def schedule_delete(sb: Client, sid: str) -> None:
    sb.table("schedules").delete().eq("id", sid).execute()
    schedule_list_by_date.clear()   # ③ 삭제 즉시 타임라인 반영


def schedule_get(sb: Client, sid: str) -> Optional[Dict[str, Any]]:
    res = sb.table("schedules").select("*").eq("id", sid).limit(1).execute()
    return res.data[0] if res.data else None


def schedule_sync_from_requests(sb: Client, project_id: str) -> None:
    """Sync schedule entries from approved/pending requests (auto-populate).
    ⑤ bulk INSERT 최적화 — N건의 개별 INSERT → 1회 bulk INSERT.
    """
    # 1. 대상 requests 조회
    req_res = (sb.table("requests").select("*")
               .eq("project_id", project_id)
               .in_("status", ["PENDING_APPROVAL", "APPROVED"])
               .execute())
    all_reqs = req_res.data or []
    if not all_reqs:
        return

    # 2. 이미 연결된 req_id 목록 조회
    sched_res = (sb.table("schedules").select("req_id")
                 .eq("project_id", project_id)
                 .not_.is_("req_id", "null")
                 .execute())
    linked_ids = {r["req_id"] for r in (sched_res.data or [])}

    from config import TIME_SLOTS
    bulk_rows = []   # ⑤ bulk INSERT용 수집 리스트

    for r in all_reqs:
        if r.get("id") in linked_ids:
            continue
        req_status   = r.get("status", "")
        sched_status = "PENDING" if req_status == "PENDING_APPROVAL" else "APPROVED"
        sched_color  = "#fbbf24" if sched_status == "PENDING" else "#22c55e"
        time_from    = r.get("time_from", "08:00") or "08:00"
        time_to      = r.get("time_to") or _add_30min(time_from)

        try:
            fi = TIME_SLOTS.index(time_from)
            ti = TIME_SLOTS.index(time_to)
        except ValueError:
            fi, ti = 0, 1

        slot_pairs = [(TIME_SLOTS[i], TIME_SLOTS[i + 1])
                      for i in range(fi, ti) if i + 1 < len(TIME_SLOTS)]
        if not slot_pairs:
            slot_pairs = [(time_from, _add_30min(time_from))]

        base = {
            "req_id":        r.get("id", ""),
            "title":         r.get("company_name", "자재 반출입"),
            "schedule_date": r.get("date", r.get("created_at", "")[:10]),
            "kind":          r.get("kind", "IN"),
            "gate":          r.get("gate", ""),
            "company_name":  r.get("company_name", ""),
            "vehicle_info":  f"{r.get('vehicle_type','')} {r.get('vehicle_ton','')}t".strip(),
            "status":        sched_status,
            "color":         sched_color,
            "created_by":    "system",
        }
        for sf, st_ in slot_pairs:
            bulk_rows.append({
                "id":            new_id(),
                "project_id":    project_id,
                "created_at":    now_str(),
                **base,
                "time_from": sf,
                "time_to":   st_,
            })

    # ⑤ 신규 rows가 있을 때만 한 번에 bulk INSERT
    if bulk_rows:
        sb.table("schedules").insert(bulk_rows).execute()
        schedule_list_by_date.clear()   # ③ sync insert 후 타임라인 즉시 반영


def _add_30min(time_str: str) -> str:
    try:
        parts = time_str.split(":")
        h, m = int(parts[0]), int(parts[1])
        m += 30
        if m >= 60:
            m -= 60
            h += 1
        if h >= 24:
            h, m = 23, 59
        return f"{h:02d}:{m:02d}"
    except (ValueError, IndexError):
        return "08:30"
