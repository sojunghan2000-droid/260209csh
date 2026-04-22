# Material Gate Tool v3.0.0 — Claude Code 프로젝트 메모리

## 프로젝트 개요
건설현장 자재 반출입 승인·실행·산출물 관리 시스템 (Streamlit 기반)

**워크플로우:**
```
스케줄링 → 요청 등록 → 승인(안전/공사 서명) → 실행(사진촬영+체크리스트) → 산출물(PDF) → 공유
```

## 실행 방법
```bash
# 앱 실행 (Windows)
python -m streamlit run app.py --server.port 8501

# 의존성 설치
pip install -r requirements.txt

# 문법 검사
python -m py_compile app.py
```

## 배포 (Deployment)

**플랫폼:** Streamlit Community Cloud (Vercel 아님 — Streamlit 앱은 Vercel 네이티브 미지원)

**배포 URL:** https://material-process-management-fwj7blrkqcledcn35xrkav.streamlit.app/

**자동 재배포:** `mpm` remote의 `master` 브랜치에 push되면 Streamlit Cloud가 자동으로 재빌드·재배포 (별도 배포 명령 불필요).

**Git remote 구성:**

| remote | URL | 역할 |
|---|---|---|
| `mpm` | `https://github.com/sojunghan2000-droid/Material-Process-Management.git` | **배포 연결 레포** — Streamlit Cloud가 이 레포를 추적 |
| `origin` | `https://github.com/sojunghan2000-droid/260209csh.git` | 보조 레포 — `mpm`과 동기화 유지 권장 |

**배포 절차:**
```bash
# 1. fast-forward 안전 확인
git merge-base --is-ancestor mpm/master master && echo OK

# 2. 양쪽 remote에 master 푸시 (순서 무관)
git push mpm master
git push origin master

# 3. 배포 URL 접속하여 Streamlit Cloud 빌드 완료 및 정상 동작 확인
```

**주의:**
- `.streamlit/secrets.toml`은 커밋하지 않음 (untracked). Streamlit Cloud의 **App settings → Secrets**에서 관리.
- force push 금지 (배포 히스토리 보호).

## 디렉토리 구조
```
app.py              # 진입점 + 페이지 라우터
config.py           # 전역 상수 (ROLES, STATUS, KIND 등)
requirements.txt    # 의존성

auth/               # 프로젝트 선택 + 로그인
core/               # CSS, 헤더, 네비게이션, 사이드바
db/                 # SQLite 연결, 마이그레이션, 프로젝트/모듈 CRUD
modules/
  request/          # 요청 등록 (CRUD + 페이지)
  approval/         # 승인/반려 (서명 포함)
  execution/        # 실행 (사진촬영 + 체크리스트)
  outputs/          # PDF 생성 + 공유
  ledger/           # 전체 대장 조회
  schedule/         # 스케줄링 캘린더
  admin/            # 관리자 설정
shared/             # 공통 유틸 (helpers, signature, share)
MaterialToolShared/ # 런타임 데이터 (DB, 사진, PDF 출력물)
```

## 핵심 규칙

### DB
- SQLite 단일 파일: `MaterialToolShared/gate_tool.db`
- 모든 CRUD는 `db/` 또는 각 모듈의 `crud.py`에서 처리
- `shared.helpers.now_str()` — 타임스탬프, `new_id()` — UUID
- `project_id`가 모든 테이블의 멀티테넌시 키

### 상태 머신
```
요청: PENDING_APPROVAL → APPROVED / REJECTED → EXECUTING → DONE
승인: PENDING → APPROVED / REJECTED
```

### 세션 상태 키
| 키 | 설명 |
|---|---|
| `PROJECT_ID` | 현재 선택된 프로젝트 |
| `AUTH_OK` | 로그인 여부 |
| `USER_ROLE` | 협력사/공사/안전/경비 |
| `IS_ADMIN` | 관리자 여부 |
| `ACTIVE_PAGE` | 현재 페이지 |
| `BASE_DIR` | 파일 저장 루트 (`MaterialToolShared`) |

## 코딩 스타일
- **Diff만 출력** — 전체 파일 재작성 금지, SEARCH/REPLACE 블록 사용
- **설명 최소화** — 코드만, 대화형 텍스트 불필요
- **변경 없는 긴 구간** → `# ... existing code ...` 주석 처리
- 타입힌트 사용 (`sqlite3.Connection`, `Dict[str, Any]` 등)
- Streamlit 컴포넌트는 페이지 파일에만, 비즈니스 로직은 `crud.py`에 분리

