# ============================================================
# Material In/Out Approval Tool — SINGLE FILE INTEGRATED
# - AIO: DB + PDF + FileServer + Streamlit UI
# - Mobile/Web responsive, Admin PIN visible via toggle
# - Outputs: Plan PDF / Checkcard PDF / Permit PDF(QR) / ZIP bundle
# - External share: PUBLIC_BASE_URL + Flask file server token links
# ============================================================

import os, io, re, json, uuid, time, base64, hashlib, zipfile, sqlite3, threading
from datetime import datetime
from typing import Dict, Any, Optional, List

import streamlit as st

# ----- Optional/Required libs -----
from flask import Flask, abort, send_file
from werkzeug.middleware.proxy_fix import ProxyFix

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
from reportlab.lib import colors
from reportlab.platypus import Table, TableStyle

import qrcode
from PIL import Image


# =========================
# 0) SETTINGS (ENV)
# =========================
APP_NAME = "자재 반출입 승인툴"
APP_VER  = "v2.5.0-single"

# 로컬 저장 루트(서버 PC). 클라우드/로컬 호환.
BASE_DIR = os.getenv("MATERIAL_BASE", os.path.join(os.getcwd(), "MaterialToolShared"))

# 외부/모바일에서 열 수 있는 파일 링크를 만들기 위한 공개 주소
# 예) https://59.11.100.40:8801  또는  https://your.domain.com
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "https://YOUR-PUBLIC-HOST:8801").rstrip("/")

# File server (외부 PDF 링크 제공)
FILE_SERVER_HOST = os.getenv("FILE_SERVER_HOST", "0.0.0.0")
FILE_SERVER_PORT = int(os.getenv("FILE_SERVER_PORT", "8801"))

# Streamlit port(실행 시 --server.port로 설정 권장)
# STREAMLIT_PORT = int(os.getenv("STREAMLIT_PORT", "8501"))

# 기본 PIN (DB meta에 저장되며, 관리자 화면에서 변경 가능)
SITE_PIN_DEFAULT  = os.getenv("MTOOL_SITE_PIN", "1357")
ADMIN_PIN_DEFAULT = os.getenv("MTOOL_ADMIN_PIN", "8642")

# 방문자 교육 링크(허가증 QR에 인코딩)
DEFAULT_VISITOR_TRAINING_URL = os.getenv("VISITOR_TRAINING_URL", "https://example.com/visitor-training")


# =========================
# 1) PATHS / DIRS
# =========================
def p(*parts): return os.path.normpath(os.path.join(*parts))

PATHS = {
    "BASE": BASE_DIR,
    "DATA": p(BASE_DIR, "data"),
    "DB":   p(BASE_DIR, "data", "gate.db"),
    "OUT":  p(BASE_DIR, "output"),
    "PDF":  p(BASE_DIR, "output", "pdf"),
    "CHECK":p(BASE_DIR, "output", "check"),
    "PERMIT":p(BASE_DIR,"output","permit"),
    "ZIP":  p(BASE_DIR, "output", "zip"),
    "PHOTOS":p(BASE_DIR,"output","photos"),
    "TMP":  p(BASE_DIR, "tmp"),
}

def ensure_dirs():
    os.makedirs(PATHS["DATA"], exist_ok=True)
    for k in ["OUT","PDF","CHECK","PERMIT","ZIP","PHOTOS","TMP"]:
        os.makedirs(PATHS[k], exist_ok=True)

ensure_dirs()


# =========================
# 2) DB (SQLite)
# =========================
def db_connect():
    con = sqlite3.connect(PATHS["DB"], check_same_thread=False)
    con.row_factory = sqlite3.Row
    return con

def db_init():
    con = db_connect()
    cur = con.cursor()

    cur.execute("""
    CREATE TABLE IF NOT EXISTS meta (
        k TEXT PRIMARY KEY,
        v TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS requests (
        id TEXT PRIMARY KEY,
        created_at TEXT NOT NULL,
        site_name TEXT NOT NULL,
        kind TEXT NOT NULL,              -- inbound/outbound
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
        status TEXT NOT NULL,            -- REQUESTED/APPROVED/REJECTED/EXECUTING/DONE
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
        request_id TEXT NOT NULL,
        category TEXT NOT NULL,          -- required1/required2/required3/optional
        created_at TEXT NOT NULL,
        path TEXT NOT NULL,
        uploaded_by TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS checkcards (
        request_id TEXT PRIMARY KEY,
        json TEXT NOT NULL,
        updated_at TEXT NOT NULL
    );
    """)

    cur.execute("""
    CREATE TABLE IF NOT EXISTS files (
        token TEXT PRIMARY KEY,
        request_id TEXT NOT NULL,
        file_type TEXT NOT NULL,       -- plan/check/permit/zip
        path TEXT NOT NULL,
        created_at TEXT NOT NULL
    );
    """)

    con.commit()

    # seed meta
    def upsert_meta(k, v):
        cur.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
        con.commit()

    cur.execute("SELECT v FROM meta WHERE k='site_pin'")
    if cur.fetchone() is None:
        upsert_meta("site_pin", SITE_PIN_DEFAULT)

    cur.execute("SELECT v FROM meta WHERE k='admin_pin'")
    if cur.fetchone() is None:
        upsert_meta("admin_pin", ADMIN_PIN_DEFAULT)

    cur.execute("SELECT v FROM meta WHERE k='visitor_training_url'")
    if cur.fetchone() is None:
        upsert_meta("visitor_training_url", DEFAULT_VISITOR_TRAINING_URL)

    con.close()

db_init()

def meta_get(k: str) -> str:
    con = db_connect(); cur = con.cursor()
    cur.execute("SELECT v FROM meta WHERE k=?", (k,))
    row = cur.fetchone()
    con.close()
    return row["v"] if row else ""

