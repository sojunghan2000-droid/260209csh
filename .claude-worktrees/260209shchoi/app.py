# ============================================================
# Material In/Out Approval Tool (SITE) - app.py v2.6.1
# - FIX: 모바일 "직접 서명" (캔버스) + 옵션 이미지 업로드
# - FIX: 모바일 "직접 촬영" (camera_input) + 추가사진(옵션) 업로드
# - 기존 흐름/DB/산출물 구조 유지
# ============================================================
import os
import io
import re
import json
import time
import uuid
import base64
import shutil
import zipfile
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple
import streamlit as st
# --- PDF
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.units import mm
# --- Optional QR generation
QR_AVAILABLE = True
try:
    import qrcode
except Exception:
    QR_AVAILABLE = False
# --- Optional signature canvas
CANVAS_AVAILABLE = True
try:
    from streamlit_drawable_canvas import st_canvas
    from PIL import Image
except Exception:
    CANVAS_AVAILABLE = False
# -------------------------
# Constants / Version
# -------------------------
APP_VERSION = "v2.6.1"
APP_TITLE = "자재 반출입 승인 · 실행 · 산출물(통합)"
DEFAULT_SITE_NAME = "현장명(수정)"
DEFAULT_BASE_DIR = "MaterialToolShared"  # 한 폴더로 통합
DEFAULT_SITE_PIN = "1234"   # 관리자에서 변경 권장
DEFAULT_ADMIN_PIN = "9999"  # 관리자에서 변경 권장
ROLES = ["협력사", "공사", "안전", "경비"]  # 공무 -> 공사
REQ_STATUS = ["PENDING_APPROVAL", "APPROVED", "REJECTED", "EXECUTING", "DONE"]
KIND_IN = "IN"
KIND_OUT = "OUT"
EXEC_REQUIRED_PHOTOS = [
    ("pre_load", "상차 전(촬영)"),
    ("post_load", "상차 후(촬영)"),
    ("area_ctrl", "하역/통제구간(촬영)"),
]
# -------------------------
# Helpers
# -------------------------
def now_str() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")
def today_str() -> str:
    return datetime.now().strftime("%Y-%m-%d")
def ensure_dir(p: Path) -> Path:
    p.mkdir(parents=True, exist_ok=True)
    return p
