# ============================================================
# Material Gate Tool — v2.5.1 (Single-file, Overwrite Edition)
# - Mobile/Web friendly UI (no fragile sidebar dependency)
# - Role/Pin auth: Site PIN + optional Admin PIN (toggle)
# - SQLite (auto-migrate incl. "requests.id" missing)
# - Workflow: Request -> Approve(Sign) -> Execute(3 photos required + optional) -> Outputs
# - Outputs:
#   1) 반입/반출 계획서 PDF
#   2) 실행사진 첨부 PDF(필수 3종 + 옵션)
#   3) 자재 상/하차 점검카드 PDF
#   4) 차량 진출입 허가증 PDF (QR 포함: 방문자교육 URL)
#   5) 전체 묶음 PDF(원클릭 보기용) + ZIP
# - Kakao group chat support: "복사할 문구" + 링크(서버호스팅시)
# ============================================================

import os
import io
import re
import json
import time
import uuid
import base64
import hashlib
import zipfile
import sqlite3
from datetime import datetime
from typing import Dict, Any, List, Optional, Tuple

import streamlit as st
from PIL import Image

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib.utils import ImageReader

try:
    import qrcode
except Exception:
    qrcode = None


# ----------------------------
# App Config
# ----------------------------
APP_NAME = "자재 반출입 승인 · 실행 · 산출물(통합)"
APP_VERSION = "2.5.1"
DEFAULT_SITE_PIN = "1234"
DEFAULT_ADMIN_PIN = "9999"

# base dir: set to shared folder if you want (ex: D:\MaterialToolShared)
BASE_DIR = os.environ.get("MATERIAL_TOOL_BASE", os.path.join(os.getcwd(), "MaterialToolShared"))

DATA_DIR = os.path.join(BASE_DIR, "data")
OUT_DIR = os.path.join(BASE_DIR, "output")
OUT_PDF = os.path.join(OUT_DIR, "pdf")
OUT_ZIP = os.path.join(OUT_DIR, "zip")
OUT_PHOTOS = os.path.join(OUT_DIR, "photos")
OUT_SIGN = os.path.join(OUT_DIR, "sign")

DB_PATH = os.path.join(DATA_DIR, "gate.db")

# when server is accessible, this base URL helps generate clickable links for Kakao message
PUBLIC_BASE_URL = os.environ.get("MATERIAL_TOOL_PUBLIC_URL", "").rstrip("/")  # e.g. http://59.11.xx.xx:8501


# ----------------------------
# Utils
# ----------------------------
def now_str():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def dt_compact():
    return datetime.now().strftime("%Y%m%d_%H%M%S")

def ensure_dirs():
    for d in [BASE_DIR, DATA_DIR, OUT_DIR, OUT_PDF, OUT_ZIP, OUT_PHOTOS, OUT_SIGN]:
        os.makedirs(d, exist_ok=True)

def sha256(s: str) -> str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def safe_filename(s: str) -> str:
    s = re.sub(r"[^\w\-가-힣\.]+", "_", s.strip())
    return s[:120] if len(s) > 120 else s

def b64_of_bytes(b: bytes) -> str:
    return base64.b64encode(b).decode("utf-8")

def parse_int(x, default=0):
    try:
        return int(str(x).strip())
    except Exception:
        return default

def parse_float(x, default=0.0):
    try:
        return float(str(x).strip())
    except Exception:
        return default

def today_yyyy_mm_dd():
    return datetime.now().strftime("%Y-%m-%d")

def default_time_from():
    return "06:00"

def default_time_to():
    return "07:00"


# ----------------------------
# DB Layer (with migration)
# ----------------------------
def db_connect():
    con = sqlite3.connect(DB_PATH, check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def _table_exists(cur, name: str) -> bool:
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,))
    return cur.fetchone() is not None

def _table_columns(cur, table: str) -> List[str]:
    cur.execute(f"PRAGMA table_info({table})")
    return [r[1] for r in cur.fetchall()]  # name

def db_init_and_migrate():
    ensure_dirs()
    con = db_connect()
    cur = con.cursor()

    # --- core tables ---
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS users (
        id TEXT PRIMARY KEY,
        name TEXT NOT NULL,
        role TEXT NOT NULL,
        can_upload INTEGER NOT NULL DEFAULT 1,
        created_at TEXT NOT NULL
    );
    """)

    # 최신 스키마: requests.id TEXT PK
    cur.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,

        site_name TEXT NOT NULL,
        kind TEXT NOT NULL, -- IN / OUT
        company_name TEXT NOT NULL,

        item_name TEXT NOT NULL,
        item_type TEXT NOT NULL,
        work_type TEXT NOT NULL,

        leader TEXT NOT NULL,
        date TEXT NOT NULL,
        time_from TEXT NOT NULL,
        time_to TEXT NOT NULL,
        gate TEXT NOT NULL,

        vehicle_spec TEXT NOT NULL,
        vehicle_count INTEGER NOT NULL,

        pkg_json TEXT NOT NULL,      -- list of packages
        unload_place TEXT NOT NULL,
        unload_method TEXT NOT NULL,
        stack_place TEXT NOT NULL,
        stack_method TEXT NOT NULL,
        stack_height TEXT NOT NULL,

        safety_json TEXT NOT NULL,   -- dict of safety measures

        status TEXT NOT NULL,        -- REQUESTED/APPROVED/REJECTED/EXECUTED

        requester_name TEXT NOT NULL,
        requester_role TEXT NOT NULL,

        approver_name TEXT,
        approver_role TEXT,
        approved_at TEXT,

        reject_reason TEXT,

        executed_at TEXT
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS photos (
        id TEXT PRIMARY KEY,
        req_id TEXT NOT NULL,
        kind TEXT NOT NULL, -- BEFORE/AFTER/AREA/OPTIONAL
        caption TEXT,
        file_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(req_id) REFERENCES requests(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS checkcards (
        req_id TEXT PRIMARY KEY,
        attendees_json TEXT NOT NULL, -- list
        checks_json TEXT NOT NULL,    -- dict
        created_at TEXT NOT NULL,
        FOREIGN KEY(req_id) REFERENCES requests(id)
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS signatures (
        req_id TEXT PRIMARY KEY,
        signer_name TEXT NOT NULL,
        signer_role TEXT NOT NULL,
        sign_png_path TEXT NOT NULL,
        created_at TEXT NOT NULL,
        FOREIGN KEY(req_id) REFERENCES requests(id)
    );
    """)

    # --------- Migration: old requests table without 'id' ----------
    # If requests exists but missing id column, rebuild and copy best-effort.
    if _table_exists(cur, "requests"):
        cols = _table_columns(cur, "requests")
        if "id" not in cols:
            backup_name = f"requests_backup_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            cur.execute(f"ALTER TABLE requests RENAME TO {backup_name}")
            con.commit()

            # recreate latest table already executed above (IF NOT EXISTS) won't run because renamed.
            cur.execute("""
            CREATE TABLE IF NOT EXISTS requests (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,

                site_name TEXT NOT NULL,
                kind TEXT NOT NULL,
                company_name TEXT NOT NULL,

                item_name TEXT NOT NULL,
                item_type TEXT NOT NULL,
                work_type TEXT NOT NULL,

                leader TEXT NOT NULL,
                date TEXT NOT NULL,
                time_from TEXT NOT NULL,
                time_to TEXT NOT NULL,
                gate TEXT NOT NULL,

                vehicle_spec TEXT NOT NULL,
                vehicle_count INTEGER NOT NULL,

                pkg_json TEXT NOT NULL,
                unload_place TEXT NOT NULL,
                unload_method TEXT NOT NULL,
                stack_place TEXT NOT NULL,
                stack_method TEXT NOT NULL,
                stack_height TEXT NOT NULL,

                safety_json TEXT NOT NULL,

                status TEXT NOT NULL,

                requester_name TEXT NOT NULL,
                requester_role TEXT NOT NULL,

                approver_name TEXT,
                approver_role TEXT,
                approved_at TEXT,

                reject_reason TEXT,

                executed_at TEXT
            );
            """)
            con.commit()

            # copy common columns
            old_cols = _table_columns(cur, backup_name)
            new_cols = _table_columns(cur, "requests")
            common = [c for c in old_cols if c in new_cols]
            if common:
                col_list = ",".join(common)
                cur.execute(f"SELECT rowid, {col_list} FROM {backup_name}")
                rows = cur.fetchall()
                for r in rows:
                    rowid = r[0]
                    values = list(r[1:])
                    new_id = f"migr-{rowid}-{uuid.uuid4().hex[:8]}"
                    cols_insert = ["id"] + common
                    vals_insert = [new_id] + values
                    cur.execute(
                        f"INSERT INTO requests ({','.join(cols_insert)}) VALUES ({','.join(['?']*len(vals_insert))})",
                        vals_insert
                    )
            con.commit()

    # --- default settings ---
    def set_default(key, val):
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        if cur.fetchone() is None:
            cur.execute("INSERT INTO settings(key,value) VALUES(?,?)", (key, val))

    set_default("site_pin_hash", sha256(DEFAULT_SITE_PIN))
    set_default("admin_pin_hash", sha256(DEFAULT_ADMIN_PIN))
    set_default("site_name_default", "현장명(수정)")
    set_default("sic_training_url_default", "https://example.com/visitor-training")  # replace in admin
    set_default("public_base_url", PUBLIC_BASE_URL)

    con.commit()
    return con


