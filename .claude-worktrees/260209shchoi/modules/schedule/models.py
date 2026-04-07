"""Schedule-specific table definitions and queries.

Note: actual CREATE TABLE is in db/migrations.py.
This file holds query constants and data validation.
"""

TIME_SLOTS_START = "06:00"
TIME_SLOTS_END = "18:30"
SLOT_INTERVAL_MINUTES = 30


def generate_time_slots():
    """Generate list of 30-min time slots from 06:00 to 22:00.

    Returns a list of "HH:MM" strings, e.g. ["06:00", "06:30", "07:00", ...].
    """
    slots = []
    start_h, start_m = [int(x) for x in TIME_SLOTS_START.split(":")]
    end_h, end_m = [int(x) for x in TIME_SLOTS_END.split(":")]
    h, m = start_h, start_m
    while (h, m) < (end_h, end_m):
        slots.append(f"{h:02d}:{m:02d}")
        m += SLOT_INTERVAL_MINUTES
        if m >= 60:
            m -= 60
            h += 1
    return slots


def check_conflict(sb, project_id, schedule_date, time_from, time_to, exclude_id=None):
    """Check if a time slot conflicts with existing schedules.

    Returns a list of conflicting schedule dicts. Empty list means no conflict.
    """
    q = (sb.table("schedules").select("*")
         .eq("project_id", project_id)
         .eq("schedule_date", schedule_date)
         .lt("time_from", time_to)
         .gt("time_to", time_from))
    if exclude_id:
        q = q.neq("id", exclude_id)
    res = q.execute()
    return res.data or []
