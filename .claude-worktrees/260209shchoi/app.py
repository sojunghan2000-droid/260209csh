# ============================================================
# Material Gate Tool v2.4.0 (권한/모바일/단톡/통합PDF 완료본)
# - B안: 현장 PIN + 역할(Role) 기반 권한관리
# - 단톡 문구: 최근 문구 항상 표시(사라짐 방지)
# - ZIP 불편 해결: 통합 PDF PACKET 생성(한번에 보기)
# ============================================================

import os, json, zipfile, sqlite3, socket, html
from pathlib import Path
from datetime import datetime, date
import pandas as pd
import qrcode
from PIL import Image

import streamlit as st
import streamlit.components.v1 as components
from streamlit_drawable_canvas import st_canvas

from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader


# -----------------------------
# 0) 공유폴더(현장 공용) - 서버PC 기준
# -----------------------------
BASE = Path(os.environ.get("MATERIAL_BASE", "./MaterialToolShared"))
DATA = BASE / "data"
OUT  = BASE / "output"
PDFD = OUT / "pdf"
QRD  = OUT / "qr"
ZIPD = OUT / "zip"
PHOTOD = OUT / "photos"
SIGND = OUT / "sign"
CHECKD = OUT / "check"
PACKD  = OUT / "packet"

for p in [DATA, OUT, PDFD, QRD, ZIPD, PHOTOD, SIGND, CHECKD, PACKD]:
    p.mkdir(parents=True, exist_ok=True)

DB = DATA / "gate.db"
SITE_NAME = "자재 반출입 승인"
PORT = 8501

VISITOR_TRAINING_URL_DEFAULT = "https://YOUR-SIC-TRAINING-LINK"  # ✅ 현장 방문자교육 링크로 교체


# -----------------------------
# ✅ 0-1) 권한(B안)
# -----------------------------
SITE_PIN = "260209"        # ✅ 현장 공통 접속 PIN (6자리 권장)
ADMIN_PIN = "9999"         # ✅ 관리자 추가 인증 PIN (승인/설정)
ALLOW_EXEC_ROLE = {"공무", "안전", "관리자"}    # 실행(사진/점검) 권한
ALLOW_PHOTO_ROLE = {"공무", "안전", "관리자"}   # 사진 등록 권한
ALLOW_APPROVE_ROLE = {"관리자"}                 # 승인 권한


# -----------------------------
# 1) DB
# -----------------------------
def db():
    con = sqlite3.connect(DB, timeout=30, isolation_level=None)
    con.execute("PRAGMA journal_mode=WAL;")
    con.execute("PRAGMA synchronous=NORMAL;")
    return con

def ensure_column(con, table, col, coltype):
    cols = [r[1] for r in con.execute(f"PRAGMA table_info({table});").fetchall()]
    if col not in cols:
        con.execute(f"ALTER TABLE {table} ADD COLUMN {col} {coltype};")

def init_db():
    with db() as con:
        con.execute("""
        CREATE TABLE IF NOT EXISTS requests(
            rid TEXT PRIMARY KEY,
            io_type TEXT,
            company TEXT,
            material TEXT,
            vehicle TEXT,
            driver_phone TEXT,
            gate TEXT,
            work_date TEXT,
            work_time TEXT,
            note TEXT,
            risk TEXT,
            status TEXT,
            created_at TEXT,
            created_by TEXT,
            approved_at TEXT,
            approved_by TEXT,
            exec_at TEXT,
            exec_by TEXT
        );
        """)
        con.execute("""
        CREATE TABLE IF NOT EXISTS events(
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            ts TEXT,
            rid TEXT,
            event TEXT,
            actor TEXT,
            payload TEXT
        );
        """)
init_db()

def log_event(rid: str, event: str, actor: str, payload: dict | None = None):
    payload_json = json.dumps(payload or {}, ensure_ascii=False)
    with db() as con:
        con.execute(
            "INSERT INTO events(ts,rid,event,actor,payload) VALUES(?,?,?,?,?)",
            (datetime.now().isoformat(timespec="seconds"), rid, event, actor, payload_json)
        )

def get_last_kakao_msg():
    with db() as con:
        row = con.execute("""
            SELECT payload FROM events
            WHERE event='KAKAO_MSG'
            ORDER BY id DESC LIMIT 1
        """).fetchone()
    if not row:
        return ""
    try:
        return json.loads(row[0]).get("text","")
    except:
        return ""

def new_rid():
    return "REQ_" + datetime.now().strftime("%Y%m%d_%H%M%S") + "_" + str(os.getpid())[-3:]

def fetch_requests(limit=600):
    with db() as con:
        rows = con.execute("""
            SELECT rid, io_type, company, material, vehicle, driver_phone, gate, work_date, work_time,
                   risk, status, created_at, created_by, approved_at, approved_by, exec_at, exec_by
            FROM requests
            ORDER BY created_at DESC
            LIMIT ?
        """, (limit,)).fetchall()
    cols = ["rid","io_type","company","material","vehicle","driver_phone","gate","work_date","work_time",
            "risk","status","created_at","created_by","approved_at","approved_by","exec_at","exec_by"]
    return pd.DataFrame(rows, columns=cols)

def get_request(rid: str):
    with db() as con:
        r = con.execute("""
            SELECT rid, io_type, company, material, vehicle, driver_phone, gate, work_date, work_time, note, risk, status,
                   created_at, created_by, approved_at, approved_by, exec_at, exec_by
            FROM requests WHERE rid=?
        """, (rid,)).fetchone()
    if not r:
        return None
    keys = ["rid","io_type","company","material","vehicle","driver_phone","gate","work_date","work_time","note","risk","status",
            "created_at","created_by","approved_at","approved_by","exec_at","exec_by"]
    return dict(zip(keys, r))


# -----------------------------
# 2) QR / 서버주소
# -----------------------------
def local_ip_candidates():
    ips=set()
    try:
        host = socket.gethostname()
        for info in socket.getaddrinfo(host, None):
            ip = info[4][0]
            if "." in ip and not ip.startswith("127."):
                ips.add(ip)
    except:
        pass
    if not ips:
        ips.add("192.168.0.10")
    return sorted(list(ips))