def safe_filename(s: str) -> str:
    s = re.sub(r"[\\/:*?\"<>|]", "_", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s[:120] if len(s) > 120 else s
def b64_download_link(file_path: Path, label: str) -> str:
    data = file_path.read_bytes()
    b64 = base64.b64encode(data).decode()
    return f'<a href="data:application/octet-stream;base64,{b64}" download="{file_path.name}">{label}</a>'
def infer_server_base_url() -> str:
    return st.session_state.get("PUBLIC_BASE_URL", "").strip()
def bytes_from_camera_or_upload(upl) -> Optional[bytes]:
    if upl is None:
        return None
    # st.camera_input returns UploadedFile-like with getvalue()
    try:
        return upl.getvalue()
    except Exception:
        try:
            return upl.getbuffer()
        except Exception:
            return None
def png_bytes_from_canvas_rgba(canvas_rgba) -> Optional[bytes]:
    # canvas_rgba: numpy array (H,W,4)
    if not CANVAS_AVAILABLE:
        return None
    try:
        img = Image.fromarray(canvas_rgba.astype("uint8"), mode="RGBA")
        # 투명 배경 -> 흰 배경 합성(현장 문서용)
        bg = Image.new("RGBA", img.size, (255, 255, 255, 255))
        bg.alpha_composite(img)
        out = io.BytesIO()
        bg.convert("RGB").save(out, format="PNG")
        return out.getvalue()
    except Exception:
        return None
# -------------------------
# Paths (Unified)
# -------------------------
def get_base_dir() -> Path:
    base = st.session_state.get("BASE_DIR", DEFAULT_BASE_DIR)
    return Path(base)
def path_db() -> Path:
    return ensure_dir(get_base_dir() / "data") / "gate.db"
def path_output_root() -> Path:
    return ensure_dir(get_base_dir() / "output")
def path_output(kind: str) -> Dict[str, Path]:
    root = path_output_root()
    d = {
        "pdf": ensure_dir(root / "pdf"),
        "qr": ensure_dir(root / "qr"),
        "zip": ensure_dir(root / "zip"),
        "photos": ensure_dir(root / "photos"),
        "sign": ensure_dir(root / "sign"),
        "check": ensure_dir(root / "check"),
        "permit": ensure_dir(root / "permit"),
        "bundle": ensure_dir(root / "bundle"),
    }
    return d
# -------------------------
# DB init & migration
# -------------------------
def con_open() -> sqlite3.Connection:
    p = path_db()
    con = sqlite3.connect(str(p), check_same_thread=False, timeout=10)
    con.row_factory = sqlite3.Row
    return con
def db_init_and_migrate(con: sqlite3.Connection) -> None:
    cur = con.cursor()
    cur.execute("""
    CREATE TABLE IF NOT EXISTS settings (
      key TEXT PRIMARY KEY,
      value TEXT NOT NULL,
      updated_at TEXT NOT NULL
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS requests (
      id TEXT PRIMARY KEY,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      status TEXT NOT NULL,
      kind TEXT NOT NULL,
      company_name TEXT,
      item_name TEXT,
      item_type TEXT,
      work_type TEXT,
      date TEXT,
      time_from TEXT,
      time_to TEXT,
      gate TEXT,
      vehicle_type TEXT,
      vehicle_ton TEXT,
      vehicle_count INTEGER,
      driver_name TEXT,
      driver_phone TEXT,
      notes TEXT,
      requester_name TEXT,
      requester_role TEXT,
      risk_level TEXT,
      sic_training_url TEXT
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS approvals (
      id TEXT PRIMARY KEY,
      req_id TEXT NOT NULL,
      step_no INTEGER NOT NULL,
      role_required TEXT NOT NULL,
      status TEXT NOT NULL,
      signer_name TEXT,
      signer_role TEXT,
      sign_png_path TEXT,
      stamp_png_path TEXT,
      signed_at TEXT,
      reject_reason TEXT,
      created_at TEXT NOT NULL,
      FOREIGN KEY(req_id) REFERENCES requests(id)
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS executions (
      req_id TEXT PRIMARY KEY,
      executed_by TEXT,
      executed_role TEXT,
      executed_at TEXT,
      check_json TEXT,
      required_photo_ok INTEGER DEFAULT 0,
      notes TEXT,
      FOREIGN KEY(req_id) REFERENCES requests(id)
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS photos (
      id TEXT PRIMARY KEY,
      req_id TEXT NOT NULL,
      slot_key TEXT,
      label TEXT,
      file_path TEXT NOT NULL,
      created_at TEXT NOT NULL,
      FOREIGN KEY(req_id) REFERENCES requests(id)
    );
    """)
    cur.execute("""
    CREATE TABLE IF NOT EXISTS outputs (
      req_id TEXT PRIMARY KEY,
      plan_pdf_path TEXT,
      permit_pdf_path TEXT,
      check_pdf_path TEXT,
      exec_pdf_path TEXT,
      bundle_pdf_path TEXT,
      zip_path TEXT,
      qr_png_path TEXT,
      created_at TEXT NOT NULL,
      updated_at TEXT NOT NULL,
      FOREIGN KEY(req_id) REFERENCES requests(id)
    );
    """)
    con.commit()
    def set_default(key: str, val: str):
        cur.execute("SELECT value FROM settings WHERE key=?", (key,))
        r = cur.fetchone()
        if not r:
            cur.execute("INSERT INTO settings(key,value,updated_at) VALUES(?,?,?)", (key, val, now_str()))
            con.commit()
    set_default("site_name", DEFAULT_SITE_NAME)
    set_default("site_pin", DEFAULT_SITE_PIN)
    set_default("admin_pin", DEFAULT_ADMIN_PIN)
    set_default("sic_training_url_default", "https://example.com/visitor-training")
    set_default("approval_routing_json", json.dumps({
        "IN":  ["공사"],
        "OUT": ["안전", "공사"]
    }, ensure_ascii=False))
    set_default("public_base_url", "")
def settings_get(con: sqlite3.Connection, key: str, default: str = "") -> str:
    cur = con.cursor()
    cur.execute("SELECT value FROM settings WHERE key=?", (key,))
    r = cur.fetchone()
    return r["value"] if r else default
def settings_set(con: sqlite3.Connection, key: str, value: str) -> None:
    cur = con.cursor()
    cur.execute("""
      INSERT INTO settings(key,value,updated_at) VALUES(?,?,?)
      ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=excluded.updated_at
    """, (key, value, now_str()))
    con.commit()
# -------------------------
# Request CRUD
# -------------------------
def req_insert(con: sqlite3.Connection, data: Dict[str, Any]) -> str:
    rid = uuid.uuid4().hex
    cur = con.cursor()
    cols = [
        "id","created_at","updated_at","status","kind",
        "company_name","item_name","item_type","work_type","date","time_from","time_to",
        "gate","vehicle_type","vehicle_ton","vehicle_count",
        "driver_name","driver_phone","notes",
        "requester_name","requester_role","risk_level","sic_training_url"
    ]
    row = {
        "id": rid,
        "created_at": now_str(),
        "updated_at": now_str(),
        "status": "PENDING_APPROVAL",
        **{k: data.get(k) for k in cols if k not in ["id","created_at","updated_at","status"]}
    }
    placeholders = ",".join(["?"]*len(cols))
    cur.execute(f"INSERT INTO requests({','.join(cols)}) VALUES({placeholders})", [row.get(c) for c in cols])
    con.commit()
    return rid
def req_update_status(con: sqlite3.Connection, rid: str, status: str) -> None:
    cur = con.cursor()
    cur.execute("UPDATE requests SET status=?, updated_at=? WHERE id=?", (status, now_str(), rid))
    con.commit()
def req_get(con: sqlite3.Connection, rid: str) -> Optional[Dict[str, Any]]:
    cur = con.cursor()
    cur.execute("SELECT * FROM requests WHERE id=?", (rid,))
    r = cur.fetchone()
    return dict(r) if r else None
def req_list(con: sqlite3.Connection, status: Optional[str] = None, kind: Optional[str] = None, limit: int = 200) -> List[Dict[str, Any]]:
    cur = con.cursor()
    q = "SELECT * FROM requests"
    w = []
    args = []
    if status:
        w.append("status=?"); args.append(status)
    if kind:
        w.append("kind=?"); args.append(kind)
    if w:
        q += " WHERE " + " AND ".join(w)
    q += " ORDER BY created_at DESC LIMIT ?"
    args.append(limit)
    cur.execute(q, args)
    return [dict(x) for x in cur.fetchall()]
# -------------------------
# Approval logic
# -------------------------
def routing_get(con: sqlite3.Connection) -> Dict[str, List[str]]:
    s = settings_get(con, "approval_routing_json", "{}")
    try:
        return json.loads(s)
    except Exception:
        return {"IN": ["공사"], "OUT": ["안전", "공사"]}
def approvals_create_default(con: sqlite3.Connection, rid: str, kind: str) -> None:
    routing = routing_get(con)
    roles = routing.get(kind, ["공사"]) or ["공사"]
    cur = con.cursor()
    for i, role in enumerate(roles, start=1):
        cur.execute("""
          INSERT INTO approvals(id, req_id, step_no, role_required, status, created_at)
          VALUES(?,?,?,?,?,?)
        """, (uuid.uuid4().hex, rid, i, role, "PENDING", now_str()))
    con.commit()
def approvals_inbox(con: sqlite3.Connection, user_role: str, is_admin: bool) -> List[Dict[str, Any]]:
    cur = con.cursor()
    if is_admin:
        cur.execute("""
          SELECT a.*, r.kind, r.company_name, r.item_name, r.date, r.time_from, r.time_to, r.gate, r.status AS req_status
          FROM approvals a JOIN requests r ON a.req_id=r.id
          WHERE a.status='PENDING'
          ORDER BY r.created_at DESC, a.step_no ASC
        """)
    else:
        cur.execute("""
          SELECT a.*, r.kind, r.company_name, r.item_name, r.date, r.time_from, r.time_to, r.gate, r.status AS req_status
          FROM approvals a JOIN requests r ON a.req_id=r.id
          WHERE a.status='PENDING' AND a.role_required=?
          ORDER BY r.created_at DESC, a.step_no ASC
        """, (user_role,))
    return [dict(x) for x in cur.fetchall()]
def approvals_for_req(con: sqlite3.Connection, rid: str) -> List[Dict[str, Any]]:
    cur = con.cursor()
    cur.execute("SELECT * FROM approvals WHERE req_id=? ORDER BY step_no ASC", (rid,))
    return [dict(x) for x in cur.fetchall()]
def approval_mark(con: sqlite3.Connection, approval_id: str, action: str, signer_name: str, signer_role: str,
                  sign_path: Optional[str], stamp_path: Optional[str], reject_reason: str = "") -> Tuple[str, str]:
    cur = con.cursor()
    cur.execute("SELECT req_id, status FROM approvals WHERE id=?", (approval_id,))
    row = cur.fetchone()
    if not row:
        return ("", "승인항목을 찾지 못했습니다.")
    rid = row["req_id"]
    if row["status"] != "PENDING":
        return (rid, "이미 처리된 승인입니다.")
    if action == "APPROVE":
        cur.execute("""
          UPDATE approvals SET status='APPROVED',
            signer_name=?, signer_role=?, sign_png_path=?, stamp_png_path=?, signed_at=?
          WHERE id=?
        """, (signer_name, signer_role, sign_path, stamp_path, now_str(), approval_id))
        con.commit()
        cur.execute("SELECT COUNT(*) AS cnt FROM approvals WHERE req_id=? AND status='PENDING'", (rid,))
        left = cur.fetchone()["cnt"]
        if left == 0:
            req_update_status(con, rid, "APPROVED")
            return (rid, "최종 승인 완료")
        else:
            return (rid, "승인 완료(다음 승인자 대기)")
    else:
        cur.execute("""
          UPDATE approvals SET status='REJECTED',
            signer_name=?, signer_role=?, reject_reason=?, signed_at=?
          WHERE id=?
        """, (signer_name, signer_role, reject_reason, now_str(), approval_id))
        con.commit()
        req_update_status(con, rid, "REJECTED")
        return (rid, "반려 처리 완료")
# -------------------------
# Photo management
# -------------------------
def photo_add(con: sqlite3.Connection, rid: str, slot_key: str, label: str, file_bytes: bytes, suffix: str = ".jpg") -> str:
    out = path_output("X")["photos"]
    fname = f"{rid}_{slot_key}_{uuid.uuid4().hex[:8]}{suffix}"
    fpath = out / fname
    fpath.write_bytes(file_bytes)
    cur = con.cursor()
    pid = uuid.uuid4().hex
    cur.execute("""
      INSERT INTO photos(id, req_id, slot_key, label, file_path, created_at)
      VALUES(?,?,?,?,?,?)
    """, (pid, rid, slot_key, label, str(fpath), now_str()))
    con.commit()
    return str(fpath)
def photos_for_req(con: sqlite3.Connection, rid: str) -> List[Dict[str, Any]]:
    cur = con.cursor()
    cur.execute("SELECT * FROM photos WHERE req_id=? ORDER BY created_at ASC", (rid,))
    return [dict(x) for x in cur.fetchall()]
def required_photos_ok(con: sqlite3.Connection, rid: str) -> bool:
    photos = photos_for_req(con, rid)
    keys = set([p["slot_key"] for p in photos if p.get("slot_key")])
    return all(k in keys for k, _ in EXEC_REQUIRED_PHOTOS)
# -------------------------
# Check card
# -------------------------
CHECK_ITEMS = [
    ("attendees", "0. 필수 참석자", "협력회사 담당자, 장비운전원, 차량운전원, 유도원, 안전보조원/감시단"),
    ("company", "1. 협력회사", ""),
    ("cargo_type", "2. 화물/자재 종류", ""),
    ("tie_2points", "3. 화물 당 2개소 이상 결속 여부 확인", "양호/불량"),
    ("rope_banding", "4. 고정용 로프 및 밴딩 상태 점검 여부", "양호/불량"),
    ("height_4m", "5. 화물 높이 4M 이하 적재, 낙하위험 발생여부", "양호/주의/불량"),
    ("width_close", "6. 적재함 폭 초과 상차 금지, 적재함 닫힘 여부", "양호/불량"),
    ("wheel_chock", "7. 자재차량 고임목 설치 여부", "양호/불량"),
    ("within_load", "8. 적재하중 이내 적재 여부", "양호/불량"),
    ("center_of_gravity", "9. 화물 무게중심 확인(한쪽 쏠림 여부)", "양호/주의/불량"),
    ("unload_zone_ctrl", "10. 자재 하역구간 구획 및 통제 여부", "양호/불량"),
]
def execution_upsert(con: sqlite3.Connection, rid: str, executed_by: str, executed_role: str, check_json: Dict[str, Any], notes: str) -> None:
    cur = con.cursor()
    ok = 1 if required_photos_ok(con, rid) else 0
    cur.execute("""
      INSERT INTO executions(req_id, executed_by, executed_role, executed_at, check_json, required_photo_ok, notes)
      VALUES(?,?,?,?,?,?,?)
      ON CONFLICT(req_id) DO UPDATE SET
        executed_by=excluded.executed_by,
        executed_role=excluded.executed_role,
        executed_at=excluded.executed_at,
        check_json=excluded.check_json,
        required_photo_ok=excluded.required_photo_ok,
        notes=excluded.notes
    """, (rid, executed_by, executed_role, now_str(), json.dumps(check_json, ensure_ascii=False), ok, notes))
    con.commit()
def execution_get(con: sqlite3.Connection, rid: str) -> Optional[Dict[str, Any]]:
    cur = con.cursor()
    cur.execute("SELECT * FROM executions WHERE req_id=?", (rid,))
    r = cur.fetchone()
    return dict(r) if r else None
# -------------------------
# Output generation (PDF/QR/ZIP)
# -------------------------
def qr_generate_png(url: str, out_path: Path) -> Optional[Path]:
    if not QR_AVAILABLE:
        return None
    img = qrcode.make(url)
    img.save(out_path)
    return out_path
def pdf_simple_header(c: canvas.Canvas, title: str, subtitle: str = ""):
    c.setFont("Helvetica-Bold", 16)
    c.drawString(20*mm, 287*mm, title)
    if subtitle:
        c.setFont("Helvetica", 10)
        c.drawString(20*mm, 281*mm, subtitle)
    c.line(20*mm, 278*mm, 190*mm, 278*mm)
def pdf_plan(con: sqlite3.Connection, req: Dict[str, Any], approvals: List[Dict[str, Any]], out_path: Path) -> Path:
    c = canvas.Canvas(str(out_path), pagesize=A4)
    pdf_simple_header(c, f"자재 반출입 계획서 ({'반입' if req['kind']==KIND_IN else '반출'})",
                      f"생성: {now_str()} · {APP_VERSION}")
    y = 270*mm
    c.setFont("Helvetica", 10)
    fields = [
        ("회사명", req.get("company_name","")),
        ("취급 자재/도구명", req.get("item_name","")),
        ("공종/자재종류", req.get("item_type","")),
        ("작업 지휘자", req.get("requester_name","")),
        ("일자", req.get("date","")),
        ("시간", f"{req.get('time_from','')} ~ {req.get('time_to','')}"),
        ("사용 GATE", req.get("gate","")),
        ("운반 차량(규격/대수)", f"{req.get('vehicle_type','')} / {req.get('vehicle_ton','')}톤 / {req.get('vehicle_count',1)}대"),
        ("기사", f"{req.get('driver_name','')} ({req.get('driver_phone','')})"),
        ("비고", req.get("notes","")),
    ]
    for k,v in fields:
        c.drawString(20*mm, y, f"{k}: {v}")
        y -= 7*mm
    y -= 3*mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20*mm, y, "승인")
    y -= 6*mm
    c.setFont("Helvetica", 10)
    for ap in approvals:
        line = f"{ap['step_no']}. {ap['role_required']} - {ap['status']}"
        if ap["status"] == "APPROVED":
            line += f" · {ap.get('signer_name','')} · {ap.get('signed_at','')}"
        if ap["status"] == "REJECTED":
            line += f" · 사유: {ap.get('reject_reason','')}"
        c.drawString(22*mm, y, line)
        y -= 6*mm
    c.showPage()
    c.save()
    return out_path