## 자주 쓰는 패턴

### 새 모듈 추가 시
1. `modules/<name>/` 디렉토리 생성
2. `crud.py`, `page.py`, `__init__.py` 작성
3. `app.py`의 `PAGE_ROUTER`에 등록
4. `db/models.py`의 `DEFAULT_MODULES`에 등록
5. `db/migrations.py`에 테이블 DDL 추가

### 승인 라우팅 변경
`settings` 테이블의 `approval_routing_json` 키 수정:
```json
{"IN": ["공사"], "OUT": ["안전", "공사"]}
```

## 알려진 이슈 / TODO
- `app.py.bak`, `app_legacy.py`, `app_new.py` — 정리 필요한 레거시 파일
- `=1.30.0`, `nul` — 잘못 생성된 파일, 삭제 가능

---

## 🎨 UI 디자인 Agent 지침 — 모바일 반응형 우선 설계

> **이 섹션은 UI/CSS 작업 시 항상 준수해야 합니다.**
> Streamlit 앱은 모바일 현장 작업자(경비, 협력사)가 스마트폰으로 주로 사용합니다.

### 브레이크포인트 체계

| 구분 | 범위 | 컬럼 동작 |
|------|------|-----------|
| 스마트폰 | ≤ 480px | 모든 `st.columns` → 100% 1열 스택 |
| 태블릿 | 481px ~ 768px | 4열 → 2열 (50% × 2) |
| 데스크톱 | ≥ 769px | 원래 레이아웃 유지 |

### 모바일 필수 규칙

```
1. 터치 타겟: 모든 버튼 min-height: 44px (iOS HIG 기준)
2. 입력 필드 font-size: 16px (iOS Safari 자동 줌 방지)
3. 제출 버튼: min-height: 52px, font-size: 15px
4. 가로 스크롤 금지: overflow-x: hidden 준수
5. 긴 텍스트: white-space: normal + word-break: break-word
6. 컨테이너 padding: 좌우 12px (스마트폰), 24px (태블릿+)
```

### CSS 작성 패턴

```css
/* ✅ 올바른 패턴: 모바일 우선 → 데스크톱 확장 */
.컴포넌트 {
  /* 기본: 모바일 스타일 */
  width: 100%;
  font-size: 16px;
  padding: 12px;
}
@media (min-width: 481px) {
  /* 태블릿+ 확장 */
}
@media (min-width: 769px) {
  /* 데스크톱 확장 */
}

/* ❌ 금지 패턴: 고정 px 폭 */
.컴포넌트 { width: 320px; }  /* → min-width 또는 % 사용 */
```

### Streamlit 컬럼 반응형 처리

```python
# 스마트폰에서 자동으로 1열로 전환되는 패턴
# core/css.py의 @media (max-width:480px) 규칙이 처리함
# 단, 날짜 네비게이션처럼 항상 1줄 유지가 필요한 경우:
# → 부모에 전용 key 부여 + .st-key-XXX flex-wrap:nowrap CSS 추가

c1, c2, c3, c4 = st.columns(4)  # 자동 2열(태블릿)/1열(모바일) 전환
```

### 신규 컴포넌트 CSS 체크리스트

새 HTML/CSS 컴포넌트를 추가할 때 반드시 확인:

- [ ] `@media (max-width: 480px)` 블록에 모바일 오버라이드 포함
- [ ] 고정 px 폭 없음 (min-width, max-width, %, clamp() 사용)
- [ ] `clamp()` 활용: `font-size: clamp(11px, 2vw, 14px)`
- [ ] 그리드 컬럼 수 모바일에서 축소: `grid-template-columns: 50px 1fr`
- [ ] 불필요한 컬럼 모바일에서 `display: none`
- [ ] CSS 변수 사용: `var(--border-light)`, `var(--text-muted)` 등 (하드코딩 금지)

### 기존 CSS 구조 위치

| 파일 | 역할 |
|------|------|
| `core/css.py` | 전역 CSS (변수, 버튼, 폼, 레이아웃, 반응형) |
| `modules/schedule/css/schedule.py` | 스케줄 타임라인 전용 CSS |

신규 모듈 CSS는 `modules/{모듈}/css/{모듈}.py`에 작성 후 `get_{모듈}_css()` 함수로 반환.

### 현장 UX 우선순위

1. **경비/협력사** → 스마트폰 세로 모드, 한 손 조작, 큰 버튼
2. **공사/안전 담당자** → 태블릿 또는 데스크톱, 서명 입력 필요
3. **관리자** → 데스크톱, 데이터 테이블·필터 사용
