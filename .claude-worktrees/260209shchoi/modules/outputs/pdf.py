"""PDF generation functions."""

from pathlib import Path
from typing import Dict, Any, List, Optional

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

try:
    from reportlab.lib.utils import ImageReader
except Exception:
    pass

# 한글 폰트 등록 (Windows + Linux Cloud 환경 모두 지원)
_FONT_NORMAL = "Helvetica"
_FONT_BOLD   = "Helvetica-Bold"
try:
    import os, urllib.request, tempfile

    def _download_nanum(url: str, dest: str) -> bool:
        """폰트를 URL에서 다운로드해 dest에 저장. 성공 시 True."""
        try:
            # 유효한 TTF 파일이면 재사용 (폰트 파일은 최소 100KB 이상)
            if os.path.exists(dest) and os.path.getsize(dest) > 100_000:
                return True
            # 불완전하거나 잘못된 캐시 파일 삭제
            if os.path.exists(dest):
                os.remove(dest)
            urllib.request.urlretrieve(url, dest)
            return os.path.exists(dest) and os.path.getsize(dest) > 100_000
        except Exception:
            return False

    _TMP = tempfile.gettempdir()
    # 폰트 후보: 로컬 경로 우선, 없으면 GitHub에서 다운로드
    _NANUM_URL_N = (
        "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Regular.ttf"
    )
    _NANUM_URL_B = (
        "https://raw.githubusercontent.com/google/fonts/main/ofl/nanumgothic/NanumGothic-Bold.ttf"
    )
    _candidates_normal = [
        "C:/Windows/Fonts/malgun.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothic.ttf",
        "/usr/share/fonts/nanum/NanumGothic.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothic.ttf",
        os.path.join(_TMP, "NanumGothic.ttf"),   # 캐시 다운로드
    ]
    _candidates_bold = [
        "C:/Windows/Fonts/malgunbd.ttf",
        "/usr/share/fonts/truetype/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/nanum/NanumGothicBold.ttf",
        "/usr/share/fonts/truetype/nanum/NanumBarunGothicBold.ttf",
        os.path.join(_TMP, "NanumGothicBold.ttf"),
    ]

    # 로컬 경로에 없으면 다운로드 후 /tmp에 캐시
    _found_normal = any(os.path.exists(p) for p in _candidates_normal[:-1])
    if not _found_normal:
        _download_nanum(_NANUM_URL_N, os.path.join(_TMP, "NanumGothic.ttf"))
    _found_bold = any(os.path.exists(p) for p in _candidates_bold[:-1])
    if not _found_bold:
        _download_nanum(_NANUM_URL_B, os.path.join(_TMP, "NanumGothicBold.ttf"))

    for _path in _candidates_normal:
        if os.path.exists(_path):
            pdfmetrics.registerFont(TTFont("KoreanFont", _path))
            _FONT_NORMAL = "KoreanFont"
            break
    for _path in _candidates_bold:
        if os.path.exists(_path):
            pdfmetrics.registerFont(TTFont("KoreanFont-Bold", _path))
            _FONT_BOLD = "KoreanFont-Bold"
            break
except Exception:
    pass

QR_AVAILABLE = True
try:
    import qrcode
except Exception:
    QR_AVAILABLE = False

from shared.helpers import now_str
from config import KIND_IN, CHECK_ITEMS, APP_VERSION
from modules.execution.crud import final_approved_signs


def qr_generate_png(url: str, out_path: Path) -> Optional[Path]:
    """Generate a QR code PNG from a URL."""
    if not QR_AVAILABLE:
        return None
    qrcode.make(url).save(out_path)
    return out_path


def pdf_simple_header(c: canvas.Canvas, title: str, subtitle: str = "") -> None:
    """Draw a simple header on a PDF page."""
    c.setFont(_FONT_BOLD, 16)
    c.drawString(20 * mm, 287 * mm, title)
    if subtitle:
        c.setFont(_FONT_NORMAL, 10)
        c.drawString(20 * mm, 281 * mm, subtitle)
    c.line(20 * mm, 278 * mm, 190 * mm, 278 * mm)