def make_qr_png(text: str, out_path: Path):
    img = qrcode.make(text)
    img.save(out_path)

def server_url(ip: str):
    return f"http://{ip}:{PORT}"


# -----------------------------
# 3) 파일 저장 (사진/서명)
# -----------------------------
def save_upload(rid: str, tag: str, up) -> str:
    if up is None:
        return ""
    folder = PHOTOD / rid
    folder.mkdir(parents=True, exist_ok=True)
    ext = up.name.split(".")[-1].lower()
    outp = folder / f"{tag}_{datetime.now().strftime('%H%M%S')}.{ext}"
    outp.write_bytes(up.getbuffer())
    return str(outp)

def save_camera(rid: str, tag: str, cam) -> str:
    if cam is None:
        return ""
    folder = PHOTOD / rid
    folder.mkdir(parents=True, exist_ok=True)
    outp = folder / f"{tag}_{datetime.now().strftime('%H%M%S')}.jpg"
    outp.write_bytes(cam.getvalue())
    return str(outp)

def save_cam_or_upload(rid: str, tag: str, cam, up) -> str:
    p = save_camera(rid, tag, cam)
    if p:
        return p
    return save_upload(rid, tag, up)

def sign_path(rid: str) -> Path:
    return SIGND / f"{rid}.png"


# -----------------------------
# 4) 단톡 복사 UI
# -----------------------------
def copy_box(text: str, title="단톡 공유 문구"):
    safe = html.escape(text)
    components.html(f"""
    <div style="background:#FFFFFF;border:1px solid #E5E7EB;border-radius:18px;padding:14px;margin-top:8px;
                box-shadow:0 6px 18px rgba(17,24,39,.08);">
      <div style="font-weight:900;margin-bottom:10px;color:#111827;font-size:15px;">{html.escape(title)}</div>
      <textarea id="kakaoText" style="width:100%;height:170px;border-radius:14px;border:1px solid #E5E7EB;
                background:#F9FAFB;color:#111827;padding:12px;resize:vertical;font-size:13px;line-height:1.45;">{safe}</textarea>
      <div style="display:flex;gap:10px;justify-content:flex-end;margin-top:10px;">
        <button id="copyBtn" style="padding:10px 14px;border-radius:14px;border:1px solid rgba(37,99,235,.25);
          background:linear-gradient(180deg, rgba(37,99,235,.95), rgba(37,99,235,.78));
          color:white;font-weight:900;cursor:pointer;">📋 복사</button>
      </div>
      <div id="copied" style="display:none;color:#059669;font-weight:900;margin-top:8px;">✅ 복사 완료</div>
    </div>
    <script>
      const btn=document.getElementById("copyBtn");
      btn.addEventListener("click", async ()=> {{
        const t=document.getElementById("kakaoText");
        t.select(); t.setSelectionRange(0, 999999);
        try {{ await navigator.clipboard.writeText(t.value); }}
        catch(e) {{ document.execCommand('copy'); }}
        document.getElementById("copied").style.display="block";
        setTimeout(()=>document.getElementById("copied").style.display="none", 1700);
      }});
    </script>
    """, height=292)

def msg_template(title: str, r: dict, files: dict | None = None, extra: str = ""):
    files = files or {}
    lines = []
    lines.append(f"[{SITE_NAME}] {title}")
    lines.append(f"- 요청ID: {r['rid']}")
    lines.append(f"- 구분/상태/위험도: {r['io_type']} / {r['status']} / {r.get('risk','')}")
    lines.append(f"- 협력회사: {r['company']}")
    lines.append(f"- 자재: {r['material']}")
    lines.append(f"- 차량/연락처: {r['vehicle']} / {r.get('driver_phone','')}")
    lines.append(f"- GATE/시간: {r['gate']} / {r['work_date']} {r['work_time']}")
    if r.get("approved_by"):
        lines.append(f"- 승인: {r.get('approved_by','')} ({r.get('approved_at','')})")
    if files.get("packet"):       lines.append(f"- 통합PDF(PACKET): {files['packet']}")
    if files.get("approval_pdf"): lines.append(f"- 승인서: {files['approval_pdf']}")
    if files.get("permit_pdf"):   lines.append(f"- 허가증(QR): {files['permit_pdf']}")
    if files.get("check_pdf"):    lines.append(f"- 점검카드: {files['check_pdf']}")
    if files.get("exec_pdf"):     lines.append(f"- 실행기록(사진): {files['exec_pdf']}")
    if files.get("zip"):          lines.append(f"- 공유팩(zip): {files['zip']}")
    lines.append(f"- 사진폴더(서버PC): {PHOTOD / r['rid']}")
    if extra.strip(): lines.append(f"- 비고: {extra.strip()}")
    return "\n".join(lines)


