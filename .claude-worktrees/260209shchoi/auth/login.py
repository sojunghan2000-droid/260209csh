"""Login and project selection pages (Supabase Auth)."""
import streamlit as st
from supabase import Client
from config import ROLES
from auth.session import auth_login, auth_reset, user_create, project_has_users
from db.models import project_list, project_get, project_create, modules_for_project, module_toggle


# ── 공통 헤더 ──────────────────────────────────────────────────────────────

def _login_header(project_name: str, subtitle: str) -> None:
    st.markdown(f"""
    <div style="text-align:center; padding:16px 0 8px 0;">
      <h3 style="color:var(--primary-700);display:flex;align-items:center;
                 justify-content:center;gap:6px;">
        <img src="data:image/svg+xml;base64,PHN2ZyB4bWxucz0iaHR0cDovL3d3dy53My5vcmcvMjAwMC9zdmciIHZpZXdCb3g9IjAgMCAxMDAgMTE1Ij4KICA8ZWxsaXBzZSBjeD0iNTAiIGN5PSIxMDQiIHJ4PSIyNiIgcnk9IjExIiBmaWxsPSIjMWE0ZmM0Ii8+CiAgPHBhdGggZD0iTTUwIDQKICAgIEMyOSA0IDEyIDIxIDEyIDQyCiAgICBDMTIgNjAgMzAgNzggNDIgOTIKICAgIEM0NSA5NiA1MCAxMDIgNTAgMTAyCiAgICBDNTAgMTAyIDU1IDk2IDU4IDkyCiAgICBDNzAgNzggODggNjAgODggNDIKICAgIEM4OCAyMSA3MSA0IDUwIDQgWiIKICAgIGZpbGw9IiMyOWI2ZjYiLz4KICA8Y2lyY2xlIGN4PSI1MCIgY3k9IjQwIiByPSIxOCIgZmlsbD0id2hpdGUiLz4KPC9zdmc+Cg=="
             style="height:1.1em;width:auto;vertical-align:middle;" />
        {project_name}
      </h3>
      <p style="color:var(--text-muted); font-size:13px;">{subtitle}</p>
    </div>
    """, unsafe_allow_html=True)


# ── 프로젝트 선택 ─────────────────────────────────────────────────────────

def page_project_select(sb: Client):
    """Project selection screen — Step 1."""
    st.markdown("""
    <div style="text-align:center; padding:24px 0 16px 0;">
      <div style="font-size:36px;">🏗️</div>
      <h2 style="margin:8px 0 4px 0; color:var(--primary-700);">자재 반출입 관리 프로세스</h2>
      <p style="color:var(--text-muted); font-size:13px;">프로젝트를 선택하세요</p>
    </div>
    """, unsafe_allow_html=True)

    projects = project_list(sb)

    with st.container(key="proj_select_wrap"):
        if projects:
            project_names = [p["name"] for p in projects]
            col_sel, col_btn = st.columns([8.8, 1.2])
            with col_sel:
                selected = st.selectbox(
                    "프로젝트 선택", project_names,
                    index=None, placeholder="프로젝트 선택",
                    label_visibility="collapsed", key="proj_select_box",
                )
            with col_btn:
                if st.button("▶", key="proj_go_btn", type="primary"):
                    if selected:
                        proj = next(p for p in projects if p["name"] == selected)
                        st.session_state["PROJECT_ID"]   = proj["id"]
                        st.session_state["PROJECT_NAME"] = proj["name"]
                        st.rerun()
                    else:
                        st.toast("프로젝트를 선택하세요.", icon="⚠️")
        else:
            st.info("등록된 프로젝트가 없습니다. 새 프로젝트를 생성하세요.")

    with st.container(key="proj_new_wrap"):
        with st.expander("＋ 새 프로젝트 만들기"):
            new_name = st.text_input("프로젝트명*", key="new_proj_name")
            new_desc = st.text_input("설명", key="new_proj_desc")
            c1, c2 = st.columns(2)
            with c1:
                new_site_pin = st.text_input("현장 PIN*", value="1234", key="new_proj_pin")
            with c2:
                new_admin_pin = st.text_input("Admin PIN*", value="9999", key="new_proj_admin_pin")
            if st.button("프로젝트 생성", type="primary", key="create_proj"):
                if not new_name.strip():
                    st.error("프로젝트명을 입력하세요.")
                else:
                    pid = project_create(sb, new_name.strip(), new_desc.strip(),
                                         new_site_pin, new_admin_pin)
                    st.success(f"프로젝트 생성 완료: {new_name}")
                    st.session_state["PROJECT_ID"]   = pid
                    st.session_state["PROJECT_NAME"] = new_name.strip()
                    st.rerun()


# ── 로그인 폼 ─────────────────────────────────────────────────────────────