def meta_set(k: str, v: str):
    con = db_connect(); cur = con.cursor()
    cur.execute("INSERT INTO meta(k,v) VALUES(?,?) ON CONFLICT(k) DO UPDATE SET v=excluded.v", (k, v))
    con.commit(); con.close()

def req_insert(d: Dict[str, Any]):
    con = db_connect(); cur = con.cursor()
    cols = list(d.keys())
    cur.execute(f"INSERT INTO requests ({','.join(cols)}) VALUES ({','.join(['?']*len(cols))})", [d[c] for c in cols])
    con.commit(); con.close()

def req_update(req_id: str, fields: Dict[str, Any]):
    con = db_connect(); cur = con.cursor()
    sets = ", ".join([f"{k}=?" for k in fields.keys()])
    cur.execute(f"UPDATE requests SET {sets} WHERE id=?", [*fields.values(), req_id])
    con.commit(); con.close()

def req_get(req_id: str) -> Optional[Dict[str, Any]]:
    con = db_connect(); cur = con.cursor()
    cur.execute("SELECT * FROM requests WHERE id=?", (req_id,))
    row = cur.fetchone()
    con.close()
    return dict(row) if row else None

def req_list(status: Optional[str]=None) -> List[Dict[str, Any]]:
    con = db_connect(); cur = con.cursor()
    if status:
        cur.execute("SELECT * FROM requests WHERE status=? ORDER BY created_at DESC", (status,))
    else:
        cur.execute("SELECT * FROM requests ORDER BY created_at DESC")
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows

def photo_add(req_id: str, category: str, path: str, uploaded_by: str):
    con = db_connect(); cur = con.cursor()
    cur.execute("""
      INSERT INTO photos(id,request_id,category,created_at,path,uploaded_by)
      VALUES(?,?,?,?,?,?)
    """, (str(uuid.uuid4()), req_id, category, now(), path, uploaded_by))
    con.commit(); con.close()

def photo_list(req_id: str) -> List[Dict[str, Any]]:
    con = db_connect(); cur = con.cursor()
    cur.execute("SELECT * FROM photos WHERE request_id=? ORDER BY created_at ASC", (req_id,))
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows

def checkcard_upsert(req_id: str, data: Dict[str, Any]):
    con = db_connect(); cur = con.cursor()
    cur.execute("""
      INSERT INTO checkcards(request_id,json,updated_at)
      VALUES(?,?,?)
      ON CONFLICT(request_id) DO UPDATE SET json=excluded.json, updated_at=excluded.updated_at
    """, (req_id, json.dumps(data, ensure_ascii=False), now()))
    con.commit(); con.close()

def checkcard_get(req_id: str) -> Dict[str, Any]:
    con = db_connect(); cur = con.cursor()
    cur.execute("SELECT json FROM checkcards WHERE request_id=?", (req_id,))
    row = cur.fetchone()
    con.close()
    if not row: return {}
    try: return json.loads(row["json"])
    except: return {}

def file_token_upsert(token: str, req_id: str, file_type: str, path: str):
    con = db_connect(); cur = con.cursor()
    cur.execute("""
      INSERT INTO files(token,request_id,file_type,path,created_at)
      VALUES(?,?,?,?,?)
      ON CONFLICT(token) DO UPDATE SET path=excluded.path, created_at=excluded.created_at
    """, (token, req_id, file_type, path, now()))
    con.commit(); con.close()

def file_by_token(token: str) -> Optional[Dict[str, Any]]:
    con = db_connect(); cur = con.cursor()
    cur.execute("SELECT * FROM files WHERE token=?", (token,))
    row = cur.fetchone()
    con.close()
    return dict(row) if row else None

def files_for_request(req_id: str) -> List[Dict[str, Any]]:
    con = db_connect(); cur = con.cursor()
    cur.execute("SELECT * FROM files WHERE request_id=? ORDER BY created_at DESC", (req_id,))
    rows = [dict(r) for r in cur.fetchall()]
    con.close()
    return rows


# =========================
# 3) Utilities
# =========================
def now() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def safe_filename(s: str) -> str:
    s = re.sub(r"[^\w\-\.\(\)\[\]\s가-힣]", "_", s)
    s = re.sub(r"\s+", "_", s).strip("_")
    return s[:120] if s else "file"

def make_token(req_id: str, file_type: str) -> str:
    raw = f"{req_id}:{file_type}:{time.time()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:18]

def public_file_url(token: str) -> str:
    return f"{PUBLIC_BASE_URL}/f/{token}"

def embed_pdf(path: str, height: int = 680):
    with open(path, "rb") as f:
        b64 = base64.b64encode(f.read()).decode("utf-8")
    html = f"""
    <iframe src="data:application/pdf;base64,{b64}"
            width="100%" height="{height}"
            style="border:1px solid #E5E7EB;border-radius:14px;background:white;">
    </iframe>
    """
    st.markdown(html, unsafe_allow_html=True)

def save_uploads(req_id: str, files, subdir: str) -> List[str]:
    saved = []
    base = p(PATHS["PHOTOS"], req_id, subdir)
    os.makedirs(base, exist_ok=True)
    for f in files:
        name = safe_filename(f.name)
        out = p(base, f"{int(time.time())}_{name}")
        with open(out, "wb") as wf:
            wf.write(f.getbuffer())
        saved.append(out)
    return saved


# =========================
# 4) PDF generators
# =========================
def _draw_header(c: canvas.Canvas, title: str, sub: str=""):
    c.setFillColor(colors.HexColor("#0B5FFF"))
    c.rect(0, A4[1]-22*mm, A4[0], 22*mm, stroke=0, fill=1)
    c.setFillColor(colors.white)
    c.setFont("Helvetica-Bold", 16)
    c.drawString(15*mm, A4[1]-14*mm, title)
    c.setFont("Helvetica", 10)
    if sub:
        c.drawString(15*mm, A4[1]-19*mm, sub)