# ----------------------------
# Data Access
# ----------------------------
def settings_get(con, key, default=""):
    cur = con.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    r = cur.fetchone()
    return r["value"] if r else default

def settings_set(con, key, value):
    cur = con.cursor()
    cur.execute("INSERT INTO settings(key,value) VALUES(?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",
                (key, value))
    con.commit()

def req_insert(con, data: Dict[str, Any]) -> str:
    rid = uuid.uuid4().hex
    cur = con.cursor()
    cur.execute("""
        INSERT INTO requests(
            id, created_at, site_name, kind, company_name,
            item_name, item_type, work_type,
            leader, date, time_from, time_to, gate,
            vehicle_spec, vehicle_count, pkg_json,
            unload_place, unload_method, stack_place, stack_method, stack_height,
            safety_json, status, requester_name, requester_role
        ) VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
    """, (
        rid, now_str(), data["site_name"], data["kind"], data["company_name"],
        data["item_name"], data["item_type"], data["work_type"],
        data["leader"], data["date"], data["time_from"], data["time_to"], data["gate"],
        data["vehicle_spec"], int(data["vehicle_count"]), json.dumps(data["pkg_list"], ensure_ascii=False),
        data["unload_place"], data["unload_method"], data["stack_place"], data["stack_method"], data["stack_height"],
        json.dumps(data["safety"], ensure_ascii=False),
        "REQUESTED", data["requester_name"], data["requester_role"]
    ))
    con.commit()
    return rid

def req_list(con, status: Optional[str]=None, limit=200):
    cur = con.cursor()
    if status:
        cur.execute("SELECT * FROM requests WHERE status=? ORDER BY created_at DESC LIMIT ?", (status, limit))
    else:
        cur.execute("SELECT * FROM requests ORDER BY created_at DESC LIMIT ?", (limit,))
    return [dict(r) for r in cur.fetchall()]

def req_get(con, rid: str) -> Optional[Dict[str, Any]]:
    cur = con.cursor()
    cur.execute("SELECT * FROM requests WHERE id=?", (rid,))
    r = cur.fetchone()
    return dict(r) if r else None

def req_update_status(con, rid: str, status: str, **kwargs):
    cur = con.cursor()
    fields = ["status=?"]
    vals = [status]
    for k,v in kwargs.items():
        fields.append(f"{k}=?")
        vals.append(v)
    vals.append(rid)
    cur.execute(f"UPDATE requests SET {', '.join(fields)} WHERE id=?", vals)
    con.commit()

def photo_add(con, rid: str, kind: str, caption: str, file_path: str):
    cur = con.cursor()
    pid = uuid.uuid4().hex
    cur.execute("INSERT INTO photos(id, req_id, kind, caption, file_path, created_at) VALUES(?,?,?,?,?,?)",
                (pid, rid, kind, caption, file_path, now_str()))
    con.commit()

def photo_list(con, rid: str):
    cur = con.cursor()
    cur.execute("SELECT * FROM photos WHERE req_id=? ORDER BY created_at ASC", (rid,))
    return [dict(r) for r in cur.fetchall()]

def checkcard_upsert(con, rid: str, attendees: List[str], checks: Dict[str, Any]):
    cur = con.cursor()
    cur.execute("""
        INSERT INTO checkcards(req_id, attendees_json, checks_json, created_at)
        VALUES(?,?,?,?)
        ON CONFLICT(req_id) DO UPDATE SET
            attendees_json=excluded.attendees_json,
            checks_json=excluded.checks_json,
            created_at=excluded.created_at
    """, (rid, json.dumps(attendees, ensure_ascii=False), json.dumps(checks, ensure_ascii=False), now_str()))
    con.commit()

def checkcard_get(con, rid: str):
    cur = con.cursor()
    cur.execute("SELECT * FROM checkcards WHERE req_id=?", (rid,))
    r = cur.fetchone()
    return dict(r) if r else None

def sign_upsert(con, rid: str, signer_name: str, signer_role: str, png_path: str):
    cur = con.cursor()
    cur.execute("""
        INSERT INTO signatures(req_id, signer_name, signer_role, sign_png_path, created_at)
        VALUES(?,?,?,?,?)
        ON CONFLICT(req_id) DO UPDATE SET
            signer_name=excluded.signer_name,
            signer_role=excluded.signer_role,
            sign_png_path=excluded.sign_png_path,
            created_at=excluded.created_at
    """, (rid, signer_name, signer_role, png_path, now_str()))
    con.commit()

def sign_get(con, rid: str):
    cur = con.cursor()
    cur.execute("SELECT * FROM signatures WHERE req_id=?", (rid,))
    r = cur.fetchone()
    return dict(r) if r else None


# ----------------------------
# PDF Generation
# ----------------------------
def _draw_title(c, title: str):
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20*mm, 285*mm, title)
    c.setFont("Helvetica", 9)
    c.drawRightString(200*mm, 285*mm, f"{APP_NAME} v{APP_VERSION} · {now_str()}")

def _draw_box(c, x, y, w, h, label=None):
    c.rect(x, y, w, h, stroke=1, fill=0)
    if label:
        c.setFont("Helvetica-Bold", 9)
        c.drawString(x+3, y+h-12, label)

def _qr_image(training_url: str, size_px=260):
    if not qrcode:
        return None
    qr = qrcode.QRCode(version=2, box_size=6, border=2)
    qr.add_data(training_url)
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")
    img = img.resize((size_px, size_px))
    return img

