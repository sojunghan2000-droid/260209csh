# Smart Factory - Welding Defect Detector

Google Vertex AI AutoML Vision을 활용한 용접 불량 판별 앱입니다.

## Quick Start

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Vertex AI 연동

1. `app.py`에서 `PROJECT_ID`, `ENDPOINT_ID`, `LOCATION` 설정
2. 서비스 계정 키 파일(`key.json`)을 프로젝트 루트에 배치
3. `USE_VERTEX_AI = True`로 변경
