"""Global CSS injection for the application."""
import streamlit as st


def inject_css():
    """Inject all global CSS styles."""
    st.markdown("""
    <style>
    :root {
      --primary-950: #0c1222;
      --primary-900: #1a1f3a;
      --primary-800: #1e3a8a;
      --primary-700: #2563eb;
      --primary-600: #3b82f6;
      --primary-500: #6366f1;
      --primary-400: #818cf8;
      --primary-300: #a5b4fc;
      --primary-200: #c7d2fe;
      --primary-100: #e0e7ff;
      --neutral-950: #0f172a;
      --neutral-900: #1e293b;
      --neutral-800: #334155;
      --neutral-700: #475569;
      --neutral-600: #64748b;
      --neutral-500: #78869b;
      --neutral-400: #94a3b8;
      --neutral-300: #cbd5e1;
      --neutral-200: #e2e8f0;
      --neutral-100: #f1f5f9;
      --success: #10b981;
      --warning: #f59e0b;
      --error: #ef4444;
      --info: #3b82f6;
      --bg-light: #f8fafc;
      --bg-card: #ffffff;
      --bg-hover: #f1f5f9;
      --bg-disabled: #e2e8f0;
      --text-primary: #0f172a;
      --text-secondary: #475569;
      --text-muted: #64748b;
      --text-disabled: #cbd5e1;
      --text-inverse: #ffffff;
      --border-light: #e2e8f0;
      --border-primary: #cbd5e1;
      --border-dark: #94a3b8;
      --shadow-xs: 0 1px 2px 0 rgba(15,23,42,0.05);
      --shadow-sm: 0 1px 3px 0 rgba(15,23,42,0.1),0 1px 2px -1px rgba(15,23,42,0.1);
      --shadow-md: 0 4px 6px -1px rgba(15,23,42,0.1),0 2px 4px -2px rgba(15,23,42,0.1);
      --shadow-lg: 0 10px 15px -3px rgba(15,23,42,0.1),0 4px 6px -4px rgba(15,23,42,0.1);
      --shadow-xl: 0 20px 25px -5px rgba(15,23,42,0.1),0 8px 10px -6px rgba(15,23,42,0.1);
      --shadow-glass: 0 8px 32px 0 rgba(31,38,135,0.37);
      --spacing-xs: 4px;
      --spacing-sm: 8px;
      --spacing-md: 12px;
      --spacing-lg: 16px;
      --spacing-xl: 20px;
      --spacing-2xl: 24px;
      --spacing-3xl: 32px;
      --radius-sm: 6px;
      --radius-md: 8px;
      --radius-lg: 12px;
      --radius-xl: 16px;
      --radius-2xl: 20px;
      --radius-full: 9999px;
      --font-size-xs: 12px;
      --font-size-sm: 14px;
      --font-size-base: 16px;
      --font-size-lg: 18px;
      --font-size-xl: 20px;
      --font-size-2xl: 24px;
      --font-size-3xl: 30px;
      --font-size-4xl: 36px;
      --font-weight-regular: 400;
      --font-weight-medium: 500;
      --font-weight-semibold: 600;
      --font-weight-bold: 700;
      --font-weight-extrabold: 800;
      --line-height-tight: 1.3;
      --line-height-normal: 1.5;
      --line-height-relaxed: 1.7;
    }
    html, body, [class*="css"] {
      font-family: -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,"Noto Sans KR",sans-serif;
      color: var(--text-primary);
      line-height: var(--line-height-normal);
    }
    ::selection {
      background: var(--primary-200);
      color: var(--primary-950);
    }
    ::-webkit-scrollbar {
      width: 8px;
      height: 8px;
    }
    ::-webkit-scrollbar-track {
      background: var(--bg-light);
    }
    ::-webkit-scrollbar-thumb {
      background: var(--neutral-300);
      border-radius: var(--radius-full);
    }
    ::-webkit-scrollbar-thumb:hover {
      background: var(--neutral-400);
    }
    .stApp {
      background: linear-gradient(135deg, var(--bg-light) 0%, #f0f4f8 100%);
    }
    .card {
      background: var(--bg-card);
      border: 1px solid var(--border-light);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow-md);
      padding: var(--spacing-xl) var(--spacing-2xl);
      backdrop-filter: blur(10px);
      transition: all 0.3s cubic-bezier(0.4,0,0.2,1);
      margin-bottom: 12px !important;
    }
    .card:hover {
      box-shadow: var(--shadow-lg);
      border-color: var(--primary-200);
    }
    /* 프로젝트 선택 카드 버튼 통합 스타일 */
    [class*="st-key-sel_proj_"] button {
      background: var(--bg-card) !important;
      border: 1px solid var(--border-light) !important;
      border-radius: var(--radius-xl) !important;
      box-shadow: var(--shadow-md) !important;
      padding: 8px 12px !important;
      min-height: 110px !important;
      transition: box-shadow 0.2s ease, transform 0.15s ease, border-color 0.2s ease !important;
    }
    [class*="st-key-sel_proj_"] button:hover {
      box-shadow: var(--shadow-lg) !important;
      transform: translateY(-2px) !important;
      border-color: var(--primary-400) !important;
    }
    .home-inbox-item {
      font-size: 12px;
      color: var(--text-secondary);
      margin-top: 4px;
    }
    .stHorizontalBlock:has([class*="st-key-topnav"]) {
      background: var(--bg-card);
      border: 1px solid var(--border-light);
      border-radius: var(--radius-xl);
      box-shadow: var(--shadow-sm);
      padding: var(--spacing-sm) var(--spacing-lg);
      margin-bottom: var(--spacing-lg) !important;
      flex-wrap: nowrap !important;
      overflow: hidden;
    }
    .stHorizontalBlock:has([class*="st-key-topnav"]) > [data-testid="stColumn"] {
      flex: 1 1 0 !important;
      min-width: 0 !important;
      align-self: stretch !important;
    }
    .stHorizontalBlock:has([class*="st-key-topnav"]) [data-testid="stColumn"] > div,
    .stHorizontalBlock:has([class*="st-key-topnav"]) [data-testid="stElementContainer"],
    .stHorizontalBlock:has([class*="st-key-topnav"]) [data-testid="stButton"] {
      height: 100% !important;
    }
    .stHorizontalBlock:has([class*="st-key-topnav"]) button {
      font-size: clamp(10px, 1.4vw, 14px) !important;
      padding: 18px 4px !important;
      white-space: normal !important;
      word-break: break-word;
      width: 100%;
      height: 100% !important;
      min-height: 72px !important;
      position: relative;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
    }
    .stHorizontalBlock:has([class*="st-key-topnav"]) button p,
    .stHorizontalBlock:has([class*="st-key-topnav"]) button span {
      margin: 0 !important;
      line-height: 1 !important;
      text-align: center !important;
    }
    /* 선택된 탭(primary) 글씨 흰색 강제 적용 */
    .stHorizontalBlock:has([class*="st-key-topnav"]) button[kind="primary"] p,
    .stHorizontalBlock:has([class*="st-key-topnav"]) button[kind="primary"] span,
    .stHorizontalBlock:has([class*="st-key-topnav"]) button[kind="primary"] * {
      color: #ffffff !important;
    }
    /* 모든 primary 버튼 내부 p 태그 흰색 강제 적용 */
    [data-testid="stBaseButton-primary"] p,
    [data-testid="stBaseButton-primary"] span,
    [data-testid="stBaseButton-primary"] * {
      color: #ffffff !important;
      margin-bottom: 0 !important;
    }
    /* 비선택 탭 글씨 색상 유지 */
    .stHorizontalBlock:has([class*="st-key-topnav"]) button:not([kind="primary"]) p,
    .stHorizontalBlock:has([class*="st-key-topnav"]) button:not([kind="primary"]) span {
      color: var(--text-secondary) !important;
    }
    /* 아이콘(첫 번째 p)과 버튼명(두 번째 p) 사이 간격 — 글자 높이(1em)만큼 */
    .stHorizontalBlock:has([class*="st-key-topnav"]) button p:first-child {
      margin-bottom: 1em !important;
    }
    .stHorizontalBlock:has([class*="st-key-topnav"]) button p:last-child {
      margin-top: 0 !important;
      margin-bottom: 0 !important;
    }
    /* 모바일: 아이콘 + 텍스트 모두 표시, 크기만 축소 */
    @media (max-width: 600px) {
      .stHorizontalBlock:has([class*="st-key-topnav"]) button p:first-child {
        font-size: 18px !important;
        margin-bottom: 2px !important;
      }
      .stHorizontalBlock:has([class*="st-key-topnav"]) button p:last-child {
        display: block !important;
        font-size: 10px !important;
      }
    }
    .hero {
      background: linear-gradient(135deg,var(--primary-700) 0%,var(--primary-600) 50%,var(--primary-500) 100%);
      color: var(--text-inverse);
      border-radius: var(--radius-2xl);
      padding: 10px 20px;
      box-shadow: var(--shadow-lg);
      margin-bottom: 10px;
      position: relative;
      overflow: hidden;
    }
    .hero::before {
      content: '';
      position: absolute;
      top: -50%;
      right: -50%;
      width: 200%;
      height: 200%;
      background: radial-gradient(circle,rgba(255,255,255,0.1) 1px,transparent 1px);
      background-size: 50px 50px;
      animation: float 20s linear infinite;
    }
    @keyframes float {
      0% {transform: translateX(0) translateY(0);}
      100% {transform: translateX(50px) translateY(50px);}
    }
    .hero-content {
      position: relative;
      z-index: 1;
    }
    .hero .title {
      font-size: var(--font-size-xl);
      font-weight: var(--font-weight-extrabold);
      margin-bottom: var(--spacing-xs);
      line-height: var(--line-height-tight);
      letter-spacing: -0.5px;
    }
    .hero .sub {
      font-size: var(--font-size-xs);
      opacity: 0.95;
      font-weight: var(--font-weight-medium);
      letter-spacing: 0.5px;
    }
    .stButton > button {
      border-radius: var(--radius-lg);
      font-weight: var(--font-weight-semibold);
      font-size: var(--font-size-sm);
      padding: var(--spacing-md) var(--spacing-xl);
      transition: all 0.2s cubic-bezier(0.4,0,0.2,1);
      border: none;
      cursor: pointer;
      position: relative;
      overflow: hidden;
    }
    .stButton > button[type="submit"],
    .stButton > button[kind="primary"] {
      background: linear-gradient(135deg,var(--primary-600) 0%,var(--primary-700) 100%);
      color: var(--text-inverse);
      box-shadow: var(--shadow-md);
    }
    .stButton > button[type="submit"]:hover,
    .stButton > button[kind="primary"]:hover {
      background: linear-gradient(135deg,var(--primary-700) 0%,var(--primary-800) 100%);
      box-shadow: var(--shadow-lg);
      transform: translateY(-2px);
    }
    .stButton > button[kind="secondary"],
    .stButton > button:not([type="submit"]):not([kind="primary"]) {
      background: var(--bg-hover);
      color: var(--text-primary);
      border: 1px solid var(--border-light);
    }
    .stButton > button[kind="secondary"]:hover,
    .stButton > button:not([type="submit"]):not([kind="primary"]):hover {
      background: var(--neutral-100);
      border-color: var(--primary-300);
      color: var(--primary-700);
    }
    .stButton > button:disabled {
      background: var(--bg-disabled);
      color: var(--text-disabled);
      cursor: not-allowed;
      opacity: 0.6;
    }
    /* 내부 input/textarea/select 자체 테두리 제거 — 래퍼에서만 처리 */
    .stTextInput > div > div > input,
    .stNumberInput > div > div > input,
    .stTextArea > div > div > textarea {
      background: var(--bg-card);
      border: none !important;
      outline: none !important;
      box-shadow: none !important;
      color: var(--text-primary);
      font-family: inherit;
      font-size: var(--font-size-sm);
      padding: var(--spacing-md) var(--spacing-lg);
    }
    /* Streamlit baseweb 래퍼에만 테두리 적용 */
    [data-baseweb="input"],
    [data-baseweb="textarea"],
    [data-baseweb="select"] > div:first-child {
      background: var(--bg-card) !important;
      border: 1px solid var(--neutral-500) !important;
      border-radius: var(--radius-lg) !important;
      transition: border-color 0.2s ease, box-shadow 0.2s ease;
    }
    [data-baseweb="input"]:focus-within,
    [data-baseweb="textarea"]:focus-within,
    [data-baseweb="select"] > div:first-child:focus-within {
      border-color: var(--primary-600) !important;
      box-shadow: 0 0 0 3px var(--primary-100) !important;
    }
    /* 로그인 폼 셀렉트박스 글자 크기를 텍스트 입력과 동일하게 */
    .st-key-login_form_wrap [data-baseweb="select"] > div > div > div {
      font-size: 14px !important;
    }
    /* 드롭다운 옵션 키보드 포커스 강조 */
    [data-testid="stSelectboxVirtualDropdown"] li[aria-selected="true"] > div {
      background-color: var(--primary-100) !important;
      color: var(--primary-700) !important;
      font-weight: 600 !important;
      outline: none !important;
    }
    [data-testid="stSelectboxVirtualDropdown"] li:hover > div {
      background-color: var(--primary-50) !important;
    }
    .stTextInput > label,
    .stNumberInput > label,
    .stSelectbox > label,
    .stTextArea > label {
      color: var(--text-primary);
      font-weight: var(--font-weight-semibold);
      font-size: var(--font-size-sm);
      margin-bottom: 0 !important;
    }
    /* 전역: stWidgetLabel 높이 압축 — 라벨↔입력박스 간격 최소화 */
    [data-testid="stWidgetLabel"] {
      min-height: 0 !important;
      line-height: 1.2 !important;
      padding-bottom: 2px !important;
    }
    [data-testid="stWidgetLabel"] > span {
      line-height: 1.2 !important;
    }
    /* 로그인 폼 내에서만 라벨↔입력 간격 14px 축소 */
    .st-key-login_form_wrap [data-testid="stWidgetLabel"] + div {
      margin-top: -14px !important;
    }
    /* ── Sidebar navigation ── */
    [data-testid="stSidebarContent"] {
      padding-top: var(--spacing-lg) !important;
      height: 100vh !important;
      overflow: hidden !important;
      display: flex !important;
      flex-direction: column !important;
    }
    [data-testid="stSidebarUserContent"] {
      flex: 1 !important;
      display: flex !important;
      flex-direction: column !important;
      overflow: hidden !important;
      min-height: 0 !important;
    }
    [data-testid="stSidebarUserContent"] > div {
      flex: 1 !important;
      display: flex !important;
      flex-direction: column !important;
      overflow: hidden !important;
      min-height: 0 !important;
    }
    .sidebar-user {
      padding: var(--spacing-xs) 0 var(--spacing-sm) 0;
    }
    .sidebar-user-name {
      font-size: 15px;
      font-weight: 700;
      color: var(--primary-700);
    }
    .sidebar-user-role {
      font-size: 12px;
      color: var(--text-muted);
      margin-top: 3px;
    }
    [data-testid="stSidebar"] [data-testid="stVerticalBlock"] {
      gap: 0 !important;
    }
    [data-testid="stSidebar"] [data-testid="stElementContainer"] {
      margin-bottom: 0 !important;
    }
    /* 사이드바: 반응형 높이, 스크롤 없음, 로그아웃 하단 고정 */
    [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] {
      display: flex !important;
      flex-direction: column !important;
      flex: 1 !important;
      min-height: 0 !important;
      overflow: hidden !important;
    }
    [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:last-child {
      margin-top: auto !important;
      padding-top: 8px !important;
    }
    [data-testid="stSidebar"] .stButton {
      width: 100% !important;
    }
    [data-testid="stSidebar"] .stButton > button {
      text-align: left !important;
      justify-content: flex-start !important;
      border-radius: var(--radius-md) !important;
      margin-bottom: 3px !important;
      font-size: 15px !important;
      font-weight: var(--font-weight-semibold) !important;
      padding: 10px 14px !important;
      width: 100% !important;
      letter-spacing: 0.1px;
    }
    [data-testid="stSidebar"] .stButton > button[kind="primary"] {
      background: linear-gradient(135deg,var(--primary-600),var(--primary-700)) !important;
      color: #fff !important;
      box-shadow: var(--shadow-sm) !important;
      border: none !important;
    }
    [data-testid="stSidebar"] .stButton > button:not([kind="primary"]) {
      background: transparent !important;
      border: 1px solid transparent !important;
      color: var(--text-secondary) !important;
    }
    [data-testid="stSidebar"] .stButton > button:not([kind="primary"]):hover {
      background: var(--primary-100) !important;
      color: var(--primary-700) !important;
      border-color: var(--primary-200) !important;
    }
    /* 로그아웃 버튼: 작은 텍스트 */
    [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:last-child button {
      font-size: 11px !important;
      padding: 5px 10px !important;
      color: var(--text-muted) !important;
      opacity: 0.7;
    }
    [data-testid="stSidebarUserContent"] > div > [data-testid="stVerticalBlock"] > [data-testid="stElementContainer"]:last-child button:hover {
      opacity: 1;
      color: var(--text-secondary) !important;
    }
    [data-testid="stSuccess"] {
      background: linear-gradient(135deg,#dcfce7 0%,#c7f0d8 100%);
      border: 1px solid #22c55e;
      border-radius: var(--radius-lg);
      padding: var(--spacing-lg);
      color: #166534;
    }
    [data-testid="stError"] {
      background: linear-gradient(135deg,#fee2e2 0%,#fecaca 100%);
      border: 1px solid #ef4444;
      border-radius: var(--radius-lg);
      padding: var(--spacing-lg);
      color: #991b1b;
    }
    [data-testid="stWarning"] {
      background: linear-gradient(135deg,#fef3c7 0%,#fde68a 100%);
      border: 1px solid #f59e0b;
      border-radius: var(--radius-lg);
      padding: var(--spacing-lg);
      color: #92400e;
    }
    [data-testid="stInfo"] {
      background: linear-gradient(135deg,#dbeafe 0%,#bfdbfe 100%);
      border: 1px solid #3b82f6;
      border-radius: var(--radius-lg);
      padding: var(--spacing-lg);
      color: #1e3a8a;
    }
    .kpi {
      display: flex;
      gap: var(--spacing-sm);
      flex-wrap: nowrap;
      margin-top: var(--spacing-sm);
    }
    .kpi .box {
      flex: 1 1 0;
      min-width: 0;
      background: linear-gradient(135deg,rgba(255,255,255,0.95),rgba(248,250,252,0.95));
      border: 1px solid rgba(59,130,246,0.2);
      border-radius: var(--radius-lg);
      padding: var(--spacing-xs) var(--spacing-sm);
      backdrop-filter: blur(20px);
      transition: all 0.3s ease;
      box-shadow: 0 4px 6px rgba(15,23,42,0.07);
    }
    .kpi .box:hover {
      border-color: rgba(59,130,246,0.4);
      box-shadow: 0 8px 16px rgba(37,99,235,0.15);
      transform: translateY(-2px);
    }
    .kpi .n {
      font-size: clamp(16px, 3vw, 28px);
      font-weight: var(--font-weight-extrabold);
      color: var(--primary-600);
      margin-bottom: 2px;
      line-height: 1;
    }
    .kpi .l {
      font-size: clamp(9px, 1.5vw, 12px);
      color: var(--text-muted);
      font-weight: var(--font-weight-medium);
      opacity: 0.85;
      white-space: nowrap;
    }
    .status-badge {
      display: inline-block;
      padding: 4px 12px;
      border-radius: var(--radius-full);
      font-size: var(--font-size-xs);
      font-weight: var(--font-weight-semibold);
      letter-spacing: 0.5px;
      text-transform: uppercase;
      transition: all 0.2s ease;
    }
    .status-pending {
      background: linear-gradient(135deg,#fef3c7,#fde68a);
      color: #92400e;
      border: 1px solid #f59e0b;
    }
    .status-approved {
      background: linear-gradient(135deg,#dcfce7,#c7f0d8);
      color: #166534;
      border: 1px solid #22c55e;
    }
    .status-rejected {
      background: linear-gradient(135deg,#fee2e2,#fecaca);
      color: #991b1b;
      border: 1px solid #ef4444;
    }
    [data-testid="stMarkdownContainer"] h1 {
      font-size: var(--font-size-4xl);
      font-weight: var(--font-weight-extrabold);
      color: var(--primary-950);
      margin-bottom: var(--spacing-xl);
      letter-spacing: -1px;
    }
    [data-testid="stMarkdownContainer"] h2 {
      font-size: var(--font-size-3xl);
      font-weight: var(--font-weight-bold);
      color: var(--primary-800);
      margin-bottom: var(--spacing-lg);
      margin-top: var(--spacing-2xl);
    }
    [data-testid="stMarkdownContainer"] h3 {
      font-size: var(--font-size-2xl);
      font-weight: var(--font-weight-bold);
      color: var(--primary-700);
      margin-bottom: var(--spacing-md);
    }
    [data-testid="stMarkdownContainer"] h4 {
      font-size: var(--font-size-lg);
      font-weight: var(--font-weight-semibold);
      color: var(--text-primary);
      margin-bottom: var(--spacing-md);
    }
    [data-testid="stMarkdownContainer"] p {
      color: var(--text-secondary);
      line-height: var(--line-height-relaxed);
      margin-bottom: var(--spacing-lg);
    }
    [data-testid="stMarkdownContainer"] a {
      color: var(--primary-600);
      text-decoration: none;
      font-weight: var(--font-weight-medium);
      transition: all 0.2s ease;
      position: relative;
    }
    [data-testid="stMarkdownContainer"] a:hover {
      color: var(--primary-700);
    }
    [data-testid="stMarkdownContainer"] a::after {
      content: '';
      position: absolute;
      bottom: -2px;
      left: 0;
      width: 0;
      height: 2px;
      background: var(--primary-600);
      transition: width 0.3s ease;
    }
    [data-testid="stMarkdownContainer"] a:hover::after {
      width: 100%;
    }
    .muted {
      color: var(--text-muted);
      font-weight: var(--font-weight-medium);
    }
    .small {
      font-size: var(--font-size-xs);
      color: var(--text-secondary);
    }
    .stRadio > label {
      display: flex;
      align-items: center;
      gap: var(--spacing-md);
      cursor: pointer;
      margin-bottom: var(--spacing-md);
      font-weight: var(--font-weight-medium);
      color: var(--text-primary);
    }
    .stRadio input[type="radio"] {
      accent-color: var(--primary-600);
      width: 18px;
      height: 18px;
      cursor: pointer;
    }
    .stCheckbox > label {
      display: flex;
      align-items: center;
      gap: var(--spacing-md);
      cursor: pointer;
      font-weight: var(--font-weight-medium);
      color: var(--text-primary);
    }
    .stCheckbox input[type="checkbox"] {
      accent-color: var(--primary-600);
      width: 18px;
      height: 18px;
      cursor: pointer;
    }
    /* ── Sidebar compact ── */
    [data-testid="stSidebar"] {
      min-width: 200px !important;
      max-width: 230px !important;
    }
    /* ── Compact layout ── */
    [data-testid="stAppViewContainer"] > .main > .block-container {
      max-width: 900px !important;
      padding-top: 0.5rem !important;
      padding-bottom: 0.5rem !important;
      padding-left: var(--spacing-2xl) !important;
      padding-right: var(--spacing-2xl) !important;
    }
    [data-testid="stHorizontalBlock"] {
      gap: var(--spacing-sm) !important;
    }
    [data-testid="stColumn"] {
      padding-left: var(--spacing-xs) !important;
      padding-right: var(--spacing-xs) !important;
    }
    .stTextInput,
    .stNumberInput,
    .stSelectbox,
    .stDateInput,
    .stTimeInput,
    .stTextArea {
      max-width: 100%;
    }
    /* 수직 간격 최소화 */
    [data-testid="stElementContainer"] {
      margin-bottom: 4px !important;
    }
    [data-testid="stVerticalBlock"] {
      gap: 4px !important;
    }
    /* 헤딩 마진 최소화 */
    [data-testid="stMarkdownContainer"] h3,
    [data-testid="stMarkdownContainer"] h4 {
      margin-top: 4px !important;
      margin-bottom: 4px !important;
    }
    /* 네비바 마진 최소화 */
    .stHorizontalBlock:has([class*="st-key-topnav"]) {
      margin-bottom: 8px !important;
      padding: 4px var(--spacing-md) !important;
    }
    @media (max-width: 768px) {
      .hero .title {
        font-size: var(--font-size-2xl);
      }
      [data-testid="stAppViewContainer"] {
        padding: var(--spacing-lg);
      }
      /* 태블릿: 4열 → 2열 (50% × 2) */
      [data-testid="stHorizontalBlock"] {
        flex-wrap: wrap !important;
        gap: var(--spacing-sm) !important;
      }
      /* 네비바·req-item 행 제외하고 50% 적용 */
      [data-testid="stHorizontalBlock"]:not(:has([class*="st-key-topnav"])) > [data-testid="stColumn"] {
        flex: 0 0 calc(50% - 6px) !important;
        min-width: calc(50% - 6px) !important;
        max-width: calc(50% - 6px) !important;
      }
    }
    /* ── 스마트폰 (≤480px): 전체 1열 스택킹 ── */
    @media (max-width: 480px) {
      /* 네비게이션 바·req-item 행 제외한 모든 컬럼 100% 폭 */
      [data-testid="stHorizontalBlock"]:not(:has([class*="st-key-topnav"])) > [data-testid="stColumn"] {
        flex: 0 0 100% !important;
        min-width: 100% !important;
        max-width: 100% !important;
      }
      /* 타임라인 행: 100% 규칙 오버라이드 — 3컬럼 고정 유지 */
      [class*="st-key-tl_row_"] [data-testid="stHorizontalBlock"],
      [class*="st-key-tl_header"] [data-testid="stHorizontalBlock"] {
        flex-wrap: nowrap !important;
      }
      [class*="st-key-tl_row_"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"],
      [class*="st-key-tl_header"] [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex: unset !important;
        min-width: 0 !important;
        max-width: none !important;
      }
      /* 히어로 헤더 간소화 */
      .hero { padding: 12px 16px !important; }
      .hero .title { font-size: 18px !important; }
      .hero .sub { font-size: 11px !important; }
      .kpi { gap: 6px !important; }
      .kpi .box { padding: 8px 6px !important; }
      .kpi .n { font-size: 20px !important; }
      /* 컨테이너 패딩 최소화 */
      [data-testid="stAppViewContainer"] > .main > .block-container {
        padding-left: 12px !important;
        padding-right: 12px !important;
        max-width: 100% !important;
      }
      /* 모든 입력 필드 font-size 16px — iOS Safari 자동 줌 방지 */
      input, textarea, select {
        font-size: 16px !important;
      }
      /* 일반 버튼 최소 터치 타겟 44px (→ 이동 버튼 제외) */
      button:not([class*="home_goto"]) {
        min-height: 44px !important;
      }
      /* 제출 버튼 터치 타겟 확대 */
      [data-testid="stFormSubmitButton"] button {
        min-height: 52px !important;
        font-size: 15px !important;
      }
      /* 프로젝트 선택 화면 타이틀 — 모바일 1줄 유지 */
      [data-testid="stMarkdownContainer"] h2 {
        font-size: clamp(15px, 4.5vw, 29px) !important;
        white-space: nowrap !important;
      }
      /* 프로젝트 선택 드롭박스+버튼 — 모바일에서도 1행 유지 */
      .st-key-proj_select_wrap [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
        flex: unset !important;
        min-width: unset !important;
        max-width: unset !important;
      }
      .st-key-proj_select_wrap [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:first-child {
        flex: 1 1 auto !important;
      }
      .st-key-proj_select_wrap [data-testid="stHorizontalBlock"] > [data-testid="stColumn"]:last-child {
        flex: 0 0 44px !important;
        width: 44px !important;
      }
      /* 프로젝트 선택 카드 텍스트 정렬 */
      [class*="st-key-sel_proj_"] button {
        min-height: 120px !important;
      }
      /* 폼 구분선 여백 최소화 */
      [data-testid="stForm"] hr {
        margin: 4px 0 !important;
      }
    }
    /* 날짜 네비: 전일 | 날짜박스 | 익일 — 한 줄 고정 */
    .st-key-sched_nav_row [data-testid="stHorizontalBlock"] {
      flex-wrap: nowrap !important;
    }
    .st-key-sched_nav_row [data-testid="stHorizontalBlock"] > [data-testid="stColumn"] {
      min-width: 0 !important;
      max-width: none !important;
    }
    /* 전일/익일 버튼 컬럼: 72px 고정 */
    .st-key-sched_nav_row [data-testid="stColumn"]:has(.st-key-sched_prev),
    .st-key-sched_nav_row [data-testid="stColumn"]:has(.st-key-sched_next) {
      flex: 0 0 72px !important;
      width: 72px !important;
      max-width: 72px !important;
    }
    /* 날짜 컬럼: 나머지 채움 */
    .st-key-sched_nav_row [data-testid="stColumn"]:has(.st-key-sched_date_pick) {
      flex: 1 1 auto !important;
    }
    /* 일정현황 ↔ 예약신청 열 간격 확대 */
    [data-testid="stHorizontalBlock"]:has(.st-key-tl_header) {
      gap: 48px !important;
    }
    /* 날짜 네비 하단 여백 축소 */
    .st-key-sched_nav_row {
      margin-bottom: -10px !important;
    }
    /* 타임라인 헤더·행: 날짜박스 좌우 끝과 정렬 */
    .st-key-tl_header,
    [class*="st-key-tl_row_"] {
      padding-left: 72px !important;
      padding-right: 72px !important;
    }
    /* req-item 통합 카드 버튼 스타일 */
    [class*="st-key-home_goto_"] button {
      background: var(--bg-card) !important;
      border: 1px solid var(--border-light) !important;
      border-radius: var(--radius-lg) !important;
      padding: 6px 10px !important;
      width: 100% !important;
      height: auto !important;
      min-height: 0 !important;
      white-space: normal !important;
      word-break: break-word !important;
      justify-content: flex-start !important;
    }
    [class*="st-key-home_goto_"] button [data-testid="stMarkdownContainer"] {
      text-align: left !important;
      width: 100% !important;
    }
    [class*="st-key-home_goto_"] button [data-testid="stMarkdownContainer"] p {
      margin: 0 !important;
      text-align: left !important;
      font-size: 12px !important;
      color: var(--text-primary) !important;
      line-height: 1.5 !important;
    }
    [class*="st-key-home_goto_"] button [data-testid="stMarkdownContainer"] strong {
      font-size: 13px !important;
      color: var(--text-primary) !important;
    }
    [class*="st-key-home_goto_"] button:hover {
      background: var(--neutral-100) !important;
      border-color: var(--brand-blue) !important;
    }
/* 전일/익일 버튼 텍스트 한 줄 고정 */
    .st-key-sched_prev button,
    .st-key-sched_next button {
      white-space: nowrap !important;
      font-size: 12px !important;
      padding: 4px 8px !important;
    }
    /* ── 프로젝트 선택 박스 ── */
    .st-key-proj_select_wrap,
    .st-key-proj_new_wrap {
      max-width: 360px !important;
      margin: 0 auto 10px auto !important;
    }
    /* 셀렉트+화살표를 하나의 박스처럼 통합 */
    .st-key-proj_select_wrap [data-testid="stHorizontalBlock"] {
      background: var(--bg-card) !important;
      border: 1.5px solid var(--neutral-500) !important;
      border-radius: var(--radius-lg) !important;
      overflow: hidden !important;
      gap: 0 !important;
      align-items: stretch !important;
      padding: 0 !important;
    }
    .st-key-proj_select_wrap [data-testid="stColumn"] {
      padding: 0 !important;
    }
    .st-key-proj_select_wrap [data-testid="stColumn"] > div,
    .st-key-proj_select_wrap [data-testid="stElementContainer"],
    .st-key-proj_select_wrap [data-testid="stVerticalBlock"] {
      padding: 0 !important;
      margin: 0 !important;
      gap: 0 !important;
      height: 100% !important;
    }
    .st-key-proj_select_wrap [data-testid="stButton"],
    .st-key-proj_select_wrap [data-testid="stButton"] > div {
      height: 100% !important;
      width: 100% !important;
      margin: 0 !important;
      padding: 0 !important;
    }
    /* 파란 버튼 폭 확장 — 컬럼 내 고정 너비 */
    .st-key-proj_go_btn {
      min-width: 72px !important;
    }
    /* 셀렉트박스 내부 테두리 제거 */
    .st-key-proj_select_wrap [data-baseweb="select"] > div:first-child {
      border: none !important;
      border-radius: 0 !important;
      background: transparent !important;
      box-shadow: none !important;
    }
    /* 화살표(▶) 버튼 스타일 */
    .st-key-proj_go_btn button {
      border-radius: 0 !important;
      border: none !important;
      border-left: 1.5px solid var(--neutral-500) !important;
      height: 100% !important;
      min-height: 46px !important;
      width: 100% !important;
      background: linear-gradient(135deg, var(--primary-600), var(--primary-700)) !important;
      color: #ffffff !important;
      font-size: 16px !important;
      padding: 0 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      text-align: center !important;
    }
    .st-key-proj_go_btn button > div,
    .st-key-proj_go_btn button > div > div {
      display: flex !important;
      align-items: center !important;
      justify-content: flex-start !important;
      width: 100% !important;
      padding: 0 0 0 12px !important;
      margin: 0 !important;
    }
    .st-key-proj_go_btn button p,
    .st-key-proj_go_btn button span {
      color: #ffffff !important;
      line-height: 1 !important;
      margin: 0 !important;
      padding: 0 !important;
      text-align: left !important;
      width: auto !important;
    }
    .st-key-proj_go_btn button:hover {
      background: linear-gradient(135deg, var(--primary-700), var(--primary-800)) !important;
    }
    /* 셀렉트박스 래퍼: 상하 가운데 */
    .st-key-proj_select_wrap [data-baseweb="select"] > div:first-child {
      min-height: 46px !important;
      display: flex !important;
      align-items: center !important;
    }
    /* 텍스트 영역(첫 번째 자식): 좌측 정렬 */
    .st-key-proj_select_wrap [data-baseweb="select"] > div:first-child > div:first-child {
      flex: 1 !important;
      display: flex !important;
      align-items: center !important;
      justify-content: flex-start !important;
      text-align: left !important;
      color: var(--neutral-400) !important;
      font-size: var(--font-size-sm) !important;
      padding-left: 8px !important;
    }
    /* 선택 후 텍스트는 기본색 */
    .st-key-proj_select_wrap [data-baseweb="select"] > div:first-child > div:first-child [data-testid="stMarkdownContainer"] p {
      color: var(--text-primary) !important;
      text-align: left !important;
    }
    /* 새 프로젝트 만들기 내부 간격 — 라벨↔입력 좁게, 필드 간격 24px */
    .st-key-proj_new_wrap [data-testid="stExpander"] label {
      margin-bottom: 0px !important;
      padding-bottom: 0px !important;
    }
    .st-key-proj_new_wrap [data-testid="stExpander"] [data-testid="stWidgetLabel"] {
      min-height: 0 !important;
      line-height: 1.2 !important;
      padding-bottom: 2px !important;
    }
    .st-key-proj_new_wrap [data-testid="stExpander"] [data-testid="stWidgetLabel"] > span {
      line-height: 1.2 !important;
    }
    .st-key-proj_new_wrap [data-testid="stExpander"] [data-testid="stElementContainer"] {
      margin-bottom: 24px !important;
    }
    /* 프로젝트 생성 버튼 — 높이·색상·가운데 정렬 */
    .st-key-proj_new_wrap [data-testid="stExpander"] .st-key-create_proj {
      margin-top: var(--font-size-sm) !important;
      width: 100% !important;
      display: flex !important;
      justify-content: center !important;
    }
    .st-key-proj_new_wrap [data-testid="stExpander"] .st-key-create_proj [data-testid="stButton"] {
      width: auto !important;
    }
    .st-key-proj_new_wrap [data-testid="stExpander"] .st-key-create_proj button {
      min-height: 46px !important;
      height: 46px !important;
      width: auto !important;
      padding: 0 40px !important;
      font-size: var(--font-size-sm) !important;
      font-weight: var(--font-weight-semibold) !important;
      color: #ffffff !important;
    }
    .st-key-proj_new_wrap [data-testid="stExpander"] .st-key-create_proj button p {
      color: #ffffff !important;
      margin: 0 !important;
    }
    /* 새 프로젝트 만들기 expander — 프로젝트 선택 박스와 동일 스펙 */
    .st-key-proj_new_wrap [data-testid="stExpander"] {
      border: 1.5px solid var(--neutral-500) !important;
      border-radius: var(--radius-lg) !important;
      overflow: hidden !important;
    }
    .st-key-proj_new_wrap [data-testid="stExpander"] summary {
      min-height: 46px !important;
      padding: 0 12px !important;
      position: relative !important;
    }
    /* 외부 span을 flex로 — 텍스트 가운데 */
    .st-key-proj_new_wrap [data-testid="stExpander"] summary > span {
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
      width: 100% !important;
      position: relative !important;
    }
    /* 화살표 아이콘 컨테이너 절대 위치(우측) — 텍스트 흐름에서 제거 */
    .st-key-proj_new_wrap [data-testid="stExpander"] summary > span > span:first-child {
      position: absolute !important;
      right: 0 !important;
      color: var(--neutral-400) !important;
    }
    /* 텍스트 가운데 + 색상·마진 통일 */
    .st-key-proj_new_wrap [data-testid="stExpander"] summary p {
      color: var(--neutral-400) !important;
      font-size: var(--font-size-sm) !important;
      font-weight: var(--font-weight-regular) !important;
      margin: 0 !important;
      text-align: center !important;
    }
    /* ── 로그인 폼: 입력박스↔다음라벨 간격 +14px ── */
    .st-key-login_form_wrap [data-testid="stElementContainer"] {
      margin-bottom: 18px !important;
    }
    /* ── 로그인 하단 행: 버튼 + 관리자 나란히 ── */
    .st-key-login_bottom_row [data-testid="stHorizontalBlock"] {
      align-items: center !important;
      gap: 8px !important;
      margin-top: 12px !important;
    }
    /* 로그인 버튼 — 전체 폭, 흰색, 상하 중간 */
    .st-key-login_bottom_row [data-testid="stColumn"]:first-child button {
      font-size: 18px !important;
      font-weight: 700 !important;
      color: #ffffff !important;
      height: 52px !important;
      width: 100% !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
    }
    .st-key-login_bottom_row [data-testid="stColumn"]:first-child button p {
      color: #ffffff !important;
      font-size: 18px !important;
      font-weight: 700 !important;
      margin: 0 !important;
      line-height: 1 !important;
    }
    /* 관리자 expander summary 내부 텍스트 상하 중간 */
    .st-key-login_admin_wrap [data-testid="stExpander"] summary p,
    .st-key-login_admin_wrap [data-testid="stExpander"] summary span {
      margin: 0 !important;
      line-height: 1 !important;
    }
    /* 관리자 컬럼 — 오른쪽 끝 정렬 */
    .st-key-login_admin_wrap {
      display: flex !important;
      justify-content: flex-end !important;
    }
    .st-key-login_admin_wrap > [data-testid="stVerticalBlock"] {
      width: auto !important;
    }
    /* 관리자 expander — 작은 크기, 상하 중간 */
    .st-key-login_admin_wrap [data-testid="stExpander"] {
      min-width: 110px !important;
      width: auto !important;
    }
    .st-key-login_admin_wrap [data-testid="stExpander"] summary {
      min-height: 36px !important;
      padding: 0 12px !important;
      display: flex !important;
      align-items: center !important;
    }
    /* 관리자 PIN 입력 — 라벨·입력박스 간격 최소화 */
    .st-key-login_admin_wrap [data-testid="stWidgetLabel"] {
      margin-bottom: 0 !important;
      padding-bottom: 0 !important;
      min-height: unset !important;
      line-height: 1 !important;
    }
    .st-key-login_admin_wrap [data-testid="stWidgetLabel"] label {
      margin-bottom: 0 !important;
      line-height: 1 !important;
      font-size: 12px !important;
    }
    .st-key-login_admin_wrap [data-testid="stTextInput"] {
      margin-top: 0 !important;
      padding-top: 0 !important;
    }
    .st-key-login_admin_wrap [data-baseweb="input"] {
      margin-top: 0 !important;
    }
    /* 회원가입 버튼 — 텍스트와 간격 + 로그인 버튼과 동일 높이 */
    .st-key-go_signup {
      margin-top: 16px !important;
    }
    .st-key-go_signup button {
      min-height: 40px !important;
      height: 40px !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
    }
    /* ── 폼 제출 버튼: 기본 주황 ── */
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button {
      background-color: #ED7D31 !important;
      border-color: #d46a1f !important;
      color: #ffffff !important;
      display: flex !important;
      align-items: center !important;
      justify-content: center !important;
    }
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button:hover {
      background-color: #d46a1f !important;
      border-color: #b85a18 !important;
    }
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button p,
    [data-testid="stForm"] [data-testid="stFormSubmitButton"] button * {
      color: #ffffff !important;
      margin: 0 !important;
      line-height: 1 !important;
    }
    /* ── 예약 신청 버튼(req_unified_form): 파란색 ── */
    [class*="st-key-req_unified_form"] [data-testid="stFormSubmitButton"] button {
      background-color: #2563eb !important;
      border-color: #1d4ed8 !important;
    }
    [class*="st-key-req_unified_form"] [data-testid="stFormSubmitButton"] button:hover {
      background-color: #1d4ed8 !important;
      border-color: #1e40af !important;
    }
    /* ── 홈 계획 리스트 — 계획 버튼에만 테두리 ── */
    [class*="st-key-home_goto_btn_"] button {
      border: 1.5px solid #94a3b8 !important;
      border-radius: 8px !important;
      box-shadow: 0 1px 3px rgba(0,0,0,0.06) !important;
    }
    /* ── 홈 신규 신청 버튼 — 카드와 간격 ── */
    .st-key-home_new_req {
      margin-top: 20px !important;
    }
    /* ── 홈·대장 Delete 버튼: 붉은색, 행 높이 가득 채움 ── */
    [class*="st-key-home_goto_"] [data-testid="stHorizontalBlock"],
    [class*="st-key-ledger_row_"] [data-testid="stHorizontalBlock"] {
      align-items: stretch !important;
    }
    [class*="st-key-home_del_"],
    [class*="st-key-ledger_del_"] {
      display: flex !important;
      align-items: stretch !important;
      height: 100% !important;
    }
    [class*="st-key-home_del_"] [data-testid="stElementContainer"],
    [class*="st-key-home_del_"] [data-testid="stVerticalBlock"],
    [class*="st-key-ledger_del_"] [data-testid="stElementContainer"],
    [class*="st-key-ledger_del_"] [data-testid="stVerticalBlock"] {
      height: 100% !important;
      display: flex !important;
      flex-direction: column !important;
    }
    :root [class*="st-key-home_del_"] button,
    :root [class*="st-key-ledger_del_"] button {
      background-color: #b91c1c !important;
      border-color: #b91c1c !important;
      color: #ffffff !important;
      height: 100% !important;
      width: 100% !important;
      min-height: unset !important;
      padding-top: 0 !important;
      padding-bottom: 0 !important;
    }
    :root [class*="st-key-home_del_"] button:hover,
    :root [class*="st-key-ledger_del_"] button:hover {
      background-color: #991b1b !important;
      border-color: #991b1b !important;
    }
    :root [class*="st-key-home_del_"] button,
    :root [class*="st-key-home_del_"] button p,
    :root [class*="st-key-home_del_"] button *,
    :root [class*="st-key-ledger_del_"] button,
    :root [class*="st-key-ledger_del_"] button p,
    :root [class*="st-key-ledger_del_"] button * {
      color: #f8f8f8 !important;
    }
    /* ── 차량 대수 number input 가운데 정렬 ── */
    [data-testid="stNumberInput"] input {
      text-align: center !important;
    }
    /* ── 예약 신청 폼: 구분선 상하 여백 축소 ── */
    [data-testid="stForm"] hr {
      margin-top: 4px !important;
      margin-bottom: 4px !important;
    }
    /* ── 예약 신청 폼: 라벨↔입력 간격 확대, 입력↔다음라벨 간격 확대 ── */
    [data-testid="stForm"] [data-testid="stWidgetLabel"] {
      margin-bottom: -10px !important;
      padding-bottom: 0px !important;
    }
    [data-testid="stForm"] [data-testid="stElementContainer"] {
      margin-bottom: 16px !important;
    }
    /* ── 위젯 라벨 ↔ 입력박스 간격 전역 축소 ── */
    [data-testid="stWidgetLabel"] {
      margin-bottom: -8px !important;
      padding-bottom: 0 !important;
      line-height: 1.2 !important;
    }
    /* ── 체크박스 수직 정렬 (체크박스 ↔ 라벨 텍스트) ── */
    [data-testid="stCheckbox"] label {
      display: flex !important;
      align-items: flex-start !important;
      gap: 8px !important;
      cursor: pointer;
      min-height: 24px;
    }
    [data-testid="stCheckbox"] label > span:first-child {
      flex-shrink: 0 !important;
      margin-top: 2px !important;
    }
    [data-testid="stCheckbox"] label p,
    [data-testid="stCheckbox"] label div {
      margin: 0 !important;
      line-height: 1.5 !important;
    }
    </style>
    """, unsafe_allow_html=True)