def pdf_plan(req: Dict[str, Any], out_path: str):
    kind_label = "반입" if req["kind"] == "inbound" else "반출"
    c = canvas.Canvas(out_path, pagesize=A4)
    _draw_header(c, f"자재 반출입 계획서 ({kind_label})", f"요청ID: {req['id']}  /  생성: {now()}")

    basic = [
        ["회사명", req["company_name"], "공종", req["work_type"]],
        ["취급 자재/도구명", req["item_name"], "작업 지휘자", req["leader"]],
        ["일자", req["date"], "시간", f"{req['time_from']} ~ {req['time_to']}"],
        ["사용 GATE", req["gate"], "운반 차량 규격/대수", f"{req['vehicle_spec']} / {req['vehicle_count']}대"],
    ]
    t = Table(basic, colWidths=[28*mm, 62*mm, 28*mm, 62*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("BACKGROUND",(2,0),(2,-1),colors.whitesmoke),
        ("BOX",(0,0),(-1,-1),0.8,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("FONT",(0,0),(-1,-1),"Helvetica",9),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    t.wrapOn(c, 0, 0)
    t.drawOn(c, 15*mm, A4[1]-55*mm)

    pkg = json.loads(req["pkg_json"])
    pkg_rows = [["항목명", "크기(WxDxH)", "총 무게", "PKG당 무게/개수", "총 PKG 수", "결속 방법", "적재 높이/단"]]
    for r in pkg:
        pkg_rows.append([
            r.get("name",""), r.get("size",""), r.get("total_weight",""),
            r.get("pkg_weight",""), r.get("pkg_count",""), r.get("binding",""), r.get("stack","")
        ])
    tp = Table(pkg_rows, colWidths=[26*mm, 26*mm, 20*mm, 28*mm, 18*mm, 28*mm, 28*mm])
    tp.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAF2FF")),
        ("BOX",(0,0),(-1,-1),0.8,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("FONT",(0,0),(-1,-1),"Helvetica",8.5),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),4),
        ("RIGHTPADDING",(0,0),(-1,-1),4),
        ("TOPPADDING",(0,0),(-1,-1),4),
        ("BOTTOMPADDING",(0,0),(-1,-1),4),
    ]))
    tp.wrapOn(c, 0, 0)
    tp.drawOn(c, 15*mm, A4[1]-105*mm)

    mid = [
        ["하역 장소", req["unload_place"]],
        ["하역 방법(인원/장비)", req["unload_method"]],
        ["적재 장소", req["stack_place"]],
        ["적재 방법(인원/장비)", req["stack_method"]],
        ["적재 높이/단", req["stack_height"]],
    ]
    tm = Table(mid, colWidths=[40*mm, 140*mm])
    tm.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(0,-1),colors.whitesmoke),
        ("BOX",(0,0),(-1,-1),0.8,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("FONT",(0,0),(-1,-1),"Helvetica",9),
        ("VALIGN",(0,0),(-1,-1),"MIDDLE"),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    tm.wrapOn(c, 0, 0)
    tm.drawOn(c, 15*mm, A4[1]-160*mm)

    safety = json.loads(req["safety_json"])
    srows = [["구분", "내용"]]
    for k, v in safety.items():
        srows.append([k, v])
    ts = Table(srows, colWidths=[30*mm, 150*mm])
    ts.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#F1F5F9")),
        ("BOX",(0,0),(-1,-1),0.8,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("FONT",(0,0),(-1,-1),"Helvetica",9),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),5),
        ("BOTTOMPADDING",(0,0),(-1,-1),5),
    ]))
    ts.wrapOn(c, 0, 0)
    ts.drawOn(c, 15*mm, 45*mm)

    c.setStrokeColor(colors.grey)
    c.rect(15*mm, 20*mm, A4[0]-30*mm, 18*mm, stroke=1, fill=0)
    c.setFont("Helvetica", 9)
    c.drawString(17*mm, 32*mm, "결재(서명)")
    c.drawRightString(A4[0]-17*mm, 24*mm, f"상태: {req['status']}  / 승인자: {req.get('approver_name') or '-'}")
    c.showPage()
    c.save()

