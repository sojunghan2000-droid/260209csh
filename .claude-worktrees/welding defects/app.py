import streamlit as st
import base64
import io
import time
from PIL import Image

# ============================================================
# 설정 (Vertex AI 연결 시 아래 값을 채우세요)
# ============================================================
PROJECT_ID = "your-project-id"
ENDPOINT_ID = "your-endpoint-id"
LOCATION = "us-central1"
KEY_PATH = "key.json"  # 서비스 계정 키 파일 경로

# ============================================================
# Vertex AI 연동 모드 (True: 실제 연동 / False: 시연 모드)
# ============================================================
USE_VERTEX_AI = False

# ============================================================
# 페이지 설정
# ============================================================
st.set_page_config(
    page_title="Smart Factory - Welding Inspector",
    page_icon="🏭",
    layout="centered",
)

# ============================================================
# 커스텀 CSS
# ============================================================
st.markdown("""
<style>
    /* 전체 배경 */
    .stApp {
        background: linear-gradient(135deg, #0f0c29 0%, #302b63 50%, #24243e 100%);
    }

    /* 헤더 영역 */
    .header-box {
        background: linear-gradient(90deg, #1a1a2e 0%, #16213e 100%);
        border: 1px solid #0f3460;
        border-radius: 16px;
        padding: 2rem 1.5rem;
        text-align: center;
        margin-bottom: 1.5rem;
        box-shadow: 0 4px 20px rgba(0, 0, 0, 0.3);
    }
    .header-box h1 {
        color: #e94560;
        font-size: 1.8rem;
        margin-bottom: 0.3rem;
    }
    .header-box p {
        color: #a0a0b0;
        font-size: 0.95rem;
    }

    /* 상태 카드 */
    .status-row {
        display: flex;
        gap: 0.8rem;
        margin-bottom: 1.5rem;
    }
    .status-card {
        flex: 1;
        background: #1a1a2e;
        border: 1px solid #0f3460;
        border-radius: 12px;
        padding: 1rem;
        text-align: center;
    }
    .status-card .label {
        color: #a0a0b0;
        font-size: 0.75rem;
        text-transform: uppercase;
        letter-spacing: 1px;
    }
    .status-card .value {
        color: #e94560;
        font-size: 1.4rem;
        font-weight: bold;
        margin-top: 0.3rem;
    }
    .status-card .value.green { color: #4ecca3; }
    .status-card .value.blue  { color: #00b4d8; }

    /* 결과 박스 */
    .result-defect {
        background: linear-gradient(135deg, #2d0a0a 0%, #1a0000 100%);
        border: 2px solid #e94560;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
        animation: pulse-red 2s infinite;
    }
    .result-normal {
        background: linear-gradient(135deg, #0a2d1a 0%, #001a0a 100%);
        border: 2px solid #4ecca3;
        border-radius: 16px;
        padding: 2rem;
        text-align: center;
    }
    .result-defect h2 { color: #e94560; }
    .result-normal h2 { color: #4ecca3; }
    .result-defect p, .result-normal p { color: #d0d0d0; }

    @keyframes pulse-red {
        0%, 100% { box-shadow: 0 0 10px rgba(233, 69, 96, 0.3); }
        50%      { box-shadow: 0 0 25px rgba(233, 69, 96, 0.6); }
    }

    /* 카메라 영역 스타일링 */
    .camera-section {
        background: #1a1a2e;
        border: 1px dashed #0f3460;
        border-radius: 16px;
        padding: 1.5rem;
        margin-bottom: 1.5rem;
    }

    /* 푸터 */
    .footer {
        text-align: center;
        color: #505060;
        font-size: 0.8rem;
        margin-top: 2rem;
        padding: 1rem;
        border-top: 1px solid #1a1a2e;
    }

    /* Streamlit 기본 요소 색상 조정 */
    .stSpinner > div > div { border-top-color: #e94560 !important; }
</style>
""", unsafe_allow_html=True)


# ============================================================
# Vertex AI 예측 함수
# ============================================================
def predict_with_vertex(image_bytes: bytes) -> dict:
    """Vertex AI AutoML 엔드포인트로 이미지를 전송하고 결과를 반환합니다."""
    from google.cloud import aiplatform
    from google.oauth2 import service_account

    credentials = service_account.Credentials.from_service_account_file(KEY_PATH)
    aiplatform.init(project=PROJECT_ID, location=LOCATION, credentials=credentials)

    endpoint = aiplatform.Endpoint(ENDPOINT_ID)

    # AutoML Image Classification은 base64 인코딩된 이미지를 받습니다
    b64_image = base64.b64encode(image_bytes).decode("utf-8")
    instances = [{"content": b64_image}]
    prediction = endpoint.predict(instances=instances)

    # 예측 결과 파싱
    pred = prediction.predictions[0]
    labels = pred.get("displayNames", [])
    confidences = pred.get("confidences", [])

    if labels and confidences:
        top_idx = confidences.index(max(confidences))
        return {
            "label": labels[top_idx],
            "confidence": confidences[top_idx],
            "all_labels": labels,
            "all_confidences": confidences,
        }
    return {"label": "Unknown", "confidence": 0.0, "all_labels": [], "all_confidences": []}


