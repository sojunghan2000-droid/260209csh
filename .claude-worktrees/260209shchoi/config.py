"""Global configuration constants."""
from pathlib import Path

APP_VERSION = "v3.0.0"
APP_TITLE = "자재 반출입 승인 · 실행 · 산출물(운영형)"
DEFAULT_SITE_NAME = "현장명(수정)"
DEFAULT_BASE_DIR = "MaterialToolShared"
DEFAULT_SITE_PIN = "1234"
DEFAULT_ADMIN_PIN = "9999"

ROLES = ["삼성물산", "협력사"]
REQ_STATUS = ["PENDING_APPROVAL", "APPROVED", "REJECTED", "EXECUTING", "DONE"]
KIND_IN = "IN"
KIND_OUT = "OUT"

EXEC_REQUIRED_PHOTOS = [
    ("pre_load", "상차 전(촬영)"),
    ("post_load", "상차 후(촬영)"),
    ("area_ctrl", "하역/통제구간(촬영)"),
]

RISK_LEVELS = [("LOW", "낮음"), ("MID", "보통"), ("HIGH", "높음")]

VEHICLE_TONS = ["1톤", "1.4톤", "2.5톤", "3.5톤", "5톤", "8톤", "11톤", "15톤", "25톤", "직접입력"]
GATE_ZONES = ["A존", "B존", "C존", "D존", "1GATE", "2GATE", "3GATE", "기타"]

# 30분 단위 시간 슬롯 (06:00 ~ 18:00)
TIME_SLOTS = [f"{h:02d}:{m:02d}" for h in range(6, 19) for m in (0, 30) if not (h == 18 and m == 30)]

CHECK_ITEMS = [
    ("vehicle_plate", "차량 번호판 확인"),
    ("driver_id", "운전원 신분증 확인"),
    ("ppe_helmet", "안전모 착용"),
    ("ppe_vest", "안전조끼 착용"),
    ("ppe_boots", "안전화 착용"),
    ("load_cover", "적재물 덮개 확인"),
    ("brake_check", "제동장치 확인"),
    ("fire_ext", "소화기 확인"),
    ("first_aid", "구급상자 확인"),
    ("route_ok", "이동 경로 안내"),
]
