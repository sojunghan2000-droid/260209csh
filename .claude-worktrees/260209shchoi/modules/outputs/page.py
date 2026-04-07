"""Outputs / download page."""

from pathlib import Path

import streamlit as st
from supabase import Client

from datetime import date
from shared.helpers import b64_download_link, req_display_id
from config import KIND_IN
from shared.share import make_share_text
from modules.request.crud import req_list, req_get
from modules.outputs.crud import outputs_get, generate_all_outputs


def page_outputs(sb: Client):
    st.markdown("""
    <style>
    [data-testid="stSelectbox"] [data-testid="stWidgetLabel"],
    [data-testid="stSelectbox"] label {
        margin-bottom: -14px !important;
        padding-bottom: 0 !important;
        line-height: 1 !important;
    }
    [data-testid="stExpander"] summary {
        padding: 9px 0.75rem !important;
        height: auto !important;
    }
    [data-testid="stExpander"] summary span,
    [data-testid="stExpander"] summary p {
        margin: 0 !important;
        padding: 0 !important;
        line-height: 1.2 !important;
        vertical-align: middle !important;
    }
    </style>
    """, unsafe_allow_html=True)
    st.markdown("### 📦 산출물")
    today = date.today().isoformat()
    allreq = [
        r for r in req_list(sb, None, None, 500)
        if (r.get('date') or '') >= today or r.get('status') == 'DONE'
    ]
    if not allreq:
        st.info("요청이 없습니다.")
        return
    items = [(f"{req_display_id(r)} · {r['company_name']} · {r['item_name']}", r['id']) for r in allreq]
    sel = st.selectbox("대상 선택", items, format_func=lambda x: x[0])
    rid = sel[1]
    req = req_get(sb, rid)
    outs = outputs_get(sb, rid)
    st.markdown("<div style='margin-top:16px'></div>", unsafe_allow_html=True)
    if st.button("산출물 재생성", type="primary"):
        try:
            generate_all_outputs(sb, rid)
            st.success("재생성 완료")
        except Exception as e:
            st.error(f"생성 오류: {e}")
        st.rerun()
    outs = outputs_get(sb, rid)
    if outs:
        p = outs.get("plan_pdf_path", "")
        if p and Path(p).exists():
            doc_title = "자재반입계획서" if req.get("kind") == KIND_IN else "자재반출 사진대지"
            st.markdown(b64_download_link(Path(p), f"⬇️ {doc_title} 다운로드"), unsafe_allow_html=True)
            with st.expander("🔍 미리보기"):
                try:
                    import fitz  # pymupdf
                    doc = fitz.open(str(p))
                    for i in range(len(doc)):
                        page = doc.load_page(i)
                        pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
                        st.image(pix.tobytes("png"), caption=f"{i + 1} / {len(doc)}", use_container_width=True)
                    doc.close()
                except ImportError:
                    st.warning("미리보기를 위해 `pip install pymupdf` 를 실행하세요.")
                except Exception as e:
                    st.error(f"미리보기 오류: {e}")
        else:
            st.info("산출물 재생성 버튼을 눌러주세요.")
    else:
        st.info("산출물 재생성 버튼을 눌러주세요.")
    st.markdown("#### SNS 공유 문구")
    st.text_area("", value=make_share_text(req, outs), height=200)