def pdf_checkcard(req: Dict[str, Any], check: Dict[str, Any], out_path: str):
    c = canvas.Canvas(out_path, pagesize=A4)
    _draw_header(c, "자재 상/하차 점검카드", f"요청ID: {req['id']}  /  생성: {now()}")

    c.setFont("Helvetica", 10)
    y = A4[1]-40*mm
    c.drawString(15*mm, y, "0. 필수 참석자: 협력회사 담당자, 장비운전원, 차량운전원, 유도원, 안전보조원/감시단"); y -= 8*mm
    c.drawString(15*mm, y, f"1. 협력회사: {req['company_name']}"); y -= 7*mm
    c.drawString(15*mm, y, f"2. 화물/자재 종류: {req['item_name']}"); y -= 10*mm

    items = [
        ("3. 화물 당 2개소 이상 결속 여부 확인", check.get("tie_2plus","양호")),
        ("4. 고정용 로프 및 밴딩 상태 점검 여부", check.get("rope_banding","")),
        ("5. 화물 높이 4M 이하 적재, 낙하위험 발생여부", check.get("height_under_4m","")),
        ("6. 적재함 폭 초과 상차 금지, 적재함 닫힘 여부", check.get("bed_width_close","")),
        ("7. 자재차량 고임목 설치 여부", check.get("wheel_chock","")),
        ("8. 적재하중 이내 적재 여부", check.get("within_load","")),
        ("9. 화물 무게중심 확인 (한쪽으로 쏠림 여부)", check.get("center_of_mass","")),
        ("10. 자재 하역구간 구획 및 통제 여부", check.get("zone_control","")),
    ]
    table_data = [["점검 항목", "확인/비고"]]
    for a,b in items:
        table_data.append([a,b])

    t = Table(table_data, colWidths=[120*mm, 60*mm])
    t.setStyle(TableStyle([
        ("BACKGROUND",(0,0),(-1,0),colors.HexColor("#EAF2FF")),
        ("BOX",(0,0),(-1,-1),0.8,colors.grey),
        ("INNERGRID",(0,0),(-1,-1),0.5,colors.lightgrey),
        ("FONT",(0,0),(-1,-1),"Helvetica",9),
        ("VALIGN",(0,0),(-1,-1),"TOP"),
        ("LEFTPADDING",(0,0),(-1,-1),6),
        ("RIGHTPADDING",(0,0),(-1,-1),6),
        ("TOPPADDING",(0,0),(-1,-1),6),
        ("BOTTOMPADDING",(0,0),(-1,-1),6),
    ]))
    t.wrapOn(c, 0, 0)
    t.drawOn(c, 15*mm, 45*mm)

    c.setFont("Helvetica", 9)
    c.drawString(15*mm, 30*mm, "서명(운전원/유도원/안전): _____________________________   담당자: _____________________________")
    c.showPage(); c.save()

def pdf_permit(req: Dict[str, Any], visitor_training_url: str, permit_public_url: str, out_path: str):
    c = canvas.Canvas(out_path, pagesize=A4)
    _draw_header(c, "자재 차량 진출입 허가증", f"요청ID: {req['id']}  /  생성: {now()}")

    # QR: 방문자 교육 링크(요청하신 링크)
    qr = qrcode.QRCode(version=4, error_correction=qrcode.constants.ERROR_CORRECT_M, box_size=6, border=2)
    qr.add_data(visitor_training_url.strip() or "https://example.com")
    qr.make(fit=True)
    img = qr.make_image(fill_color="black", back_color="white")

    bio = io.BytesIO()
    img.save(bio, format="PNG")
    bio.seek(0)
    from reportlab.lib.utils import ImageReader
    c.drawImage(ImageReader(bio), 15*mm, A4[1]-95*mm, width=35*mm, height=35*mm, mask='auto')

    c.setFillColor(colors.black)
    c.setFont("Helvetica-Bold", 12)
    c.drawString(55*mm, A4[1]-55*mm, f"입고 회사명: {req['company_name']}")
    c.setFont("Helvetica", 11)
    c.drawString(55*mm, A4[1]-65*mm, f"사용 GATE: {req['gate']}   /  시간: {req['time_from']}~{req['time_to']}")
    c.drawString(55*mm, A4[1]-75*mm, f"차량: {req['vehicle_spec']} ({req['vehicle_count']}대)")
    c.drawString(55*mm, A4[1]-85*mm, "필수 준수사항: 속도준수, 유도원 통제, 고임목, 결속상태 확인 등")

    c.setFont("Helvetica", 9)
    c.setFillColor(colors.HexColor("#334155"))
    c.drawString(15*mm, A4[1]-105*mm, f"방문자교육 URL(QR): {visitor_training_url}")
    c.drawString(15*mm, A4[1]-112*mm, f"허가증(웹열람): {permit_public_url}")

    c.setStrokeColor(colors.grey)
    c.rect(15*mm, 25*mm, A4[0]-30*mm, 25*mm, stroke=1, fill=0)
    c.setFont("Helvetica", 10)
    c.setFillColor(colors.black)
    c.drawString(17*mm, 40*mm, "운전원 확인(서명): _____________________")
    c.drawString(110*mm, 40*mm, "담당자 확인(서명): _____________________")

    c.showPage(); c.save()


# =========================
# 5) File Server (Flask) — token link
# =========================
flask_app = Flask(__name__)
flask_app.wsgi_app = ProxyFix(flask_app.wsgi_app, x_proto=1, x_host=1)

@flask_app.get("/health")
def health():
    return {"ok": True, "ts": now()}

@flask_app.get("/f/<token>")
def fetch_file(token: str):
    row = file_by_token(token)
    if not row:
        abort(404)
    path = row["path"]
    if not os.path.exists(path):
        abort(404)
    return send_file(path, as_attachment=False)

def start_file_server_once():
    # Streamlit rerun 방지
    if getattr(start_file_server_once, "_started", False):
        return
    start_file_server_once._started = True  # type: ignore
    th = threading.Thread(
        target=lambda: flask_app.run(host=FILE_SERVER_HOST, port=FILE_SERVER_PORT, debug=False, use_reloader=False),
        daemon=True
    )
    th.start()

start_file_server_once()


# =========================
# 6) UI (Streamlit)
# =========================
st.set_page_config(page_title=f"{APP_NAME}", page_icon="✅", layout="wide")

# Light UI CSS (간단하지만 "개발 완료 느낌")
st.markdown("""
<style>
:root{
  --bg:#F6F8FC; --card:#fff; --text:#0F172A; --muted:#64748B; --line:#E5E7EB; --pri:#0B5FFF;
  --shadow:0 10px 30px rgba(2,8,23,.08); --r:18px;
}
.stApp{ background:var(--bg); }
.block-container{ max-width:1200px; padding-top:1.0rem; padding-bottom:3.5rem;}
.card{ background:var(--card); border:1px solid var(--line); border-radius:var(--r); box-shadow:var(--shadow); padding:16px 18px;}
.kpi{ background:var(--card); border:1px solid var(--line); border-radius:16px; padding:14px; box-shadow:var(--shadow); }
.kpi .t{ font-size:12px; color:var(--muted); margin-bottom:4px;}
.kpi .v{ font-size:22px; font-weight:900; color:var(--text);}
@media (max-width:980px){ .block-container{padding-left:12px;padding-right:12px;} }
</style>
""", unsafe_allow_html=True)

