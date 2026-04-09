"""Request CRUD operations (Supabase)."""
import uuid
from typing import Dict, Any, List, Optional
import streamlit as st
from supabase import Client
from shared.helpers import now_str


def req_insert(sb: Client, data: Dict[str, Any]) -> str:
    """Insert a new request and return its ID."""
    rid = uuid.uuid4().hex
    cols = [
        "id", "created_at", "updated_at", "status", "kind", "project_id",
        "company_name", "item_name", "item_type", "work_type", "date",
        "time_from", "time_to", "gate", "vehicle_type", "vehicle_ton",
        "vehicle_count", "driver_name", "driver_phone", "notes",
        "requester_name", "requester_role", "risk_level", "sic_training_url",
    ]
    row = {
        "id": rid,
        "created_at": now_str(),
        "updated_at": now_str(),
        "status": "PENDING_APPROVAL",
        **{k: data.get(k) for k in cols if k not in ("id", "created_at", "updated_at", "status")},
    }
    sb.table("requests").insert(row).execute()
    req_list.clear()
    return rid


@st.cache_data(ttl=5)
def req_get(_sb: Client, rid: str) -> Optional[Dict[str, Any]]:
    """Get a single request by ID, including day_seq for display ID."""
    res = _sb.rpc("rpc_req_get", {"p_req_id": rid}).execute()
    return res.data if isinstance(res.data, dict) else (res.data[0] if res.data else None)


@st.cache_data(ttl=5)
def req_list(
    _sb: Client,
    status: Optional[str] = None,
    kind: Optional[str] = None,
    limit: int = 300,
    project_id: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """List requests with optional filters, including day_seq."""
    pid = project_id or st.session_state.get("PROJECT_ID", "")
    res = _sb.rpc("rpc_req_list", {
        "p_project_id": pid or "",
        "p_status": status,
        "p_kind": kind,
        "p_limit": limit,
    }).execute()
    return res.data or []


def req_update_status(sb: Client, rid: str, status: str) -> None:
    sb.table("requests").update({"status": status, "updated_at": now_str()}).eq("id", rid).execute()
    req_get.clear()
    req_list.clear()


def req_update_time(sb: Client, rid: str, time_from: str, time_to: str) -> None:
    sb.table("requests").update({
        "time_from": time_from, "time_to": time_to, "updated_at": now_str(),
    }).eq("id", rid).execute()
    req_get.clear()
    req_list.clear()


def req_delete(sb: Client, rid: str) -> None:
    """Delete a request and all associated records (cascade)."""
    sb.table("approvals").delete().eq("req_id", rid).execute()
    sb.table("executions").delete().eq("req_id", rid).execute()
    sb.table("photos").delete().eq("req_id", rid).execute()
    sb.table("outputs").delete().eq("req_id", rid).execute()
    sb.table("schedules").delete().eq("req_id", rid).execute()
    sb.table("requests").delete().eq("id", rid).execute()
    st.cache_data.clear()  # 여러 테이블 일괄 삭제 — 전체 초기화 유지