def pdf_plan(con, req: Dict[str, Any]) -> str:
    rid = req["id"]
    kind = req["kind"]
    fn = f"{dt_compact()}_{safe_filename(req['site_name'])}_{kind}_{safe_filename(req['company_name'])}_{rid[:6]}_계획서.pdf"
    path = os.path.join(OUT_PDF, fn)

    pkg_list = json.loads(req["pkg_json"])
    safety = json.loads(req["safety_json"])
    sign = sign_get(con, rid)

    c = canvas.Canvas(path, pagesize=A4)
    _draw_title(c, f"자재 반출입 계획서 ({'반입' if kind=='IN' else '반출'})")

    # Header grid
    x0, y0 = 20*mm, 245*mm
    w = 170*mm
    h = 35*mm
    _draw_box(c, x0, y0, w, h)

    c.setFont("Helvetica-Bold", 10)
    c.drawString(x0+5, y0+h-15, "기본 정보")
    c.setFont("Helvetica", 9)

    lines = [
        f"현장명: {req['site_name']}",
        f"회사명(협력사): {req['company_name']}",
        f"공종/작업: {req['work_type']}",
        f"작업 지휘자: {req['leader']}",
        f"일자: {req['date']}   시간: {req['time_from']} ~ {req['time_to']}",
        f"사용 GATE: {req['gate']}",
        f"운반 차량 규격/대수: {req['vehicle_spec']} / {req['vehicle_count']}대",
        f"취급 자재/도구명: {req['item_name']}   자재 종류: {req['item_type']}",
    ]
    ty = y0+h-30
    for s in lines:
        c.drawString(x0+8, ty, s)
        ty -= 10

    # PKG table
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, 230*mm, "1. 반입/반출 자재(PKG)")
    _draw_box(c, 20*mm, 175*mm, 170*mm, 50*mm)
    c.setFont("Helvetica-Bold", 8)
    headers = ["항목명", "크기(WxDxH)", "총 무게", "PKG당 무게", "총 PKG 수", "결속 방법", "적재 높이/단"]
    colw = [28, 28, 18, 18, 18, 28, 22]
    cx = 21*mm
    cy = 220*mm
    for i,hdr in enumerate(headers):
        c.drawString(cx, cy, hdr)
        cx += colw[i]*mm

    c.setFont("Helvetica", 8)
    row_y = 210*mm
    for r in pkg_list[:5]:
        cx = 21*mm
        vals = [
            str(r.get("name","")),
            str(r.get("size","")),
            str(r.get("total_weight","")),
            str(r.get("pkg_weight","")),
            str(r.get("pkg_count","")),
            str(r.get("binding","")),
            str(r.get("stack_height","")),
        ]
        for i,v in enumerate(vals):
            c.drawString(cx, row_y, v)
            cx += colw[i]*mm
        row_y -= 10

    # Unload/Stack
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, 168*mm, "2. 하역 및 적재")
    _draw_box(c, 20*mm, 120*mm, 170*mm, 45*mm)

    c.setFont("Helvetica", 9)
    c.drawString(23*mm, 155*mm, f"하역 장소: {req['unload_place']}")
    c.drawString(23*mm, 145*mm, f"하역 방법(인원/장비): {req['unload_method']}")
    c.drawString(23*mm, 135*mm, f"적재 장소: {req['stack_place']}")
    c.drawString(23*mm, 125*mm, f"적재 방법(인원/장비): {req['stack_method']}")
    c.drawString(120*mm, 125*mm, f"적재 높이/단: {req['stack_height']}")

    # Safety measures
    c.setFont("Helvetica-Bold", 10)
    c.drawString(20*mm, 113*mm, "3. 안전 대책")
    _draw_box(c, 20*mm, 65*mm, 170*mm, 45*mm)
    c.setFont("Helvetica", 9)
    sy = 100*mm
    for k,v in safety.items():
        c.drawString(23*mm, sy, f"- {k}: {v}")
        sy -= 10
        if sy < 70*mm:
            break

    # Sign area
    _draw_box(c, 20*mm, 20*mm, 170*mm, 40*mm, "4. 결재/서명")
    c.setFont("Helvetica", 9)
    c.drawString(23*mm, 45*mm, f"요청자: {req['requester_name']} ({req['requester_role']})  /  생성: {req['created_at']}")
    if req.get("approver_name"):
        c.drawString(23*mm, 35*mm, f"승인자: {req['approver_name']} ({req['approver_role']})  /  승인: {req.get('approved_at','')}")
    else:
        c.drawString(23*mm, 35*mm, "승인자: (미승인)")

    if sign and os.path.exists(sign["sign_png_path"]):
        img = Image.open(sign["sign_png_path"]).convert("RGBA")
        c.drawImage(ImageReader(img), 140*mm, 25*mm, width=40*mm, height=20*mm, mask='auto')
        c.setFont("Helvetica", 7)
        c.drawString(140*mm, 22*mm, "전자서명(이미지)")

    c.showPage()
    c.save()
    return path

def pdf_checkcard(con, req: Dict[str, Any]) -> str:
    rid = req["id"]
    fn = f"{dt_compact()}_{safe_filename(req['site_name'])}_{req['kind']}_{rid[:6]}_상하차점검카드.pdf"
    path = os.path.join(OUT_PDF, fn)

    cc = checkcard_get(con, rid)
    attendees = []
    checks = {}
    if cc:
        attendees = json.loads(cc["attendees_json"])
        checks = json.loads(cc["checks_json"])

    c = canvas.Canvas(path, pagesize=A4)
    _draw_title(c, "자재 상/하차 점검카드")
    c.setFont("Helvetica", 10)
    c.drawString(20*mm, 265*mm, f"현장명: {req['site_name']}")
    c.drawString(20*mm, 255*mm, f"협력회사: {req['company_name']}")
    c.drawString(20*mm, 245*mm, f"화물/자재: {req['item_name']} ({req['item_type']})")
    c.drawString(20*mm, 235*mm, f"일시: {req['date']} {req['time_from']}~{req['time_to']} / GATE: {req['gate']}")

    _draw_box(c, 20*mm, 215*mm, 170*mm, 20*mm, "0. 필수 참석자")
    c.setFont("Helvetica", 9)
    att_txt = ", ".join(attendees) if attendees else "협력회사 담당자, 장비운전원, 차량운전원, 유도원, 안전보조원/감시단"
    c.drawString(23*mm, 225*mm, att_txt)

    _draw_box(c, 20*mm, 35*mm, 170*mm, 175*mm, "1~10. 점검 항목")
    c.setFont("Helvetica", 9)
    items = [
        ("1. 협력회사", req["company_name"]),
        ("2. 화물/자재 종류", f"{req['item_name']} / {req['item_type']}"),
        ("3. 화물 당 2개소 이상 결속 여부", checks.get("3", "양호")),
        ("4. 고정용 로프 및 밴딩 상태 점검 여부", checks.get("4", "")),
        ("5. 화물 높이 4M 이하 적재, 낙하위험 발생여부", checks.get("5", "")),
        ("6. 적재함 폭 초과 상차 금지, 적재함 닫힘 여부", checks.get("6", "")),
        ("7. 자재차량 고임목 설치 여부", checks.get("7", "")),
        ("8. 적재하중 이내 적재 여부", checks.get("8", "")),
        ("9. 화물 무게중심 확인(쏠림 여부)", checks.get("9", "")),
        ("10. 자재 하역구간 구획 및 통제 여부", checks.get("10", "")),
    ]
    y = 200*mm
    for k,v in items:
        c.drawString(23*mm, y, f"{k} : {v}")
        y -= 15

    c.showPage()
    c.save()
    return path

