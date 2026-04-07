"""Sidebar rendering."""
import streamlit as st
from auth.session import auth_reset


def render_sidebar():
    """Render sidebar with user info and navigation."""
    with st.sidebar:
        if st.session_state.get("AUTH_OK", False):
            uname = st.session_state.get("USER_NAME", "")
            urole = st.session_state.get("USER_ROLE", "")
            st.markdown(f"""
            <div class="sidebar-user">
              <div class="sidebar-user-name">👤 {uname}</div>
              <div class="sidebar-user-role">{urole}</div>
            </div>
            """, unsafe_allow_html=True)
            st.markdown("---")

            active = st.session_state.get("ACTIVE_PAGE", "홈")
            PAGES = [
                ("홈",    "🏠"),
                ("관리자","⚙️"),
            ]
            for page_name, icon in PAGES:
                btn_type = "primary" if active == page_name else "secondary"
                if st.button(f"{icon} {page_name}", key=f"nav_{page_name}",
                             use_container_width=True, type=btn_type):
                    st.session_state["ACTIVE_PAGE"] = page_name
                    st.rerun()
            st.markdown("---")
            if st.button("로그아웃", use_container_width=True):
                auth_reset()
                st.rerun()
        else:
            st.caption("로그인 필요")