def draw_signatures(c: canvas.Canvas, signs: List[Dict[str, Any]], y_mm: float) -> None:
    """Draw signature images on a PDF page."""
    if not signs:
        c.setFont(_FONT_NORMAL, 9)
        c.drawString(20 * mm, y_mm * mm, "서명 없음")
        return
    x = 20 * mm
    y = y_mm * mm
    for s in signs:
        c.setFont(_FONT_NORMAL, 9)
        c.drawString(x, y + 18, f"{s.get('role_required', '')} / {s.get('signer_name', '')}")
        c.drawString(x, y + 10, f"{s.get('signed_at', '')}")
        if s.get("sign_png_path") and Path(s["sign_png_path"]).exists():
            try:
                c.drawImage(
                    ImageReader(str(s["sign_png_path"])),
                    x, y - 6,
                    width=28 * mm, height=12 * mm,
                    preserveAspectRatio=True, mask="auto",
                )
            except Exception:
                pass
        if s.get("stamp_png_path") and Path(s["stamp_png_path"]).exists():
            try:
                c.drawImage(
                    ImageReader(str(s["stamp_png_path"])),
                    x + 32 * mm, y - 6,
                    width=14 * mm, height=14 * mm,
                    preserveAspectRatio=True, mask="auto",
                )
            except Exception:
                pass
        x += 60 * mm