def pdf_permit(con: sqlite3.Connection, req: Dict[str, Any], sic_url: str, qr_path: Optional[Path], out_path: Path) -> Path:
    c = canvas.Canvas(str(out_path), pagesize=A4)
    pdf_simple_header(c, "자재 차량 진출입 허가증", f"생성: {now_str()} · {APP_VERSION}")
    c.setFont("Helvetica", 11)
    c.drawString(20*mm, 260*mm, f"입고 회사명: {req.get('company_name','')}")
    c.drawString(20*mm, 252*mm, f"운전원: {req.get('driver_name','')} / {req.get('driver_phone','')}")
    c.drawString(20*mm, 244*mm, f"사용 GATE: {req.get('gate','')} · 일시: {req.get('date','')} {req.get('time_from','')}~{req.get('time_to','')}")
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20*mm, 232*mm, "필수 준수사항")
    c.setFont("Helvetica", 10)
    rules = [
        "1. 하차 시 안전모 착용",
        "2. 운전석 유리창 개방 필수",
        "3. 현장 내 속도 10km/h 이내 주행",
        "4. 비상등 상시 점등",
        "5. 주정차 시 고임목 설치",
        "6. 유도원 통제하에 운영",
    ]
    y = 225*mm
    for r in rules:
        c.drawString(22*mm, y, r)
        y -= 6*mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20*mm, 180*mm, "방문자교육(QR)")
    c.setFont("Helvetica", 9)
    c.drawString(20*mm, 174*mm, f"URL: {sic_url}")
    if qr_path and qr_path.exists():
        try:
            from reportlab.lib.utils import ImageReader
            img = ImageReader(str(qr_path))
            c.drawImage(img, 20*mm, 125*mm, width=45*mm, height=45*mm, preserveAspectRatio=True, mask='auto')
        except Exception:
            c.drawString(20*mm, 160*mm, "(QR 삽입 실패)")
    c.setFont("Helvetica", 10)
    c.drawString(80*mm, 140*mm, "운전원 확인(서명): ____________________")
    c.drawString(80*mm, 130*mm, "담당자 확인(서명): ____________________")
    c.showPage()
    c.save()
    return out_path