def pdf_permit(con, req: Dict[str, Any], training_url: str) -> str:
    rid = req["id"]
    fn = f"{dt_compact()}_{safe_filename(req['site_name'])}_{req['kind']}_{rid[:6]}_차량진출입허가증.pdf"
    path = os.path.join(OUT_PDF, fn)

    c = canvas.Canvas(path, pagesize=A4)
    _draw_title(c, "자재 차량 진출입 허가증(현장용)")

    _draw_box(c, 20*mm, 235*mm, 170*mm, 40*mm, "기본 정보")
    c.setFont("Helvetica", 10)
    c.drawString(23*mm, 260*mm, f"입고/출고 회사명: {req['company_name']}")
    c.drawString(23*mm, 248*mm, f"자재: {req['item_name']} ({req['item_type']})  /  공종: {req['work_type']}")
    c.drawString(23*mm, 236*mm, f"일시: {req['date']} {req['time_from']}~{req['time_to']}  /  GATE: {req['gate']}")

    _draw_box(c, 20*mm, 150*mm, 170*mm, 75*mm, "필수 준수사항")
    c.setFont("Helvetica", 10)
    rules = [
        "1. 하차 시 안전모 착용",
        "2. 운전석 유리창 개방 필수",
        "3. 현장 내 속도 10km/h 이내 주행",
        "4. 비상등 상시 점등",
        "5. 주정차 시, 고임목 설치",
        "6. 유도원 통제하에 운영",
    ]
    y = 215*mm
    for r in rules:
        c.drawString(23*mm, y, r)
        y -= 12

    _draw_box(c, 20*mm, 95*mm, 80*mm, 50*mm, "SIC 방문자교육(QR)")
    qrimg = _qr_image(training_url, size_px=220)
    if qrimg:
        c.drawImage(ImageReader(qrimg), 25*mm, 98*mm, width=45*mm, height=45*mm)
    c.setFont("Helvetica", 8)
    c.drawString(25*mm, 92*mm, "QR 인식 후 이수")

    _draw_box(c, 105*mm, 95*mm, 85*mm, 50*mm, "확인(서명)")
    sign = sign_get(con, rid)
    c.setFont("Helvetica", 10)
    c.drawString(108*mm, 130*mm, f"운전원 확인: __________________")
    c.drawString(108*mm, 112*mm, f"담당자 확인: {req.get('approver_name','(미승인)')}")

    if sign and os.path.exists(sign["sign_png_path"]):
        img = Image.open(sign["sign_png_path"]).convert("RGBA")
        c.drawImage(ImageReader(img), 150*mm, 97*mm, width=35*mm, height=20*mm, mask='auto')

    c.setFont("Helvetica", 9)
    c.drawString(20*mm, 70*mm, f"방문자교육 URL: {training_url}")

    c.showPage()
    c.save()
    return path

def pdf_execution(con, req: Dict[str, Any]) -> str:
    rid = req["id"]
    photos = photo_list(con, rid)

    fn = f"{dt_compact()}_{safe_filename(req['site_name'])}_{req['kind']}_{rid[:6]}_실행사진.pdf"
    path = os.path.join(OUT_PDF, fn)

    c = canvas.Canvas(path, pagesize=A4)
    _draw_title(c, "실행 사진 기록(필수 3종 + 옵션)")

    c.setFont("Helvetica", 10)
    c.drawString(20*mm, 265*mm, f"현장명: {req['site_name']} / 협력사: {req['company_name']} / 일시: {req['date']} {req['time_from']}~{req['time_to']}")

    # sort for display
    order = {"BEFORE":0, "AFTER":1, "AREA":2, "OPTIONAL":3}
    photos_sorted = sorted(photos, key=lambda p: (order.get(p["kind"], 9), p["created_at"]))

    y = 250*mm
    per_page = 2
    idx = 0
    for p in photos_sorted:
        if idx % per_page == 0 and idx != 0:
            c.showPage()
            _draw_title(c, "실행 사진 기록(계속)")
            y = 270*mm
        kind = p["kind"]
        caption = p.get("caption") or ""
        img_path = p["file_path"]

        c.setFont("Helvetica-Bold", 10)
        y -= 10
        c.drawString(20*mm, y, f"[{kind}] {caption}  ({p['created_at']})")
        y -= 5

        if os.path.exists(img_path):
            img = Image.open(img_path)
            img = img.convert("RGB")
            # fit
            box_w = 170*mm
            box_h = 90*mm
            x0 = 20*mm
            y0 = y - box_h
            c.rect(x0, y0, box_w, box_h, stroke=1, fill=0)
            c.drawImage(ImageReader(img), x0+2, y0+2, width=box_w-4, height=box_h-4, preserveAspectRatio=True, anchor='c')
            y = y0 - 10
        else:
            c.setFont("Helvetica", 9)
            c.drawString(25*mm, y-20, "(이미지 파일 없음)")
            y -= 30
        idx += 1

    c.showPage()
    c.save()
    return path

def pdf_bundle(all_pdf_paths: List[str], bundle_name: str) -> str:
    # 간단 번들: "표지 + 파일목록" PDF (원본 병합은 라이브러리 추가 필요)
    # 실무에선 이 '번들 PDF'만 카톡에 올리고, 원본은 ZIP/개별 링크로 제공
    fn = f"{dt_compact()}_{safe_filename(bundle_name)}_전체묶음_안내.pdf"
    path = os.path.join(OUT_PDF, fn)

    c = canvas.Canvas(path, pagesize=A4)
    _draw_title(c, "산출물 전체 묶음(원클릭 보기용 안내)")
    c.setFont("Helvetica", 11)
    c.drawString(20*mm, 265*mm, "아래 산출물들이 생성되었습니다(개별 PDF).")
    c.setFont("Helvetica", 9)
    y = 250*mm
    for p in all_pdf_paths:
        c.drawString(20*mm, y, f"- {os.path.basename(p)}")
        y -= 12
        if y < 30*mm:
            c.showPage()
            _draw_title(c, "산출물 목록(계속)")
            y = 270*mm
    c.showPage()
    c.save()
    return path

def make_zip(paths: List[str], zip_title: str) -> str:
    fn = f"{dt_compact()}_{safe_filename(zip_title)}_산출물.zip"
    zpath = os.path.join(OUT_ZIP, fn)
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as zf:
        for p in paths:
            if os.path.exists(p):
                zf.write(p, arcname=os.path.basename(p))
    return zpath


# ----------------------------
# UI Helpers (Mobile/Web)
# ----------------------------
def inject_css():
    st.markdown("""
    <style>
      .block-container { padding-top: 1.0rem; padding-bottom: 3rem; max-width: 1100px; }
      /* modern card */
      .card {
        background: #ffffff;
        border: 1px solid rgba(0,0,0,0.06);
        border-radius: 16px;
        padding: 14px 16px;
        box-shadow: 0 6px 18px rgba(0,0,0,0.04);
        margin-bottom: 12px;
      }
      .muted { color: rgba(0,0,0,0.55); font-size: 0.9rem; }
      .kpi { display:flex; gap:10px; flex-wrap:wrap; }
      .kpi .box { flex:1; min-width:140px; background:#fff; border:1px solid rgba(0,0,0,0.06); border-radius:14px; padding:10px 12px; }
      .kpi .num { font-size: 1.5rem; font-weight: 800; }
      .topbar {
        background: linear-gradient(90deg, #2F80ED, #56CCF2);
        color: white; border-radius: 16px; padding: 14px 16px;
        box-shadow: 0 10px 24px rgba(47,128,237,0.18);
        margin-bottom: 12px;
      }
      .topbar h1 { font-size: 1.1rem; margin:0; }
      .topbar .sub { opacity:0.9; font-size: 0.9rem; margin-top:4px; }
      /* nicer buttons */
      div.stButton > button {
        border-radius: 12px;
        padding: 0.65rem 0.9rem;
      }
      /* hide streamlit footer */
      footer {visibility: hidden;}
    </style>
    """, unsafe_allow_html=True)

