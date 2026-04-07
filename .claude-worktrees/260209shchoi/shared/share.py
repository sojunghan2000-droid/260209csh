"""Share text generation for KakaoTalk / messenger sharing."""

from pathlib import Path
from typing import Dict, Any, Optional

from config import KIND_IN


def make_share_text(req: Dict[str, Any], outs: Optional[Dict[str, Any]]) -> str:
    """Build a human-readable share string for a request + its outputs."""
    kind_txt = "반입" if req["kind"] == KIND_IN else "반출"
    rid = req["id"]
    lines = []
    lines.append(f"[자재 {kind_txt}] {req.get('date','')} {req.get('time_from','')}~{req.get('time_to','')} / GATE:{req.get('gate','')}")
    lines.append(f"- 협력사: {req.get('company_name','')} / 자재: {req.get('item_name','')}")
    lines.append(f"- 차량: {req.get('vehicle_type','')} {str(req.get('vehicle_ton','')).replace('톤','')}톤 {req.get('vehicle_count',1)}대")
    lines.append(f"- 기사: {req.get('driver_name','')} ({req.get('driver_phone','')}) / 상태: {req.get('status','')}")
    if outs:
        doc_title = "자재반입계획서" if req["kind"] == KIND_IN else "반출사진"
        lines.append("— 산출물 —")
        if outs.get("plan_pdf_path"):
            lines.append(f"  · {doc_title}: {Path(outs.get('plan_pdf_path')).name}")
    return "\n".join(lines)