def pdf_plan(
    sb,
    req: Dict[str, Any],
    approvals: List[Dict[str, Any]],
    out_path: Path,
    photos: Optional[List[Dict[str, Any]]] = None,
) -> Path:
    """Generate the plan PDF (자재 반출입 계획서)."""
    c = canvas.Canvas(str(out_path), pagesize=A4)
    pdf_simple_header(
        c,
        "자재반입계획서" if req['kind'] == KIND_IN else "자재반출 사진대지",
        f"생성: {now_str()} · {APP_VERSION}",
    )
    y = 270 * mm
    c.setFont(_FONT_NORMAL, 10)
    fields = [
        ("회사명", req.get("company_name", "")),
        ("취급 자재/도구명", req.get("item_name", "")),
        ("공종/자재종류", req.get("item_type", "")),
        ("요청자", f"{req.get('requester_name', '')} ({req.get('requester_role', '')})"),
        ("일자", req.get("date", "")),
        ("시간", f"{req.get('time_from', '')} ~ {req.get('time_to', '')}"),
        ("사용 GATE", req.get("gate", "")),
        ("운반 차량", f"{req.get('vehicle_type', '')} / {str(req.get('vehicle_ton', '')).replace('톤', '')}톤 / {req.get('vehicle_count', 1)}대"),
        ("기사", f"{req.get('driver_name', '')} ({req.get('driver_phone', '')})"),
        ("비고", req.get("notes", "")),
    ]
    for k, v in fields:
        c.drawString(20 * mm, y, f"{k}: {v}")
        y -= 7 * mm
    y -= 4 * mm
    c.setFont(_FONT_BOLD, 11)
    c.drawString(20 * mm, y, "승인 이력")
    y -= 7 * mm
    c.setFont(_FONT_NORMAL, 10)
    for ap in approvals:
        txt = f"{ap['step_no']}. {ap['role_required']} - {ap['status']}"
        if ap["status"] == "APPROVED":
            txt += f" · {ap.get('signer_name', '')} · {ap.get('signed_at', '')}"
        if ap["status"] == "REJECTED":
            txt += f" · 사유: {ap.get('reject_reason', '')}"
        c.drawString(22 * mm, y, txt)
        y -= 6 * mm
    # 우측 하단 서명
    sign_x = 150 * mm
    c.setFont(_FONT_BOLD, 11)
    c.drawString(sign_x, 42 * mm, "최종 승인 서명")
    approved = [a for a in approvals if a.get("status") == "APPROVED"]
    x = sign_x
    y = 22 * mm
    for s in approved:
        c.setFont(_FONT_NORMAL, 9)
        c.drawString(x, y + 18, f"{s.get('role_required', '')} / {s.get('signer_name', '')}")
        c.drawString(x, y + 10, f"{s.get('signed_at', '')}")
        if s.get("sign_png_path") and Path(s["sign_png_path"]).exists():
            try:
                c.drawImage(
                    ImageReader(str(s["sign_png_path"])),
                    x, y - 6,
                    width=28 * mm, height=12 * mm,
                    preserveAspectRatio=True, mask="auto",
                )
            except Exception:
                pass
        x += 60 * mm
    c.showPage()

    # ── 사진대지 (2×2 표 형태, 가로 페이지) ─────────────────────────
    if photos:
        def _img_reader(photo: dict):
            """storage_url → URL fetch, 없으면 로컬 file_path."""
            url = photo.get("storage_url", "")
            if url:
                try:
                    import urllib.request
                    from io import BytesIO
                    with urllib.request.urlopen(url, timeout=10) as r:
                        return ImageReader(BytesIO(r.read()))
                except Exception:
                    pass
            fp = photo.get("file_path", "")
            if fp and Path(fp).exists():
                return ImageReader(str(fp))
            return None

        valid = [p for p in photos if p.get("storage_url") or (p.get("file_path") and Path(p["file_path"]).exists())]
        from reportlab.lib.pagesizes import landscape
        pw, ph = landscape(A4)   # 가로: 297mm, 세로: 210mm
        margin_x = 12 * mm
        margin_y = 12 * mm
        gap = 5 * mm
        label_h = 8 * mm
        header_h = 14 * mm
        col_w = (pw - margin_x * 2 - gap) / 2
        img_h = (ph - margin_y * 2 - header_h - gap - label_h * 2 - gap * 2) / 2

        def cell_pos(row, col):
            x = margin_x + col * (col_w + gap)
            y = ph - margin_y - header_h - row * (img_h + label_h + gap) - img_h
            return x, y

        for page_start in range(0, len(valid), 4):
            c.setPageSize((pw, ph))
            c.setFont(_FONT_BOLD, 12)
            c.drawString(margin_x, ph - 10 * mm, "사진대지")
            c.line(margin_x, ph - 12 * mm, pw - margin_x, ph - 12 * mm)

            batch = valid[page_start:page_start + 4]
            for i, photo in enumerate(batch):
                row, col = divmod(i, 2)
                px, py = cell_pos(row, col)
                label = f"[{photo.get('slot_key', '')}] {photo.get('label', '')}"

                c.setStrokeColorRGB(0.6, 0.6, 0.6)
                c.rect(px, py - label_h, col_w, img_h + label_h)
                c.line(px, py, px + col_w, py)

                pad = 2 * mm
                img_reader = _img_reader(photo)
                if img_reader:
                    try:
                        c.drawImage(
                            img_reader,
                            px + pad, py + pad,
                            width=col_w - pad * 2,
                            height=img_h - pad * 2,
                            preserveAspectRatio=True,
                            anchor='c',
                            mask="auto",
                        )
                    except Exception:
                        c.setFont(_FONT_NORMAL, 9)
                        c.drawCentredString(px + col_w / 2, py + img_h / 2, "(사진 로드 실패)")
                else:
                    c.setFont(_FONT_NORMAL, 9)
                    c.drawCentredString(px + col_w / 2, py + img_h / 2, "(사진 없음)")

                c.setFont(_FONT_NORMAL, 8)
                c.setFillColorRGB(0, 0, 0)
                c.drawCentredString(px + col_w / 2, py - label_h + 2 * mm, label)

            c.showPage()

    c.save()
    return out_path


