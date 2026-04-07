"""Top navigation bar — dynamically built from enabled modules."""
import streamlit as st
from db.models import modules_enabled_for_project
from auth.session import current_project_id

# module_key → nav icon
MODULE_ICONS = {
    "schedule":  "📅",
    "approval":  "✍️",
    "execution": "📸",
    "outputs":   "📦",
    "ledger":    "📋",
}

# module_key → ACTIVE_PAGE name
MODULE_PAGE_MAP = {
    "schedule":  "계획",
    "approval":  "승인",
    "execution": "확인",
    "outputs":   "산출물",
    "ledger":    "대장",
}


def render_topnav(con):
    """Render horizontal top navigation bar based on enabled modules."""
    active_page = st.session_state.get("ACTIVE_PAGE", "홈")
    if active_page == "관리자":
        return  # hide topnav on admin page

    project_id = current_project_id()
    if not project_id:
        return

    enabled_modules = modules_enabled_for_project(con, project_id)
    if not enabled_modules:
        return

    nav_items = [("🏠\n\n홈", "홈")]
    for mod in enabled_modules:
        key = mod["module_key"]
        icon = MODULE_ICONS.get(key, "📄")
        page_name = MODULE_PAGE_MAP.get(key, key)
        nav_items.append((f"{icon}\n\n{page_name}", page_name))

    cols = st.columns(len(nav_items))
    for col, (label, page) in zip(cols, nav_items):
        with col:
            btn_type = "primary" if active_page == page else "secondary"
            if st.button(label, key=f"topnav_{page}", use_container_width=True, type=btn_type):
                st.session_state["ACTIVE_PAGE"] = page
                st.rerun()
