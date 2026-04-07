"""Schedule module-specific CSS."""


def get_schedule_css() -> str:
    """Return CSS styles for the schedule timeline grid and related components."""
    return """
    /* 날짜 선택 박스: 연한 파란 배경, 테두리 없음, 가운데 정렬 */
    .st-key-sched_date_pick [data-baseweb="input"] {
      background: var(--primary-100, #dbeafe) !important;
      border: none !important;
      border-radius: 8px !important;
      box-shadow: none !important;
    }
    .st-key-sched_date_pick [data-baseweb="input"]:focus-within {
      box-shadow: none !important;
      border: none !important;
    }
    .st-key-sched_date_pick input {
      text-align: center !important;
      color: var(--primary-700, #1d4ed8) !important;
      font-weight: 600 !important;
    }
    .sched-timeline {
        border: 1px solid var(--border-color, #e5e7eb);
        border-radius: 8px;
        overflow: hidden;
        margin-top: 8px;
    }
    .sched-header {
        display: grid;
        grid-template-columns: 60px 1fr 1fr;
        background: var(--bg-secondary, #f3f4f6);
        font-size: 12px;
        font-weight: 600;
        padding: 6px 0;
        text-align: center;
        border-bottom: 1px solid var(--border-color, #e5e7eb);
    }
    .sched-row {
        display: grid;
        grid-template-columns: 60px 1fr 1fr;
        border-bottom: 1px solid var(--border-color, #e5e7eb);
        align-items: start;
    }
    .sched-row:last-child {
        border-bottom: none;
    }
    .sched-time {
        font-size: 11px;
        color: var(--text-muted, #6b7280);
        padding: 4px 6px;
        text-align: center;
        border-right: 1px solid var(--border-color, #e5e7eb);
    }
    .sched-cell {
        min-height: 22px;
        padding: 1px 4px;
        font-size: 11px;
        border-right: 1px solid var(--border-color, #e5e7eb);
    }
    .sched-cell:last-child {
        border-right: none;
    }
    .sched-block {
        font-size: 11px;
        padding: 2px 6px;
        border-radius: 4px;
        background: var(--bg-hover, #f9fafb);
        margin: 1px 0;
        overflow: hidden;
        text-overflow: ellipsis;
        white-space: nowrap;
    }
    @media (max-width: 768px) {
        /* 태블릿: 반출 컬럼 숨기고 반입만 표시 */
        .sched-header,
        .sched-row {
            grid-template-columns: 52px 1fr !important;
        }
        .sched-header > span:last-child,
        .sched-row > span:last-child {
            display: none !important;
        }
        .sched-block {
            font-size: 10px !important;
            padding: 2px 4px !important;
        }
    }
    @media (max-width: 480px) {
        /* 모바일: 타임라인 최소화 */
        .sched-timeline {
            margin-top: 4px !important;
        }
        .sched-header,
        .sched-row {
            grid-template-columns: 44px 1fr !important;
        }
        .sched-header > span:last-child,
        .sched-row > span:last-child {
            display: none !important;
        }
        .sched-header {
            font-size: 10px !important;
            padding: 4px 0 !important;
        }
        .sched-time {
            font-size: 10px !important;
            padding: 3px 2px !important;
        }
        .sched-cell {
            min-height: 18px !important;
            padding: 1px 3px !important;
        }
        .sched-block {
            font-size: 10px !important;
            padding: 1px 4px !important;
            max-width: 100% !important;
        }
    }
    """
