"""Signature and stamp capture UI components."""

import uuid
from pathlib import Path
from typing import Optional, Tuple

import streamlit as st

from db.connection import path_output
from shared.helpers import bytes_from_camera_or_upload, png_bytes_from_canvas_rgba

CANVAS_AVAILABLE = True
try:
    from streamlit_drawable_canvas import st_canvas
except Exception:
    CANVAS_AVAILABLE = False


def save_bytes_to_file(folder_key: str, rid: str, tag: str, data: bytes, suffix: str) -> str:
    """Save raw bytes into the output folder and return the file path."""
    out = path_output()[folder_key]
    fp = out / f"{rid}_{tag}_{uuid.uuid4().hex[:8]}{suffix}"
    fp.write_bytes(data)
    return str(fp)


def ui_signature_block(rid: str, label: str, key_prefix: str) -> Tuple[Optional[str], Optional[str]]:
    """Render signature + stamp upload block. Returns (sign_path, stamp_path)."""
    st.markdown(f"#### {label}")
    st.markdown("""
    <style>
    [class*="_canvas"] iframe,
    [class*="_sign_img_wrap"] [data-testid="stImage"] {
        display: block !important;
        margin: 0 auto !important;
        text-align: center !important;
    }
    [class*="_sign_img_wrap"] [data-testid="stImage"] img {
        display: block !important;
        margin: 0 auto !important;
    }
    @media (max-width: 480px) {
        [class*="_btn_row"] .stHorizontalBlock,
        [class*="_sign_preview_row"] .stHorizontalBlock {
            flex-wrap: nowrap !important;
        }
        [class*="_btn_row"] .stHorizontalBlock > div {
            flex: 0 0 50% !important;
            max-width: 50% !important;
        }
        [class*="_sign_preview_row"] .stHorizontalBlock > div:first-child {
            flex: 1 1 auto !important;
            min-width: 0 !important;
        }
        [class*="_sign_preview_row"] .stHorizontalBlock > div:last-child {
            flex: 0 0 auto !important;
        }
    }
    [class*="_sign_change"] button,
    [class*="_stamp_change"] button {
        min-height: 22px !important;
        height: 22px !important;
        padding: 0 8px !important;
        font-size: 12px !important;
        background-color: #6b7280 !important;
        border-color: #6b7280 !important;
        color: #ffffff !important;
    }
    [class*="_sign_change"] button p,
    [class*="_stamp_change"] button p {
        line-height: 22px !important;
        margin: 0 !important;
        font-size: 12px !important;
        color: #ffffff !important;
    }
    [class*="_sign_change"] button:hover,
    [class*="_stamp_change"] button:hover {
        background-color: #4b5563 !important;
        border-color: #4b5563 !important;
    }
    [class*="_save"] button,
    [class*="_clear"] button {
        min-height: 28px !important;
        height: 28px !important;
        padding: 0 !important;
        display: flex !important;
        align-items: center !important;
        justify-content: center !important;
    }
    [class*="_save"] button p,
    [class*="_clear"] button p {
        line-height: 28px !important;
        margin: 0 !important;
        padding: 0 !important;
    }
</style>
    """, unsafe_allow_html=True)
    sign_path = None
    stamp_path = None
    mode = st.radio("서명 방식", ["직접 서명(권장)", "이미지 업로드(옵션)"], horizontal=True, key=f"{key_prefix}_mode")
    if mode == "직접 서명(권장)":
        if not CANVAS_AVAILABLE:
            st.warning("streamlit-drawable-canvas, pillow 설치 필요")
        else:
            st.caption("손가락/펜으로 서명하세요. (지우기: Clear)")
            _, col_c, _ = st.columns([1, 4, 1])
            with col_c:
                canvas_res = st_canvas(
                    fill_color="rgba(255, 255, 255, 0)",
                    stroke_width=4,
                    stroke_color="#111111",
                    background_color="#ffffff",
                    height=180,
                    width=340,
                    drawing_mode="freedraw",
                    key=f"{key_prefix}_canvas",
                )
            with st.container(key=f"{key_prefix}_btn_row"):
                colA, colB = st.columns(2, gap="small")
            with colA:
                if st.button("서명 저장", key=f"{key_prefix}_save", use_container_width=True):
                    if canvas_res.image_data is None:
                        st.error("서명이 없습니다.")
                    else:
                        png = png_bytes_from_canvas_rgba(canvas_res.image_data)
                        if not png:
                            st.error("서명 저장 실패")
                        else:
                            sign_path = save_bytes_to_file("sign", rid, "sign_draw", png, ".png")
                            st.success("서명 저장 완료")
            with colB:
                st.button("Clear", key=f"{key_prefix}_clear", use_container_width=True)
            if sign_path:
                st.session_state[f"{key_prefix}_sign_path"] = sign_path
            sign_path = st.session_state.get(f"{key_prefix}_sign_path", None)
    else:
        sign_preview = st.session_state.get(f"{key_prefix}_sign_preview")
        if sign_preview and not st.session_state.get(f"{key_prefix}_sign_editing"):
            import base64
            b64 = base64.b64encode(sign_preview["data"]).decode()
            st.markdown(
                f"<div style='text-align:center;'>"
                f"<img src='data:image/png;base64,{b64}' width='200' style='display:inline-block;'/>"
                f"<div style='font-size:12px;color:#666;margin-top:1px;margin-bottom:12px;'>{sign_preview['name']}</div>"
                f"</div>",
                unsafe_allow_html=True,
            )
            col_l, col_m, col_r = st.columns([2, 1, 2])
            with col_m:
                if st.button("변경", key=f"{key_prefix}_sign_change", use_container_width=True):
                    st.session_state[f"{key_prefix}_sign_editing"] = True
                    st.rerun()
            sign_path = st.session_state.get(f"{key_prefix}_sign_path")
        else:
            upl = st.file_uploader("서명 이미지 업로드(PNG/JPG)", type=["png", "jpg", "jpeg"], key=f"{key_prefix}_sign_upload")
            if upl:
                data = bytes_from_camera_or_upload(upl)
                if data:
                    suffix = Path(upl.name).suffix.lower() or ".png"
                    sign_path = save_bytes_to_file("sign", rid, "sign_upl", data, suffix)
                    st.session_state[f"{key_prefix}_sign_path"] = sign_path
                    st.session_state[f"{key_prefix}_sign_preview"] = {"data": data, "name": upl.name}
                    st.session_state[f"{key_prefix}_sign_editing"] = False
                    st.rerun()

    stamp_path = st.session_state.get(f"{key_prefix}_stamp_path", None)
    return sign_path, stamp_path