def predict_demo(image_bytes: bytes) -> dict:
    """시연용 가상 예측 함수 (Vertex AI 미연결 상태)."""
    import random

    time.sleep(1.5)  # 분석하는 시간 시뮬레이션

    # 랜덤으로 결과 생성 (시연용)
    is_defect = random.random() < 0.4
    if is_defect:
        label = random.choice(["Bad Weld", "Defect"])
        confidence = round(random.uniform(0.75, 0.98), 4)
    else:
        label = "Good Weld"
        confidence = round(random.uniform(0.85, 0.99), 4)

    return {
        "label": label,
        "confidence": confidence,
        "all_labels": ["Bad Weld", "Good Weld", "Defect"],
        "all_confidences": [
            round(random.uniform(0.01, 0.3), 4),
            round(random.uniform(0.01, 0.3), 4),
            round(random.uniform(0.01, 0.3), 4),
        ],
    }


# ============================================================
# 세션 상태 초기화
# ============================================================
if "total_inspected" not in st.session_state:
    st.session_state.total_inspected = 0
if "defect_count" not in st.session_state:
    st.session_state.defect_count = 0
if "normal_count" not in st.session_state:
    st.session_state.normal_count = 0

# ============================================================
# 헤더
# ============================================================
st.markdown("""
<div class="header-box">
    <h1>🏭 Smart Factory</h1>
    <p style="font-size:1.3rem; color:#e94560; font-weight:bold;">
        Welding Defect Detector
    </p>
    <p>Powered by Google Vertex AI &middot; AutoML Vision</p>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 상태 대시보드
# ============================================================
total = st.session_state.total_inspected
defects = st.session_state.defect_count
normals = st.session_state.normal_count
defect_rate = f"{(defects / total * 100):.1f}%" if total > 0 else "—"

st.markdown(f"""
<div class="status-row">
    <div class="status-card">
        <div class="label">Total Inspected</div>
        <div class="value blue">{total}</div>
    </div>
    <div class="status-card">
        <div class="label">Defects</div>
        <div class="value">{defects}</div>
    </div>
    <div class="status-card">
        <div class="label">Normal</div>
        <div class="value green">{normals}</div>
    </div>
    <div class="status-card">
        <div class="label">Defect Rate</div>
        <div class="value">{defect_rate}</div>
    </div>
</div>
""", unsafe_allow_html=True)

# ============================================================
# 모드 표시
# ============================================================
mode_label = "🟢 LIVE (Vertex AI)" if USE_VERTEX_AI else "🟡 DEMO MODE"
st.caption(f"Current Mode: **{mode_label}**")

# ============================================================
# 입력 방식 선택 (카메라 / 파일 업로드)
# ============================================================
st.markdown("### 📸 Capture or Upload")
tab_camera, tab_upload = st.tabs(["Camera", "File Upload"])

img_file = None

with tab_camera:
    img_file_cam = st.camera_input("Capture the welding area")
    if img_file_cam:
        img_file = img_file_cam

with tab_upload:
    img_file_up = st.file_uploader(
        "Upload a welding image",
        type=["jpg", "jpeg", "png", "bmp"],
    )
    if img_file_up:
        img_file = img_file_up

# ============================================================
# 분석 수행
# ============================================================
if img_file is not None:
    # 이미지 표시
    image = Image.open(img_file)
    st.image(image, caption="Input Image", use_container_width=True)

    # 분석 시작
    with st.spinner("🔍 AI is analyzing the weld..."):
        image_bytes = img_file.getvalue()

        if USE_VERTEX_AI:
            result = predict_with_vertex(image_bytes)
        else:
            result = predict_demo(image_bytes)

    # 카운터 업데이트
    st.session_state.total_inspected += 1
    is_defect = result["label"] in ("Bad Weld", "Defect")
    if is_defect:
        st.session_state.defect_count += 1
    else:
        st.session_state.normal_count += 1

    # ========================================================
    # 결과 표시
    # ========================================================
    confidence_pct = f"{result['confidence'] * 100:.1f}%"

    if is_defect:
        st.markdown(f"""
        <div class="result-defect">
            <h2>🚨 DEFECT DETECTED</h2>
            <p style="font-size:1.2rem;"><b>{result['label']}</b></p>
            <p>Confidence: <b>{confidence_pct}</b></p>
            <hr style="border-color:#e94560;">
            <p>⚠️ Stop the line immediately and notify the supervisor.</p>
        </div>
        """, unsafe_allow_html=True)
        # 소리 알림 (브라우저 지원 시)
        st.toast("DEFECT DETECTED! Line stop required.", icon="🚨")
    else:
        st.markdown(f"""
        <div class="result-normal">
            <h2>✅ NORMAL</h2>
            <p style="font-size:1.2rem;"><b>{result['label']}</b></p>
            <p>Confidence: <b>{confidence_pct}</b></p>
            <hr style="border-color:#4ecca3;">
            <p>Product passed inspection. Proceed to next stage.</p>
        </div>
        """, unsafe_allow_html=True)

    # ========================================================
    # 세부 예측 결과 (확장 패널)
    # ========================================================
    with st.expander("📊 Detailed Prediction Results"):
        for lbl, conf in zip(result["all_labels"], result["all_confidences"]):
            pct = conf * 100
            bar_color = "#e94560" if lbl in ("Bad Weld", "Defect") else "#4ecca3"
            st.markdown(f"**{lbl}**")
            st.progress(conf)
            st.caption(f"{pct:.2f}%")

# ============================================================
# 푸터
# ============================================================
st.markdown("""
<div class="footer">
    Smart Factory Welding Inspector v1.0<br>
    Powered by Google Cloud Vertex AI &middot; Built with Streamlit<br>
    <small>Set <code>USE_VERTEX_AI = True</code> and configure credentials to connect to your model.</small>
</div>
""", unsafe_allow_html=True)
