"""Module management UI for toggling project modules."""

import streamlit as st
from supabase import Client
from db.models import modules_for_project, module_toggle


def render_module_manager(sb: Client, project_id: str):
    """Render module toggle UI with descriptions."""
    st.markdown("#### 📦 기능 모듈 설정")
    modules = modules_for_project(sb, project_id)
    for mod in modules:
        col1, col2 = st.columns([1, 4])
        with col1:
            enabled = st.toggle(mod["module_name"], value=bool(mod["enabled"]),
                                key=f"mod_{mod['module_key']}")
            if enabled != bool(mod["enabled"]):
                module_toggle(sb, project_id, mod["module_key"], int(enabled))
                st.rerun()
        with col2:
            st.caption(mod["module_desc"])
