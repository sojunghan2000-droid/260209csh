"""Module registry — maps module keys to page functions."""
from typing import Dict, Callable, Any


def get_page_router() -> Dict[str, Callable]:
    """Return mapping of page_name → page_function.

    Lazy imports to avoid circular dependencies.
    """
    from modules.request.page import page_request
    from modules.approval.page import page_approval
    from modules.execution.page import page_execute
    from modules.outputs.page import page_outputs
    from modules.ledger.page import page_ledger
    from modules.admin.page import page_admin
    from modules.schedule.page import page_schedule

    return {
        "요청":     page_request,
        "승인":     page_approval,
        "확인":     page_execute,
        "산출물":   page_outputs,
        "대장":     page_ledger,
        "관리자":   page_admin,
        "스케줄링": page_schedule,
    }
