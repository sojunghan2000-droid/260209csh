# ============================================================
# MaterialTool app.py v2.4.3 (FULL OVERWRITE / Production PoC)
# - 필수 3종(상차 전/후, 결속근접) 충족해야 EXECUTED 등록 가능
# - 추가 사진은 옵션(여러 장) 저장/리포트 포함
# - A안: 역할=관리자 선택 시 Admin PIN 입력칸 표시
# - QR 안정화: URL 정규화/검증 + 로그인/승인 화면 QR 미리보기 + 클릭 테스트 링크
# - Workflow: 신청(PENDING) -> 승인(APPROVED) -> 게이트확인 -> 실행(EXECUTED)
# - Outputs: 승인서PDF, 허가증(QR)PDF, 점검카드PDF, 실행사진PDF,
#            PACKET_LIGHT, PACKET_FULL(단톡 1개 업로드용), ZIP(옵션)
# - Storage: SQLite(DB파일) + 폴더 기반 산출물 저장
# ============================================================

import os
import io
import re
import json
import zipfile
import hashlib
import sqlite3
from datetime import datetime, date
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple

import streamlit as st
from PIL import Image

import qrcode
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors

from streamlit_drawable_canvas import st_canvas


# =========================
# 0) CONFIG
# =========================
APP_VERSION = "2.4.3"
APP_TITLE = "자재 반출입 승인 Tool"

ROLE_OPTIONS = ["협력사", "공무", "안전", "경비", "관리자"]

BASE = Path(os.environ.get("MATERIAL_BASE", "./MaterialToolShared"))

SITE_PIN = os.getenv("MTOOL_SITE_PIN", "1234")
ADMIN_PIN = os.getenv("MTOOL_ADMIN_PIN", "9999")

DEFAULT_SIC_URL = os.getenv("MTOOL_SIC_URL", "https://example.com/visitor-training")

# 공유폴더 UNC(선택)  예) \\SERVER01\\MaterialToolShared
SHARE_UNC = os.getenv("MTOOL_SHARE_UNC", "").strip()

PHOTO_ROLES_DEFAULT = {"공무", "안전", "관리자"}
REQUIRED_PHOTOS = 3

DB_PATH = BASE / "data" / "gate.db"


# =========================
# 1) UTIL
# =========================
def now_ts() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def safe_text(s: str, limit: int = 300) -> str:
    s = (s or "").strip()
    s = re.sub(r"[\r\n\t]+", " ", s)
    return s[:limit]

def _hash_pin(pin: str) -> str:
    return hashlib.sha256((pin or "").strip().encode("utf-8")).hexdigest()

SITE_PIN_H = _hash_pin(SITE_PIN)
ADMIN_PIN_H = _hash_pin(ADMIN_PIN)

def verify_pin(pin: str, pin_hash: str) -> bool:
    return _hash_pin(pin) == pin_hash

def ensure_dirs():
    (BASE / "data").mkdir(parents=True, exist_ok=True)
    (BASE / "output" / "pdf").mkdir(parents=True, exist_ok=True)
    (BASE / "output" / "packet").mkdir(parents=True, exist_ok=True)
    (BASE / "output" / "check").mkdir(parents=True, exist_ok=True)
    (BASE / "output" / "photos").mkdir(parents=True, exist_ok=True)
    (BASE / "output" / "sign").mkdir(parents=True, exist_ok=True)
    (BASE / "output" / "zip").mkdir(parents=True, exist_ok=True)

def get_unc_path(local_path: str) -> str:
    try:
        p = Path(local_path)
        if not SHARE_UNC:
            return local_path
        rel = p.relative_to(BASE)
        return str(Path(SHARE_UNC) / rel).replace("/", "\\")
    except Exception:
        return local_path

def bytes_to_jpg_bytes(img_bytes: bytes, max_w: int = 1600) -> bytes:
    im = Image.open(io.BytesIO(img_bytes)).convert("RGB")
    w, h = im.size
    if w > max_w:
        r = max_w / float(w)
        im = im.resize((int(w * r), int(h * r)))
    out = io.BytesIO()
    im.save(out, format="JPEG", quality=88)
    return out.getvalue()

def normalize_url(raw: str) -> str:
    """
    - 앞뒤 공백 제거
    - 스킴이 없으면 https:// 자동 부여
    - 내부에 공백이 있으면 제거(일부 QR리더 호환)
    """
    u = (raw or "").strip()
    u = u.replace(" ", "")
    if not u:
        return ""
    if not (u.lower().startswith("http://") or u.lower().startswith("https://")):
        u = "https://" + u
    return u

def validate_url(u: str) -> Tuple[bool, str]:
    """
    단순 검증(현장용): 스킴/도메인 형태 정도만 체크.
    """
    if not u:
        return False, "URL이 비어있습니다."
    if not (u.lower().startswith("http://") or u.lower().startswith("https://")):
        return False, "http:// 또는 https:// 로 시작해야 합니다."
    # 최소 도메인 형태
    if "://" in u:
        host = u.split("://", 1)[1]
        host = host.split("/", 1)[0]
        if "." not in host and host.lower() != "localhost":
            return False, "도메인/호스트 형식이 이상합니다(예: example.com)."
    return True, ""

def make_qr_png_bytes(url: str) -> bytes:
    qr = qrcode.QRCode(version=2, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=8, border=2)
    qr.add_data(url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white").convert("RGB")
    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()

def save_bytes(path: Path, data: bytes):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)

def make_zip(zip_path: Path, files: List[Path]) -> Path:
    zip_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for f in files:
            if f and f.exists():
                zf.write(f, arcname=f.name)
    return zip_path


# =========================
# 2) DB (SQLite)
# =========================
def db_connect() -> sqlite3.Connection:
    con = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    con.execute("PRAGMA busy_timeout=5000;")
    return con