def pdf_permit(
    sb,
    req: Dict[str, Any],
    sic_url: str,
    qr_path: Optional[Path],
    out_path: Path,
) -> Path:
    """Generate the permit PDF (자재 차량 진출입 허가증)."""
    c = canvas.Canvas(str(out_path), pagesize=A4)
    pdf_simple_header(c, "자재 차량 진출입 허가증", f"생성: {now_str()} · {APP_VERSION}")
    c.setFont(_FONT_NORMAL, 11)
    c.drawString(20 * mm, 260 * mm, f"입고 회사명: {req.get('company_name', '')}")
    c.drawString(20 * mm, 252 * mm, f"운전원: {req.get('driver_name', '')} / {req.get('driver_phone', '')}")
    c.drawString(
        20 * mm, 244 * mm,
        f"사용 GATE: {req.get('gate', '')} · 일시: {req.get('date', '')} {req.get('time_from', '')}~{req.get('time_to', '')}",
    )
    c.setFont(_FONT_BOLD, 11)
    c.drawString(20 * mm, 232 * mm, "필수 준수사항")
    c.setFont(_FONT_NORMAL, 10)
    rules = [
        "1. 하차 시 안전모 착용",
        "2. 운전석 유리창 개방 필수",
        "3. 현장 내 속도 10km/h 이내 주행",
        "4. 비상등 상시 점등",
        "5. 주정차 시 고임목 설치",
        "6. 유도원 통제하에 운영",
    ]
    y = 225 * mm
    for r in rules:
        c.drawString(22 * mm, y, r)
        y -= 6 * mm
    c.setFont(_FONT_BOLD, 11)
    c.drawString(20 * mm, 180 * mm, "방문자교육(QR)")
    c.setFont(_FONT_NORMAL, 9)
    c.drawString(20 * mm, 174 * mm, f"URL: {sic_url}")
    if qr_path and qr_path.exists():
        try:
            c.drawImage(
                ImageReader(str(qr_path)),
                20 * mm, 125 * mm,
                width=45 * mm, height=45 * mm,
                preserveAspectRatio=True, mask="auto",
            )
        except Exception:
            c.drawString(20 * mm, 160 * mm, "(QR 삽입 실패)")
    c.setFont(_FONT_BOLD, 11)
    c.drawString(80 * mm, 145 * mm, "담당자 승인")
    draw_signatures(c, final_approved_signs(sb, req["id"])[-1:], 122)
    c.showPage()
    c.save()
    return out_path


def pdf_check_card(
    sb,
    req: Dict[str, Any],
    check_json: Dict[str, Any],
    out_path: Path,
) -> Path:
    """Generate the check card PDF (자재 상/하차 점검카드)."""
    c = canvas.Canvas(str(out_path), pagesize=A4)
    pdf_simple_header(c, "자재 상/하차 점검카드", f"요청ID: {req['id']} · 생성: {now_str()} · {APP_VERSION}")
    c.setFont(_FONT_NORMAL, 10)
    c.drawString(20 * mm, 270 * mm, f"협력회사: {req.get('company_name', '')}")
    c.drawString(20 * mm, 262 * mm, f"화물/자재: {req.get('item_name', '')} / 종류: {req.get('item_type', '')}")
    c.drawString(
        20 * mm, 254 * mm,
        f"일시: {req.get('date', '')} {req.get('time_from', '')}~{req.get('time_to', '')} / GATE: {req.get('gate', '')}",
    )
    y = 240 * mm
    for key, title in CHECK_ITEMS:
        val = "✓" if check_json.get(key) else "✗"
        c.drawString(20 * mm, y, f"{title}: {val}")
        y -= 7 * mm
        if y < 20 * mm:
            c.showPage()
            y = 270 * mm
    c.showPage()
    c.save()
    return out_path


def pdf_exec_summary(
    sb,
    req: Dict[str, Any],
    photos: List[Dict[str, Any]],
    out_path: Path,
) -> Path:
    """Generate the execution summary PDF (실행 기록/사진 요약)."""
    c = canvas.Canvas(str(out_path), pagesize=A4)
    pdf_simple_header(c, "실행 기록(사진 요약)", f"요청ID: {req['id']} · 생성: {now_str()} · {APP_VERSION}")
    c.setFont(_FONT_NORMAL, 10)
    y = 270 * mm
    c.drawString(
        20 * mm, y,
        f"회사: {req.get('company_name', '')} / 자재: {req.get('item_name', '')} / {'반입' if req['kind'] == KIND_IN else '반출'}",
    )
    y -= 8 * mm
    c.drawString(
        20 * mm, y,
        f"일시: {req.get('date', '')} {req.get('time_from', '')}~{req.get('time_to', '')} / GATE: {req.get('gate', '')}",
    )
    y -= 12 * mm
    c.setFont(_FONT_BOLD, 11)
    c.drawString(20 * mm, y, "사진 목록")
    y -= 8 * mm
    c.setFont(_FONT_NORMAL, 10)
    for p in photos:
        c.drawString(22 * mm, y, f"- [{p.get('slot_key', '')}] {p.get('label', '')} · {Path(p['file_path']).name}")
        y -= 6 * mm
        if y < 20 * mm:
            c.showPage()
            y = 270 * mm
    c.showPage()
    c.save()
    return out_path