# session
st.session_state.setdefault("auth_ok", False)
st.session_state.setdefault("is_admin", False)
st.session_state.setdefault("user_name", "")
st.session_state.setdefault("user_role", "공무")
st.session_state.setdefault("site_name", "현장명(수정)")
st.session_state.setdefault("selected_req_id", None)

# KPI
def kpis():
    rows = req_list()
    today = datetime.now().strftime("%Y-%m-%d")
    today_cnt = sum(1 for r in rows if r["created_at"][:10] == today)
    approved = sum(1 for r in rows if r["status"] == "APPROVED")
    pending  = sum(1 for r in rows if r["status"] == "REQUESTED")
    done     = sum(1 for r in rows if r["status"] == "DONE")
    rejecting= sum(1 for r in rows if r["status"] == "REJECTED")
    c1,c2,c3,c4,c5 = st.columns(5)
    c1.markdown(f"<div class='kpi'><div class='t'>오늘 요청</div><div class='v'>{today_cnt}</div></div>", unsafe_allow_html=True)
    c2.markdown(f"<div class='kpi'><div class='t'>대기</div><div class='v'>{pending}</div></div>", unsafe_allow_html=True)
    c3.markdown(f"<div class='kpi'><div class='t'>승인</div><div class='v'>{approved}</div></div>", unsafe_allow_html=True)
    c4.markdown(f"<div class='kpi'><div class='t'>반려</div><div class='v'>{rejecting}</div></div>", unsafe_allow_html=True)
    c5.markdown(f"<div class='kpi'><div class='t'>완료</div><div class='v'>{done}</div></div>", unsafe_allow_html=True)

# Sidebar Login
with st.sidebar:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("🔐 로그인")

    admin_mode = st.toggle("관리자 모드로 로그인", value=False, help="이 토글을 켜면 Admin PIN 입력칸이 나타납니다.")
    site_pin  = st.text_input("현장 PIN", type="password", placeholder="4자리")
    admin_pin = ""
    if admin_mode:
        admin_pin = st.text_input("Admin PIN", type="password", placeholder="관리자 4자리")

    st.divider()
    name = st.text_input("이름/직책", placeholder="예) 공무팀장 홍길동")
    role = st.selectbox("역할", ["공무","안전","경비","협력사","기타"], index=0)
    site_name = st.text_input("현장명", value=st.session_state["site_name"])
    visitor_url = st.text_input("방문자교육 URL(QR)", value=meta_get("visitor_training_url") or DEFAULT_VISITOR_TRAINING_URL)

    c1,c2 = st.columns(2)
    with c1:
        if st.button("로그인", use_container_width=True):
            ok_site = (site_pin.strip() == meta_get("site_pin"))
            ok_admin= (admin_mode and admin_pin.strip() == meta_get("admin_pin"))
            if not ok_site:
                st.error("현장 PIN이 틀립니다.")
            else:
                st.session_state["auth_ok"] = True
                st.session_state["is_admin"] = bool(ok_admin)
                st.session_state["user_name"] = name.strip() or "사용자"
                st.session_state["user_role"] = role
                st.session_state["site_name"] = site_name.strip() or "현장명"
                meta_set("visitor_training_url", visitor_url.strip())
                st.success("로그인 완료")
                st.rerun()
    with c2:
        if st.button("로그아웃", use_container_width=True):
            st.session_state["auth_ok"] = False
            st.session_state["is_admin"] = False
            st.session_state["selected_req_id"] = None
            st.success("로그아웃 완료")
            st.rerun()

    st.caption(f"파일 링크 서버: {PUBLIC_BASE_URL}  (포트 {FILE_SERVER_PORT})")
    st.markdown("</div>", unsafe_allow_html=True)

if not st.session_state["auth_ok"]:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.title(f"{APP_NAME}")
    st.caption(f"{APP_VER} · 단일 파일 통합본")
    st.info("좌측에서 현장 PIN으로 로그인하면 시작합니다. 관리자 PIN은 '관리자 모드' 토글을 켜면 입력칸이 보입니다.")
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

# Header
st.markdown(f"""
<div class='card'>
  <div style="display:flex;align-items:center;justify-content:space-between;gap:12px;flex-wrap:wrap;">
    <div>
      <div style="font-size:22px;font-weight:900;">{st.session_state['site_name']} · 자재 반출입 승인</div>
      <div style="color:#64748B;margin-top:4px;">
        로그인: {st.session_state['user_name']} · {st.session_state['user_role']} {"(ADMIN)" if st.session_state['is_admin'] else ""}
      </div>
    </div>
    <div style="color:#64748B;">
      산출물 저장: <b>{PATHS['BASE']}</b><br/>
      파일링크: <b>{PUBLIC_BASE_URL}/f/&lt;token&gt;</b>
    </div>
  </div>
</div>
""", unsafe_allow_html=True)

kpis()
st.divider()

# Navigation
tabs = st.tabs(["① 신청", "② 승인", "③ 실행", "④ 대장/열람", "⑤ 관리자"])

