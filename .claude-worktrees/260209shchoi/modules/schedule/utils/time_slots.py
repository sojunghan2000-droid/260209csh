"""Time slot utilities."""
from datetime import datetime, timedelta


def generate_30min_slots(start="06:00", end="22:00"):
    """Generate a list of 30-minute time slot strings.

    Args:
        start: Start time in "HH:MM" format (default "06:00").
        end: End time in "HH:MM" format (default "22:00").

    Returns:
        List of "HH:MM" strings at 30-minute intervals.
    """
    slots = []
    current = datetime.strptime(start, "%H:%M")
    end_dt = datetime.strptime(end, "%H:%M")
    while current < end_dt:
        slots.append(current.strftime("%H:%M"))
        current += timedelta(minutes=30)
    return slots


def slots_overlap(a_from, a_to, b_from, b_to):
    """Check if two time ranges overlap.

    Args:
        a_from: Start of range A ("HH:MM").
        a_to: End of range A ("HH:MM").
        b_from: Start of range B ("HH:MM").
        b_to: End of range B ("HH:MM").

    Returns:
        True if the two ranges overlap, False otherwise.
    """
    return a_from < b_to and b_from < a_to