def pdf_check_card(con: sqlite3.Connection, req: Dict[str, Any], check_json: Dict[str, Any], out_path: Path) -> Path:
    c = canvas.Canvas(str(out_path), pagesize=A4)
    pdf_simple_header(c, "자재 상/하차 점검카드", f"요청ID: {req['id']} · 생성: {now_str()} · {APP_VERSION}")
    c.setFont("Helvetica", 10)
    c.drawString(20*mm, 270*mm, f"협력회사: {req.get('company_name','')}")
    c.drawString(20*mm, 262*mm, f"화물/자재: {req.get('item_name','')} / 종류: {req.get('item_type','')}")
    c.drawString(20*mm, 254*mm, f"일시: {req.get('date','')} {req.get('time_from','')}~{req.get('time_to','')} / GATE: {req.get('gate','')}")
    y = 240*mm
    for key, title, hint in CHECK_ITEMS:
        val = (check_json.get(key) or "").strip()
        c.drawString(20*mm, y, f"{title}: {val}")
        y -= 7*mm
        if y < 20*mm:
            c.showPage()
            y = 270*mm
    c.showPage()
    c.save()
    return out_path
def pdf_exec_summary(con: sqlite3.Connection, req: Dict[str, Any], photos: List[Dict[str, Any]], out_path: Path) -> Path:
    c = canvas.Canvas(str(out_path), pagesize=A4)
    pdf_simple_header(c, "실행 기록(사진 요약)", f"요청ID: {req['id']} · 생성: {now_str()} · {APP_VERSION}")
    c.setFont("Helvetica", 10)
    y = 270*mm
    c.drawString(20*mm, y, f"회사: {req.get('company_name','')} / 자재: {req.get('item_name','')} / {'반입' if req['kind']==KIND_IN else '반출'}")
    y -= 8*mm
    c.drawString(20*mm, y, f"일시: {req.get('date','')} {req.get('time_from','')}~{req.get('time_to','')} / GATE: {req.get('gate','')}")
    y -= 12*mm
    c.setFont("Helvetica-Bold", 11)
    c.drawString(20*mm, y, "사진 목록")
    y -= 8*mm
    c.setFont("Helvetica", 10)
    for p in photos:
        c.drawString(22*mm, y, f"- [{p.get('slot_key','')}] {p.get('label','')} · {Path(p['file_path']).name}")
        y -= 6*mm
        if y < 20*mm:
            c.showPage()
            y = 270*mm
    c.showPage()
    c.save()
    return out_path
def outputs_upsert(con: sqlite3.Connection, rid: str, **paths: str) -> None:
    cur = con.cursor()
    cur.execute("SELECT req_id FROM outputs WHERE req_id=?", (rid,))
    exists = cur.fetchone() is not None
    if not exists:
        cur.execute("INSERT INTO outputs(req_id, created_at, updated_at) VALUES(?,?,?)", (rid, now_str(), now_str()))
        con.commit()
    for k, v in paths.items():
        if v is None:
            continue
        cur.execute(f"UPDATE outputs SET {k}=?, updated_at=? WHERE req_id=?", (v, now_str(), rid))
    con.commit()
def outputs_get(con: sqlite3.Connection, rid: str) -> Optional[Dict[str, Any]]:
    cur = con.cursor()
    cur.execute("SELECT * FROM outputs WHERE req_id=?", (rid,))
    r = cur.fetchone()
    return dict(r) if r else None
def zip_build(con: sqlite3.Connection, rid: str, out_zip: Path, include_files: List[Path]) -> Path:
    with zipfile.ZipFile(out_zip, "w", zipfile.ZIP_DEFLATED) as z:
        for f in include_files:
            if f and f.exists():
                z.write(str(f), arcname=f.name)
    return out_zip
def generate_all_outputs(con: sqlite3.Connection, rid: str) -> Dict[str, str]:
    req = req_get(con, rid)
    if not req:
        raise ValueError("요청을 찾을 수 없습니다.")
    out = path_output("X")
    approvals = approvals_for_req(con, rid)
    exec_row = execution_get(con, rid)
    photos = photos_for_req(con, rid)
    sic_default = settings_get(con, "sic_training_url_default", "https://example.com/visitor-training")
    sic_url = (req.get("sic_training_url") or "").strip() or sic_default
    qr_path = out["qr"] / f"{rid}_sic_qr.png"
    qr_saved = qr_generate_png(sic_url, qr_path) if QR_AVAILABLE else None
    if qr_saved:
        outputs_upsert(con, rid, qr_png_path=str(qr_saved))
    plan_pdf = out["pdf"] / f"{rid}_plan.pdf"
    pdf_plan(con, req, approvals, plan_pdf)
    permit_pdf = out["permit"] / f"{rid}_permit.pdf"
    pdf_permit(con, req, sic_url, qr_saved, permit_pdf)
    check_pdf = None
    check_json = {}
    if exec_row and exec_row.get("check_json"):
        try:
            check_json = json.loads(exec_row["check_json"])
        except Exception:
            check_json = {}
        check_pdf = out["check"] / f"{rid}_checkcard.pdf"
        pdf_check_card(con, req, check_json, check_pdf)
    exec_pdf = out["pdf"] / f"{rid}_exec.pdf"
    pdf_exec_summary(con, req, photos, exec_pdf)
    bundle_pdf = out["bundle"] / f"{rid}_bundle.pdf"
    c = canvas.Canvas(str(bundle_pdf), pagesize=A4)
    pdf_simple_header(c, "산출물 번들 안내", f"요청ID: {rid} · 생성: {now_str()} · {APP_VERSION}")
    c.setFont("Helvetica", 11)
    c.drawString(20*mm, 260*mm, "아래 파일들이 함께 생성되었습니다.")
    c.setFont("Helvetica", 10)
    y = 248*mm
    for f in [plan_pdf, permit_pdf, check_pdf, exec_pdf, qr_saved]:
        if f and Path(f).exists():
            c.drawString(22*mm, y, f"- {Path(f).name}")
            y -= 7*mm
    c.drawString(20*mm, 220*mm, f"저장 위치: {str(path_output_root())}")
    c.showPage()
    c.save()
    zip_path = out["zip"] / f"{rid}_outputs.zip"
    include = [plan_pdf, permit_pdf, exec_pdf, bundle_pdf]
    if check_pdf:
        include.append(check_pdf)
    if qr_saved:
        include.append(qr_saved)
    for p in photos:
        fp = Path(p["file_path"])
        if fp.exists():
            include.append(fp)
    zip_build(con, rid, zip_path, include)
    outputs_upsert(
        con, rid,
        plan_pdf_path=str(plan_pdf),
        permit_pdf_path=str(permit_pdf),
        check_pdf_path=str(check_pdf) if check_pdf else "",
        exec_pdf_path=str(exec_pdf),
        bundle_pdf_path=str(bundle_pdf),
        zip_path=str(zip_path),
    )
    return {
        "plan_pdf": str(plan_pdf),
        "permit_pdf": str(permit_pdf),
        "check_pdf": str(check_pdf) if check_pdf else "",
        "exec_pdf": str(exec_pdf),
        "bundle_pdf": str(bundle_pdf),
        "zip": str(zip_path),
        "qr": str(qr_saved) if qr_saved else "",
        "root": str(path_output_root()),
    }