# ① 신청
with tabs[0]:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("① 반입/반출 신청")
    cA,cB = st.columns(2)

    with cA:
        kind = st.radio("구분", ["반입(IN)","반출(OUT)"], horizontal=True)
        company = st.text_input("회사명(협력사)", placeholder="예) 덕일플러스건설(주)")
        item_name = st.text_input("취급 자재/도구명", placeholder="예) 덕트/철근/소부재")
        item_type = st.text_input("자재 종류", placeholder="예) 덕트자재")
        work_type = st.text_input("공종", placeholder="예) MEP / 철근콘크리트")
        leader = st.text_input("작업 지휘자", placeholder="예) OOO")
        date = st.date_input("일자").strftime("%Y-%m-%d")
        time_from = st.text_input("시간(시작)", value="07:00")
        time_to   = st.text_input("시간(종료)", value="09:00")
        gate = st.selectbox("사용 GATE", ["1GATE","2GATE","3GATE","4GATE","기타"], index=2)

    with cB:
        vehicle_spec = st.text_input("차량 규격", value="11TON")
        vehicle_count = st.number_input("대수", min_value=1, max_value=50, value=1, step=1)

        st.caption("PKG(1~3개만 적어도 운영 가능)")
        pkg_n = st.number_input("PKG 행 수", min_value=1, max_value=8, value=1, step=1)
        pkg_rows = []
        for i in range(int(pkg_n)):
            with st.expander(f"PKG #{i+1}", expanded=(i==0)):
                pkg_rows.append({
                    "name": st.text_input(f"항목명 #{i+1}", key=f"pkg_name_{i}"),
                    "size": st.text_input(f"크기(WxDxH) #{i+1}", key=f"pkg_size_{i}"),
                    "total_weight": st.text_input(f"총 무게 #{i+1}", key=f"pkg_tw_{i}"),
                    "pkg_weight": st.text_input(f"PKG당 무게/개수 #{i+1}", key=f"pkg_pw_{i}"),
                    "pkg_count": st.text_input(f"총 PKG 수 #{i+1}", key=f"pkg_pc_{i}"),
                    "binding": st.text_input(f"결속 방법 #{i+1}", key=f"pkg_bind_{i}"),
                    "stack": st.text_input(f"적재 높이/단 #{i+1}", key=f"pkg_stack_{i}"),
                })

    st.markdown("##### 하역/적재")
    d1,d2 = st.columns(2)
    with d1:
        unload_place = st.text_input("하역 장소", placeholder="예) 1F GATE#3")
        unload_method= st.text_area("하역 방법(인원/장비)", height=70, placeholder="예) 지게차 4.5t 1대, 유도원 2명")
    with d2:
        stack_place = st.text_input("적재 장소", placeholder="예) 1F GATE#3 복공판")
        stack_method= st.text_area("적재 방법(인원/장비)", height=70, placeholder="예) 지게차 하역 후 이동")
        stack_height= st.text_input("적재 높이/단", placeholder="예) 1단")

    st.markdown("##### 안전대책(최소 필수)")
    safety = {
        "구획 방법": st.text_input("구획 방법", value="라바콘/바리케이드/유도원 통제"),
        "전도": st.text_input("전도", value="결속 및 균형 유지"),
        "협착": st.text_input("협착", value="신호수 배치/작업반경 통제"),
        "붕괴": st.text_input("붕괴", value="과다 적재 금지"),
        "추락": st.text_input("추락", value="상부 작업 시 추락방지"),
        "낙하": st.text_input("낙하", value="결속 상태 확인/낙하물 방지"),
    }

    if st.button("요청 등록", type="primary", use_container_width=True):
        req_id = datetime.now().strftime("%y%m%d") + "-" + uuid.uuid4().hex[:8]
        data = {
            "id": req_id,
            "created_at": now(),
            "site_name": st.session_state["site_name"],
            "kind": "inbound" if kind.startswith("반입") else "outbound",
            "company_name": company.strip(),
            "item_name": item_name.strip(),
            "item_type": item_type.strip(),
            "work_type": work_type.strip(),
            "leader": leader.strip(),
            "date": date,
            "time_from": time_from.strip(),
            "time_to": time_to.strip(),
            "gate": gate,
            "vehicle_spec": vehicle_spec.strip(),
            "vehicle_count": int(vehicle_count),
            "pkg_json": json.dumps(pkg_rows, ensure_ascii=False),
            "unload_place": unload_place.strip(),
            "unload_method": unload_method.strip(),
            "stack_place": stack_place.strip(),
            "stack_method": stack_method.strip(),
            "stack_height": stack_height.strip(),
            "safety_json": json.dumps(safety, ensure_ascii=False),
            "status": "REQUESTED",
            "requester_name": st.session_state["user_name"],
            "requester_role": st.session_state["user_role"],
            "approver_name": None,
            "approver_role": None,
            "approved_at": None,
            "reject_reason": None,
            "executed_at": None,
        }
        req_insert(data)
        st.session_state["selected_req_id"] = req_id
        st.success(f"등록 완료: {req_id} (승인 탭으로 이동해 승인 처리하세요)")
    st.markdown("</div>", unsafe_allow_html=True)