# -----------------------------
# 5) PDF 생성 (승인서 / 허가증 / 점검카드 / 실행기록) + PACKET
# -----------------------------
def gen_approval_pdf(r: dict) -> str:
    rid = r["rid"]
    out = PDFD / f"{rid}_approval.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 805, "자재 반출입 승인서")
    c.setFont("Helvetica", 10)
    c.drawString(50, 784, f"현장: {SITE_NAME}    요청ID: {rid}")
    c.drawString(50, 766, f"구분: {r['io_type']}    상태: {r['status']}    위험도: {r.get('risk','')}")
    c.drawString(50, 748, f"협력회사: {r['company']}    자재: {r['material']}")
    c.drawString(50, 730, f"차량: {r['vehicle']}    운전원: {r.get('driver_phone','')}")
    c.drawString(50, 712, f"GATE/시간: {r['gate']} / {r['work_date']} {r['work_time']}")
    c.drawString(50, 694, f"비고: {(r.get('note','') or '')[:90]}")

    c.drawString(50, 660, f"신청: {r.get('created_by','')}  ({r.get('created_at','')})")
    c.drawString(50, 642, f"승인: {r.get('approved_by','')}  ({r.get('approved_at','')})")

    sp = sign_path(rid)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 610, "전자서명(승인자)")
    c.rect(50, 545, 160, 55)
    if sp.exists():
        try:
            im = Image.open(sp)
            c.drawImage(ImageReader(im), 52, 547, width=156, height=51, preserveAspectRatio=True, anchor='c')
        except:
            c.setFont("Helvetica", 10)
            c.drawString(60, 570, "서명 이미지 로드 실패")

    qr_file = QRD / f"{rid}_req.png"
    make_qr_png(rid, qr_file)
    c.drawString(350, 610, "게이트 확인 QR(요청ID)")
    c.rect(350, 510, 170, 170)
    try:
        c.drawImage(str(qr_file), 360, 520, width=150, height=150, preserveAspectRatio=True, anchor='c')
    except:
        pass

    c.setFont("Helvetica", 9)
    c.drawString(50, 55, f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.save()
    return str(out)

def gen_entry_permit_pdf(r: dict, training_url: str) -> str:
    rid = r["rid"]
    out = PDFD / f"{rid}_permit.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)

    c.setFont("Helvetica-Bold", 16)
    c.drawString(70, 790, "자재 차량 진출입 허가증")

    c.setFont("Helvetica", 10)
    c.drawString(70, 770, f"요청ID: {rid} | 구분: {r['io_type']} | 일자/시간: {r['work_date']} {r['work_time']}")
    c.drawString(70, 754, f"GATE: {r['gate']} | 차량번호: {r['vehicle']}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(70, 720, "입고 회사명")
    c.rect(70, 690, 300, 26)
    c.setFont("Helvetica", 11)
    c.drawString(78, 698, r.get("company",""))

    c.setFont("Helvetica-Bold", 11)
    c.drawString(390, 720, "운전원 연락처")
    c.rect(390, 690, 150, 26)
    c.setFont("Helvetica", 11)
    c.drawString(398, 698, r.get("driver_phone",""))

    c.setFont("Helvetica-Bold", 12)
    c.drawString(70, 650, "★ 필수 준수사항 ★")
    c.setFont("Helvetica", 11)
    items = [
        "1. 하차 시 안전모 착용",
        "2. 운전석 유리창 개방 필수",
        "3. 현장 내 속도 10km/h 이내 주행",
        "4. 비상등 상시 점등",
        "5. 주정차 시, 고임목 설치",
        "6. 유도원 통제하에 운행",
    ]
    y = 625
    for it in items:
        c.drawString(80, y, it)
        y -= 18

    qr_file = QRD / f"{rid}_training.png"
    make_qr_png(training_url, qr_file)

    c.setFont("Helvetica-Bold", 11)
    c.drawString(70, 475, "{ SIC 방문자교육 }")
    c.rect(70, 320, 150, 150)
    try:
        c.drawImage(str(qr_file), 78, 328, width=134, height=134, preserveAspectRatio=True, anchor="c")
    except:
        pass
    c.setFont("Helvetica", 9)
    c.drawString(70, 305, "QR코드 인식 후 이수")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(260, 420, "운전원 확인:")
    c.rect(350, 395, 190, 40)
    c.drawString(260, 355, "담당자 확인:")
    c.rect(350, 330, 190, 40)

    sp = sign_path(rid)
    if sp.exists():
        try:
            im = Image.open(sp)
            c.drawImage(ImageReader(im), 352, 332, width=186, height=36, preserveAspectRatio=True, anchor="c")
        except:
            pass

    c.setFont("Helvetica", 9)
    c.drawString(70, 55, f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.save()
    return str(out)

def gen_check_pdf(r: dict, checklist: dict, attendees: dict) -> str:
    rid = r["rid"]
    out = CHECKD / f"{rid}_check.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 805, "자재 상/하차 점검카드")
    c.setFont("Helvetica", 10)
    c.drawString(50, 784, f"요청ID: {rid}   구분: {r['io_type']}   차량: {r['vehicle']}")
    c.drawString(50, 768, f"협력회사: {r['company']}   자재: {r['material']}   GATE/시간: {r['gate']} / {r['work_date']} {r['work_time']}")

    y=735
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "0. 필수 참석자")
    y-=18
    c.setFont("Helvetica", 10)
    base = ["협력회사 담당자","장비운전원","차량운전원","유도원","안전보조원/감시단"]
    for p in base:
        ok = bool(attendees.get(p, False))
        c.drawString(60, y, f"□ {p}   ({'참석' if ok else '미확인'})")
        y-=14

    y-=12
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, y, "1~10. 점검 항목")
    y-=18
    c.setFont("Helvetica", 10)

    items = [
        (1, "협력회사", r["company"]),
        (2, "화물/자재 종류", r["material"]),
        (3, "화물 당 2개소 이상 결속 여부 확인", checklist.get("3", True)),
        (4, "고정용 로프 및 밴딩 상태 점검 여부", checklist.get("4", True)),
        (5, "화물 높이 4M 이하 적재, 낙하위험 발생여부", checklist.get("5", True)),
        (6, "적재함 폭 초과 상차 금지, 적재함 닫힘 여부", checklist.get("6", True)),
        (7, "자재차량 고임목 설치 여부", checklist.get("7", True)),
        (8, "적재하중 이내 적재 여부", checklist.get("8", True)),
        (9, "화물 무게중심 확인(한쪽으로 쏠림 여부)", checklist.get("9", True)),
        (10,"자재 하역구간 구획 및 통제 여부", checklist.get("10", True)),
    ]
    for no, txt, val in items:
        v = "OK" if (val is True) else ("FAIL" if (val is False) else str(val))
        c.drawString(50, y, f"{no}. {txt}: {v}")
        y-=16
        if y<80:
            c.showPage(); y=805

    c.setFont("Helvetica", 9)
    c.drawString(50, 55, f"작성/확인: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.save()
    return str(out)

def gen_exec_pdf(r: dict, photo_paths: dict) -> str:
    rid = r["rid"]
    out = PDFD / f"{rid}_exec.pdf"
    c = canvas.Canvas(str(out), pagesize=A4)

    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 805, "자재 반출입 실행 기록(사진)")
    c.setFont("Helvetica", 10)
    c.drawString(50, 784, f"요청ID: {rid}   구분: {r['io_type']}   상태: {r['status']}")
    c.drawString(50, 768, f"협력회사: {r['company']}   자재: {r['material']}   차량: {r['vehicle']}")
    c.drawString(50, 752, f"GATE/시간: {r['gate']} / {r['work_date']} {r['work_time']}")

    slots = [("상차 전", photo_paths.get("before","")),
             ("상차 후", photo_paths.get("after","")),
             ("결속/로프/밴딩", photo_paths.get("tie",""))]
    boxes = [(50, 480, 250, 230),
             (330,480, 250, 230),
             (50, 210, 530, 230)]

    def draw_img(label, pth, x,y,w,h):
        c.setFont("Helvetica-Bold", 11)
        c.drawString(x, y+h+10, label)
        c.rect(x, y, w, h)
        if pth and Path(pth).exists():
            try:
                im = Image.open(pth)
                c.drawImage(ImageReader(im), x+2, y+2, width=w-4, height=h-4, preserveAspectRatio=True, anchor='c')
            except:
                c.setFont("Helvetica", 10)
                c.drawString(x+10, y+h/2, "이미지 로드 실패")
        else:
            c.setFont("Helvetica", 10)
            c.drawString(x+10, y+h/2, "미등록")

    for (label, pth), (x,y,w,h) in zip(slots, boxes):
        draw_img(label, pth, x,y,w,h)

    c.setFont("Helvetica", 9)
    c.drawString(50, 55, f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.save()
    return str(out)

def gen_packet_pdf(r: dict, training_url: str,
                   checklist: dict | None = None,
                   attendees: dict | None = None,
                   photo_paths: dict | None = None,
                   mode: str = "LIGHT") -> str:
    """
    PACKET = 한번에 보기용 통합 PDF
    mode=LIGHT : 승인서 + 허가증
    mode=FULL  : 승인서 + 허가증 + 점검카드 + 실행사진(3)
    """
    rid = r["rid"]
    out = PACKD / (f"{rid}_PACKET_LIGHT.pdf" if mode=="LIGHT" else f"{rid}_PACKET_FULL.pdf")
    c = canvas.Canvas(str(out), pagesize=A4)

    # 표지/요약
    c.setFont("Helvetica-Bold", 16)
    c.drawString(50, 805, "자재 반출입 통합 문서(PACKET)")
    c.setFont("Helvetica", 10)
    c.drawString(50, 785, f"요청ID: {rid} | 구분: {r['io_type']} | 상태: {r['status']} | 위험도: {r.get('risk','')}")
    c.drawString(50, 770, f"협력회사: {r['company']} | 자재: {r['material']}")
    c.drawString(50, 755, f"차량/연락처: {r['vehicle']} / {r.get('driver_phone','')}")
    c.drawString(50, 740, f"GATE/시간: {r['gate']} / {r['work_date']} {r['work_time']}")

    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 708, "포함 문서")
    c.setFont("Helvetica", 10)
    lines = ["- 승인서", "- 허가증(QR)"]
    if mode=="FULL":
        lines += ["- 상/하차 점검카드", "- 실행사진(상차 전/후/결속)"]
    y=690
    for s in lines:
        c.drawString(60, y, s); y-=14

    c.setFont("Helvetica", 9)
    c.drawString(50, 60, f"생성: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    c.showPage()

    # 1) 승인서 페이지(간략 재구성)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 805, "1. 승인서(요약)")
    c.setFont("Helvetica", 10)
    c.drawString(50, 780, f"신청: {r.get('created_by','')} ({r.get('created_at','')})")
    c.drawString(50, 765, f"승인: {r.get('approved_by','')} ({r.get('approved_at','')})")

    sp = sign_path(rid)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 730, "전자서명(승인자)")
    c.rect(50, 665, 180, 55)
    if sp.exists():
        try:
            im = Image.open(sp)
            c.drawImage(ImageReader(im), 52, 667, width=176, height=51, preserveAspectRatio=True, anchor='c')
        except:
            pass

    req_qr = QRD / f"{rid}_req.png"
    make_qr_png(rid, req_qr)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(300, 730, "게이트 확인 QR(요청ID)")
    c.rect(300, 640, 220, 220)
    try:
        c.drawImage(str(req_qr), 325, 665, width=170, height=170, preserveAspectRatio=True, anchor="c")
    except:
        pass

    c.showPage()

    # 2) 허가증 페이지(요약)
    c.setFont("Helvetica-Bold", 14)
    c.drawString(50, 805, "2. 진출입 허가증(QR)")
    c.setFont("Helvetica", 10)
    c.drawString(50, 780, "필수 준수사항: 하차 안전모 / 유리창 개방 / 10km/h / 비상등 / 고임목 / 유도원 통제")

    train_qr = QRD / f"{rid}_training.png"
    make_qr_png(training_url, train_qr)
    c.setFont("Helvetica-Bold", 11)
    c.drawString(50, 740, "{ SIC 방문자교육 }")
    c.rect(50, 560, 220, 220)
    try:
        c.drawImage(str(train_qr), 75, 585, width=170, height=170, preserveAspectRatio=True, anchor="c")
    except:
        pass
    c.setFont("Helvetica", 10)
    c.drawString(300, 720, f"입고 회사명: {r.get('company','')}")
    c.drawString(300, 700, f"운전원 연락처: {r.get('driver_phone','')}")
    c.drawString(300, 680, f"차량번호: {r.get('vehicle','')}")
    c.drawString(300, 660, f"GATE/시간: {r.get('gate','')} / {r.get('work_date','')} {r.get('work_time','')}")

    c.showPage()

    if mode=="FULL":
        # 3) 점검카드
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 805, "3. 상/하차 점검카드")
        checklist = checklist or {}
        attendees = attendees or {}
        c.setFont("Helvetica", 10)

        y = 775
        c.drawString(50, y, "0) 필수 참석자"); y-=18
        base = ["협력회사 담당자","장비운전원","차량운전원","유도원","안전보조원/감시단"]
        for p in base:
            ok = bool(attendees.get(p, False))
            c.drawString(60, y, f"- {p}: {'참석' if ok else '미확인'}")
            y-=14

        y-=10
        c.drawString(50, y, "3~10) 핵심 점검"); y-=18
        mapping = {
            "3":"화물 당 2개소 이상 결속 여부 확인",
            "4":"고정용 로프 및 밴딩 상태 점검 여부",
            "5":"화물 높이 4M 이하 적재, 낙하위험 발생여부",
            "6":"적재함 폭 초과 상차 금지, 적재함 닫힘 여부",
            "7":"자재차량 고임목 설치 여부",
            "8":"적재하중 이내 적재 여부",
            "9":"화물 무게중심 확인(한쪽으로 쏠림 여부)",
            "10":"자재 하역구간 구획 및 통제 여부",
        }
        for k,txt in mapping.items():
            v = checklist.get(k, True)
            c.drawString(60, y, f"- {txt}: {'OK' if v else 'FAIL'}")
            y-=14

        c.showPage()

        # 4) 실행사진
        c.setFont("Helvetica-Bold", 14)
        c.drawString(50, 805, "4. 실행 사진(상차 전/후/결속)")
        photo_paths = photo_paths or {}
        slots = [("상차 전", photo_paths.get("before","")),
                 ("상차 후", photo_paths.get("after","")),
                 ("결속/로프/밴딩", photo_paths.get("tie",""))]
        boxes = [(50, 480, 250, 230),
                 (330,480, 250, 230),
                 (50, 210, 530, 230)]

        def draw_img(label, pth, x,y,w,h):
            c.setFont("Helvetica-Bold", 11)
            c.drawString(x, y+h+10, label)
            c.rect(x, y, w, h)
            if pth and Path(pth).exists():
                try:
                    im = Image.open(pth)
                    c.drawImage(ImageReader(im), x+2, y+2, width=w-4, height=h-4, preserveAspectRatio=True, anchor='c')
                except:
                    c.setFont("Helvetica", 10)
                    c.drawString(x+10, y+h/2, "이미지 로드 실패")
            else:
                c.setFont("Helvetica", 10)
                c.drawString(x+10, y+h/2, "미등록")

        for (label, pth), (x,y,w,h) in zip(slots, boxes):
            draw_img(label, pth, x,y,w,h)

    c.save()
    return str(out)