# -------------------------
# UI / Styling
# -------------------------
def inject_css():
    st.markdown("""
    <style>
    :root{ --bg:#f6f8fb; --card:#ffffff; --text:#0f172a; --muted:#64748b; --line:#e2e8f0;
      --brand:#2563eb; --brand2:#06b6d4; --danger:#ef4444; --ok:#16a34a;
      --shadow: 0 10px 30px rgba(2,6,23,.08); --radius: 18px; }
    html, body, [class*="css"] { font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif; }
    .stApp { background: var(--bg); }
    .card { background: var(--card); border: 1px solid var(--line); border-radius: var(--radius);
      box-shadow: var(--shadow); padding: 16px 18px; }
    .hero { background: linear-gradient(135deg, rgba(37,99,235,.95), rgba(6,182,212,.85));
      color: white; border-radius: 22px; padding: 18px 18px; box-shadow: var(--shadow);
      border: 1px solid rgba(255,255,255,.18); }
    .hero .title { font-size: 20px; font-weight: 800; margin-bottom: 4px; }
    .hero .sub { font-size: 12px; opacity: .9; }
    .kpi { display:flex; gap:10px; flex-wrap:wrap; margin-top:12px; }
    .kpi .box { flex:1; min-width:140px; background: rgba(255,255,255,.12); border:1px solid rgba(255,255,255,.18);
      border-radius: 16px; padding: 10px 12px; }
    .kpi .n { font-size: 20px; font-weight: 800; }
    .kpi .l { font-size: 11px; opacity:.92; letter-spacing:.3px; }
    .pill{ display:inline-block; padding:4px 10px; border-radius:999px; border:1px solid var(--line);
      background:#fff; font-size:12px; color:var(--muted); margin-right:6px; }
    .small{ font-size:12px; } .muted{ color: var(--muted); }
    .stTabs [data-baseweb="tab-list"] { gap: 6px; }
    .stTabs [data-baseweb="tab"]{ background:#fff; border:1px solid var(--line); border-radius: 999px;
      padding: 8px 14px; box-shadow: 0 2px 10px rgba(2,6,23,.04); }
    .stTabs [aria-selected="true"]{ border-color: rgba(37,99,235,.35); box-shadow: 0 10px 20px rgba(37,99,235,.14); }
    </style>
    """, unsafe_allow_html=True)
# -------------------------
# Auth / Session
# -------------------------
def auth_reset():
    st.session_state["AUTH_OK"] = False
    st.session_state["IS_ADMIN"] = False
    st.session_state["USER_NAME"] = ""
    st.session_state["USER_ROLE"] = "협력사"
def auth_login(con: sqlite3.Connection, site_pin: str, name: str, role: str, is_admin: bool, admin_pin: str) -> Tuple[bool, str]:
    sp = settings_get(con, "site_pin", DEFAULT_SITE_PIN)
    ap = settings_get(con, "admin_pin", DEFAULT_ADMIN_PIN)
    if site_pin != sp:
        return False, "현장 PIN이 올바르지 않습니다."
    if not name.strip():
        return False, "이름/직책을 입력해주세요."
    if role not in ROLES:
        return False, "역할 선택이 올바르지 않습니다."
    if is_admin and admin_pin != ap:
        return False, "Admin PIN이 올바르지 않습니다."
    st.session_state["AUTH_OK"] = True
    st.session_state["IS_ADMIN"] = bool(is_admin)
    st.session_state["USER_NAME"] = name.strip()
    st.session_state["USER_ROLE"] = role
    return True, "로그인 완료"
# -------------------------
# Share text
# -------------------------
def make_share_text(req: Dict[str, Any], outs: Optional[Dict[str, Any]]) -> str:
    kind_txt = "반입" if req["kind"] == KIND_IN else "반출"
    rid = req["id"]
    base_url = infer_server_base_url()
    link = f"{base_url}?rid={rid}" if base_url else f"(내부망 접속주소 설정 필요) 요청ID={rid}"
    def nm(p):
        return Path(p).name if p else ""
    lines = []
    lines.append(f"[자재 {kind_txt} 안내] {req.get('date','')} {req.get('time_from','')}~{req.get('time_to','')} / GATE:{req.get('gate','')}")
    lines.append(f"- 협력사: {req.get('company_name','')} / 자재: {req.get('item_name','')}")
    lines.append(f"- 차량: {req.get('vehicle_type','')} {req.get('vehicle_ton','')}톤 {req.get('vehicle_count',1)}대 / 기사: {req.get('driver_name','')} ({req.get('driver_phone','')})")
    lines.append(f"- 상태: {req.get('status','')}")
    lines.append(f"- 상세/산출물: {link}")
    if outs:
        lines.append("— 산출물 —")
        if outs.get("plan_pdf_path"): lines.append(f"  · 계획서PDF: {nm(outs.get('plan_pdf_path'))}")
        if outs.get("permit_pdf_path"): lines.append(f"  · 허가증PDF(QR): {nm(outs.get('permit_pdf_path'))}")
        if outs.get("check_pdf_path"): lines.append(f"  · 점검카드PDF: {nm(outs.get('check_pdf_path'))}")
        if outs.get("exec_pdf_path"): lines.append(f"  · 실행요약PDF: {nm(outs.get('exec_pdf_path'))}")
        if outs.get("zip_path"): lines.append(f"  · ZIP(일괄): {nm(outs.get('zip_path'))}")
    lines.append("※ 단톡방에는 위 문구를 그대로 붙여넣고, 파일은 내부망에서 열람/다운로드하세요.")
    return "\n".join(lines)
# -------------------------
# Signature (direct draw + optional upload)
# -------------------------
def save_bytes_to_file(folder_key: str, rid: str, tag: str, data: bytes, suffix: str) -> str:
    out = path_output("X")[folder_key]
    fp = out / f"{rid}_{tag}_{uuid.uuid4().hex[:8]}{suffix}"
    fp.write_bytes(data)
    return str(fp)
def ui_signature_block(rid: str, label: str, key_prefix: str) -> Tuple[Optional[str], Optional[str]]:
    """
    returns (sign_path, stamp_path)
    - sign: direct draw preferred, else optional upload
    - stamp: optional upload
    """
    st.markdown(f"#### {label}")
    sign_path = None
    stamp_path = None
    mode = st.radio("서명 방식", ["직접 서명(권장)", "이미지 업로드(옵션)"], horizontal=True, key=f"{key_prefix}_mode")
    if mode == "직접 서명(권장)":
        if not CANVAS_AVAILABLE:
            st.warning("직접 서명 기능을 사용하려면 패키지 설치가 필요합니다: streamlit-drawable-canvas, pillow")
        else:
            st.caption("손가락/펜으로 서명하세요. (지우기: Clear)")
            canvas_res = st_canvas(
                fill_color="rgba(255, 255, 255, 0)",
                stroke_width=4,
                stroke_color="#111111",
                background_color="#ffffff",
                height=180,
                width=520,
                drawing_mode="freedraw",
                key=f"{key_prefix}_canvas",
            )
            colA, colB = st.columns(2)
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
            # 저장된 서명 경로는 세션에 보관(버튼 클릭 후 rerun 되므로)
            if sign_path:
                st.session_state[f"{key_prefix}_sign_path"] = sign_path
            sign_path = st.session_state.get(f"{key_prefix}_sign_path", None)
    else:
        upl = st.file_uploader("서명 이미지 업로드(PNG/JPG)", type=["png", "jpg", "jpeg"], key=f"{key_prefix}_sign_upload")
        if upl:
            data = bytes_from_camera_or_upload(upl)
            if data:
                suffix = Path(upl.name).suffix.lower() or ".png"
                sign_path = save_bytes_to_file("sign", rid, "sign_upl", data, suffix)
                st.session_state[f"{key_prefix}_sign_path"] = sign_path
                st.success("서명 이미지 저장 완료")
        sign_path = st.session_state.get(f"{key_prefix}_sign_path", None)
    st.divider()
    st.caption("도장(옵션)")
    stamp_upl = st.file_uploader("도장 이미지 업로드(옵션)", type=["png", "jpg", "jpeg"], key=f"{key_prefix}_stamp_upload")
    if stamp_upl:
        data = bytes_from_camera_or_upload(stamp_upl)
        if data:
            suffix = Path(stamp_upl.name).suffix.lower() or ".png"
            stamp_path = save_bytes_to_file("sign", rid, "stamp", data, suffix)
            st.session_state[f"{key_prefix}_stamp_path"] = stamp_path
            st.success("도장 이미지 저장 완료")
    stamp_path = st.session_state.get(f"{key_prefix}_stamp_path", None)
    return sign_path, stamp_path