# ② 승인
with tabs[1]:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("② 승인/반려")
    rows = req_list()
    if not rows:
        st.info("요청이 없습니다.")
    else:
        # pick
        labels = [f"{r['id']} | {r['status']} | {r['company_name']} | {r['item_name']} | {r['date']} {r['time_from']}~{r['time_to']} | {r['gate']}" for r in rows]
        sel = st.selectbox("요청 선택", labels, index=0)
        req_id = sel.split("|")[0].strip()
        st.session_state["selected_req_id"] = req_id
        req = req_get(req_id)
        st.json({k:req[k] for k in ["id","status","kind","company_name","item_name","item_type","work_type","leader","date","time_from","time_to","gate","vehicle_spec","vehicle_count","requester_name","requester_role","approver_name","approved_at","reject_reason"]}, expanded=False)

        can_approve = st.session_state["is_admin"] or st.session_state["user_role"] in ["공무","안전"]
        if not can_approve:
            st.warning("승인 권한이 없습니다. (관리자 또는 공무/안전만 승인)")
        else:
            c1,c2 = st.columns(2)
            with c1:
                if st.button("승인", type="primary", use_container_width=True, disabled=req["status"]!="REQUESTED"):
                    req_update(req_id, {
                        "status":"APPROVED",
                        "approver_name": st.session_state["user_name"],
                        "approver_role": st.session_state["user_role"],
                        "approved_at": now(),
                        "reject_reason": None
                    })
                    st.success("승인 완료")
                    st.rerun()
            with c2:
                reason = st.text_input("반려 사유", placeholder="예) 차량번호/규격 확인 필요")
                if st.button("반려", use_container_width=True, disabled=req["status"]!="REQUESTED"):
                    req_update(req_id, {"status":"REJECTED", "reject_reason": reason})
                    st.warning("반려 처리됨")
                    st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ③ 실행