# -----------------------------
# 6) ZIP 공유팩(옵션)
# -----------------------------
def make_share_zip(rid: str, files: list[str]) -> str:
    out = ZIPD / f"{rid}_sharepack.zip"
    with zipfile.ZipFile(out, "w", compression=zipfile.ZIP_DEFLATED) as z:
        for f in files:
            if f and Path(f).exists():
                z.write(f, arcname=Path(f).name)
        pdir = PHOTOD / rid
        if pdir.exists():
            for fp in pdir.glob("*.*"):
                z.write(fp, arcname=f"photos/{fp.name}")
        sp = sign_path(rid)
        if sp.exists():
            z.write(sp, arcname=f"sign/{sp.name}")
    return str(out)


# -----------------------------
# 7) 산출물 패널
# -----------------------------
def outputs_panel(rid: str | None = None):
    with st.expander("📦 산출물 생성 위치 / 생성 파일 확인", expanded=False):
        st.code(f"""
※ 아래 경로는 '서버PC(스트림릿 실행 PC)' 기준입니다.
공유폴더(BASE): {BASE}
PDF:  {PDFD}
PACKET: {PACKD}
QR:   {QRD}
ZIP:  {ZIPD}
사진: {PHOTOD}
서명: {SIGND}
점검: {CHECKD}
DB:   {DB}
""".strip())

        if rid:
            st.markdown("**이번 요청 생성 파일(최대 40개 표시)**")
            files = []
            for folder in [PDFD, PACKD, QRD, ZIPD, CHECKD]:
                files += sorted(Path(folder).glob(f"*{rid}*"))
            pdir = PHOTOD / rid
            if pdir.exists():
                files += sorted(pdir.glob("*.*"))
            sp = sign_path(rid)
            if sp.exists():
                files.append(sp)

            if not files:
                st.info("아직 생성된 산출물이 없습니다.")
            else:
                for f in files[:40]:
                    st.write(f"• {f}")