# -------------------------
# Camera (direct capture + optional upload)
# -------------------------
def ui_photo_capture_required(con: sqlite3.Connection, rid: str):
    st.markdown("#### 1) 실행 사진(필수 3종) — 직접 촬영")
    st.caption("모바일에서는 아래 촬영 버튼을 누르면 카메라로 바로 촬영됩니다. (촬영이 안 되는 환경이면 업로드로 대체 가능)")
    for key, label in EXEC_REQUIRED_PHOTOS:
        st.markdown(f"**{label}***")
        cam = st.camera_input(label, key=f"cam_{rid}_{key}")
        if cam is not None:
            data = bytes_from_camera_or_upload(cam)
            if data:
                photo_add(con, rid, key, label, data, suffix=".jpg")
                st.success(f"촬영 저장 완료: {label}")
        # 예외적으로 PC/차단환경 대비: 업로드 대체(숨김이 아니라 "대체수단"으로 노출)
        with st.expander("촬영이 안되면(대체) 파일 업로드"):
            upl = st.file_uploader(f"{label} 업로드", type=["png", "jpg", "jpeg"], key=f"upl_{rid}_{key}")
            if upl:
                data2 = bytes_from_camera_or_upload(upl)
                if data2:
                    suffix = Path(upl.name).suffix.lower() or ".jpg"
                    photo_add(con, rid, key, label, data2, suffix=suffix)
                    st.success(f"업로드 저장 완료: {label}")
def ui_photo_optional_upload(con: sqlite3.Connection, rid: str):
    st.markdown("#### 2) 추가 사진(옵션) — 업로드")
    opt = st.file_uploader("추가 사진 업로드(여러 장 가능)", type=["png","jpg","jpeg"], accept_multiple_files=True, key=f"opt_{rid}")
    if opt:
        for f in opt:
            data = bytes_from_camera_or_upload(f)
            if data:
                suffix = Path(f.name).suffix.lower() or ".jpg"
                photo_add(con, rid, "optional", f"추가사진({f.name})", data, suffix=suffix)
        st.success(f"추가 사진 {len(opt)}장 업로드 완료")
# -------------------------
# Pages
# -------------------------
def ui_header(con: sqlite3.Connection):
    site_name = settings_get(con, "site_name", DEFAULT_SITE_NAME)
    user = st.session_state.get("USER_NAME", "")
    role = st.session_state.get("USER_ROLE", "")
    total = len(req_list(con, None, None, 9999))
    pend = len(req_list(con, "PENDING_APPROVAL", None, 9999))
    appr = len(req_list(con, "APPROVED", None, 9999))
    rej = len(req_list(con, "REJECTED", None, 9999))
    st.markdown(f"""
      <div class="hero">
        <div class="title">{APP_TITLE}</div>
        <div class="sub">현장: {site_name} · 사용자: {user} ({role}) · {APP_VERSION}</div>
        <div class="kpi">
          <div class="box"><div class="n">{total}</div><div class="l">TOTAL</div></div>
          <div class="box"><div class="n">{pend}</div><div class="l">PENDING</div></div>
          <div class="box"><div class="n">{appr}</div><div class="l">APPROVED</div></div>
          <div class="box"><div class="n">{rej}</div><div class="l">REJECTED</div></div>
        </div>
      </div>
    """, unsafe_allow_html=True)
def page_login(con: sqlite3.Connection):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🔐 로그인(현장용)")
    col1, col2 = st.columns(2)
    with col1:
        site_pin = st.text_input("현장 PIN*", type="password", placeholder="예) 4자리")
        name = st.text_input("이름/직책*", placeholder="예) 공사팀장 홍길동")
        role = st.selectbox("역할*", ROLES, index=ROLES.index(st.session_state.get("USER_ROLE","협력사")) if st.session_state.get("USER_ROLE","협력사") in ROLES else 0)
    with col2:
        st.caption("관리자 모드(선택)")
        is_admin = st.toggle("관리자 모드로 로그인", value=False)
        admin_pin = ""
        if is_admin:
            admin_pin = st.text_input("Admin PIN*", type="password", placeholder="관리자 전용")
        st.caption("방문자교육 URL(기본값)")
        st.code(settings_get(con, "sic_training_url_default", "https://example.com/visitor-training"), language="text")
    if st.button("로그인", type="primary", use_container_width=True):
        ok, msg = auth_login(con, site_pin, name, role, is_admin, admin_pin)
        if ok:
            st.success(msg)
            st.rerun()
        else:
            st.error(msg)
    st.markdown("</div>", unsafe_allow_html=True)