with tabs[2]:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("③ 실행 등록 (필수 3장 + 추가 사진 옵션) + 산출물 생성")

    approved = req_list("APPROVED")
    if not approved:
        st.info("승인된 건이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        labels = [f"{r['id']} | {r['company_name']} | {r['item_name']} | {r['date']} {r['time_from']}~{r['time_to']} | {r['gate']}" for r in approved]
        sel = st.selectbox("승인건 선택", labels, index=0)
        req_id = sel.split("|")[0].strip()
        st.session_state["selected_req_id"] = req_id
        req = req_get(req_id)

        st.caption("필수 3장은 충족해야 등록됩니다. 추가 사진은 무제한(옵션)으로 계속 가능.")
        left,right = st.columns(2)
        with left:
            required_files = st.file_uploader("필수 사진 3장", type=["png","jpg","jpeg"], accept_multiple_files=True, key="req_ph")
            optional_files = st.file_uploader("추가 사진(옵션)", type=["png","jpg","jpeg"], accept_multiple_files=True, key="opt_ph")

        with right:
            st.markdown("**자재 상/하차 점검카드**")
            check = {
                "tie_2plus": st.text_input("3. 2개소 이상 결속 여부", value="양호"),
                "rope_banding": st.text_input("4. 로프/밴딩 상태", value=""),
                "height_under_4m": st.text_input("5. 높이 4m 이하/낙하위험", value=""),
                "bed_width_close": st.text_input("6. 적재함 폭/닫힘", value=""),
                "wheel_chock": st.text_input("7. 고임목 설치", value=""),
                "within_load": st.text_input("8. 적재하중 이내", value=""),
                "center_of_mass": st.text_input("9. 무게중심(쏠림)", value=""),
                "zone_control": st.text_input("10. 하역구간 통제", value=""),
            }

        if st.button("실행 등록 + 산출물 생성", type="primary", use_container_width=True):
            if not required_files or len(required_files) < 3:
                st.error("필수 사진은 최소 3장 필요합니다.")
            else:
                # save photos
                req_saved = save_uploads(req_id, required_files, "required")
                opt_saved = save_uploads(req_id, optional_files or [], "optional")

                # store categories: first 3 -> required1~3, rest if any -> optional
                for i, path in enumerate(req_saved[:3]):
                    photo_add(req_id, f"required{i+1}", path, st.session_state["user_name"])
                # if more than 3 in required uploader, treat surplus as optional
                for path in req_saved[3:]:
                    photo_add(req_id, "optional", path, st.session_state["user_name"])
                for path in opt_saved:
                    photo_add(req_id, "optional", path, st.session_state["user_name"])

                # checkcard save
                checkcard_upsert(req_id, check)

                # generate PDFs
                stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                prefix = safe_filename(f"{req['site_name']}_{req['id']}_{stamp}")

                plan_path   = p(PATHS["PDF"],   f"{prefix}_계획서.pdf")
                check_path  = p(PATHS["CHECK"], f"{prefix}_점검카드.pdf")
                permit_path = p(PATHS["PERMIT"],f"{prefix}_허가증(QR).pdf")
                zip_path    = p(PATHS["ZIP"],   f"{prefix}_BUNDLE.zip")

                pdf_plan(req, plan_path)
                pdf_checkcard(req, check, check_path)

                # permit token URL for printing in permit PDF
                permit_token = make_token(req_id, "permit")
                permit_public = public_file_url(permit_token)
                visitor_url = meta_get("visitor_training_url") or DEFAULT_VISITOR_TRAINING_URL
                pdf_permit(req, visitor_url, permit_public, permit_path)

                # register tokens for plan/check/permit
                plan_token  = make_token(req_id, "plan")
                check_token = make_token(req_id, "check")
                file_token_upsert(plan_token, req_id, "plan", plan_path)
                file_token_upsert(check_token, req_id, "check", check_path)
                file_token_upsert(permit_token, req_id, "permit", permit_path)

                # bundle zip
                all_photos = [x["path"] for x in photo_list(req_id)]
                with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as z:
                    for fp in [plan_path, check_path, permit_path]:
                        if os.path.exists(fp):
                            z.write(fp, arcname=os.path.basename(fp))
                    for fp in all_photos:
                        if os.path.exists(fp):
                            z.write(fp, arcname=p("photos", os.path.basename(fp)))
                    z.writestr("request.json", json.dumps(req, ensure_ascii=False, indent=2))
                    z.writestr("paths.txt", "\n".join([f"{k}={v}" for k,v in PATHS.items()]))

                zip_token = make_token(req_id, "zip")
                file_token_upsert(zip_token, req_id, "zip", zip_path)

                # status done
                req_update(req_id, {"status":"DONE", "executed_at": now()})

                # show share message
                msg = f"""[{req['site_name']}] 자재 {('반입' if req['kind']=='inbound' else '반출')} 실행완료
- 요청ID: {req_id}
- 회사: {req['company_name']}
- 자재: {req['item_name']} ({req['item_type']})
- 일시: {req['date']} {req['time_from']}~{req['time_to']}
- GATE: {req['gate']}

[PDF 바로보기]
- 계획서: {public_file_url(plan_token)}
- 점검카드: {public_file_url(check_token)}
- 허가증(QR포함): {public_file_url(permit_token)}

(공유용 ZIP) {public_file_url(zip_token)}
"""
                st.success("실행 등록 및 산출물 생성 완료")
                st.text_area("카톡 단톡방 공유 문구(복사)", value=msg, height=220)

                st.caption("※ 일반 카카오 단톡방은 서버가 자동 전송하기 어렵습니다(정책/보안). 위 문구+링크를 복사해 단톡방에 붙여넣는 방식이 가장 안정적입니다.")
                st.rerun()

    st.markdown("</div>", unsafe_allow_html=True)

# ④ 대장/열람
with tabs[3]:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("④ 대장 / PDF 열람")
    rows = req_list()
    if not rows:
        st.info("대장이 비어 있습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        q = st.text_input("검색(요청ID/회사/자재/게이트)", value="")
        def match(r):
            if not q.strip(): return True
            s = (r["id"]+r["company_name"]+r["item_name"]+r["gate"]).lower()
            return q.lower() in s
        filt = [r for r in rows if match(r)]
        labels = [f"{r['id']} | {r['status']} | {r['company_name']} | {r['item_name']} | {r['date']} | {r['gate']}" for r in filt] or ["(검색 결과 없음)"]
        sel = st.selectbox("요청 선택", labels, index=0)
        if sel.startswith("("):
            st.markdown("</div>", unsafe_allow_html=True)
        else:
            req_id = sel.split("|")[0].strip()
            st.session_state["selected_req_id"] = req_id
            req = req_get(req_id)
            st.json({k:req[k] for k in ["id","status","kind","company_name","item_name","item_type","date","time_from","time_to","gate","approver_name","approved_at","executed_at"]}, expanded=False)

            # latest files by type
            fs = files_for_request(req_id)
            if not fs:
                st.warning("산출물이 없습니다. (실행 탭에서 생성)")
                st.markdown("</div>", unsafe_allow_html=True)
            else:
                by = {}
                for f in fs:
                    if f["file_type"] not in by:
                        by[f["file_type"]] = f

                c1,c2,c3 = st.columns(3)
                if "plan" in by:
                    with c1:
                        st.markdown("**계획서**")
                        st.write(public_file_url(by["plan"]["token"]))
                        if st.button("계획서 보기", use_container_width=True):
                            embed_pdf(by["plan"]["path"])
                if "check" in by:
                    with c2:
                        st.markdown("**점검카드**")
                        st.write(public_file_url(by["check"]["token"]))
                        if st.button("점검카드 보기", use_container_width=True):
                            embed_pdf(by["check"]["path"])
                if "permit" in by:
                    with c3:
                        st.markdown("**허가증(QR)**")
                        st.write(public_file_url(by["permit"]["token"]))
                        if st.button("허가증 보기", use_container_width=True):
                            embed_pdf(by["permit"]["path"])

                # quick downloads
                st.markdown("#### 다운로드")
                for k in ["plan","check","permit","zip"]:
                    if k in by and os.path.exists(by[k]["path"]):
                        with open(by[k]["path"], "rb") as f:
                            st.download_button(f"{k.upper()} 다운로드", f, file_name=os.path.basename(by[k]["path"]), use_container_width=True)

    st.markdown("</div>", unsafe_allow_html=True)

# ⑤ 관리자
with tabs[4]:
    st.markdown("<div class='card'>", unsafe_allow_html=True)
    st.subheader("⑤ 관리자")
    if not st.session_state["is_admin"]:
        st.warning("관리자 모드로 로그인해야 접근 가능합니다. (좌측 '관리자 모드로 로그인' 토글 ON)")
        st.markdown("</div>", unsafe_allow_html=True)
    else:
        st.markdown("### PIN/링크 설정")
        col1,col2 = st.columns(2)
        with col1:
            new_site = st.text_input("현장 PIN 변경", value=meta_get("site_pin"), type="password")
            if st.button("현장 PIN 저장", use_container_width=True):
                meta_set("site_pin", new_site.strip())
                st.success("저장 완료")
        with col2:
            new_admin = st.text_input("Admin PIN 변경", value=meta_get("admin_pin"), type="password")
            if st.button("Admin PIN 저장", use_container_width=True):
                meta_set("admin_pin", new_admin.strip())
                st.success("저장 완료")

        new_visitor = st.text_input("방문자교육 URL(QR)", value=meta_get("visitor_training_url") or DEFAULT_VISITOR_TRAINING_URL)
        if st.button("방문자교육 URL 저장", use_container_width=True):
            meta_set("visitor_training_url", new_visitor.strip())
            st.success("저장 완료")

        st.divider()
        st.markdown("### 저장 위치/운영 점검")
        st.code("\n".join([f"{k}: {v}" for k,v in PATHS.items()]), language="text")
        st.code(f"PUBLIC_BASE_URL: {PUBLIC_BASE_URL}\nFILE_SERVER: {FILE_SERVER_HOST}:{FILE_SERVER_PORT}\n/health: {PUBLIC_BASE_URL}/health", language="text")
        st.caption("외부 접속이 안 되면: 공인IP/도메인, 포트(8801) 방화벽 오픈, 리버스프록시/HTTPS 여부를 확인해야 합니다.")

    st.markdown("</div>", unsafe_allow_html=True)