# -----------------------------
# 8) UI
# -----------------------------
st.set_page_config(page_title=f"{SITE_NAME} v2.4.0", layout="centered", initial_sidebar_state="collapsed")
st.markdown("""
<style>
  #MainMenu, footer, header {visibility:hidden;}
  .block-container{max-width:980px;padding-top:0.65rem;padding-bottom:1.0rem;}
  [data-testid="stAppViewContainer"]{background:linear-gradient(180deg,#F6F7FB 0%, #FFFFFF 40%, #F6F7FB 100%);}
  .topbar{
     background:linear-gradient(135deg,#2563EB 0%, #06B6D4 100%);
     border-radius:22px; padding:14px 16px; color:white;
     box-shadow:0 14px 30px rgba(37,99,235,.18);
     margin-bottom:10px;
  }
  .topbar .title{font-size:18px;font-weight:900;line-height:1.2;}
  .topbar .sub{opacity:.9;font-size:12.5px;font-weight:700;margin-top:4px;}
  .pill{display:inline-flex;align-items:center;gap:6px;background:rgba(255,255,255,.18);
        padding:7px 10px;border-radius:999px;font-weight:800;font-size:12px;}
  .card{
     background:#FFFFFF;border:1px solid #E5E7EB;border-radius:18px;padding:14px;
     box-shadow:0 8px 20px rgba(17,24,39,.06);
     margin-top:10px;
  }
</style>
""", unsafe_allow_html=True)


