import os
import caldav
from caldav.elements import dav
from datetime import datetime, timedelta, timezone
from icalendar import Calendar, Event, vText
import uuid


CALENDAR_NAME = "Schoology Assignments"


def get_client():
    username = os.environ["ICLOUD_USERNAME"]
    password = os.environ["ICLOUD_APP_PASSWORD"]
    client = caldav.DAVClient(
        url="https://caldav.icloud.com",
        username=username,
        password=password,
    )
    return client


def get_or_create_calendar(principal):
    """Find the Schoology calendar or create it if it doesn't exist."""
    for cal in principal.calendars():
        if cal.name == CALENDAR_NAME:
            return cal

    # Create it if not found
    calendar = principal.make_calendar(name=CALENDAR_NAME)
    print(f"Created new calendar: {CALENDAR_NAME}")
    return calendar


def get_existing_uids(calendar) -> set[str]:
    """Fetch all event UIDs currently in the calendar to avoid duplicates."""
    uids = set()
    try:
        events = calendar.events()
        for event in events:
            cal = Calendar.from_ical(event.data)
            for component in cal.walk():
                if component.name == "VEVENT":
                    uid = str(component.get("UID", ""))
                    if uid:
                        uids.add(uid)
    except Exception as e:
        print(f"Warning: could not fetch existing events: {e}")
    return uids


def assignment_to_uid(assignment: dict) -> str:
    """Deterministic UID so the same assignment always maps to the same event."""
    return f"schoology-{assignment['section_id']}-{assignment['id']}"


def build_ical_event(assignment: dict) -> bytes:
    """Build an iCalendar VEVENT for an assignment."""
    cal = Calendar()
    cal.add("prodid", "-//Schoology Sync//EN")
    cal.add("version", "2.0")

    event = Event()
    event.add("uid", assignment_to_uid(assignment))
    event.add("summary", f"[{assignment['course_name']}] {assignment['title']}")
    event.add("dtstart", assignment["due_dt"])
    event.add("dtend", assignment["due_dt"] + timedelta(hours=1))
    event.add("dtstamp", datetime.now(timezone.utc))

    # Build description
    desc_parts = []
    if assignment.get("description"):
        desc_parts.append(assignment["description"])
    if assignment.get("max_points"):
        desc_parts.append(f"Points: {assignment['max_points']}")
    if assignment.get("current_grade") is not None:
        desc_parts.append(f"Current grade: {assignment['current_grade']:.0f}%")
    if assignment.get("reasons"):
        desc_parts.append(f"Flagged: {', '.join(assignment['reasons'])}")

    event.add("description", "\n".join(desc_parts))

    # Color-code by priority using categories
    priority_map = {"high": "RED", "medium": "ORANGE", "low": "NONE"}
    event.add("categories", [assignment.get("priority", "low").upper()])

    cal.add_component(event)
    return cal.to_ical()


def sync_to_calendar(assignments: list[dict]) -> dict:
    """
    Sync assignments to iCloud Calendar.
    Returns a summary dict with counts.
    """
    client = get_client()
    principal = client.principal()
    calendar = get_or_create_calendar(principal)
    existing_uids = get_existing_uids(calendar)

    added = 0
    skipped = 0
    errors = 0

    for assignment in assignments:
        uid = assignment_to_uid(assignment)

        if uid in existing_uids:
            skipped += 1
            continue

        try:
            ical_data = build_ical_event(assignment)
            calendar.add_event(ical_data.decode("utf-8"))
            added += 1
            print(f"  ✓ Added: [{assignment['course_name']}] {assignment['title']}")
        except Exception as e:
            errors += 1
            print(f"  ✗ Failed to add {assignment['title']}: {e}")

    return {"added": added, "skipped": skipped, "errors": errors}