def topbar(user: Dict[str,str], site_name: str):
    st.markdown(f"""
    <div class="topbar">
      <h1>{APP_NAME}</h1>
      <div class="sub">현장: <b>{site_name}</b> · 사용자: <b>{user.get('name','')}</b> ({user.get('role','')}) · v{APP_VERSION}</div>
    </div>
    """, unsafe_allow_html=True)

def kpi_boxes(counts: Dict[str,int]):
    st.markdown('<div class="kpi">', unsafe_allow_html=True)
    for label, num in counts.items():
        st.markdown(f"""
          <div class="box">
            <div class="muted">{label}</div>
            <div class="num">{num}건</div>
          </div>
        """, unsafe_allow_html=True)
    st.markdown('</div>', unsafe_allow_html=True)

def role_badge(role: str) -> str:
    return role


# ----------------------------
# Auth
# ----------------------------
def auth_login(con) -> Tuple[bool, Optional[Dict[str,str]], str]:
    site_pin_hash = settings_get(con, "site_pin_hash", sha256(DEFAULT_SITE_PIN))
    admin_pin_hash = settings_get(con, "admin_pin_hash", sha256(DEFAULT_ADMIN_PIN))
    default_site_name = settings_get(con, "site_name_default", "현장명(수정)")
    default_training = settings_get(con, "sic_training_url_default", "https://example.com/visitor-training")

    st.markdown(f"### 🔐 로그인(현장용)")
    st.caption("현장 PIN은 필수, 관리자 모드는 토글을 켜면 Admin PIN 입력칸이 나타납니다.")

    col1, col2 = st.columns([1,1], gap="large")
    with col1:
        site_pin = st.text_input("현장 PIN *", type="password", placeholder="예) 4자리", key="login_site_pin")
        name = st.text_input("이름/직책 *", placeholder="예) 공무팀장 홍길동", key="login_name")
        role = st.selectbox("역할 *", ["공무","안전","경비/게이트","협력사","관리자(현장)"], index=0, key="login_role")
    with col2:
        admin_mode = st.toggle("관리자 모드로 로그인(ADMIN)", value=False, key="login_admin_mode")
        admin_pin = ""
        if admin_mode:
            admin_pin = st.text_input("Admin PIN *", type="password", placeholder="관리자 PIN", key="login_admin_pin")
        st.text_input("SIC 방문자교육 URL(QR)", value=default_training, key="login_training_url")
        st.text_input("현장명", value=default_site_name, key="login_site_name")

    ok = False
    msg = ""
    user = None

    if st.button("로그인", type="primary"):
        if sha256(site_pin) != site_pin_hash:
            msg = "현장 PIN이 올바르지 않습니다."
        elif not name.strip():
            msg = "이름/직책을 입력해 주세요."
        elif admin_mode and sha256(admin_pin) != admin_pin_hash:
            msg = "Admin PIN이 올바르지 않습니다."
        else:
            ok = True
            user = {
                "name": name.strip(),
                "role": role.strip(),
                "is_admin": "1" if admin_mode else "0",
                "site_name": st.session_state.get("login_site_name", default_site_name),
                "training_url": st.session_state.get("login_training_url", default_training),
            }
            msg = "로그인 성공"

    if msg:
        (st.success if ok else st.error)(msg)

    return ok, user, default_site_name


# ----------------------------
# App Pages
# ----------------------------
def page_home(con, user):
    site_name = user["site_name"]
    topbar(user, site_name)

    all_reqs = req_list(con, None, 500)
    counts = {
        "오늘 요청": sum(1 for r in all_reqs if (r["created_at"][:10] == today_yyyy_mm_dd())),
        "승인": sum(1 for r in all_reqs if r["status"]=="APPROVED"),
        "대기": sum(1 for r in all_reqs if r["status"]=="REQUESTED"),
        "실행": sum(1 for r in all_reqs if r["status"]=="EXECUTED"),
        "반려": sum(1 for r in all_reqs if r["status"]=="REJECTED"),
    }
    kpi_boxes(counts)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("진행 카드(클릭 이동)")
    tabs = st.columns(5)
    if tabs[0].button("① 신청"):
        st.session_state.page = "신청"
    if tabs[1].button("② 승인"):
        st.session_state.page = "승인"
    if tabs[2].button("③ 실행(사진/점검)"):
        st.session_state.page = "실행"
    if tabs[3].button("④ 산출물"):
        st.session_state.page = "산출물"
    if tabs[4].button("⑤ 대장"):
        st.session_state.page = "대장"
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("산출물 생성 위치(PC 기준)")
    st.code(
        f"공유폴더(BASE): {BASE_DIR}\n"
        f"PDF: {OUT_PDF}\n"
        f"ZIP: {OUT_ZIP}\n"
        f"사진: {OUT_PHOTOS}\n"
        f"서명: {OUT_SIGN}\n"
        f"DB: {DB_PATH}\n"
    )
    st.markdown("</div>", unsafe_allow_html=True)