# -----------------------------
# 9) ✅ 로그인(현장PIN + 역할)
# -----------------------------
if "authed" not in st.session_state:
    st.session_state.authed = False
if "actor" not in st.session_state:
    st.session_state.actor = ""
if "role" not in st.session_state:
    st.session_state.role = ""
if "training_url" not in st.session_state:
    st.session_state.training_url = VISITOR_TRAINING_URL_DEFAULT
if "last_msg" not in st.session_state:
    st.session_state.last_msg = get_last_kakao_msg()

with st.sidebar:
    st.subheader("설정")
    st.caption("모바일 인앱브라우저 이슈로 사이드바는 보조용입니다.")
    if st.session_state.authed:
        st.write(f"👤 {st.session_state.actor} / {st.session_state.role}")
        if st.button("로그아웃", use_container_width=True):
            st.session_state.authed=False
            st.session_state.actor=""
            st.session_state.role=""
            st.rerun()

if not st.session_state.authed:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🔐 로그인(현장용)")
    pin = st.text_input("현장 PIN*", type="password")
    a = st.text_input("이름/직책*", placeholder="예) 공무팀장 홍길동")
    role = st.selectbox("역할*", ["협력사","공무","안전","경비","관리자"])
    u = st.text_input("SIC 방문자교육 URL", value=VISITOR_TRAINING_URL_DEFAULT)
    col1, col2 = st.columns(2)
    if col1.button("로그인", use_container_width=True):
        if pin != SITE_PIN:
            st.error("PIN이 올바르지 않습니다.")
        elif not a.strip():
            st.error("이름/직책을 입력하세요.")
        else:
            st.session_state.authed = True
            st.session_state.actor = a.strip()
            st.session_state.role = role
            st.session_state.training_url = u.strip() if u.strip() else VISITOR_TRAINING_URL_DEFAULT
            st.rerun()
    if col2.button("닫기", use_container_width=True):
        st.stop()
    st.markdown("</div>", unsafe_allow_html=True)
    st.stop()

actor = st.session_state.actor
role = st.session_state.role
training_url = st.session_state.training_url


# -----------------------------
# 10) 상단 탭 네비
# -----------------------------
if "page" not in st.session_state:
    st.session_state.page = "홈"
tabs = ["홈", "신청", "승인", "게이트", "실행", "대장"]
page = st.radio(" ", tabs, horizontal=True, index=tabs.index(st.session_state.page))
st.session_state.page = page


# -----------------------------
# 11) 헤더 + KPI
# -----------------------------
df_all = fetch_requests()
today = date.today().isoformat()
cnt_req = int((df_all["work_date"] == today).sum()) if not df_all.empty else 0
cnt_apv = int((df_all["status"] == "APPROVED").sum()) if not df_all.empty else 0
cnt_pen = int((df_all["status"] == "PENDING").sum()) if not df_all.empty else 0
cnt_exec = int(df_all["exec_at"].notna().sum()) if not df_all.empty else 0
cnt_risk = int((df_all["risk"] == "고위험").sum()) if not df_all.empty else 0

st.markdown(f"""
<div class="topbar">
  <div class="title">{SITE_NAME} · 내부망 운영</div>
  <div class="sub">
    <span class="pill">👤 {html.escape(actor)} ({html.escape(role)})</span>
    <span class="pill">📅 {today}</span>
  </div>
</div>
""", unsafe_allow_html=True)

k1, k2, k3, k4, k5 = st.columns(5)
if k1.button(f"오늘요청\n{cnt_req}", use_container_width=True):
    st.session_state.page = "대장"; st.rerun()
if k2.button(f"승인\n{cnt_apv}", use_container_width=True):
    st.session_state.page = "승인"; st.rerun()
if k3.button(f"대기\n{cnt_pen}", use_container_width=True):
    st.session_state.page = "승인"; st.rerun()
if k4.button(f"실행\n{cnt_exec}", use_container_width=True):
    st.session_state.page = "실행"; st.rerun()
if k5.button(f"고위험\n{cnt_risk}", use_container_width=True):
    st.session_state.page = "대장"; st.rerun()

# ✅ 최근 단톡 문구(사라짐 방지)
if st.session_state.last_msg:
    copy_box(st.session_state.last_msg, "최근 단톡 공유 문구(자동 유지)")

outputs_panel(None)


# -----------------------------
# 홈: 접속 QR
# -----------------------------
if page == "홈":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📌 현장 접속 QR (협력사 포함)")
    st.write("같은 Wi-Fi/내부망에서 휴대폰으로 QR 찍으면 바로 접속됩니다.")
    ips = local_ip_candidates()
    ip = st.selectbox("서버PC IP 선택(고정IP 추천)", ips, index=0)
    url = server_url(ip)

    qr_file = QRD / f"SERVER_{ip}_{PORT}.png"
    make_qr_png(url, qr_file)

    st.markdown(f"**접속 주소:** `{url}`")
    st.image(str(qr_file), width=260, caption="현장 출입구/사무실 부착용")

    st.write("---")
    st.markdown("#### ✅ 운영 체크")
    st.write("- 실행: `streamlit run app.py --server.address 0.0.0.0 --server.port 8501`")
    st.write("- 방화벽 허용(8501) + IP 고정(DHCP 예약)")
    st.write("- 앱 내부 PIN으로 무단 접근 차단")
    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# 신청 (모든 역할 가능)
