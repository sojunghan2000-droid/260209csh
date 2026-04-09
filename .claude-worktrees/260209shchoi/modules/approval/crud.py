"""Approval CRUD operations (Supabase)."""
import json
import uuid
from typing import Dict, Any, List, Optional, Tuple
import streamlit as st
from supabase import Client
from shared.helpers import now_str
from db.models import settings_get
from modules.request.crud import req_update_status, req_get, req_list


def routing_get(sb: Client) -> Dict[str, List[str]]:
    try:
        return json.loads(settings_get(sb, "approval_routing_json", "{}"))
    except Exception:
        return {"IN": ["공사"], "OUT": ["안전", "공사"]}


def approvals_create_default(sb: Client, rid: str, kind: str) -> None:
    roles = routing_get(sb).get(kind, ["공사"]) or ["공사"]
    rows = [
        {"id": uuid.uuid4().hex, "req_id": rid, "step_no": i,
         "role_required": role, "status": "PENDING", "created_at": now_str()}
        for i, role in enumerate(roles, start=1)
    ]
    sb.table("approvals").insert(rows).execute()
    approvals_inbox.clear()
    approvals_for_req.clear()


@st.cache_data(ttl=3)
def approvals_inbox(
    _sb: Client, user_role: str, is_admin: bool,
    project_id: str = "",
) -> List[Dict[str, Any]]:
    pid = project_id or st.session_state.get("PROJECT_ID", "")
    res = _sb.rpc("rpc_approvals_inbox", {
        "p_project_id": pid,
        "p_user_role": user_role,
        "p_is_admin": is_admin,
    }).execute()
    return res.data or []


@st.cache_data(ttl=3)
def approvals_for_req(_sb: Client, rid: str) -> List[Dict[str, Any]]:
    res = _sb.table("approvals").select("*").eq("req_id", rid).order("step_no").execute()
    return res.data or []


def approval_mark(
    sb: Client,
    approval_id: str,
    action: str,
    signer_name: str,
    signer_role: str,
    sign_path: Optional[str],
    stamp_path: Optional[str],
    reject_reason: str = "",
) -> Tuple[str, str]:
    res = sb.rpc("rpc_approval_mark", {
        "p_approval_id":   approval_id,
        "p_action":        action,
        "p_signer_name":   signer_name,
        "p_signer_role":   signer_role,
        "p_sign_path":     sign_path,
        "p_stamp_path":    stamp_path,
        "p_reject_reason": reject_reason,
    }).execute()
    result = res.data or {}
    if isinstance(result, list):
        result = result[0] if result else {}
    approvals_inbox.clear()
    approvals_for_req.clear()
    req_get.clear()
    req_list.clear()
    return result.get("rid", ""), result.get("msg", "처리 완료")