def page_request(con, user):
    topbar(user, user["site_name"])
    st.subheader("신청(반입/반출)")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    colA, colB = st.columns([1,1], gap="large")
    with colA:
        kind = st.selectbox("구분", ["IN","OUT"], format_func=lambda x: "반입" if x=="IN" else "반출")
        company_name = st.text_input("협력회사(회사명)", "")
        item_name = st.text_input("취급 자재/도구명", "")
        item_type = st.text_input("자재 종류", "")
        work_type = st.text_input("공종/작업", "")
        leader = st.text_input("작업 지휘자", "")
    with colB:
        date = st.date_input("일자", value=datetime.now()).strftime("%Y-%m-%d")
        time_from = st.text_input("시작 시간", value=default_time_from())
        time_to = st.text_input("종료 시간", value=default_time_to())
        gate = st.text_input("사용 GATE", value="1GATE")
        vehicle_spec = st.text_input("운반 차량 규격", value="11TON")
        vehicle_count = st.number_input("대수", min_value=1, max_value=50, value=1, step=1)

    st.markdown("#### PKG 입력(최소 1개)")
    pkg_count = st.number_input("PKG 행 수", min_value=1, max_value=8, value=1, step=1)
    pkg_list = []
    for i in range(int(pkg_count)):
        st.markdown(f"**PKG #{i+1}**")
        c1,c2,c3 = st.columns([1,1,1])
        with c1:
            pn = st.text_input(f"항목명_{i}", value="철근" if i==0 else "")
            ps = st.text_input(f"크기(WxDxH)_{i}", value="D10*500" if i==0 else "")
        with c2:
            tw = st.text_input(f"총 무게_{i}", value="8.3TON" if i==0 else "")
            pw = st.text_input(f"PKG당 무게_{i}", value="0.9TON" if i==0 else "")
        with c3:
            pc = st.text_input(f"총 PKG 수_{i}", value="10" if i==0 else "")
            bd = st.text_input(f"결속 방법_{i}", value="철근 결속" if i==0 else "")
            sh = st.text_input(f"적재 높이/단(PKG)_{i}", value="2단" if i==0 else "")
        pkg_list.append({
            "name": pn, "size": ps, "total_weight": tw, "pkg_weight": pw,
            "pkg_count": pc, "binding": bd, "stack_height": sh
        })

    st.markdown("#### 하역/적재")
    c1,c2 = st.columns([1,1])
    with c1:
        unload_place = st.text_input("하역 장소", value="1F GATE#3")
        unload_method = st.text_input("하역 방법(인원/장비)", value="지게차 하역")
    with c2:
        stack_place = st.text_input("적재 장소", value="복공판")
        stack_method = st.text_input("적재 방법(인원/장비)", value="지게차 하역 후 이동")
        stack_height = st.text_input("적재 높이/단(전체)", value="1단")

    st.markdown("#### 안전 대책(기본값 제공, 현장에 맞게 수정)")
    safety = {
        "구획/통제": st.text_input("구획/통제", value="라바콘/이미지휀스"),
        "전도": st.text_input("전도", value="자재 적재시 결속 및 균형 유지"),
        "협착": st.text_input("협착", value="신호 철저, 주변 통제"),
        "붕괴": st.text_input("붕괴", value="과다 적재 금지"),
        "추락": st.text_input("추락", value="상부 작업 시 추락방지"),
        "낙하": st.text_input("낙하", value="결속 상태 확인/낙하물 방지"),
    }

    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    if st.button("요청 등록", type="primary"):
        # minimal validation
        if not company_name.strip() or not item_name.strip() or not leader.strip():
            st.error("협력회사/자재명/작업지휘자는 필수입니다.")
        else:
            rid = req_insert(con, {
                "site_name": user["site_name"],
                "kind": kind,
                "company_name": company_name.strip(),
                "item_name": item_name.strip(),
                "item_type": item_type.strip(),
                "work_type": work_type.strip(),
                "leader": leader.strip(),
                "date": date,
                "time_from": time_from.strip(),
                "time_to": time_to.strip(),
                "gate": gate.strip(),
                "vehicle_spec": vehicle_spec.strip(),
                "vehicle_count": int(vehicle_count),
                "pkg_list": pkg_list,
                "unload_place": unload_place.strip(),
                "unload_method": unload_method.strip(),
                "stack_place": stack_place.strip(),
                "stack_method": stack_method.strip(),
                "stack_height": stack_height.strip(),
                "safety": safety,
                "requester_name": user["name"],
                "requester_role": user["role"],
            })
            st.success(f"요청 등록 완료: {rid}")
            st.session_state.page = "승인"
            st.session_state.selected_rid = rid
    st.markdown("</div>", unsafe_allow_html=True)

def _signature_pad() -> Optional[bytes]:
    # Simple signature input: accept PNG upload (phone scribble app) or draw via canvas is not native without extra components
    st.caption("서명은 **PNG 업로드 방식**으로 지원합니다(모바일: 서명앱/사진, PC: 서명 이미지). 도장 이미지는 옵션입니다.")
    up = st.file_uploader("서명 이미지(PNG 권장)", type=["png","jpg","jpeg"])
    if up:
        return up.read()
    return None

def page_approve(con, user):
    topbar(user, user["site_name"])
    st.subheader("승인(서명)")

    # list pending
    pending = req_list(con, "REQUESTED", 200)
    if not pending:
        st.info("대기(REQUESTED) 건이 없습니다.")
        return

    options = [f"{r['created_at']} | {('반입' if r['kind']=='IN' else '반출')} | {r['company_name']} | {r['item_name']} | {r['id']}" for r in pending]
    default_idx = 0
    if st.session_state.get("selected_rid"):
        for i,r in enumerate(pending):
            if r["id"] == st.session_state.selected_rid:
                default_idx = i
                break
    sel = st.selectbox("승인 대상 선택", options, index=default_idx)
    rid = sel.split("|")[-1].strip()
    st.session_state.selected_rid = rid
    req = req_get(con, rid)
    if not req:
        st.error("요청을 불러오지 못했습니다.")
        return

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write(f"**구분:** {('반입' if req['kind']=='IN' else '반출')}  /  **협력사:** {req['company_name']}  /  **자재:** {req['item_name']} ({req['item_type']})")
    st.write(f"**일시:** {req['date']} {req['time_from']}~{req['time_to']}  /  **GATE:** {req['gate']}")
    st.write(f"**요청자:** {req['requester_name']} ({req['requester_role']})")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1,col2 = st.columns([1,1], gap="large")
    with col1:
        approve_name = st.text_input("승인자(이름/직책)", value=user["name"])
        approve_role = st.text_input("승인자 역할", value=user["role"])
        sig_bytes = _signature_pad()
    with col2:
        reject_reason = st.text_area("반려 사유(반려 시 필수)", height=120)

    a1,a2 = st.columns(2)
    with a1:
        if st.button("승인(서명 저장)", type="primary"):
            if req["status"] != "REQUESTED":
                st.warning("이미 처리된 건입니다.")
            else:
                if not sig_bytes:
                    st.error("서명 이미지를 업로드해 주세요.")
                else:
                    # save sign
                    sign_fn = f"{dt_compact()}_{rid[:6]}_{safe_filename(approve_name)}_sign.png"
                    sign_path = os.path.join(OUT_SIGN, sign_fn)
                    with open(sign_path, "wb") as f:
                        f.write(sig_bytes)
                    sign_upsert(con, rid, approve_name.strip(), approve_role.strip(), sign_path)
                    req_update_status(con, rid, "APPROVED",
                                     approver_name=approve_name.strip(),
                                     approver_role=approve_role.strip(),
                                     approved_at=now_str())
                    st.success("승인 완료")
                    st.session_state.page = "실행"
    with a2:
        if st.button("반려", type="secondary"):
            if not reject_reason.strip():
                st.error("반려 사유를 입력해 주세요.")
            else:
                req_update_status(con, rid, "REJECTED", reject_reason=reject_reason.strip())
                st.success("반려 처리 완료")
    st.markdown("</div>", unsafe_allow_html=True)