# -----------------------------
elif page == "신청":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📝 반입/반출 신청")

    io_type = st.radio("구분*", ["반입","반출"], horizontal=True)
    company = st.text_input("협력회사*", "")
    material = st.text_input("자재/화물*", "")
    vehicle = st.text_input("차량번호*", "")
    driver_phone = st.text_input("운전원 연락처*", "", placeholder="예) 010-1234-5678")
    gate = st.selectbox("사용 GATE*", ["1GATE","2GATE","3GATE"])
    work_date = st.date_input("일자*", value=date.today()).isoformat()
    work_time = st.selectbox("시간*", [f"{h:02d}:{m:02d}" for h in range(6,21) for m in (0,30)])
    risk = st.selectbox("위험도(간단)*", ["정상","고위험"])
    note = st.text_area("비고(선택)", "", height=110)

    can_submit = all([company.strip(), material.strip(), vehicle.strip(), driver_phone.strip()])
    if st.button("📨 신청 등록", use_container_width=True, disabled=not can_submit):
        rid = new_rid()
        now = datetime.now().isoformat(timespec="seconds")
        with db() as con:
            con.execute("""
                INSERT INTO requests(
                  rid,io_type,company,material,vehicle,driver_phone,gate,work_date,work_time,note,risk,status,created_at,created_by
                )
                VALUES(?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, (rid, io_type, company, material, vehicle, driver_phone, gate, work_date, work_time, note, risk, "PENDING", now, actor))
        log_event(rid, "REQUEST_CREATED", actor, {"io_type":io_type})

        r = get_request(rid)
        msg = msg_template("신청 접수", r, extra="승인 완료되면: 통합PDF(PACKET) 생성 후 단톡 공유")
        log_event(rid, "KAKAO_MSG", actor, {"text": msg})
        st.session_state.last_msg = msg

        st.success(f"등록 완료: {rid}")
        copy_box(msg, "단톡 공유 문구(신청 접수)")
        outputs_panel(rid)

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# 승인 (관리자만 + ADMIN_PIN 추가확인)
# -----------------------------
elif page == "승인":
    if role not in ALLOW_APPROVE_ROLE:
        st.error("승인 기능은 관리자만 가능합니다.")
        st.stop()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("✅ 승인(전자서명)")

    admin_pin = st.text_input("관리자 PIN(추가 확인)*", type="password")
    if admin_pin != ADMIN_PIN:
        st.warning("관리자 PIN 입력 후 승인 기능이 활성화됩니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    if df_all.empty:
        st.info("요청이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    df_view = df_all[["rid","io_type","status","risk","company","material","vehicle","driver_phone","gate","work_date","work_time","created_by","created_at"]].copy()
    st.dataframe(df_view, use_container_width=True, hide_index=True)

    rid = st.selectbox("승인할 요청ID(대기만 가능)", df_view["rid"].tolist())
    r = get_request(rid)
    if not r:
        st.error("요청을 찾지 못했습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    if r["status"] != "PENDING":
        st.warning("이미 처리된 요청입니다. (대기 상태만 승인 가능)")
        outputs_panel(rid)
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    st.markdown(f"**{r['io_type']} / {r['company']} / {r['material']}**")
    st.caption(f"차량/연락처: {r['vehicle']} / {r.get('driver_phone','')}  ·  GATE/시간: {r['gate']} / {r['work_date']} {r['work_time']}")

    st.markdown("#### ✍️ 전자서명 (승인자)")
    canv = st_canvas(
        stroke_width=3,
        stroke_color="#111827",
        background_color="#FFFFFF",
        height=160,
        drawing_mode="freedraw",
        key=f"sign_{rid}"
    )

    if st.button("✅ 승인 완료 + PACKET 생성", use_container_width=True):
        if canv.image_data is not None:
            Image.fromarray(canv.image_data.astype("uint8")).save(sign_path(rid))

        now = datetime.now().isoformat(timespec="seconds")
        with db() as con:
            con.execute("UPDATE requests SET status='APPROVED', approved_at=?, approved_by=? WHERE rid=?",
                        (now, actor, rid))
        log_event(rid, "APPROVED", actor, {})

        r2 = get_request(rid)
        approval_pdf = gen_approval_pdf(r2)
        permit_pdf = gen_entry_permit_pdf(r2, training_url)
        packet = gen_packet_pdf(r2, training_url, mode="LIGHT")
        req_qr = str(QRD / f"{rid}_req.png")
        share_zip = make_share_zip(rid, [approval_pdf, permit_pdf, req_qr, packet])

        msg = msg_template("승인 완료", r2, files={
            "packet": packet,
            "approval_pdf": approval_pdf,
            "permit_pdf": permit_pdf,
            "zip": share_zip
        }, extra="단톡: PACKET(PDF) 1개 올리면 한번에 열람 가능")
        log_event(rid, "KAKAO_MSG", actor, {"text": msg})
        st.session_state.last_msg = msg

        st.success("승인 완료 + PACKET 생성 완료")
        copy_box(msg, "단톡 공유 문구(승인 완료)")
        outputs_panel(rid)

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# 게이트 확인 (경비/관리자/공무/안전 권장, 제한은 안 둠)
# -----------------------------
elif page == "게이트":
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("🚧 게이트 확인")
    st.caption("승인서 QR(요청ID)을 스캔한 값(REQ_...)을 입력하면 통과/차단이 바로 나옵니다.")

    rid = st.text_input("요청ID 입력", value="", placeholder="예) REQ_20260206_070000_123")
    if st.button("🔍 확인", use_container_width=True):
        r = get_request(rid.strip())
        if not r:
            st.error("❌ 해당 요청이 없습니다.")
        else:
            if r["status"] == "APPROVED":
                st.success("✅ 통과 OK (승인 완료)")
            else:
                st.error(f"❌ 통과 불가 (상태: {r['status']})")
            outputs_panel(rid.strip())
    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# 실행 (공무/안전/관리자만 + 사진 권한)
# -----------------------------
elif page == "실행":
    if role not in ALLOW_EXEC_ROLE:
        st.error("실행 등록(사진/점검)은 공무/안전/관리자만 가능합니다.")
        st.stop()

    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📸 실행 등록 (사진 + 점검카드)")

    if df_all.empty:
        st.info("요청이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    approved = df_all[df_all["status"]=="APPROVED"].copy()
    if approved.empty:
        st.warning("승인 완료된 요청이 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    rid = st.selectbox("대상(승인 완료)", approved["rid"].tolist())
    r = get_request(rid)

    st.markdown(f"**{r['io_type']} / {r['company']} / {r['material']}**")
    st.caption(f"차량/연락처: {r['vehicle']} / {r.get('driver_phone','')}  ·  GATE/시간: {r['gate']} / {r['work_date']} {r['work_time']}")

    st.markdown("#### 0. 참석자 체크(필수)")
    base = ["협력회사 담당자","장비운전원","차량운전원","유도원","안전보조원/감시단"]
    attendees = {}
    for p in base:
        attendees[p] = st.checkbox(p, value=True, key=f"att_{rid}_{p}")

    st.markdown("#### 3~10. 핵심 점검(필수)")
    checks = {
        "3":"화물 당 2개소 이상 결속 여부 확인",
        "4":"고정용 로프 및 밴딩 상태 점검 여부",
        "5":"화물 높이 4M 이하 적재, 낙하위험 발생여부",
        "6":"적재함 폭 초과 상차 금지, 적재함 닫힘 여부",
        "7":"자재차량 고임목 설치 여부",
        "8":"적재하중 이내 적재 여부",
        "9":"화물 무게중심 확인(한쪽으로 쏠림 여부)",
        "10":"자재 하역구간 구획 및 통제 여부",
    }
    checklist = {}
    for k,txt in checks.items():
        checklist[k] = st.checkbox(txt, value=True, key=f"ck_{rid}_{k}")

    can_photo = (role in ALLOW_PHOTO_ROLE)
    if not can_photo:
        st.warning("현재 역할은 사진 등록 권한이 없습니다.")
        st.stop()

    st.markdown("#### 실행 사진(필수 3종)")
    cam_before = st.camera_input("상차 전(촬영)", key=f"cam_before_{rid}")
    cam_after  = st.camera_input("상차 후(촬영)", key=f"cam_after_{rid}")
    cam_tie    = st.camera_input("결속/로프/밴딩(근접 촬영)", key=f"cam_tie_{rid}")

    with st.expander("📎 파일 업로드(선택: PC/기존 사진)", expanded=False):
        up_before = st.file_uploader("상차 전(업로드)", type=["jpg","jpeg","png"], key=f"up_before_{rid}")
        up_after  = st.file_uploader("상차 후(업로드)", type=["jpg","jpeg","png"], key=f"up_after_{rid}")
        up_tie    = st.file_uploader("결속/로프/밴딩(업로드)", type=["jpg","jpeg","png"], key=f"up_tie_{rid}")

    if st.button("✅ 실행 완료 + PACKET(FULL) 생성", use_container_width=True):
        miss_att = [p for p in base if not attendees.get(p, False)]
        if miss_att:
            st.error(f"필수 참석자 미확인: {', '.join(miss_att)}"); st.stop()

        fail_ck = [k for k,v in checklist.items() if not v]
        if fail_ck:
            st.error("점검 FAIL 항목이 있어 실행 완료 처리 불가"); st.stop()

        p_before = save_cam_or_upload(rid, "before", cam_before, up_before)
        p_after  = save_cam_or_upload(rid, "after",  cam_after,  up_after)
        p_tie    = save_cam_or_upload(rid, "tie",    cam_tie,    up_tie)

        if not (p_before and p_after and p_tie):
            st.error("필수 사진(3종)이 필요합니다. (촬영 또는 업로드)"); st.stop()

        now = datetime.now().isoformat(timespec="seconds")
        with db() as con:
            con.execute("UPDATE requests SET exec_at=?, exec_by=? WHERE rid=?", (now, actor, rid))
        log_event(rid, "EXEC_COMPLETED", actor, {"photos": True})

        r2 = get_request(rid)
        approval_pdf = gen_approval_pdf(r2)
        permit_pdf = gen_entry_permit_pdf(r2, training_url)
        check_pdf = gen_check_pdf(r2, checklist, attendees)
        exec_pdf = gen_exec_pdf(r2, {"before":p_before,"after":p_after,"tie":p_tie})
        packet = gen_packet_pdf(
            r2, training_url,
            checklist=checklist, attendees=attendees,
            photo_paths={"before":p_before,"after":p_after,"tie":p_tie},
            mode="FULL"
        )
        req_qr = str(QRD / f"{rid}_req.png")
        share_zip = make_share_zip(rid, [approval_pdf, permit_pdf, req_qr, check_pdf, exec_pdf, packet])

        msg = msg_template("실행 완료", r2, files={
            "packet": packet,
            "approval_pdf": approval_pdf,
            "permit_pdf": permit_pdf,
            "check_pdf": check_pdf,
            "exec_pdf": exec_pdf,
            "zip": share_zip
        }, extra="단톡: PACKET(PDF) 1개 + 문구 붙여넣기(권장)")
        log_event(rid, "KAKAO_MSG", actor, {"text": msg})
        st.session_state.last_msg = msg

        st.success("실행 완료 + PACKET(FULL) 생성 완료")
        copy_box(msg, "단톡 공유 문구(실행 완료)")
        outputs_panel(rid)

    st.markdown("</div>", unsafe_allow_html=True)


# -----------------------------
# 대장
# -----------------------------
else:
    st.markdown('<div class="card">', unsafe_allow_html=True)
    st.subheader("📒 대장")

    if df_all.empty:
        st.info("데이터가 없습니다.")
        st.markdown("</div>", unsafe_allow_html=True)
        st.stop()

    only_today = st.toggle("오늘 건만 보기", value=True)
    df2 = df_all[df_all["work_date"]==today].copy() if only_today else df_all.copy()
    st.dataframe(df2, use_container_width=True, hide_index=True)

    st.write("---")
    rid = st.text_input("요청ID 이벤트 로그 조회(선택)", value="")
    if rid.strip():
        with db() as con:
            rows = con.execute("SELECT ts,event,actor,payload FROM events WHERE rid=? ORDER BY id ASC", (rid.strip(),)).fetchall()
        if rows:
            st.markdown("#### 이벤트 로그")
            st.dataframe(pd.DataFrame(rows, columns=["ts","event","actor","payload"]), use_container_width=True, hide_index=True)
        else:
            st.info("로그가 없습니다.")
        outputs_panel(rid.strip())

    st.markdown("</div>", unsafe_allow_html=True)
