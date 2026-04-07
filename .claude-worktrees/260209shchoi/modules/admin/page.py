"""Admin settings page."""

import json

import streamlit as st
from supabase import Client

from config import DEFAULT_SITE_NAME, DEFAULT_SITE_PIN, DEFAULT_ADMIN_PIN, ROLES
from db.models import settings_get, settings_set
from modules.approval.crud import routing_get
from modules.admin.module_manager import render_module_manager


def page_admin(sb: Client):
    st.markdown("### 🛠 관리자 설정")
    if not st.session_state.get("IS_ADMIN", False):
        st.warning("관리자 모드로 로그인해야 합니다.")
        return

    st.markdown("#### ⚙️ 현장 설정")
    site_name = st.text_input("현장명", value=settings_get(sb, "site_name", DEFAULT_SITE_NAME))
    site_pin = st.text_input("현장 PIN", value=settings_get(sb, "site_pin", DEFAULT_SITE_PIN))
    admin_pin = st.text_input("Admin PIN", value=settings_get(sb, "admin_pin", DEFAULT_ADMIN_PIN))

    st.markdown("---")

    st.markdown("#### 🔄 승인 라우팅")
    routing = routing_get(sb)
    in_route = st.multiselect("반입(IN) 승인순서", options=ROLES, default=routing.get("IN", ["공사"]))
    out_route = st.multiselect("반출(OUT) 승인순서", options=ROLES, default=routing.get("OUT", ["안전", "공사"]))

    if st.button("저장", type="primary", use_container_width=True):
        settings_set(sb, "site_name", site_name.strip() or DEFAULT_SITE_NAME)
        settings_set(sb, "site_pin", site_pin.strip() or DEFAULT_SITE_PIN)
        settings_set(sb, "admin_pin", admin_pin.strip() or DEFAULT_ADMIN_PIN)
        settings_set(sb, "approval_routing_json", json.dumps({"IN": in_route or ["공사"], "OUT": out_route or ["안전", "공사"]}, ensure_ascii=False))
        st.success("저장 완료")
        st.rerun()

    st.markdown("---")

    # Module management section
    project_id = st.session_state.get("PROJECT_ID")
    if project_id:
        render_module_manager(sb, project_id)
    else:
        st.caption("프로젝트를 선택하면 모듈 설정을 관리할 수 있습니다.")