def page_execute(con, user):
    topbar(user, user["site_name"])
    st.subheader("실행 등록 (사진 + 점검카드)")

    approved = req_list(con, "APPROVED", 200)
    if not approved:
        st.info("승인(APPROVED) 건이 없습니다.")
        return

    options = [f"{r['approved_at'] or r['created_at']} | {('반입' if r['kind']=='IN' else '반출')} | {r['company_name']} | {r['item_name']} | {r['id']}" for r in approved]
    default_idx = 0
    if st.session_state.get("selected_rid"):
        for i,r in enumerate(approved):
            if r["id"] == st.session_state.selected_rid:
                default_idx = i
                break
    sel = st.selectbox("실행 대상 선택", options, index=default_idx)
    rid = sel.split("|")[-1].strip()
    st.session_state.selected_rid = rid
    req = req_get(con, rid)
    if not req:
        st.error("요청을 불러오지 못했습니다.")
        return

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write(f"**{('반입' if req['kind']=='IN' else '반출')} / {req['company_name']} / {req['item_name']}**")
    st.write(f"일시: {req['date']} {req['time_from']}~{req['time_to']}  |  GATE: {req['gate']}")
    st.markdown("</div>", unsafe_allow_html=True)

    # --- checkcard ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### ✅ 상/하차 점검카드 입력")
    default_att = "협력회사 담당자,장비운전원,차량운전원,유도원,안전보조원/감시단"
    att_str = st.text_input("필수 참석자(쉼표로 구분)", value=default_att)
    attendees = [a.strip() for a in att_str.split(",") if a.strip()]

    st.markdown("#### 점검 항목(필요시 수정)")
    checks = {}
    checks["3"] = st.selectbox("3. 화물 당 2개소 이상 결속 여부", ["양호","불량"], index=0)
    checks["4"] = st.text_input("4. 고정용 로프/밴딩 상태", value="양호")
    checks["5"] = st.text_input("5. 화물 높이 4M 이하/낙하위험", value="이상 없음")
    checks["6"] = st.text_input("6. 적재함 폭 초과/닫힘 여부", value="적재함 닫힘")
    checks["7"] = st.text_input("7. 고임목 설치 여부", value="설치")
    checks["8"] = st.text_input("8. 적재하중 이내 적재", value="준수")
    checks["9"] = st.text_input("9. 무게중심 쏠림 여부", value="이상 없음")
    checks["10"] = st.text_input("10. 하역구간 구획/통제", value="구획 및 통제")

    if st.button("점검카드 저장", type="primary"):
        checkcard_upsert(con, rid, attendees, checks)
        st.success("점검카드 저장 완료")
    st.markdown("</div>", unsafe_allow_html=True)

    # --- photos ---
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📸 실행 사진 업로드")
    st.caption("필수 3종: **상차 전(BEFORE), 상차 후(AFTER), 작업구역/통제(AREA)**  /  추가 사진은 **옵션(OPTIONAL)** 으로 무제한 가능")

    # 권한(사진 업로드) — 간단: 관리자만 금지 토글 가능
    allow_upload = True
    if user.get("is_admin") == "1":
        allow_upload = st.toggle("이 건에 대해 사진 업로드 허용", value=True, help="협력사/현장 사용자가 사진을 올릴 수 있게 할지")
    if not allow_upload:
        st.warning("현재 이 건은 사진 업로드가 비활성화 상태입니다(관리자 설정).")

    col1,col2 = st.columns([1,1], gap="large")
    with col1:
        before = st.file_uploader("필수1) 상차 전(BEFORE)", type=["png","jpg","jpeg"], key="up_before", disabled=not allow_upload)
        after = st.file_uploader("필수2) 상차 후(AFTER)", type=["png","jpg","jpeg"], key="up_after", disabled=not allow_upload)
        area = st.file_uploader("필수3) 작업구역/통제(AREA)", type=["png","jpg","jpeg"], key="up_area", disabled=not allow_upload)
    with col2:
        optional_files = st.file_uploader("추가(옵션) 사진(여러 장 가능)", type=["png","jpg","jpeg"], accept_multiple_files=True, key="up_opt", disabled=not allow_upload)
        opt_caption = st.text_input("옵션 사진 공통 캡션(선택)", value="추가 사진")

    if st.button("사진 저장", type="primary", disabled=not allow_upload):
        saved = 0
        def _save_one(file, kind, caption):
            nonlocal saved
            if not file:
                return
            ext = file.name.split(".")[-1].lower()
            fn = f"{dt_compact()}_{rid[:6]}_{kind}_{uuid.uuid4().hex[:6]}.{ext}"
            pth = os.path.join(OUT_PHOTOS, fn)
            with open(pth, "wb") as f:
                f.write(file.read())
            photo_add(con, rid, kind, caption, pth)
            saved += 1

        _save_one(before, "BEFORE", "상차 전")
        _save_one(after, "AFTER", "상차 후")
        _save_one(area, "AREA", "작업구역/통제")
        if optional_files:
            for f in optional_files:
                # each is UploadedFile
                ext = f.name.split(".")[-1].lower()
                fn = f"{dt_compact()}_{rid[:6]}_OPTIONAL_{uuid.uuid4().hex[:6]}.{ext}"
                pth = os.path.join(OUT_PHOTOS, fn)
                with open(pth, "wb") as out:
                    out.write(f.read())
                photo_add(con, rid, "OPTIONAL", opt_caption.strip() or "추가 사진", pth)
                saved += 1
        st.success(f"사진 저장 완료: {saved}장")

    photos = photo_list(con, rid)
    st.markdown("#### 현재 등록된 사진")
    if photos:
        for p in photos[-12:]:
            st.write(f"- [{p['kind']}] {p.get('caption','')} · {p['created_at']}")
    else:
        st.info("아직 등록된 사진이 없습니다.")

    # gate condition: required 3 kinds must exist before execute complete
    kinds = set([p["kind"] for p in photos])
    required_ok = all(k in kinds for k in ["BEFORE","AFTER","AREA"])
    st.markdown("---")
    st.write("필수 3종 충족 여부:", "✅ 충족" if required_ok else "❌ 미충족(상차 전/후/통제 3종 필요)")

    if st.button("실행 완료 처리(산출물 생성)", type="primary", disabled=not required_ok):
        # save executed status
        req_update_status(con, rid, "EXECUTED", executed_at=now_str())
        st.success("실행 완료 처리 완료. 산출물 페이지에서 생성/다운로드 하세요.")
        st.session_state.page = "산출물"
    st.markdown("</div>", unsafe_allow_html=True)

