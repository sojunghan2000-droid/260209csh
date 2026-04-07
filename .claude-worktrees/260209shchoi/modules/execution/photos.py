"""Photo capture UI components for execution page."""

from pathlib import Path

import streamlit as st
from supabase import Client

from config import EXEC_REQUIRED_PHOTOS
from shared.helpers import bytes_from_camera_or_upload
from modules.execution.crud import photo_add, photos_for_req, photo_delete_slot


def ui_photo_capture_required(sb: Client, rid: str):
    """Render the required-photo capture section (3 mandatory slots)."""
    st.markdown("""
    <style>
    [data-testid="stRadio"] > label,
    [data-testid="stRadio"] [data-testid="stWidgetLabel"] {
        display: none !important;
    }
    [data-testid="stAlert"] {
        padding-top: 6px !important;
        padding-bottom: 6px !important;
        min-height: unset !important;
    }
    [data-testid="stAlert"] [data-testid="stAlertContentIsb"] svg {
        width: 16px !important;
        height: 16px !important;
    }
    [data-testid="stCameraInput"] video,
    [data-testid="stCameraInput"] canvas,
    [data-testid="stCameraInput"] img {
        max-width: 720px !important;
        max-height: 540px !important;
        width: 100% !important;
    }
    [data-testid="stCameraInput"] > div {
        max-width: 720px !important;
        margin: 0 auto !important;
    }
    [data-testid="stCameraInput"] [data-testid="stWidgetLabel"],
    [data-testid="stCameraInput"] label {
        margin-bottom: 0 !important;
        padding-bottom: 0 !important;
        line-height: 1 !important;
    }
    [data-testid="stCameraInput"] [data-testid="stWidgetLabel"] p {
        margin-bottom: 4px !important;
    }
    [data-testid="stCameraInputWebcamComponent"] > div:first-child {
        max-height: 500px !important;
        overflow: hidden !important;
    }
    .registered-photo {
        max-width: 720px !important;
        margin: 0 auto 8px auto !important;
    }
    .registered-photo img {
        max-width: 720px !important;
        max-height: 540px !important;
        width: 100% !important;
        border-radius: 6px !important;
        border: 1px solid #e2e8f0 !important;
    }
    [class*="st-key-photo_change_btn_"] {
        display: flex !important;
        justify-content: center !important;
    }
    [class*="st-key-photo_change_btn_"] button {
        padding: 0 10px !important;
        min-height: unset !important;
        height: 28px !important;
        font-size: 12px !important;
        line-height: 28px !important;
        border-radius: 4px !important;
        background: #f59e0b !important;
        border-color: #f59e0b !important;
        color: #ffffff !important;
        width: auto !important;
        min-width: 48px !important;
        display: inline-flex !important;
        align-items: center !important;
    }
    [class*="st-key-photo_change_btn_"] button:hover {
        background: #d97706 !important;
        border-color: #d97706 !important;
        transform: none !important;
    }
    [class*="st-key-photo_change_btn_"] button p {
        font-size: 12px !important;
        line-height: 1 !important;
        margin: 0 !important;
        color: #ffffff !important;
    }
    [data-testid="stCameraInputWebcamComponent"] > div > p {
        margin-top: 4px !important;
        margin-bottom: 4px !important;
    }
    [data-testid="stCameraInputWebcamStyledBox"] {
        margin-top: 0 !important;
        margin-bottom: 0 !important;
    }
    [data-testid="stCameraInputButton"] {
        margin-top: 4px !important;
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("#### 1. 필수 사진(3종)")
    for slot_key, label in EXEC_REQUIRED_PHOTOS:
        existing = next((p for p in photos_for_req(sb, rid) if p['slot_key'] == slot_key), None)
        change_key = f"photo_change_{rid}_{slot_key}"
        if existing and not st.session_state.get(change_key, False):
            # 라벨 + 등록됨 배지 한 줄 (HTML inline), 변경 버튼은 사진 아래
            st.markdown(
                f"<div style='display:flex;align-items:center;gap:8px;margin-bottom:10px'>"
                f"<span style='font-weight:600;font-size:14px'>- {label}</span>"
                f"<span style='background:#dcfce7;border:1px solid #86efac;border-radius:6px;"
                f"padding:3px 8px;font-size:13px;color:#166534;white-space:nowrap'>✅ 등록됨</span>"
                f"</div>",
                unsafe_allow_html=True
            )
            img_path = Path(existing['file_path'])
            if img_path.exists():
                st.image(str(img_path), width=480)
            if st.button("변경", key=f"photo_change_btn_{slot_key}", use_container_width=False):
                st.session_state[change_key] = True
                st.rerun()
        else:
            # 미등록 또는 변경 모드: 제목 + 촬영/업로드 위젯 표시
            st.markdown(f"**- {label}**")
            mode = st.radio(f"{slot_key}_mode", ["직접 촬영(권장)", "파일 업로드"], horizontal=True, key=f"photo_{slot_key}_mode", label_visibility="collapsed")
            if mode == "직접 촬영(권장)":
                pic = st.camera_input("카메라로 촬영", key=f"photo_{slot_key}_camera")
                if pic:
                    data = bytes_from_camera_or_upload(pic)
                    if data:
                        photo_delete_slot(sb, rid, slot_key)
                        photo_add(sb, rid, slot_key, label, data, ".jpg")
                        st.session_state.pop(change_key, None)
                        st.rerun()
            else:
                upl = st.file_uploader("사진 파일 선택", type=["jpg", "jpeg", "png"], key=f"photo_{slot_key}_upload")
                if upl:
                    data = bytes_from_camera_or_upload(upl)
                    if data:
                        photo_delete_slot(sb, rid, slot_key)
                        photo_add(sb, rid, slot_key, label, data, ".jpg")
                        st.session_state.pop(change_key, None)
                        st.rerun()
            if not existing:
                st.caption("(미등록)")
        st.markdown("<div style='margin-bottom:16px'></div>", unsafe_allow_html=True)


def ui_photo_optional_upload(sb: Client, rid: str):
    """Render the optional additional photo upload section."""
    st.markdown("#### 2. 추가 사진(선택)")
    uploads = st.file_uploader("추가 사진들(복수 선택 가능)", type=["jpg", "jpeg", "png"], accept_multiple_files=True, key="additional_photos")
    if uploads:
        for upl in uploads:
            data = bytes_from_camera_or_upload(upl)
            if data:
                photo_add(sb, rid, "additional", upl.name, data, ".jpg")
        if uploads:
            st.success(f"{len(uploads)}개 사진 저장 완료")
            st.rerun()
