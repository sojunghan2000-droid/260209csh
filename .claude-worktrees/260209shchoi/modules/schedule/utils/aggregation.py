"""Statistics and aggregation for schedules."""
from typing import List, Dict, Any
from config import KIND_IN, KIND_OUT


def daily_stats(schedules: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Compute daily statistics from a list of schedule entries.

    Returns a dict with:
        - total: total count
        - in_count: number of IN entries
        - out_count: number of OUT entries
        - by_status: dict of status -> count
        - by_gate: dict of gate -> count
    """
    total = len(schedules)
    in_count = sum(1 for s in schedules if s.get("kind") == KIND_IN)
    out_count = sum(1 for s in schedules if s.get("kind") == KIND_OUT)

    by_status: Dict[str, int] = {}
    for s in schedules:
        status = s.get("status", "PENDING")
        by_status[status] = by_status.get(status, 0) + 1

    by_gate: Dict[str, int] = {}
    for s in schedules:
        gate = s.get("gate", "N/A") or "N/A"
        by_gate[gate] = by_gate.get(gate, 0) + 1

    return {
        "total": total,
        "in_count": in_count,
        "out_count": out_count,
        "by_status": by_status,
        "by_gate": by_gate,
    }


def gate_distribution(schedules: List[Dict[str, Any]]) -> Dict[str, Dict[str, int]]:
    """Compute gate distribution with IN/OUT breakdown.

    Returns a dict of gate -> {"in": count, "out": count, "total": count}.
    """
    dist: Dict[str, Dict[str, int]] = {}
    for s in schedules:
        gate = s.get("gate", "N/A") or "N/A"
        if gate not in dist:
            dist[gate] = {"in": 0, "out": 0, "total": 0}
        kind = s.get("kind", "")
        if kind == KIND_IN:
            dist[gate]["in"] += 1
        elif kind == KIND_OUT:
            dist[gate]["out"] += 1
        dist[gate]["total"] += 1
    return dist