def page_outputs(con, user):
    topbar(user, user["site_name"])
    st.subheader("산출물 생성/다운로드 · 카톡 단톡방 공유")

    executed = req_list(con, "EXECUTED", 300)
    if not executed:
        st.info("실행(EXECUTED) 건이 없습니다.")
        return

    options = [f"{r['executed_at'] or r['approved_at'] or r['created_at']} | {('반입' if r['kind']=='IN' else '반출')} | {r['company_name']} | {r['item_name']} | {r['id']}" for r in executed]
    default_idx = 0
    if st.session_state.get("selected_rid"):
        for i,r in enumerate(executed):
            if r["id"] == st.session_state.selected_rid:
                default_idx = i
                break

    sel = st.selectbox("산출 대상 선택", options, index=default_idx)
    rid = sel.split("|")[-1].strip()
    st.session_state.selected_rid = rid
    req = req_get(con, rid)
    if not req:
        st.error("요청을 불러오지 못했습니다.")
        return

    training_url = user.get("training_url") or settings_get(con, "sic_training_url_default", "https://example.com/visitor-training")
    public_url = settings_get(con, "public_base_url", PUBLIC_BASE_URL).rstrip("/")

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.write(f"**{('반입' if req['kind']=='IN' else '반출')} / {req['company_name']} / {req['item_name']}**")
    st.write(f"일시: {req['date']} {req['time_from']}~{req['time_to']}  |  GATE: {req['gate']}")
    st.caption("버튼을 누르면 PDF/ZIP이 생성되고, 아래에서 다운로드할 수 있습니다.")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    col1,col2 = st.columns([1,1], gap="large")
    with col1:
        gen_plan = st.button("① 계획서 PDF 생성", type="primary")
        gen_exec = st.button("② 실행사진 PDF 생성")
    with col2:
        gen_check = st.button("③ 상/하차 점검카드 PDF 생성")
        gen_permit = st.button("④ 차량 진출입 허가증(QR) 생성")

    gen_all = st.button("✅ 전체 산출물 일괄 생성 + ZIP + 카톡문구", type="primary")

    # store last outputs in session
    if "last_outputs" not in st.session_state:
        st.session_state.last_outputs = []

    produced = []

    if gen_plan:
        produced.append(pdf_plan(con, req))
    if gen_exec:
        produced.append(pdf_execution(con, req))
    if gen_check:
        produced.append(pdf_checkcard(con, req))
    if gen_permit:
        produced.append(pdf_permit(con, req, training_url))

    if gen_all:
        p1 = pdf_plan(con, req)
        p2 = pdf_execution(con, req)
        p3 = pdf_checkcard(con, req)
        p4 = pdf_permit(con, req, training_url)
        produced.extend([p1,p2,p3,p4])
        bundle = pdf_bundle([p1,p2,p3,p4], f"{req['site_name']}_{req['company_name']}_{rid[:6]}")
        produced.append(bundle)
        zpath = make_zip([p1,p2,p3,p4,bundle], f"{req['site_name']}_{req['company_name']}_{rid[:6]}")
        produced.append(zpath)

    if produced:
        st.session_state.last_outputs = produced
        st.success(f"생성 완료: {len(produced)}개")

    st.markdown("### 📁 최근 생성된 산출물")
    outs = st.session_state.last_outputs or []
    if not outs:
        st.info("아직 생성된 산출물이 없습니다. 위 버튼을 눌러 생성하세요.")
    else:
        for p in outs:
            if not os.path.exists(p):
                continue
            b = os.path.basename(p)
            with open(p, "rb") as f:
                data = f.read()
            st.download_button(f"다운로드: {b}", data, file_name=b)

    st.markdown("---")
    st.markdown("### 💬 카톡 단톡방 공유(1:1이 아닌 단톡용)")
    st.caption("일반 카카오 단톡은 ‘자동 업로드’가 어렵습니다(공식 API/비즈메시지/봇 필요). 대신 **단톡에 붙여넣을 문구 + 링크**를 즉시 생성합니다.")
    # If public URL exists, create pseudo links (note: streamlit doesn't serve arbitrary static files by URL by default)
    # We'll provide file path + (옵션) 서버 공유 URL 운영 가이드.
    msg_lines = []
    msg_lines.append(f"[{req['site_name']}] 자재 {'반입' if req['kind']=='IN' else '반출'} 승인/실행 산출물 공유")
    msg_lines.append(f"- 협력사: {req['company_name']}")
    msg_lines.append(f"- 자재: {req['item_name']} ({req['item_type']})")
    msg_lines.append(f"- 일시: {req['date']} {req['time_from']}~{req['time_to']} / GATE: {req['gate']}")
    msg_lines.append(f"- 실행사진(필수 3종) 포함 / 점검카드 포함 / 허가증(QR) 포함")
    msg_lines.append("")
    msg_lines.append("[산출물 위치(공유폴더)]")
    msg_lines.append(f"PDF: {OUT_PDF}")
    msg_lines.append(f"ZIP: {OUT_ZIP}")
    msg_lines.append("")
    if outs:
        msg_lines.append("[파일명]")
        for p in outs:
            if os.path.exists(p):
                msg_lines.append(f"- {os.path.basename(p)}")
    msg_lines.append("")
    msg_lines.append(f"[방문자교육 URL] {training_url}")

    st.text_area("단톡방에 붙여넣을 문구", value="\n".join(msg_lines), height=220)
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🔎 ‘ZIP은 보기 불편’ 해결")
    st.write("1) 현장에선 보통 **‘전체묶음_안내.pdf’**만 단톡에 올리고")
    st.write("2) 필요 시 개별 PDF를 추가로 올리는 방식이 가장 빠릅니다.")
    st.write("3) 진짜 ‘링크로 바로보기’를 하려면: 서버에서 `output/pdf`를 **웹서버(nginx/Apache/사내 파일서버)**로 공개해야 합니다(보안정책 준수).")
    st.markdown("</div>", unsafe_allow_html=True)

def page_registry(con, user):
    topbar(user, user["site_name"])
    st.subheader("대장(전체 조회)")

    rows = req_list(con, None, 500)
    if not rows:
        st.info("데이터가 없습니다.")
        return

    # compact table
    view = []
    for r in rows:
        view.append({
            "상태": r["status"],
            "구분": "반입" if r["kind"]=="IN" else "반출",
            "협력사": r["company_name"],
            "자재": r["item_name"],
            "일자": r["date"],
            "시간": f"{r['time_from']}~{r['time_to']}",
            "GATE": r["gate"],
            "요청자": r["requester_name"],
            "승인자": r.get("approver_name") or "",
            "ID": r["id"],
        })
    st.dataframe(view, use_container_width=True)
    st.caption("ID를 복사해서 승인/실행/산출 페이지에서 선택하면 됩니다.")

def page_admin(con, user):
    topbar(user, user["site_name"])
    st.subheader("관리자 설정(ADMIN)")

    if user.get("is_admin") != "1":
        st.warning("관리자 모드로 로그인한 사용자만 접근 가능합니다.")
        return

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### PIN / 현장 기본값 설정")
    site_pin_new = st.text_input("현장 PIN 변경(4자리 권장)", type="password")
    admin_pin_new = st.text_input("Admin PIN 변경(4자리 권장)", type="password")
    site_name_def = st.text_input("기본 현장명", value=settings_get(con, "site_name_default", "현장명(수정)"))
    sic_url_def = st.text_input("기본 방문자교육 URL", value=settings_get(con, "sic_training_url_default", "https://example.com/visitor-training"))
    pub_url = st.text_input("공개 Base URL(선택)", value=settings_get(con, "public_base_url", PUBLIC_BASE_URL))

    if st.button("설정 저장", type="primary"):
        if site_pin_new.strip():
            settings_set(con, "site_pin_hash", sha256(site_pin_new.strip()))
        if admin_pin_new.strip():
            settings_set(con, "admin_pin_hash", sha256(admin_pin_new.strip()))
        settings_set(con, "site_name_default", site_name_def.strip())
        settings_set(con, "sic_training_url_default", sic_url_def.strip())
        settings_set(con, "public_base_url", pub_url.strip())
        st.success("저장 완료")
    st.markdown("</div>", unsafe_allow_html=True)

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 운영 팁(보안환경)")
    st.write("- SQLite는 **서버/PC 로컬에 파일로 저장**됩니다. (현재 DB 위치:)")
    st.code(DB_PATH)
    st.write("- 다수 사용자가 동시에 쓰려면: **한 대 PC/서버에서 Streamlit을 띄우고** 모두 그 주소로 접속하는 구조가 안정적입니다.")
    st.write("- 외부 접속 허용 시: VPN/Reverse proxy/방화벽 정책을 반드시 따르세요.")
    st.markdown("</div>", unsafe_allow_html=True)


# ----------------------------
# Main
# ----------------------------
def main():
    st.set_page_config(page_title=APP_NAME, layout="wide")
    inject_css()

    con = db_init_and_migrate()

    # init session
    if "authed" not in st.session_state:
        st.session_state.authed = False
        st.session_state.user = None
        st.session_state.page = "홈"
        st.session_state.selected_rid = None

    if not st.session_state.authed:
        ok, user, _ = auth_login(con)
        if ok:
            st.session_state.authed = True
            st.session_state.user = user
            st.session_state.page = "홈"
        st.stop()

    user = st.session_state.user

    # Top navigation (mobile friendly, no fragile sidebar)
    nav = ["홈","신청","승인","실행","산출물","대장","관리자"]
    cols = st.columns(len(nav))
    for i, name in enumerate(nav):
        if cols[i].button(name):
            st.session_state.page = name

    page = st.session_state.page

    if page == "홈":
        page_home(con, user)
    elif page == "신청":
        page_request(con, user)
    elif page == "승인":
        page_approve(con, user)
    elif page == "실행":
        page_execute(con, user)
    elif page == "산출물":
        page_outputs(con, user)
    elif page == "대장":
        page_registry(con, user)
    elif page == "관리자":
        page_admin(con, user)
    else:
        st.session_state.page = "홈"
        page_home(con, user)

if __name__ == "__main__":
    main()