"""Schedule CRUD operations (Supabase)."""
from typing import List, Dict, Any, Optional
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
    return sid


def schedule_list_by_date(sb: Client, project_id: str, schedule_date: str) -> List[Dict[str, Any]]:
    res = (sb.table("schedules").select("*")
           .eq("project_id", project_id).eq("schedule_date", schedule_date)
           .order("time_from").execute())
    return res.data or []


def schedule_update(sb: Client, sid: str, **kwargs) -> None:
    allowed = {
        "title", "schedule_date", "time_from", "time_to", "kind", "gate",
        "company_name", "vehicle_info", "status", "color", "req_id",
    }
    filtered = {k: v for k, v in kwargs.items() if k in allowed}
    if filtered:
        sb.table("schedules").update(filtered).eq("id", sid).execute()


def schedule_delete(sb: Client, sid: str) -> None:
    sb.table("schedules").delete().eq("id", sid).execute()


def schedule_get(sb: Client, sid: str) -> Optional[Dict[str, Any]]:
    res = sb.table("schedules").select("*").eq("id", sid).limit(1).execute()
    return res.data[0] if res.data else None


def schedule_sync_from_requests(sb: Client, project_id: str) -> None:
    """Sync schedule entries from approved/pending requests (auto-populate)."""
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
            schedule_insert(sb, project_id, {**base, "time_from": sf, "time_to": st_})


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