def _page_login_form(sb: Client, project_id: str, project_name: str) -> None:
    _login_header(project_name, "아이디와 비밀번호를 입력하세요")
    st.markdown("""
    <style>
    .st-key-back_to_proj_login button {
        min-height: 0 !important; height: 32px !important;
        padding: 0 12px !important; border-radius: 0.5rem !important;
        border: none !important; display: inline-flex !important;
        align-items: center !important; justify-content: center !important;
    }
    .st-key-back_to_proj_login button p { line-height:1!important; margin:0!important; padding:0!important; }
    </style>
    """, unsafe_allow_html=True)

    if st.button("← 다른 프로젝트 선택", key="back_to_proj_login"):
        st.session_state.pop("PROJECT_ID", None)
        st.session_state.pop("PROJECT_NAME", None)
        st.rerun()

    with st.container(key="login_form_wrap"):
        with st.form("login_form"):
            username  = st.text_input("아이디 *", placeholder="등록한 아이디 입력")
            password  = st.text_input("비밀번호 *", type="password")
            submitted = st.form_submit_button("로그인", type="primary", use_container_width=True)

        if submitted:
            if not username.strip() or not password:
                st.error("아이디와 비밀번호를 모두 입력하세요.")
            else:
                ok, msg = auth_login(sb, username, password)
                (st.success if ok else st.error)(msg)
                if ok:
                    st.rerun()

    with st.container(key="login_signup_btn"):
        st.markdown(
            '<div style="text-align:center;padding-top:14px;font-size:13px;color:#64748b;">'
            '계정이 없으신가요?</div><div style="height:12px;"></div>',
            unsafe_allow_html=True,
        )
        st.markdown("""
        <style>
        .st-key-login_signup_btn button { display:flex!important; align-items:center!important; justify-content:center!important; }
        .st-key-login_signup_btn button p { line-height:1!important; margin:0!important; padding:0!important; }
        </style>
        """, unsafe_allow_html=True)
        if st.button("회원가입", key="go_signup", use_container_width=True):
            st.session_state["auth_mode"] = "signup"
            st.rerun()


# ── 회원가입 폼 ───────────────────────────────────────────────────────────

def _page_signup_form(sb: Client, project_id: str, project_name: str) -> None:
    _login_header(project_name, "계정을 만들어 서비스를 이용하세요")
    st.markdown("""
    <style>
    .st-key-back_to_login button {
        min-height: 0 !important; height: 32px !important;
        padding: 0 12px !important; border-radius: 0.5rem !important;
        border: none !important; display: inline-flex !important;
        align-items: center !important; justify-content: center !important;
    }
    .st-key-signup_form_wrap [data-testid="stExpander"] summary { min-height:0!important; height:auto!important; padding:9px 0.75rem!important; }
    .st-key-back_to_login button p { line-height:1!important; margin:0!important; padding:0!important; }
    </style>
    """, unsafe_allow_html=True)

    if st.button("← 로그인으로 돌아가기", key="back_to_login"):
        st.session_state["auth_mode"] = "login"
        st.rerun()

    project = project_get(sb, project_id) or {}
    expected_admin_pin = project.get("admin_pin", "")

    with st.container(key="signup_form_wrap"):
        with st.form("signup_form", clear_on_submit=False):
            username = st.text_input("아이디 *", placeholder="영문·숫자 조합 (로그인 시 사용)")
            name     = st.text_input("이름/직책 *", placeholder="예) 김삼성/건축시공")
            role     = st.selectbox("부서 *", ROLES, index=None, placeholder="소속 부서 선택")
            st.markdown("---")
            pw1 = st.text_input("비밀번호 *", type="password", placeholder="4자 이상")
            pw2 = st.text_input("비밀번호 확인 *", type="password")
            with st.expander("🔐 관리자 계정 신청 (선택)"):
                admin_pin_input = st.text_input(
                    "Admin PIN", type="password",
                    placeholder="관리자 PIN 입력 시 관리자 권한 부여",
                    key="signup_admin_pin",
                )
            submitted = st.form_submit_button("가입하기", type="primary", use_container_width=True)

        if submitted:
            errors = []
            if not username.strip(): errors.append("아이디")
            if not name.strip():     errors.append("이름/직책")
            if not role:             errors.append("부서")
            if not pw1:              errors.append("비밀번호")
            if pw1 != pw2:
                st.error("비밀번호가 일치하지 않습니다.")
                return
            if errors:
                st.error(f"필수 입력 항목을 확인하세요: {', '.join(errors)}")
                return
            is_admin = bool(admin_pin_input and admin_pin_input == expected_admin_pin)
            if admin_pin_input and not is_admin:
                st.error("Admin PIN이 올바르지 않습니다.")
                return
            ok, msg = user_create(sb, project_id, username, pw1, name, role, is_admin)
            if ok:
                st.success(f"✅ {msg} 로그인하세요.")
                st.session_state["auth_mode"] = "login"
                st.rerun()
            else:
                st.error(msg)


# ── 메인 진입점 ───────────────────────────────────────────────────────────

def page_login(sb: Client):
    """Authentication screen (Supabase Auth)."""
    project_id   = st.session_state.get("PROJECT_ID", "")
    project_name = st.session_state.get("PROJECT_NAME", "프로젝트")

    if "auth_mode" not in st.session_state:
        st.session_state["auth_mode"] = "login"

    if st.session_state["auth_mode"] == "signup":
        _page_signup_form(sb, project_id, project_name)
    else:
        _page_login_form(sb, project_id, project_name)
