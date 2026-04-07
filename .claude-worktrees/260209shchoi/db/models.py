"""CRUD for projects and project_modules tables (Supabase)."""
import uuid
from typing import Optional, List, Dict, Any
from supabase import Client
from shared.helpers import now_str


# ── Settings ──────────────────────────────────────────────────────────

def settings_get(sb: Client, key: str, default: str = "") -> str:
    res = sb.table("settings").select("value").eq("key", key).limit(1).execute()
    return res.data[0]["value"] if res.data else default


def settings_set(sb: Client, key: str, value: str) -> None:
    sb.table("settings").upsert(
        {"key": key, "value": value, "updated_at": now_str()},
        on_conflict="key",
    ).execute()


# ── Projects ──────────────────────────────────────────────────────────

def project_create(sb: Client, name: str, description: str,
                   site_pin: str, admin_pin: str) -> str:
    """Create a project and insert default modules. Returns project id."""
    pid = uuid.uuid4().hex
    sb.table("projects").insert({
        "id": pid, "name": name, "description": description,
        "site_pin": site_pin, "admin_pin": admin_pin, "created_at": now_str(),
    }).execute()
    modules_init_for_project(sb, pid)
    return pid


def project_list(sb: Client) -> List[Dict[str, Any]]:
    res = sb.table("projects").select("*").order("created_at", desc=True).execute()
    return res.data or []


def project_get(sb: Client, project_id: str) -> Optional[Dict[str, Any]]:
    res = sb.table("projects").select("*").eq("id", project_id).limit(1).execute()
    return res.data[0] if res.data else None


def project_update(sb: Client, project_id: str, **kwargs) -> None:
    allowed = {"name", "description", "site_pin", "admin_pin"}
    fields = {k: v for k, v in kwargs.items() if k in allowed}
    if not fields:
        return
    sb.table("projects").update(fields).eq("id", project_id).execute()


# ── Project Modules ───────────────────────────────────────────────────

DEFAULT_MODULES = [
    ("schedule",  "📅 계획",   "일정 캘린더 + 신규 요청 등록 통합",               1, 0),
    ("approval",  "✍️ 승인",   "안전/공사 담당자의 요청 승인·반려 처리",           1, 1),
    ("execution", "📸 실행",   "현장 사진 촬영 및 체크리스트 확인",               1, 2),
    ("outputs",   "📦 산출물", "PDF 계획서·허가서·실행요약 생성 및 공유",          1, 3),
    ("ledger",    "📋 대장",   "전체 요청·승인 내역 검색 및 엑셀 다운로드",        1, 4),
]


def modules_init_for_project(sb: Client, project_id: str) -> None:
    rows = [
        {"project_id": project_id, "module_key": key, "module_name": module_name,
         "module_desc": module_desc, "enabled": enabled, "sort_order": sort_order}
        for key, module_name, module_desc, enabled, sort_order in DEFAULT_MODULES
    ]
    sb.table("project_modules").upsert(rows, on_conflict="project_id,module_key").execute()


def modules_for_project(sb: Client, project_id: str) -> List[Dict[str, Any]]:
    res = sb.table("project_modules").select("*").eq("project_id", project_id).order("sort_order").execute()
    return res.data or []


def modules_enabled_for_project(sb: Client, project_id: str) -> List[Dict[str, Any]]:
    res = (sb.table("project_modules").select("*")
           .eq("project_id", project_id).eq("enabled", 1)
           .order("sort_order").execute())
    return res.data or []


def module_toggle(sb: Client, project_id: str, module_key: str, enabled: int) -> None:
    sb.table("project_modules").update({"enabled": enabled}).eq("project_id", project_id).eq("module_key", module_key).execute()
