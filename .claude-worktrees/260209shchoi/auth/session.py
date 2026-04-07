"""Authentication and session management — Hybrid Auth.

신규 가입: profiles 테이블에 password_hash/salt 저장 (Supabase Auth 미사용)
기존 계정: supabase_uid 보유 → Supabase Auth sign_in_with_password 사용
로그인:    profile에 password_hash 있으면 로컬 PBKDF2, 없으면 Supabase Auth
"""
import hashlib
import os
from typing import Dict, Optional, Tuple

import streamlit as st
from supabase import Client

from shared.helpers import new_id, now_str


# ── 비밀번호 해싱 (PBKDF2-SHA256) ─────────────────────────────────────

def _new_salt() -> str:
    return os.urandom(16).hex()


def _hash_pw(password: str, salt: str) -> str:
    return hashlib.pbkdf2_hmac(
        "sha256", password.encode("utf-8"), salt.encode("utf-8"), 100_000
    ).hex()


# ── 이메일 패턴 (기존 Supabase Auth 계정용) ───────────────────────────

def _make_email(project_id: str, username: str) -> str:
    return f"{username.strip()}@{project_id[:8]}.gate"


# ── 계정 CRUD ─────────────────────────────────────────────────────────

def user_create(sb: Client, project_id: str, username: str,
                password: str, name: str, role: str,
                is_admin: bool = False) -> Tuple[bool, str]:
    """신규 계정 생성 — profiles 테이블에 password_hash/salt 저장 (Supabase Auth 미사용)."""
    # 중복 체크
    dup = (sb.table("profiles").select("id")
           .eq("project_id", project_id)
           .eq("username", username.strip())
           .limit(1).execute())
    if dup.data:
        return False, "이미 사용 중인 아이디입니다."
    if len(password) < 4:
        return False, "비밀번호는 4자 이상이어야 합니다."

    salt    = _new_salt()
    pw_hash = _hash_pw(password, salt)

    sb.table("profiles").insert({
        "id":           new_id(),
        "project_id":   project_id,
        "username":     username.strip(),
        "name":         name.strip(),
        "role":         role,
        "is_admin":     int(is_admin),
        "supabase_uid": None,
        "password_hash": pw_hash,
        "salt":          salt,
        "created_at":   now_str(),
    }).execute()

    return True, "계정이 생성되었습니다."


def auth_login(sb: Client, username: str, password: str) -> Tuple[bool, str]:
    """하이브리드 로그인.
    - password_hash 있음 → 로컬 PBKDF2 검증
    - password_hash 없고 supabase_uid 있음 → Supabase Auth sign_in_with_password
    """
    project_id = st.session_state.get("PROJECT_ID", "")

    # profiles 조회
    prof_res = (sb.table("profiles").select("*")
                .eq("project_id", project_id)
                .eq("username", username.strip())
                .limit(1).execute())
    if not prof_res.data:
        return False, "아이디 또는 비밀번호가 올바르지 않습니다."

    user = prof_res.data[0]

    # ── 경로 A: 로컬 password_hash (신규 가입 계정) ──────────────────
    if user.get("password_hash") and user.get("salt"):
        if _hash_pw(password, user["salt"]) != user["password_hash"]:
            return False, "아이디 또는 비밀번호가 올바르지 않습니다."

    # ── 경로 B: Supabase Auth (기존 계정, supabase_uid 보유) ──────────
    elif user.get("supabase_uid"):
        email = _make_email(project_id, username)
        try:
            res = sb.auth.sign_in_with_password({"email": email, "password": password})
            if not res.user:
                return False, "아이디 또는 비밀번호가 올바르지 않습니다."
            st.session_state["SUPABASE_SESSION"] = res.session
        except Exception:
            return False, "아이디 또는 비밀번호가 올바르지 않습니다."

    else:
        return False, "계정 정보가 올바르지 않습니다. 관리자에게 문의하세요."

    # 로그인 세션 설정
    st.session_state["AUTH_OK"]   = True
    st.session_state["IS_ADMIN"]  = bool(user.get("is_admin"))
    st.session_state["USER_NAME"] = user.get("name", "")
    st.session_state["USER_ROLE"] = user.get("role", "협력사")
    return True, "로그인 완료"


def auth_reset():
    """Reset all auth session state."""
    st.session_state["AUTH_OK"]   = False
    st.session_state["IS_ADMIN"]  = False
    st.session_state["USER_NAME"] = ""
    st.session_state["USER_ROLE"] = "협력사"
    st.session_state["ACTIVE_PAGE"] = "홈"
    st.session_state.pop("SUPABASE_SESSION", None)


def project_has_users(sb: Client, project_id: str) -> bool:
    res = sb.table("profiles").select("id").eq("project_id", project_id).limit(1).execute()
    return bool(res.data)


def user_list(sb: Client, project_id: str):
    res = (sb.table("profiles")
           .select("id,username,name,role,is_admin,created_at")
           .eq("project_id", project_id)
           .order("created_at", desc=True)
           .execute())
    return res.data or []


def user_delete(sb: Client, user_id: str) -> None:
    sb.table("profiles").delete().eq("id", user_id).execute()


def session_has_project() -> bool:
    return bool(st.session_state.get("PROJECT_ID"))


def session_is_authed() -> bool:
    return st.session_state.get("AUTH_OK", False)


def current_project_id() -> str:
    return st.session_state.get("PROJECT_ID", "")
