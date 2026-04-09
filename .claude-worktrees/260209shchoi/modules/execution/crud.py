"""Execution CRUD operations (Supabase)."""
import json
import uuid
from pathlib import Path
from typing import Dict, Any, List, Optional
import streamlit as st
from supabase import Client
from shared.helpers import now_str, file_sha1
from db.connection import path_output
from config import EXEC_REQUIRED_PHOTOS


def photo_exists_same(sb: Client, rid: str, slot_key: str, file_hash: str) -> bool:
    res = (sb.table("photos").select("id")
           .eq("req_id", rid).eq("slot_key", slot_key).eq("file_hash", file_hash)
           .limit(1).execute())
    return bool(res.data)


def photo_add(
    sb: Client,
    rid: str,
    slot_key: str,
    label: str,
    file_bytes: bytes,
    suffix: str = ".jpg",
) -> str:
    fhash = file_sha1(file_bytes)
    if photo_exists_same(sb, rid, slot_key, fhash):
        return ""
    fname = f"{rid}_{slot_key}_{uuid.uuid4().hex[:8]}{suffix}"
    storage_url = ""
    try:
        sb.storage.from_("photos").upload(
            path=fname,
            file=file_bytes,
            file_options={"content-type": "image/jpeg", "upsert": "true"},
        )
        storage_url = sb.storage.from_("photos").get_public_url(fname)
    except Exception:
        pass
    # 로컬 파일 fallback (로컬 실행 시)
    file_path = ""
    try:
        out = path_output()["photo"]
        fpath = out / fname
        fpath.write_bytes(file_bytes)
        file_path = str(fpath)
    except Exception:
        pass
    sb.table("photos").insert({
        "id": uuid.uuid4().hex, "req_id": rid, "slot_key": slot_key,
        "label": label, "file_path": file_path, "storage_url": storage_url,
        "file_hash": fhash, "created_at": now_str(),
    }).execute()
    photos_for_req.clear()
    return storage_url or file_path


def photo_delete_slot(sb: Client, rid: str, slot_key: str) -> None:
    res = sb.table("photos").select("file_path,storage_url").eq("req_id", rid).eq("slot_key", slot_key).execute()
    for row in (res.data or []):
        # 로컬 파일 삭제
        try:
            if row.get("file_path"):
                Path(row["file_path"]).unlink(missing_ok=True)
        except Exception:
            pass
        # Storage 파일 삭제
        try:
            if row.get("storage_url"):
                fname = row["storage_url"].split("/")[-1]
                sb.storage.from_("photos").remove([fname])
        except Exception:
            pass
    sb.table("photos").delete().eq("req_id", rid).eq("slot_key", slot_key).execute()
    photos_for_req.clear()


@st.cache_data(ttl=5)
def photos_for_req(_sb: Client, rid: str) -> List[Dict[str, Any]]:
    res = _sb.table("photos").select("*").eq("req_id", rid).order("created_at").execute()
    return res.data or []


def required_photos_ok(sb: Client, rid: str) -> bool:
    keys = {p["slot_key"] for p in photos_for_req(sb, rid)}
    return all(k in keys for k, _ in EXEC_REQUIRED_PHOTOS)


def execution_upsert(
    sb: Client,
    rid: str,
    executed_by: str,
    executed_role: str,
    check_json: Dict[str, Any],
    notes: str,
) -> None:
    ok = 1 if required_photos_ok(sb, rid) else 0
    sb.table("executions").upsert({
        "req_id": rid, "executed_by": executed_by, "executed_role": executed_role,
        "executed_at": now_str(), "check_json": json.dumps(check_json, ensure_ascii=False),
        "required_photo_ok": ok, "notes": notes,
    }, on_conflict="req_id").execute()
    execution_get.clear()


@st.cache_data(ttl=5)
def execution_get(_sb: Client, rid: str) -> Optional[Dict[str, Any]]:
    res = _sb.table("executions").select("*").eq("req_id", rid).limit(1).execute()
    return res.data[0] if res.data else None


@st.cache_data(ttl=5)
def final_approved_signs(_sb: Client, rid: str) -> List[Dict[str, Any]]:
    res = (_sb.table("approvals").select("*")
           .eq("req_id", rid).eq("status", "APPROVED")
           .order("step_no").execute())
    return res.data or []