def page_request(con: sqlite3.Connection):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📝 요청 등록(협력사/현장)")
    c1, c2 = st.columns(2)
    with c1:
        kind = st.radio("구분", [("반입(IN)", KIND_IN), ("반출(OUT)", KIND_OUT)], horizontal=True)
        kind_val = kind[1]
        company_name = st.text_input("협력사(회사명)", value="")
        item_name = st.text_input("취급 자재/도구명(화물명)", value="")
        item_type = st.text_input("공종/자재종류", value="")
        work_type = st.text_input("세부(예: 철근/고철/소부재 등)", value="")
        risk_level = st.selectbox("위험도", ["LOW", "MID", "HIGH"], index=0)
        notes = st.text_area("비고/특이사항", height=80)
    with c2:
        date = st.text_input("일자", value=today_str())
        time_from = st.text_input("시간(시작)", value="06:00")
        time_to = st.text_input("시간(종료)", value="07:00")
        gate = st.text_input("사용 GATE", value="1GATE")
        vehicle_type = st.text_input("차량 종류", value="카고/집게차/덤프 등")
        vehicle_ton = st.text_input("차량 톤수", value="5")
        vehicle_count = st.number_input("대수", min_value=1, max_value=50, value=1, step=1)
        driver_name = st.text_input("운전원 성명", value="")
        driver_phone = st.text_input("운전원 연락처", value="")
        sic_training_url = st.text_input("방문자교육 URL(요청별, 비우면 기본값 사용)", value="")
    if st.button("요청 등록", type="primary", use_container_width=True):
        data = dict(
            kind=kind_val,
            company_name=company_name,
            item_name=item_name,
            item_type=item_type,
            work_type=work_type,
            date=date,
            time_from=time_from,
            time_to=time_to,
            gate=gate,
            vehicle_type=vehicle_type,
            vehicle_ton=vehicle_ton,
            vehicle_count=int(vehicle_count),
            driver_name=driver_name,
            driver_phone=driver_phone,
            notes=notes,
            requester_name=st.session_state.get("USER_NAME",""),
            requester_role=st.session_state.get("USER_ROLE",""),
            risk_level=risk_level,
            sic_training_url=sic_training_url.strip()
        )
        rid = req_insert(con, data)
        approvals_create_default(con, rid, kind_val)
        st.success(f"요청 등록 완료 · ID={rid}")
        st.session_state["RID_FOCUS"] = rid
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
def page_approval(con: sqlite3.Connection):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### ✍️ 승인(서명)")
    st.caption("서명은 '직접 서명'이 기본이며, 필요 시 이미지 업로드도 가능합니다.")
    is_admin = st.session_state.get("IS_ADMIN", False)
    role = st.session_state.get("USER_ROLE", "")
    inbox = approvals_inbox(con, role, is_admin)
    if not inbox:
        st.info("현재 대기 중인 승인 건이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    items = []
    for it in inbox:
        kind_txt = "반입" if it["kind"] == KIND_IN else "반출"
        items.append((f"[{it['role_required']}] {kind_txt} · {it.get('company_name','')} · {it.get('item_name','')} · {it.get('date','')} {it.get('time_from','')}~{it.get('time_to','')} · {it.get('gate','')}", it["id"]))
    label, approval_id = st.selectbox("승인 대상 선택", items, format_func=lambda x: x[0])
    approval_id = approval_id[1] if isinstance(approval_id, tuple) else approval_id
    target = next((x for x in inbox if x["id"] == approval_id), None)
    if not target:
        st.error("승인 데이터를 찾지 못했습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    rid = target["req_id"]
    req = req_get(con, rid)
    st.markdown(f"- 요청ID: **{rid}** / 상태: **{req.get('status','')}**")
    st.markdown(f"- 승인 단계: **{target['step_no']}** / 요구 역할: **{target['role_required']}**")
    st.divider()
    sign_path, stamp_path = ui_signature_block(rid, "서명 입력", key_prefix=f"ap_{approval_id}")
    reject_reason = st.text_area("반려 사유(반려 시 필수)", height=80)
    colA, colB = st.columns(2)
    with colA:
        if st.button("승인(서명 저장)", type="primary", use_container_width=True):
            if not sign_path:
                st.error("서명이 필요합니다. (직접 서명 저장 또는 이미지 업로드)")
            else:
                rid2, msg = approval_mark(con, approval_id, "APPROVE",
                                          st.session_state.get("USER_NAME",""),
                                          st.session_state.get("USER_ROLE",""),
                                          sign_path, stamp_path, "")
                st.success(msg)
                req2 = req_get(con, rid2)
                if req2 and req2["status"] == "APPROVED":
                    try:
                        generate_all_outputs(con, rid2)
                        st.success("승인본 PDF/허가증/QR 산출 완료")
                    except Exception as e:
                        st.warning(f"산출 생성 중 일부 실패: {e}")
                st.session_state["RID_FOCUS"] = rid2
                st.rerun()
    with colB:
        if st.button("반려", use_container_width=True):
            if not reject_reason.strip():
                st.error("반려 사유를 입력해주세요.")
            else:
                rid2, msg = approval_mark(con, approval_id, "REJECT",
                                          st.session_state.get("USER_NAME",""),
                                          st.session_state.get("USER_ROLE",""),
                                          None, None, reject_reason.strip())
                st.success(msg)
                st.session_state["RID_FOCUS"] = rid2
                st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
def page_execute(con: sqlite3.Connection):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📸 실행 등록(사진 + 점검카드)")
    st.caption("필수 3종은 '직접 촬영'이 기본, 추가 사진은 업로드(옵션)입니다.")
    candidates = req_list(con, None, None, 500)
    if not candidates:
        st.info("요청이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    rid_focus = st.session_state.get("RID_FOCUS","")
    default_index = 0
    if rid_focus:
        for i, r in enumerate(candidates):
            if r["id"] == rid_focus:
                default_index = i
                break
    items = [(f"{r['id'][:8]} · {'반입' if r['kind']==KIND_IN else '반출'} · {r.get('company_name','')} · {r.get('item_name','')} · {r.get('status','')}", r["id"]) for r in candidates]
    sel = st.selectbox("대상 요청 선택", items, index=default_index)
    rid = sel[1] if isinstance(sel, tuple) else sel
    req = req_get(con, rid)
    if not req:
        st.error("요청을 찾지 못했습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    if req["status"] in ["APPROVED","EXECUTING","DONE"]:
        req_update_status(con, rid, "EXECUTING")
    else:
        st.warning("이 건은 아직 승인 완료가 아닙니다. (승인 완료 후 실행 등록 권장)")
    st.divider()
    ui_photo_capture_required(con, rid)
    ui_photo_optional_upload(con, rid)
    photos = photos_for_req(con, rid)
    ok = required_photos_ok(con, rid)
    st.markdown(f"- 필수 3종 충족: {'✅' if ok else '❌'}")
    if photos:
        with st.expander("업로드/촬영된 사진 목록 보기"):
            for p in photos:
                st.write(f"- [{p['slot_key']}] {p['label']} · {Path(p['file_path']).name}")
    st.divider()
    st.markdown("#### 3) 자재 상/하차 점검카드")
    exec_row = execution_get(con, rid)
    existing = {}
    if exec_row and exec_row.get("check_json"):
        try:
            existing = json.loads(exec_row["check_json"])
        except Exception:
            existing = {}
    check_json = {}
    for key, title, hint in CHECK_ITEMS:
        default_val = existing.get(key,"")
        if key == "attendees":
            check_json[key] = st.text_input(title, value=default_val or hint)
        else:
            check_json[key] = st.text_input(title, value=default_val)
    notes = st.text_area("실행 메모(옵션)", value=(exec_row.get("notes","") if exec_row else ""), height=80)
    if st.button("실행 등록(점검+사진 검증)", type="primary", use_container_width=True):
        if not ok:
            st.error("필수 3종 사진이 모두 등록되어야 실행 등록이 가능합니다. (추가사진은 옵션)")
        else:
            execution_upsert(con, rid, st.session_state.get("USER_NAME",""), st.session_state.get("USER_ROLE",""), check_json, notes)
            req_update_status(con, rid, "DONE")
            try:
                generate_all_outputs(con, rid)
                st.success("실행 등록 완료 + 산출물(PDF/QR/ZIP) 생성 완료")
            except Exception as e:
                st.warning(f"산출 생성 중 일부 실패: {e}")
            st.session_state["RID_FOCUS"] = rid
            st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
def page_outputs(con: sqlite3.Connection):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📦 산출물/다운로드/공유")
    allreq = req_list(con, None, None, 500)
    if not allreq:
        st.info("요청이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    rid_focus = st.session_state.get("RID_FOCUS","")
    default_index = 0
    if rid_focus:
        for i, r in enumerate(allreq):
            if r["id"] == rid_focus:
                default_index = i
                break
    items = [(f"{r['id'][:8]} · {'반입' if r['kind']==KIND_IN else '반출'} · {r.get('company_name','')} · {r.get('item_name','')} · {r.get('status','')}", r["id"]) for r in allreq]
    sel = st.selectbox("대상 선택", items, index=default_index)
    rid = sel[1] if isinstance(sel, tuple) else sel
    req = req_get(con, rid)
    outs = outputs_get(con, rid)
    if st.button("산출물 재생성", type="primary"):
        try:
            generate_all_outputs(con, rid)
            st.success("재생성 완료")
        except Exception as e:
            st.error(f"재생성 실패: {e}")
        st.rerun()
    st.divider()
    st.markdown("#### 산출물 생성 위치(통합)")
    st.code(str(path_output_root()), language="text")
    if not outs:
        st.warning("아직 산출물이 없습니다. (승인 완료 또는 실행 등록 후 생성됩니다)")
    else:
        st.markdown("#### 파일")
        def show_file(key: str, title: str):
            p = outs.get(key,"")
            if p and Path(p).exists():
                st.markdown(f"- **{title}**: {Path(p).name}", unsafe_allow_html=True)
                st.markdown(b64_download_link(Path(p), f"⬇️ {title} 다운로드"), unsafe_allow_html=True)
            else:
                st.markdown(f"- {title}: (없음)")
        show_file("plan_pdf_path", "계획서 PDF")
        show_file("permit_pdf_path", "허가증 PDF(QR)")
        show_file("check_pdf_path", "점검카드 PDF")
        show_file("exec_pdf_path", "실행요약 PDF")
        show_file("bundle_pdf_path", "번들 안내 PDF")
        show_file("zip_path", "ZIP(일괄)")
    st.divider()
    st.markdown("#### 카톡 단톡 공유문구(붙여넣기용)")
    st.text_area("복사해서 단톡방에 붙여넣으세요", value=make_share_text(req, outs), height=220)
    st.markdown("</div>", unsafe_allow_html=True)
def page_ledger(con: sqlite3.Connection):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 📚 대장(전체 이력)")
    rows = req_list(con, None, None, 500)
    if not rows:
        st.info("데이터가 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    c1, c2, c3 = st.columns(3)
    with c1:
        f_kind = st.selectbox("구분", ["ALL","IN","OUT"], index=0)
    with c2:
        f_status = st.selectbox("상태", ["ALL"]+REQ_STATUS, index=0)
    with c3:
        q = st.text_input("검색(회사/자재/ID)", value="").strip()
    def ok(r):
        if f_kind != "ALL" and r["kind"] != f_kind: return False
        if f_status != "ALL" and r["status"] != f_status: return False
        if q:
            s = f"{r['id']} {r.get('company_name','')} {r.get('item_name','')}"
            if q.lower() not in s.lower(): return False
        return True
    filtered = [r for r in rows if ok(r)]
    st.write(f"표시 {len(filtered)}건 / 전체 {len(rows)}건")
    for r in filtered[:200]:
        kind_txt = "반입" if r["kind"]==KIND_IN else "반출"
        st.markdown(f"""
        <div style="border:1px solid #e2e8f0; background:#fff; border-radius:14px; padding:10px 12px; margin-bottom:8px;">
          <div style="font-weight:800;">{kind_txt} · {r.get('company_name','')} · {r.get('item_name','')}</div>
          <div class="small muted">ID: {r['id']} · {r.get('date','')} {r.get('time_from','')}~{r.get('time_to','')} · GATE:{r.get('gate','')} · 상태:{r.get('status','')}</div>
        </div>
        """, unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)
def page_admin(con: sqlite3.Connection):
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.markdown("### 🛠 관리자 설정")
    if not st.session_state.get("IS_ADMIN", False):
        st.warning("관리자 모드로 로그인해야 접근 가능합니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        return
    site_name = st.text_input("현장명", value=settings_get(con,"site_name",DEFAULT_SITE_NAME))
    site_pin = st.text_input("현장 PIN(변경 권장)", value=settings_get(con,"site_pin",DEFAULT_SITE_PIN))
    admin_pin = st.text_input("Admin PIN(변경 권장)", value=settings_get(con,"admin_pin",DEFAULT_ADMIN_PIN))
    sic_default = st.text_input("방문자교육 URL 기본값", value=settings_get(con,"sic_training_url_default","https://example.com/visitor-training"))
    st.divider()
    st.markdown("#### 승인 라우팅(현장 방식)")
    routing = routing_get(con)
    in_route = st.text_input("반입(IN) 승인 순서(쉼표구분)", value=",".join(routing.get("IN",["공사"])))
    out_route = st.text_input("반출(OUT) 승인 순서(쉼표구분)", value=",".join(routing.get("OUT",["안전","공사"])))
    st.divider()
    st.markdown("#### 외부/내부 공유용 Base URL")
    public_base_url = st.text_input("PUBLIC_BASE_URL", value=settings_get(con,"public_base_url",""))
    if st.button("설정 저장", type="primary", use_container_width=True):
        settings_set(con, "site_name", site_name.strip() or DEFAULT_SITE_NAME)
        settings_set(con, "site_pin", site_pin.strip() or DEFAULT_SITE_PIN)
        settings_set(con, "admin_pin", admin_pin.strip() or DEFAULT_ADMIN_PIN)
        settings_set(con, "sic_training_url_default", sic_default.strip() or "https://example.com/visitor-training")
        def parse_route(s: str) -> List[str]:
            parts = [x.strip() for x in s.split(",") if x.strip()]
            parts = [p for p in parts if p in ROLES]
            return parts or ["공사"]
        routing2 = {"IN": parse_route(in_route), "OUT": parse_route(out_route)}
        settings_set(con, "approval_routing_json", json.dumps(routing2, ensure_ascii=False))
        settings_set(con, "public_base_url", public_base_url.strip())
        st.session_state["PUBLIC_BASE_URL"] = public_base_url.strip()
        st.success("저장 완료")
        st.rerun()
    st.divider()
    if st.button("⚠️ 산출물 폴더(output) 비우기(테스트용)", use_container_width=True):
        out = path_output_root()
        if out.exists():
            shutil.rmtree(out)
        ensure_dir(out)
        st.success("output 폴더 초기화 완료")
        st.rerun()
    st.markdown("</div>", unsafe_allow_html=True)
# -------------------------
# Main
# -------------------------
def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="✅", layout="wide")
    inject_css()
    if "AUTH_OK" not in st.session_state:
        auth_reset()
    if "BASE_DIR" not in st.session_state:
        st.session_state["BASE_DIR"] = DEFAULT_BASE_DIR
    con = con_open()
    db_init_and_migrate(con)
    if "PUBLIC_BASE_URL" not in st.session_state:
        st.session_state["PUBLIC_BASE_URL"] = settings_get(con, "public_base_url", "")
    with st.sidebar:
        st.markdown("## ⚙️ 사용자/환경")
        st.text_input("BASE 폴더(통합)", value=st.session_state["BASE_DIR"], key="base_dir_ui")
        if st.button("BASE 폴더 적용"):
            st.session_state["BASE_DIR"] = st.session_state["base_dir_ui"].strip() or DEFAULT_BASE_DIR
            st.rerun()
        st.markdown("---")
        st.markdown("### 현재 사용자")
        if st.session_state.get("AUTH_OK", False):
            st.write(st.session_state.get("USER_NAME",""))
            st.write(st.session_state.get("USER_ROLE",""))
            st.write("관리자" if st.session_state.get("IS_ADMIN",False) else "일반")
            if st.button("로그아웃"):
                auth_reset()
                st.rerun()
        else:
            st.caption("로그인 필요")
        st.markdown("---")
        st.caption("산출물 위치")
        st.code(str(path_output_root()), language="text")
        if not CANVAS_AVAILABLE:
            st.warning("직접서명(캔버스) 사용 시 설치 필요:\n- streamlit-drawable-canvas\n- pillow")
    if not st.session_state.get("AUTH_OK", False):
        page_login(con)
        return
    ui_header(con)
    tabs = st.tabs(["홈", "요청", "승인", "실행", "산출물", "대장", "관리자"])
    with tabs[0]:
        st.markdown('<div class="card">', unsafe_allow_html=True)
        st.markdown("### 🏠 홈")
        st.markdown("""
        - **요청**: 협력사 입력
        - **승인**: 안전/공사/경비 서명 승인(직접서명 기본)
        - **실행**: 필수 3종 '직접 촬영' + 점검카드 + (추가사진 업로드 옵션)
        - **산출물**: PDF/QR/ZIP 생성 + 단톡 붙여넣기용 공유문구 제공
        """)
        st.markdown("</div>", unsafe_allow_html=True)
    with tabs[1]:
        page_request(con)
    with tabs[2]:
        page_approval(con)
    with tabs[3]:
        page_execute(con)
    with tabs[4]:
        page_outputs(con)
    with tabs[5]:
        page_ledger(con)
    with tabs[6]:
        page_admin(con)
if __name__ == "__main__":
    main()