def db_init():
    ensure_dirs()
    con = db_connect()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings(
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS requests(
      req_id TEXT PRIMARY KEY,
      io_type TEXT NOT NULL,
      site_name TEXT NOT NULL,
      partner_company TEXT NOT NULL,
      material_type TEXT NOT NULL,
      vehicle_no TEXT NOT NULL,
      driver_phone TEXT NOT NULL,
      gate TEXT NOT NULL,
      work_date TEXT NOT NULL,
      work_time TEXT NOT NULL,
      risk_level TEXT NOT NULL,
      note TEXT,

      requester_name TEXT NOT NULL,
      requester_role TEXT NOT NULL,
      created_at TEXT NOT NULL,

      status TEXT NOT NULL,
      approved_by TEXT,
      approved_at TEXT,
      admin_sign_path TEXT,
      stamp_path TEXT,
      sic_url TEXT,

      exec_by TEXT,
      exec_at TEXT,
      photo_dir TEXT,

      checklist_json TEXT,
      photos_json TEXT,
      outputs_json TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS logs(
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      req_id TEXT NOT NULL,
      action TEXT NOT NULL,
      actor TEXT NOT NULL,
      actor_role TEXT NOT NULL,
      detail TEXT,
      created_at TEXT NOT NULL
    );
    """)
    con.commit()
    con.close()

def db_get_setting(key: str, default: str = "") -> str:
    con = db_connect()
    row = con.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
    con.close()
    return row["value"] if row else default

def db_set_setting(key: str, value: str):
    con = db_connect()
    con.execute(
        "INSERT INTO settings(key,value,updated_at) VALUES(?,?,?) "
        "ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at",
        (key, value, now_ts())
    )
    con.commit()
    con.close()

def db_log(req_id: str, action: str, actor: str, actor_role: str, detail: str = ""):
    con = db_connect()
    con.execute(
        "INSERT INTO logs(req_id,action,actor,actor_role,detail,created_at) VALUES(?,?,?,?,?,?)",
        (req_id, action, actor, actor_role, safe_text(detail, 900), now_ts())
    )
    con.commit()
    con.close()

def db_insert_request(payload: Dict[str, Any]):
    con = db_connect()
    cols = ", ".join(payload.keys())
    placeholders = ", ".join(["?"] * len(payload))
    con.execute(f"INSERT INTO requests({cols}) VALUES({placeholders})", tuple(payload.values()))
    con.commit()
    con.close()

def db_update_request(req_id: str, patch: Dict[str, Any]):
    con = db_connect()
    sets = ", ".join([f"{k}=?" for k in patch.keys()])
    con.execute(f"UPDATE requests SET {sets} WHERE req_id=?", tuple(patch.values()) + (req_id,))
    con.commit()
    con.close()

def db_get_request(req_id: str) -> Optional[sqlite3.Row]:
    con = db_connect()
    row = con.execute("SELECT * FROM requests WHERE req_id=?", (req_id,)).fetchone()
    con.close()
    return row

def db_list_requests(status: Optional[str] = None, date_filter: Optional[str] = None, limit: int = 300) -> List[sqlite3.Row]:
    con = db_connect()
    q = "SELECT * FROM requests WHERE 1=1"
    params = []
    if status:
        q += " AND status=?"
        params.append(status)
    if date_filter:
        q += " AND work_date=?"
        params.append(date_filter)
    q += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    rows = con.execute(q, tuple(params)).fetchall()
    con.close()
    return rows

def db_get_logs(req_id: str, limit: int = 50) -> List[sqlite3.Row]:
    con = db_connect()
    rows = con.execute(
        "SELECT * FROM logs WHERE req_id=? ORDER BY id DESC LIMIT ?",
        (req_id, limit)
    ).fetchall()
    con.close()
    return rows


# =========================
# 3) PDF HELPERS
# =========================
def _draw_box(c: canvas.Canvas, x, y, w, h, title: str = ""):
    c.setStrokeColor(colors.HexColor("#D9DEE7"))
    c.setLineWidth(1)
    c.roundRect(x, y, w, h, 8, stroke=1, fill=0)
    if title:
        c.setFillColor(colors.HexColor("#111827"))
        c.setFont("Helvetica-Bold", 10)
        c.drawString(x + 8, y + h - 16, title)

def _kv(c: canvas.Canvas, x, y, k: str, v: str, key_w: float = 70):
    c.setFont("Helvetica-Bold", 9)
    c.setFillColor(colors.HexColor("#374151"))
    c.drawString(x, y, k)
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(x + key_w, y, safe_text(v, 70))

def pdf_approval(req: sqlite3.Row) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFillColor(colors.HexColor("#0B5FFF"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(24*mm, H - 22*mm, f"자재 반출입 승인서 ({'반입' if req['io_type']=='IN' else '반출'})")

    c.setFillColor(colors.HexColor("#6B7280"))
    c.setFont("Helvetica", 9)
    c.drawString(24*mm, H - 28*mm, f"REQ ID: {req['req_id']}  |  생성: {req['created_at']}  |  v{APP_VERSION}")

    _draw_box(c, 20*mm, H - 92*mm, W - 40*mm, 58*mm, "신청 정보")
    y = H - 54*mm
    _kv(c, 26*mm, y, "협력사", req["partner_company"])
    _kv(c, 105*mm, y, "자재", req["material_type"])
    y -= 14
    _kv(c, 26*mm, y, "차량번호", req["vehicle_no"])
    _kv(c, 105*mm, y, "운전원", req["driver_phone"])
    y -= 14
    _kv(c, 26*mm, y, "GATE", req["gate"])
    _kv(c, 105*mm, y, "일시", f"{req['work_date']} {req['work_time']}")
    y -= 14
    _kv(c, 26*mm, y, "위험도", req["risk_level"])
    _kv(c, 105*mm, y, "비고", req["note"] or "-")

    _draw_box(c, 20*mm, H - 155*mm, W - 40*mm, 50*mm, "결재")
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#111827"))
    c.drawString(26*mm, H - 124*mm, f"기안: {req['requester_name']} ({req['requester_role']})")
    c.drawString(26*mm, H - 138*mm, f"결재: {req['approved_by'] or '-'}   |   결재시각: {req['approved_at'] or '-'}")

    sx = 145*mm
    sy = H - 150*mm
    sign_path = req["admin_sign_path"]
    stamp_path = req["stamp_path"]

    if stamp_path and Path(stamp_path).exists():
        try:
            img = Image.open(stamp_path).convert("RGBA")
            tmp = io.BytesIO()
            img.save(tmp, format="PNG")
            tmp.seek(0)
            c.drawImage(tmp, sx, sy, width=24*mm, height=24*mm, mask="auto")
        except Exception:
            pass

    if sign_path and Path(sign_path).exists():
        try:
            img = Image.open(sign_path).convert("RGBA")
            tmp = io.BytesIO()
            img.save(tmp, format="PNG")
            tmp.seek(0)
            c.drawImage(tmp, sx + 28*mm, sy, width=40*mm, height=18*mm, mask="auto")
        except Exception:
            pass

    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(20*mm, 18*mm, "본 문서는 현장 운영 Tool에서 자동 생성되었습니다. (대장에서 승인/실행/사진 이력 확인)")
    c.showPage()
    c.save()
    return buf.getvalue()

def pdf_permit_with_qr(req: sqlite3.Row, sic_url: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(24*mm, H - 22*mm, "자재 차량 진출입 허가증 (QR 포함)")

    c.setFillColor(colors.HexColor("#6B7280"))
    c.setFont("Helvetica", 9)
    c.drawString(24*mm, H - 28*mm, f"REQ ID: {req['req_id']}  |  {req['work_date']} {req['work_time']}")

    _draw_box(c, 20*mm, H - 92*mm, W - 40*mm, 58*mm, "기본 정보")
    y = H - 54*mm
    _kv(c, 26*mm, y, "구분", "반입" if req["io_type"] == "IN" else "반출")
    _kv(c, 105*mm, y, "협력사", req["partner_company"])
    y -= 14
    _kv(c, 26*mm, y, "차량번호", req["vehicle_no"])
    _kv(c, 105*mm, y, "운전원", req["driver_phone"])
    y -= 14
    _kv(c, 26*mm, y, "GATE", req["gate"])
    _kv(c, 105*mm, y, "자재", req["material_type"])

    _draw_box(c, 20*mm, H - 170*mm, W - 40*mm, 65*mm, "필수 준수사항(요약)")
    rules = [
        "현장 내 속도 10km/h 이내",
        "유도원 통제 준수",
        "상/하차 구간 통제 후 작업",
        "비상등 점등 및 안전모 착용",
        "주정차 시 고임목 설치",
        "낙하/전도 위험요소 즉시 조치",
    ]
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.HexColor("#111827"))
    yy = H - 132*mm
    for i, r in enumerate(rules, 1):
        c.drawString(26*mm, yy, f"{i}. {r}")
        yy -= 12

    qr_bytes = make_qr_png_bytes(sic_url)
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGB")
    tmp = io.BytesIO()
    qr_img.save(tmp, format="PNG")
    tmp.seek(0)

    _draw_box(c, 20*mm, 35*mm, 70*mm, 70*mm, "방문자교육 QR")
    c.drawImage(tmp, 27*mm, 44*mm, width=56*mm, height=56*mm)
    c.setFont("Helvetica", 8)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(24*mm, 28*mm, f"URL: {sic_url}")

    c.showPage()
    c.save()
    return buf.getvalue()

def pdf_checkcard(req: sqlite3.Row, checklist: Dict[str, Any]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(24*mm, H - 22*mm, "자재 상/하차 점검카드")

    c.setFillColor(colors.HexColor("#6B7280"))
    c.setFont("Helvetica", 9)
    c.drawString(24*mm, H - 28*mm, f"REQ ID: {req['req_id']}  |  {req['work_date']} {req['work_time']}")

    _draw_box(c, 20*mm, H - 85*mm, W - 40*mm, 45*mm, "기본 정보")
    y = H - 50*mm
    _kv(c, 26*mm, y, "협력사", req["partner_company"])
    _kv(c, 105*mm, y, "자재", req["material_type"])
    y -= 14
    _kv(c, 26*mm, y, "차량번호", req["vehicle_no"])
    _kv(c, 105*mm, y, "GATE", req["gate"])

    _draw_box(c, 20*mm, H - 265*mm, W - 40*mm, 170*mm, "점검 항목")
    items = [
        ("0. 필수 참석자", checklist.get("attendees", "-")),
        ("1. 협력회사", checklist.get("partner_company", "-")),
        ("2. 화물/자재 종류", checklist.get("cargo_type", "-")),
        ("3. 결속 2개소 이상", checklist.get("check_3", "-")),
        ("4. 로프/밴딩 점검", checklist.get("check_4", "-")),
        ("5. 4M 이하/낙하위험", checklist.get("check_5", "-")),
        ("6. 폭초과 금지/닫힘", checklist.get("check_6", "-")),
        ("7. 고임목 설치", checklist.get("check_7", "-")),
        ("8. 적재하중 이내", checklist.get("check_8", "-")),
        ("9. 무게중심(쏠림)", checklist.get("check_9", "-")),
        ("10. 구획/통제", checklist.get("check_10", "-")),
    ]
    yy = H - 110*mm
    for k, v in items:
        c.setFont("Helvetica-Bold", 9)
        c.setFillColor(colors.HexColor("#111827"))
        c.drawString(26*mm, yy, k)
        c.setFont("Helvetica", 10)
        c.drawString(85*mm, yy, safe_text(v, 70))
        yy -= 14
        if yy < 40*mm:
            c.showPage()
            yy = H - 30*mm

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#6B7280"))
    c.drawString(20*mm, 18*mm, "본 점검카드는 현장 운영 Tool에서 자동 생성되었습니다.")
    c.showPage()
    c.save()
    return buf.getvalue()

def pdf_exec_photos(req: sqlite3.Row, photos: List[Dict[str, str]]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(24*mm, H - 22*mm, "실행 사진 기록")

    c.setFillColor(colors.HexColor("#6B7280"))
    c.setFont("Helvetica", 9)
    c.drawString(24*mm, H - 28*mm, f"REQ ID: {req['req_id']}  |  실행: {req['exec_at'] or '-'}  |  담당: {req['exec_by'] or '-'}")

    y = H - 42*mm
    for idx, p in enumerate(photos, 1):
        path = p.get("path", "")
        label = p.get("label", f"사진 {idx}")
        if not path or not Path(path).exists():
            continue

        _draw_box(c, 20*mm, y - 75*mm, W - 40*mm, 70*mm, f"{idx}. {label}")
        try:
            im = Image.open(path).convert("RGB")
            max_w = (W - 52*mm)
            max_h = 55*mm
            iw, ih = im.size
            ratio = min(max_w / iw, max_h / ih)
            draw_w, draw_h = iw * ratio, ih * ratio
            tmp = io.BytesIO()
            im.save(tmp, format="JPEG", quality=85)
            tmp.seek(0)
            c.drawImage(tmp, 26*mm, y - 68*mm, width=draw_w, height=draw_h)
        except Exception:
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.red)
            c.drawString(26*mm, y - 58*mm, f"이미지 로드 실패: {path}")

        y -= 82*mm
        if y < 50*mm:
            c.showPage()
            y = H - 25*mm

    c.showPage()
    c.save()
    return buf.getvalue()

def pdf_packet_light(req: sqlite3.Row, sic_url: str) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFillColor(colors.HexColor("#0B5FFF"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(24*mm, H - 22*mm, "PACKET (승인)")

    c.setFillColor(colors.HexColor("#6B7280"))
    c.setFont("Helvetica", 9)
    c.drawString(24*mm, H - 28*mm, f"REQ ID: {req['req_id']}  |  생성: {now_ts()}  |  v{APP_VERSION}")

    _draw_box(c, 20*mm, H - 105*mm, W - 40*mm, 70*mm, "요약")
    y = H - 58*mm
    _kv(c, 26*mm, y, "구분", "반입" if req["io_type"] == "IN" else "반출")
    _kv(c, 105*mm, y, "협력사", req["partner_company"])
    y -= 14
    _kv(c, 26*mm, y, "자재", req["material_type"])
    _kv(c, 105*mm, y, "차량", req["vehicle_no"])
    y -= 14
    _kv(c, 26*mm, y, "GATE", req["gate"])
    _kv(c, 105*mm, y, "일시", f"{req['work_date']} {req['work_time']}")
    y -= 14
    _kv(c, 26*mm, y, "결재", f"{req['approved_by'] or '-'} / {req['approved_at'] or '-'}")
    _kv(c, 105*mm, y, "위험도", req["risk_level"])

    qr_bytes = make_qr_png_bytes(sic_url)
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGB")
    tmp = io.BytesIO()
    qr_img.save(tmp, format="PNG")
    tmp.seek(0)

    _draw_box(c, 20*mm, 35*mm, 70*mm, 70*mm, "방문자교육 QR")
    c.drawImage(tmp, 27*mm, 44*mm, width=56*mm, height=56*mm)

    c.showPage()
    c.save()
    return buf.getvalue()

def pdf_packet_full(req: sqlite3.Row, sic_url: str, checklist: Dict[str, Any], photos: List[Dict[str, str]]) -> bytes:
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=A4)
    W, H = A4

    c.setFillColor(colors.HexColor("#0B5FFF"))
    c.setFont("Helvetica-Bold", 18)
    c.drawString(24*mm, H - 22*mm, "PACKET (실행 완료)")

    c.setFillColor(colors.HexColor("#6B7280"))
    c.setFont("Helvetica", 9)
    c.drawString(24*mm, H - 28*mm, f"REQ ID: {req['req_id']}  |  생성: {now_ts()}  |  v{APP_VERSION}")

    _draw_box(c, 20*mm, H - 115*mm, W - 40*mm, 80*mm, "요약")
    y = H - 58*mm
    _kv(c, 26*mm, y, "구분", "반입" if req["io_type"] == "IN" else "반출")
    _kv(c, 105*mm, y, "협력사", req["partner_company"])
    y -= 14
    _kv(c, 26*mm, y, "자재", req["material_type"])
    _kv(c, 105*mm, y, "차량", req["vehicle_no"])
    y -= 14
    _kv(c, 26*mm, y, "GATE", req["gate"])
    _kv(c, 105*mm, y, "일시", f"{req['work_date']} {req['work_time']}")
    y -= 14
    _kv(c, 26*mm, y, "결재", f"{req['approved_by'] or '-'} / {req['approved_at'] or '-'}")
    _kv(c, 105*mm, y, "실행", f"{req['exec_by'] or '-'} / {req['exec_at'] or '-'}")
    y -= 14
    _kv(c, 26*mm, y, "위험도", req["risk_level"])
    _kv(c, 105*mm, y, "비고", req["note"] or "-")

    qr_bytes = make_qr_png_bytes(sic_url)
    qr_img = Image.open(io.BytesIO(qr_bytes)).convert("RGB")
    tmp = io.BytesIO()
    qr_img.save(tmp, format="PNG")
    tmp.seek(0)

    _draw_box(c, 20*mm, 35*mm, 70*mm, 70*mm, "방문자교육 QR")
    c.drawImage(tmp, 27*mm, 44*mm, width=56*mm, height=56*mm)

    c.showPage()

    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(24*mm, H - 22*mm, "점검카드 요약")

    items = [
        ("0. 참석자", checklist.get("attendees", "-")),
        ("3. 결속", checklist.get("check_3", "-")),
        ("4. 로프/밴딩", checklist.get("check_4", "-")),
        ("5. 4M 이하/낙하", checklist.get("check_5", "-")),
        ("6. 폭초과/닫힘", checklist.get("check_6", "-")),
        ("7. 고임목", checklist.get("check_7", "-")),
        ("8. 적재하중", checklist.get("check_8", "-")),
        ("9. 무게중심", checklist.get("check_9", "-")),
        ("10. 구획/통제", checklist.get("check_10", "-")),
    ]
    _draw_box(c, 20*mm, H - 270*mm, W - 40*mm, 230*mm, "")
    yy = H - 52*mm
    for k, v in items:
        c.setFont("Helvetica-Bold", 10)
        c.setFillColor(colors.HexColor("#111827"))
        c.drawString(26*mm, yy, k)
        c.setFont("Helvetica", 10)
        c.drawString(80*mm, yy, safe_text(v, 70))
        yy -= 16

    c.showPage()

    c.setFillColor(colors.HexColor("#111827"))
    c.setFont("Helvetica-Bold", 16)
    c.drawString(24*mm, H - 22*mm, "실행 사진")

    y = H - 42*mm
    for idx, p in enumerate(photos, 1):
        path = p.get("path", "")
        label = p.get("label", f"사진 {idx}")
        if not path or not Path(path).exists():
            continue

        _draw_box(c, 20*mm, y - 75*mm, W - 40*mm, 70*mm, f"{idx}. {label}")
        try:
            im = Image.open(path).convert("RGB")
            max_w = (W - 52*mm)
            max_h = 55*mm
            iw, ih = im.size
            ratio = min(max_w / iw, max_h / ih)
            draw_w, draw_h = iw * ratio, ih * ratio
            tmp = io.BytesIO()
            im.save(tmp, format="JPEG", quality=85)
            tmp.seek(0)
            c.drawImage(tmp, 26*mm, y - 68*mm, width=draw_w, height=draw_h)
        except Exception:
            c.setFont("Helvetica", 10)
            c.setFillColor(colors.red)
            c.drawString(26*mm, y - 58*mm, f"이미지 로드 실패: {path}")

        y -= 82*mm
        if y < 50*mm:
            c.showPage()
            c.setFillColor(colors.HexColor("#111827"))
            c.setFont("Helvetica-Bold", 16)
            c.drawString(24*mm, H - 22*mm, "실행 사진(계속)")
            y = H - 42*mm

    c.showPage()
    c.save()
    return buf.getvalue()


# =========================
# 4) AUTH / SESSION (A안) + QR Preview
# =========================
def render_login_panel():
    st.session_state.setdefault("auth_ok", False)
    st.session_state.setdefault("is_admin", False)
    st.session_state.setdefault("user_name", "")
    st.session_state.setdefault("user_role", "공무")

    saved = db_get_setting("sic_url", DEFAULT_SIC_URL)
    st.session_state.setdefault("sic_url", saved)

    st.session_state.setdefault(
        "photo_roles",
        set(json.loads(db_get_setting("photo_roles", json.dumps(list(PHOTO_ROLES_DEFAULT)))))
    )
    st.session_state.setdefault("login_error", "")

    st.markdown("## 🔐 로그인(현장용)")

    with st.form("login_form", clear_on_submit=False):
        col1, col2 = st.columns([1, 1])
        with col1:
            site_pin = st.text_input("현장 PIN*", type="password", placeholder="예) 4자리")
            user_name = st.text_input("이름/직책*", placeholder="예) 공무팀장 홍길동")
            role = st.selectbox("역할*", ROLE_OPTIONS, index=ROLE_OPTIONS.index(st.session_state.get("user_role", "공무")))
        with col2:
            admin_pin = ""
            if role == "관리자":
                admin_pin = st.text_input("Admin PIN*", type="password", placeholder="관리자 전용 PIN")
                st.caption("관리자 역할은 Admin PIN이 필수입니다.")

            sic_url_raw = st.text_input("방문자교육 URL(QR)*", value=st.session_state.get("sic_url", DEFAULT_SIC_URL))

        ok = st.form_submit_button("로그인")

    # ✅ QR/링크 미리보기(로그인 전에도 확인 가능)
    sic_url_preview = normalize_url(st.session_state.get("sic_url", DEFAULT_SIC_URL))
    sic_url_preview = normalize_url(sic_url_raw) if 'sic_url_raw' in locals() else sic_url_preview
    valid, msg = validate_url(sic_url_preview)

    st.markdown("### 🔎 QR 미리보기/테스트")
    if not valid:
        st.warning(f"현재 URL 형식 경고: {msg}")
    if sic_url_preview:
        st.write("테스트 링크(눌러서 열기):")
        st.link_button("방문자교육 링크 열기", sic_url_preview)
        st.image(make_qr_png_bytes(sic_url_preview), caption=sic_url_preview, width=220)
        st.caption("※ QR이 안 열리면: (1) 이 링크가 휴대폰에서 직접 열리는지부터 확인하세요. 안 열리면 '망/보안' 문제일 가능성이 큽니다.")
    else:
        st.info("방문자교육 URL을 입력하면 QR 미리보기가 표시됩니다.")

    if ok:
        if not verify_pin(site_pin, SITE_PIN_H):
            st.session_state["auth_ok"] = False
            st.session_state["is_admin"] = False
            st.session_state["login_error"] = "현장 PIN이 올바르지 않습니다."
            return

        if not safe_text(user_name, 60):
            st.session_state["auth_ok"] = False
            st.session_state["is_admin"] = False
            st.session_state["login_error"] = "이름/직책을 입력해주세요."
            return

        if role == "관리자":
            if not verify_pin(admin_pin, ADMIN_PIN_H):
                st.session_state["auth_ok"] = False
                st.session_state["is_admin"] = False
                st.session_state["login_error"] = "Admin PIN이 올바르지 않습니다."
                return

        # ✅ 저장 시 URL 정규화
        sic_url = normalize_url(sic_url_raw) or normalize_url(DEFAULT_SIC_URL)
        st.session_state["sic_url"] = sic_url
        db_set_setting("sic_url", sic_url)

        st.session_state["auth_ok"] = True
        st.session_state["user_name"] = safe_text(user_name, 60)
        st.session_state["user_role"] = role
        st.session_state["is_admin"] = (role == "관리자")
        st.session_state["login_error"] = ""
        st.rerun()

    if st.session_state.get("login_error"):
        st.error(st.session_state["login_error"])

def require_login():
    if not st.session_state.get("auth_ok"):
        render_login_panel()
        st.stop()

def require_admin():
    require_login()
    if not st.session_state.get("is_admin"):
        st.error("이 기능은 관리자만 사용할 수 있습니다. (역할=관리자 + Admin PIN)")
        st.stop()

def can_upload_photos() -> bool:
    role = st.session_state.get("user_role", "")
    allowed = st.session_state.get("photo_roles", PHOTO_ROLES_DEFAULT)
    return role in allowed


# =========================
# 5) UI
# =========================
def inject_css():
    st.markdown(
        """
        <style>
        .block-container { padding-top: 1.1rem; padding-bottom: 2rem; max-width: 1100px; }
        .card {
          background: #ffffff;
          border: 1px solid #E5E7EB;
          border-radius: 16px;
          padding: 14px 14px;
          box-shadow: 0 10px 30px rgba(17,24,39,0.06);
        }
        .h1 { font-size: 20px; font-weight: 900; color:#0B5FFF; }
        .h2 { font-size: 16px; font-weight: 900; color:#111827; }
        .muted { color:#6B7280; font-size:12px; }
        .pill { display:inline-block; padding:4px 10px; border-radius:999px; font-size:12px;
                border:1px solid #E5E7EB; background:#F9FAFB; color:#111827; margin-right:6px; }
        .hr { height:1px; background:#E5E7EB; margin:12px 0; }
        @media (max-width: 600px) {
          .block-container { padding-left: 0.9rem; padding-right: 0.9rem; }
        }
        </style>
        """,
        unsafe_allow_html=True
    )

def header_area():
    st.markdown(f"<div class='h1'>{APP_TITLE}</div>", unsafe_allow_html=True)
    st.caption(f"v{APP_VERSION} | 저장/산출 루트: {BASE}")

def sidebar_area():
    with st.sidebar:
        st.markdown("### 👤 사용자")
        st.write(f"**{st.session_state.get('user_name','-')}**")
        st.write(f"역할: **{st.session_state.get('user_role','-')}**")
        st.write(f"관리자: {'✅' if st.session_state.get('is_admin') else '—'}")

        st.markdown("---")
        st.markdown("### 📁 산출물 위치")
        st.code(
            f"BASE: {BASE}\n"
            f"DB:   {DB_PATH}\n"
            f"PDF:  {BASE}/output/pdf\n"
            f"PACKET:{BASE}/output/packet\n"
            f"CHECK:{BASE}/output/check\n"
            f"PHOTO:{BASE}/output/photos\n"
            f"SIGN: {BASE}/output/sign\n"
            f"ZIP:  {BASE}/output/zip"
        )
        if SHARE_UNC:
            st.caption(f"UNC(공유경로): {SHARE_UNC}")

        with st.expander("⚙️ 운영 설정(관리자)", expanded=False):
            if st.session_state.get("is_admin"):
                st.markdown("**사진 업로드 허용 역할**")
                roles = st.multiselect("허용 역할", ROLE_OPTIONS, default=sorted(list(st.session_state.get("photo_roles", PHOTO_ROLES_DEFAULT))))
                if st.button("저장(권한)"):
                    st.session_state["photo_roles"] = set(roles)
                    db_set_setting("photo_roles", json.dumps(list(roles), ensure_ascii=False))
                    st.success("저장했습니다.")
            else:
                st.info("관리자만 설정 가능합니다.")


# =========================
# 6) WORKFLOW PAGES
# =========================
def make_req_id(io_type: str) -> str:
    return f"REQ_{datetime.now().strftime('%Y%m%d_%H%M%S')}_{io_type}"

def kpi_area():
    today = date.today().strftime("%Y-%m-%d")
    rows = db_list_requests(date_filter=today, limit=999)
    def cnt(s): return sum(1 for r in rows if r["status"] == s)
    pending, approved, executed = cnt("PENDING"), cnt("APPROVED"), cnt("EXECUTED")
    high = sum(1 for r in rows if r["risk_level"] == "HIGH")
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown(f"<span class='pill'>오늘 요청 {len(rows)}건</span>"
                f"<span class='pill'>대기 {pending}건</span>"
                f"<span class='pill'>승인 {approved}건</span>"
                f"<span class='pill'>실행 {executed}건</span>"
                f"<span class='pill'>고위험 {high}건</span>", unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

def page_home():
    kpi_area()
    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='h2'>진행 카드</div>", unsafe_allow_html=True)
    st.markdown("<div class='muted'>버튼을 누르면 해당 화면으로 이동합니다.</div>", unsafe_allow_html=True)

    col1, col2, col3 = st.columns(3)
    if col1.button("1) 신청"):
        st.session_state["page"] = "신청"
        st.rerun()
    if col2.button("3) 승인(관리자)"):
        st.session_state["page"] = "승인"
        st.rerun()
    if col3.button("6) 실행 등록"):
        st.session_state["page"] = "실행"
        st.rerun()

    col4, col5, col6 = st.columns(3)
    if col4.button("5) 게이트 확인"):
        st.session_state["page"] = "게이트"
        st.rerun()
    if col5.button("7) 대장"):
        st.session_state["page"] = "대장"
        st.rerun()
    if col6.button("로그아웃"):
        st.session_state.clear()
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

def page_apply():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='h2'>1) 반입/반출 신청</div>", unsafe_allow_html=True)
    st.caption("입력 후 저장하면 PENDING(대기)로 등록됩니다.")

    with st.form("apply_form", clear_on_submit=False):
        col1, col2 = st.columns([1, 1])
        with col1:
            io_kor = st.selectbox("구분*", ["반입", "반출"])
            partner = st.text_input("협력회사*", placeholder="예) ㈜OOO")
            material = st.text_input("화물/자재 종류*", placeholder="예) 철근/고철/덕트 등")
            vehicle_no = st.text_input("차량번호*", placeholder="예) 80가1234")
            driver_phone = st.text_input("운전원 연락처*", placeholder="예) 010-1234-5678")
        with col2:
            site_name = st.text_input("현장명*", value="현장명(수정)")
            gate = st.text_input("사용 GATE*", placeholder="예) 1GATE")
            work_date = st.date_input("일자*", value=date.today()).strftime("%Y-%m-%d")
            work_time = st.time_input("시간*", value=datetime.now().replace(second=0, microsecond=0).time()).strftime("%H:%M")
            risk = st.selectbox("위험도*", ["LOW", "MID", "HIGH"], index=1)
            note = st.text_area("비고", placeholder="특이사항/주의사항(선택)", height=90)

        submit = st.form_submit_button("신청 저장(PENDING)", type="primary")

    st.markdown("</div>", unsafe_allow_html=True)

    if submit:
        if not (partner and material and vehicle_no and driver_phone and gate and site_name):
            st.error("필수 항목(*)을 모두 입력해주세요.")
            return

        io_type = "IN" if io_kor == "반입" else "OUT"
        req_id = make_req_id(io_type)

        sic_url = normalize_url(st.session_state.get("sic_url", DEFAULT_SIC_URL)) or normalize_url(DEFAULT_SIC_URL)

        payload = dict(
            req_id=req_id,
            io_type=io_type,
            site_name=safe_text(site_name, 80),
            partner_company=safe_text(partner, 120),
            material_type=safe_text(material, 200),
            vehicle_no=safe_text(vehicle_no, 50),
            driver_phone=safe_text(driver_phone, 50),
            gate=safe_text(gate, 50),
            work_date=work_date,
            work_time=work_time,
            risk_level=risk,
            note=safe_text(note, 600),

            requester_name=st.session_state["user_name"],
            requester_role=st.session_state["user_role"],
            created_at=now_ts(),

            status="PENDING",
            approved_by=None,
            approved_at=None,
            admin_sign_path=None,
            stamp_path=None,
            sic_url=sic_url,

            exec_by=None,
            exec_at=None,
            photo_dir=None,

            checklist_json=None,
            photos_json=None,
            outputs_json=json.dumps({}, ensure_ascii=False),
        )

        db_insert_request(payload)
        db_log(req_id, "CREATE_REQUEST", st.session_state["user_name"], st.session_state["user_role"], f"{io_kor} 신청")

        st.success(f"신청 저장 완료! (REQ ID: {req_id})")

        msg = (
            f"[자재 {('반입' if io_type=='IN' else '반출')} 요청]\n"
            f"- REQ: {req_id}\n"
            f"- 협력사: {partner}\n"
            f"- 자재: {material}\n"
            f"- 차량: {vehicle_no} / {driver_phone}\n"
            f"- GATE: {gate}\n"
            f"- 일시: {work_date} {work_time}\n"
            f"- 위험도: {risk}\n"
            f"(관리자 승인 후 PACKET(PDF) 업로드 예정)"
        )
        st.text_area("📌 단톡 공유 문구(복사해서 전송)", value=msg, height=160)

def page_approve():
    require_admin()

    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='h2'>3) 승인(관리자)</div>", unsafe_allow_html=True)
    st.caption("PENDING 선택 → (도장/서명 옵션) → APPROVED + PACKET_LIGHT 생성")

    pending = db_list_requests(status="PENDING", limit=300)
    if not pending:
        st.info("승인 대기(PENDING) 건이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    options = [
        f"{r['req_id']} | {r['partner_company']} | {r['material_type']} | {r['work_date']} {r['work_time']} | {r['gate']} | {r['risk_level']}"
        for r in pending
    ]
    sel = st.selectbox("승인 대상 선택", options)
    req_id = sel.split(" | ")[0]
    req = db_get_request(req_id)

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)
    st.write(f"**REQ:** {req_id}")
    st.write(f"- 협력사: {req['partner_company']} / 자재: {req['material_type']}")
    st.write(f"- 차량: {req['vehicle_no']} / {req['driver_phone']}")
    st.write(f"- GATE: {req['gate']} / 일시: {req['work_date']} {req['work_time']}")
    st.write(f"- 위험도: {req['risk_level']}")

    st.markdown("### 🔗 방문자교육 URL(QR)")
    sic_input = st.text_input("SIC 방문자교육 URL", value=req["sic_url"] or st.session_state.get("sic_url", DEFAULT_SIC_URL), key=f"sic_{req_id}")
    sic_url = normalize_url(sic_input)

    ok, warn = validate_url(sic_url)
    if not ok:
        st.warning(f"URL 형식 경고: {warn}")
    if sic_url:
        st.link_button("링크 열기(테스트)", sic_url)
        st.image(make_qr_png_bytes(sic_url), caption=sic_url, width=220)

    st.markdown("### 🖋 전자서명(옵션)")
    st.caption("서명이 필요하면 아래 캔버스에 서명 후 저장하세요. (없어도 승인 가능)")
    canvas_result = st_canvas(
        fill_color="rgba(255, 255, 255, 0)",
        stroke_width=3,
        stroke_color="#111827",
        background_color="#FFFFFF",
        height=140,
        width=520,
        drawing_mode="freedraw",
        key=f"sign_canvas_{req_id}",
    )

    st.markdown("### 🟥 도장 이미지(옵션)")
    stamp_file = st.file_uploader("도장 이미지 업로드(PNG/JPG, 선택)", type=["png","jpg","jpeg"], key=f"stamp_{req_id}")

    colA, colB = st.columns([1, 1])

    if colA.button("승인(APPROVED) + PACKET 생성", type="primary"):
        ensure_dirs()

        sign_path = None
        stamp_path = None

        if stamp_file is not None:
            raw = stamp_file.read()
            if raw:
                p = BASE / "output" / "sign" / f"{req_id}_stamp.png"
                save_bytes(p, raw)
                stamp_path = str(p)

        if canvas_result is not None and canvas_result.image_data is not None:
            try:
                img = Image.fromarray(canvas_result.image_data.astype("uint8"), mode="RGBA")
                bbox = img.getbbox()
                if bbox:
                    p = BASE / "output" / "sign" / f"{req_id}_sign.png"
                    out = io.BytesIO()
                    img.save(out, format="PNG")
                    save_bytes(p, out.getvalue())
                    sign_path = str(p)
            except Exception:
                sign_path = None

        # ✅ 승인 시 sic_url 정규화 저장
        db_update_request(req_id, {
            "status": "APPROVED",
            "approved_by": st.session_state["user_name"],
            "approved_at": now_ts(),
            "admin_sign_path": sign_path,
            "stamp_path": stamp_path,
            "sic_url": sic_url or normalize_url(DEFAULT_SIC_URL)
        })
        db_log(req_id, "APPROVE", st.session_state["user_name"], st.session_state["user_role"], "승인 처리")

        req2 = db_get_request(req_id)
        sic2 = req2["sic_url"] or normalize_url(DEFAULT_SIC_URL)

        approval_b = pdf_approval(req2)
        permit_b = pdf_permit_with_qr(req2, sic2)
        packet_b = pdf_packet_light(req2, sic2)

        approval_p = BASE / "output" / "pdf" / f"{req_id}_approval.pdf"
        permit_p = BASE / "output" / "pdf" / f"{req_id}_permit.pdf"
        packet_p = BASE / "output" / "packet" / f"{req_id}_PACKET_LIGHT.pdf"

        save_bytes(approval_p, approval_b)
        save_bytes(permit_p, permit_b)
        save_bytes(packet_p, packet_b)

        outputs = {"approval_pdf": str(approval_p), "permit_pdf": str(permit_p), "packet_light": str(packet_p)}
        db_update_request(req_id, {"outputs_json": json.dumps(outputs, ensure_ascii=False)})

        st.success("승인 완료! PACKET_LIGHT 생성됨(단톡 업로드 권장)")
        st.code(f"PACKET_LIGHT(로컬): {packet_p}")
        if SHARE_UNC:
            st.code(f"PACKET_LIGHT(UNC): {get_unc_path(str(packet_p))}")

        st.download_button("PACKET_LIGHT 다운로드", data=packet_b, file_name=packet_p.name, mime="application/pdf")

        msg = (
            f"[자재 {('반입' if req2['io_type']=='IN' else '반출')} 승인]\n"
            f"- REQ: {req_id}\n"
            f"- 협력사: {req2['partner_company']}\n"
            f"- 자재: {req2['material_type']}\n"
            f"- 차량: {req2['vehicle_no']} / {req2['driver_phone']}\n"
            f"- GATE: {req2['gate']}\n"
            f"- 일시: {req2['work_date']} {req2['work_time']}\n"
            f"- 결재: {req2['approved_by']} ({req2['approved_at']})\n"
            f"※ PACKET_LIGHT(PDF) 업로드"
        )
        if SHARE_UNC:
            msg += f"\n- 파일(UNC): {get_unc_path(str(packet_p))}"
        st.text_area("📌 단톡 공유 문구(복사)", value=msg, height=180)

    if colB.button("반려(REJECTED)"):
        db_update_request(req_id, {"status": "REJECTED"})
        db_log(req_id, "REJECT", st.session_state["user_name"], st.session_state["user_role"], "반려 처리")
        st.warning("반려 처리했습니다.")
        st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

def page_gate():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='h2'>5) 게이트 확인</div>", unsafe_allow_html=True)
    st.caption("REQ ID로 승인/실행 상태를 확인합니다. (경비용)")

    req_id = st.text_input("REQ ID", placeholder="예) REQ_20260211_123456_IN")
    if st.button("조회", type="primary"):
        row = db_get_request(req_id.strip())
        if not row:
            st.error("해당 REQ ID가 없습니다.")
        else:
            st.success(f"상태: {row['status']}")
            st.write(f"- 협력사: {row['partner_company']} / 자재: {row['material_type']}")
            st.write(f"- 차량: {row['vehicle_no']} / {row['driver_phone']}")
            st.write(f"- GATE: {row['gate']} / 일시: {row['work_date']} {row['work_time']}")
            if row["status"] not in ("APPROVED", "EXECUTED"):
                st.warning("승인(또는 실행) 상태가 아닙니다. 게이트 통과 전 승인 필요.")
            try:
                out = json.loads(row["outputs_json"] or "{}")
            except Exception:
                out = {}
            packet = out.get("packet_light") or out.get("packet_full")
            if packet and Path(packet).exists():
                st.code(f"PACKET: {packet}")
                if SHARE_UNC:
                    st.code(f"PACKET(UNC): {get_unc_path(packet)}")
                st.download_button("PACKET 다운로드", data=Path(packet).read_bytes(), file_name=Path(packet).name, mime="application/pdf")

    st.markdown("</div>", unsafe_allow_html=True)

def page_execute():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='h2'>6) 실행 등록 (사진 + 점검카드)</div>", unsafe_allow_html=True)
    st.caption("APPROVED 선택 → 점검 → 필수사진 3종 + (옵션추가사진) 업로드 → EXECUTED + PACKET_FULL 생성")

    approved = db_list_requests(status="APPROVED", limit=300)
    executed = db_list_requests(status="EXECUTED", limit=80)

    choices = []
    for r in approved:
        choices.append(f"{r['req_id']} | {r['partner_company']} | {r['material_type']} | {r['work_date']} {r['work_time']} | {r['gate']} | APPROVED")
    for r in executed:
        choices.append(f"{r['req_id']} | {r['partner_company']} | {r['material_type']} | {r['work_date']} {r['work_time']} | {r['gate']} | EXECUTED")

    if not choices:
        st.info("실행 대상(APPROVED/EXECUTED)이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    sel = st.selectbox("대상 선택", choices)
    req_id = sel.split(" | ")[0]
    req = db_get_request(req_id)

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)
    st.write(f"**REQ:** {req_id} | 상태: **{req['status']}**")
    st.write(f"- 협력사: {req['partner_company']} / 자재: {req['material_type']}")
    st.write(f"- 차량: {req['vehicle_no']} / {req['driver_phone']}")
    st.write(f"- GATE: {req['gate']} / 일시: {req['work_date']} {req['work_time']}")
    st.write(f"- 위험도: {req['risk_level']}")

    allowed_photo = can_upload_photos()
    if not allowed_photo:
        st.warning("현재 역할은 사진 업로드 권한이 없습니다. (관리자 설정에서 역할 허용 필요)")

    st.markdown("### ✅ 점검카드")
    attendees = st.multiselect(
        "0. 필수 참석자",
        ["협력회사 담당자", "장비운전원", "차량운전원", "유도원", "안전보조원/감시단"],
        default=["협력회사 담당자", "차량운전원", "유도원"]
    )

    col1, col2 = st.columns([1, 1])
    with col1:
        check_3 = st.selectbox("3. 화물 당 2개소 이상 결속 여부", ["양호", "미흡", "해당없음"])
        check_4 = st.selectbox("4. 고정용 로프 및 밴딩 상태 점검", ["양호", "미흡", "해당없음"])
        check_5 = st.selectbox("5. 화물 높이 4M 이하/낙하위험", ["양호", "미흡", "해당없음"])
        check_6 = st.selectbox("6. 폭 초과 상차 금지/적재함 닫힘", ["양호", "미흡", "해당없음"])
    with col2:
        check_7 = st.selectbox("7. 자재차량 고임목 설치", ["양호", "미흡", "해당없음"])
        check_8 = st.selectbox("8. 적재하중 이내 적재", ["양호", "미흡", "해당없음"])
        check_9 = st.selectbox("9. 무게중심(쏠림 여부)", ["양호", "미흡", "해당없음"])
        check_10 = st.selectbox("10. 하역구간 구획/통제", ["양호", "미흡", "해당없음"])

    st.markdown("### 📷 실행 사진")
    st.caption("필수 3종(상차 전/후, 결속 근접)은 반드시 업로드해야 실행완료 등록이 됩니다. 추가 사진은 선택입니다.")

    labels_required = ["상차 전", "상차 후", "결속/밴딩 근접"]
    uploaded_required = []
    for i, lab in enumerate(labels_required):
        f = st.file_uploader(
            f"[필수 {i+1}] {lab}",
            type=["jpg", "jpeg", "png"],
            key=f"photo_req_{req_id}_{i}",
            disabled=not allowed_photo
        )
        uploaded_required.append(f)

    st.markdown("#### ➕ 추가 사진(옵션)")
    extra_files = st.file_uploader(
        "추가 사진을 여러 장 선택 업로드하세요(선택)",
        type=["jpg", "jpeg", "png"],
        accept_multiple_files=True,
        key=f"photo_extra_{req_id}",
        disabled=not allowed_photo
    )

    colA, colB = st.columns([1, 1])

    if colA.button("실행 저장 + PACKET_FULL 생성", type="primary"):
        if req["status"] not in ("APPROVED", "EXECUTED"):
            st.error("승인(APPROVED) 상태에서만 실행 등록이 가능합니다.")
            st.stop()

        if not allowed_photo:
            st.error("사진 업로드 권한이 없어 실행 완료 처리할 수 없습니다.")
            st.stop()

        if any(u is None for u in uploaded_required):
            st.error("필수 사진 3종(상차 전/후, 결속 근접)을 모두 업로드해주세요.")
            st.stop()

        ensure_dirs()
        photo_dir = BASE / "output" / "photos" / req_id
        photo_dir.mkdir(parents=True, exist_ok=True)

        photo_records = []

        for i, u in enumerate(uploaded_required):
            raw = u.read()
            jpg = bytes_to_jpg_bytes(raw)
            p = photo_dir / f"{req_id}_photo_REQ_{i+1}.jpg"
            save_bytes(p, jpg)
            photo_records.append({"label": labels_required[i], "path": str(p), "required": True})

        if extra_files:
            for j, uf in enumerate(extra_files, 1):
                raw = uf.read()
                jpg = bytes_to_jpg_bytes(raw)
                p = photo_dir / f"{req_id}_photo_OPT_{j}.jpg"
                save_bytes(p, jpg)
                photo_records.append({"label": f"추가사진 {j}", "path": str(p), "required": False})

        checklist = {
            "attendees": ", ".join(attendees),
            "partner_company": req["partner_company"],
            "cargo_type": req["material_type"],
            "check_3": check_3,
            "check_4": check_4,
            "check_5": check_5,
            "check_6": check_6,
            "check_7": check_7,
            "check_8": check_8,
            "check_9": check_9,
            "check_10": check_10,
        }

        db_update_request(req_id, {
            "status": "EXECUTED",
            "exec_by": st.session_state["user_name"],
            "exec_at": now_ts(),
            "photo_dir": str(photo_dir),
            "checklist_json": json.dumps(checklist, ensure_ascii=False),
            "photos_json": json.dumps(photo_records, ensure_ascii=False),
        })
        db_log(req_id, "EXECUTE", st.session_state["user_name"], st.session_state["user_role"], "실행 등록")

        req2 = db_get_request(req_id)
        sic_url = normalize_url(req2["sic_url"] or st.session_state.get("sic_url", DEFAULT_SIC_URL)) or normalize_url(DEFAULT_SIC_URL)

        try:
            out0 = json.loads(req2["outputs_json"] or "{}")
        except Exception:
            out0 = {}

        check_b = pdf_checkcard(req2, checklist)
        exec_b = pdf_exec_photos(req2, photo_records)
        packet_b = pdf_packet_full(req2, sic_url, checklist, photo_records)

        check_p = BASE / "output" / "check" / f"{req_id}_checkcard.pdf"
        exec_p = BASE / "output" / "pdf" / f"{req_id}_exec_photos.pdf"
        packet_p = BASE / "output" / "packet" / f"{req_id}_PACKET_FULL.pdf"

        save_bytes(check_p, check_b)
        save_bytes(exec_p, exec_b)
        save_bytes(packet_p, packet_b)

        out0.update({
            "checkcard_pdf": str(check_p),
            "exec_photos_pdf": str(exec_p),
            "packet_full": str(packet_p),
        })
        db_update_request(req_id, {"outputs_json": json.dumps(out0, ensure_ascii=False)})

        files = []
        for k in ("approval_pdf", "permit_pdf", "packet_light", "checkcard_pdf", "exec_photos_pdf", "packet_full"):
            p = out0.get(k)
            if p and Path(p).exists():
                files.append(Path(p))
        zip_p = BASE / "output" / "zip" / f"{req_id}_sharepack.zip"
        make_zip(zip_p, files)
        out0["zip_pack"] = str(zip_p)
        db_update_request(req_id, {"outputs_json": json.dumps(out0, ensure_ascii=False)})

        st.success("실행 완료! PACKET_FULL 생성됨(단톡 업로드 권장)")
        st.code(f"PACKET_FULL(로컬): {packet_p}")
        if SHARE_UNC:
            st.code(f"PACKET_FULL(UNC): {get_unc_path(str(packet_p))}")

        st.download_button("PACKET_FULL 다운로드", data=packet_b, file_name=packet_p.name, mime="application/pdf")

        msg = (
            f"[자재 {('반입' if req2['io_type']=='IN' else '반출')} 실행완료]\n"
            f"- REQ: {req_id}\n"
            f"- 협력사: {req2['partner_company']}\n"
            f"- 자재: {req2['material_type']}\n"
            f"- 차량: {req2['vehicle_no']} / {req2['driver_phone']}\n"
            f"- GATE: {req2['gate']}\n"
            f"- 일시: {req2['work_date']} {req2['work_time']}\n"
            f"- 결재: {req2['approved_by']} ({req2['approved_at']})\n"
            f"- 실행: {req2['exec_by']} ({req2['exec_at']})\n"
            f"※ PACKET_FULL(PDF) 업로드"
        )
        if SHARE_UNC:
            msg += f"\n- 파일(UNC): {get_unc_path(str(packet_p))}"

        st.text_area("📌 단톡 공유 문구(복사)", value=msg, height=200)

    if colB.button("산출물 경로 보기"):
        req2 = db_get_request(req_id)
        try:
            out = json.loads(req2["outputs_json"] or "{}")
        except Exception:
            out = {}
        st.json(out)

    st.markdown("</div>", unsafe_allow_html=True)

def page_registry():
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.markdown("<div class='h2'>7) 대장</div>", unsafe_allow_html=True)

    col1, col2 = st.columns([1, 1])
    with col1:
        date_filter = st.date_input("일자", value=date.today()).strftime("%Y-%m-%d")
    with col2:
        status_filter = st.selectbox("상태", ["(전체)", "PENDING", "APPROVED", "EXECUTED", "REJECTED"])

    rows = db_list_requests(status=None if status_filter == "(전체)" else status_filter, date_filter=date_filter, limit=300)
    if not rows:
        st.info("해당 조건의 데이터가 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return

    ids = [r["req_id"] for r in rows]
    sel = st.selectbox("REQ 선택", ids)
    req = db_get_request(sel)

    st.markdown("<div class='hr'></div>", unsafe_allow_html=True)
    st.write(f"**{req['req_id']}** | 상태: **{req['status']}**")
    st.write(f"- 협력사: {req['partner_company']} / 자재: {req['material_type']}")
    st.write(f"- 차량: {req['vehicle_no']} / {req['driver_phone']} / GATE: {req['gate']}")
    st.write(f"- 일시: {req['work_date']} {req['work_time']} / 위험도: {req['risk_level']}")
    st.write(f"- 기안: {req['requester_name']}({req['requester_role']}) @ {req['created_at']}")
    st.write(f"- 결재: {req['approved_by'] or '-'} @ {req['approved_at'] or '-'}")
    st.write(f"- 실행: {req['exec_by'] or '-'} @ {req['exec_at'] or '-'}")

    try:
        out = json.loads(req["outputs_json"] or "{}")
    except Exception:
        out = {}

    st.markdown("### 📄 산출물")
    for label, key in [
        ("PACKET_LIGHT", "packet_light"),
        ("PACKET_FULL", "packet_full"),
        ("승인서", "approval_pdf"),
        ("허가증(QR)", "permit_pdf"),
        ("점검카드", "checkcard_pdf"),
        ("실행사진", "exec_photos_pdf"),
        ("ZIP", "zip_pack"),
    ]:
        p = out.get(key)
        if p and Path(p).exists():
            colA, colB = st.columns([2, 1])
            colA.code(f"{label}: {p}")
            if SHARE_UNC:
                colA.caption(f"UNC: {get_unc_path(p)}")
            data = Path(p).read_bytes()
            mime = "application/pdf" if p.lower().endswith(".pdf") else "application/zip"
            colB.download_button("다운로드", data=data, file_name=Path(p).name, mime=mime, key=f"dl_{key}_{sel}")

    st.markdown("### 🧾 로그")
    logs = db_get_logs(sel, limit=50)
    for lg in logs:
        st.write(f"- [{lg['created_at']}] {lg['action']} / {lg['actor']}({lg['actor_role']}) — {lg['detail'] or ''}")

    st.markdown("</div>", unsafe_allow_html=True)


# =========================
# 7) APP MAIN
# =========================
def main():
    st.set_page_config(page_title=APP_TITLE, layout="wide")
    inject_css()
    db_init()

    require_login()
    header_area()
    sidebar_area()

    st.session_state.setdefault("page", "홈")

    pages = ["홈", "신청", "승인", "게이트", "실행", "대장"]
    selected = st.radio("메뉴", pages, horizontal=True, index=pages.index(st.session_state["page"]) if st.session_state["page"] in pages else 0)
    st.session_state["page"] = selected

    if selected == "홈":
        page_home()
    elif selected == "신청":
        page_apply()
    elif selected == "승인":
        page_approve()
    elif selected == "게이트":
        page_gate()
    elif selected == "실행":
        page_execute()
    elif selected == "대장":
        page_registry()

if __name__ == "__main__":
    main()
