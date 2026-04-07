"""Database connection — Supabase client factory."""
import streamlit as st
from supabase import create_client, Client
from pathlib import Path
from shared.helpers import ensure_dir


@st.cache_resource
def get_supabase() -> Client:
    """Return a cached Supabase client (singleton per Streamlit session)."""
    url = st.secrets["SUPABASE_URL"]
    key = st.secrets["SUPABASE_KEY"]
    return create_client(url, key)


# ── 로컬 파일 경로 (파일 저장소는 로컬 유지) ─────────────────────────────

def get_base_dir() -> Path:
    return Path(st.session_state.get("BASE_DIR", "MaterialToolShared"))


def path_output_root() -> Path:
    return get_base_dir() / "output"


def path_output() -> dict:
    root = path_output_root()
    return {
        "plan":   ensure_dir(root / "plan"),
        "permit": ensure_dir(root / "permit"),
        "check":  ensure_dir(root / "check"),
        "exec":   ensure_dir(root / "exec"),
        "photo":  ensure_dir(root / "photo"),
        "qr":     ensure_dir(root / "qr"),
        "bundle": ensure_dir(root / "bundle"),
        "zip":    ensure_dir(root / "zip"),
        "sign":   ensure_dir(root / "sign"),
        "stamp":  ensure_dir(root / "stamp"),
    }
