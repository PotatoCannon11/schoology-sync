import os
import caldav
from datetime import datetime, timezone
from icalendar import Calendar, Todo
import uuid


REMINDERS_LIST_NAME = "Schoology Important"


def get_client():
    username = os.environ["ICLOUD_USERNAME"]
    password = os.environ["ICLOUD_APP_PASSWORD"]
    client = caldav.DAVClient(
        url="https://caldav.icloud.com",
        username=username,
        password=password,
    )
    return client


def get_or_create_reminder_list(principal):
    """Find the Schoology reminders list or create it."""
    for cal in principal.calendars():
        # Apple Reminders lists show up as calendars with VTODO support
        if cal.name == REMINDERS_LIST_NAME:
            return cal

    calendar = principal.make_calendar(
        name=REMINDERS_LIST_NAME,
        supported_calendar_component_set=["VTODO"],
    )
    print(f"Created new reminders list: {REMINDERS_LIST_NAME}")
    return calendar


def get_existing_todo_uids(reminder_list) -> set[str]:
    """Fetch all VTODO UIDs to avoid duplicates."""
    uids = set()
    try:
        todos = reminder_list.todos()
        for todo in todos:
            cal = Calendar.from_ical(todo.data)
            for component in cal.walk():
                if component.name == "VTODO":
                    uid = str(component.get("UID", ""))
                    if uid:
                        uids.add(uid)
    except Exception as e:
        print(f"Warning: could not fetch existing reminders: {e}")
    return uids


def assignment_to_uid(assignment: dict) -> str:
    """Same deterministic UID pattern as calendar_sync for consistency."""
    return f"schoology-reminder-{assignment['section_id']}-{assignment['id']}"


def build_vtodo(assignment: dict) -> bytes:
    """Build an iCalendar VTODO for a high-priority assignment."""
    cal = Calendar()
    cal.add("prodid", "-//Schoology Sync//EN")
    cal.add("version", "2.0")

    todo = Todo()
    todo.add("uid", assignment_to_uid(assignment))
    todo.add("summary", f"⚠️ [{assignment['course_name']}] {assignment['title']}")
    todo.add("due", assignment["due_dt"])
    todo.add("dtstamp", datetime.now(timezone.utc))

    # Priority: 1 = highest in iCalendar spec
    todo.add("priority", 1)

    # Description
    desc_parts = []
    if assignment.get("reasons"):
        desc_parts.append(f"Flagged because: {', '.join(assignment['reasons'])}")
    if assignment.get("current_grade") is not None:
        desc_parts.append(f"Current grade in {assignment['course_name']}: {assignment['current_grade']:.0f}%")
    if assignment.get("max_points"):
        desc_parts.append(f"Worth: {assignment['max_points']} points")
    if assignment.get("description"):
        desc_parts.append(f"\n{assignment['description']}")

    todo.add("description", "\n".join(desc_parts))

    # Status: NEEDS-ACTION is the default incomplete state
    todo.add("status", "NEEDS-ACTION")

    cal.add_component(todo)
    return cal.to_ical()


def sync_to_reminders(assignments: list[dict]) -> dict:
    """
    Sync high-priority assignments to Apple Reminders via CalDAV.
    Only processes assignments where is_reminder=True.
    Returns a summary dict with counts.
    """
    important = [a for a in assignments if a.get("is_reminder")]

    if not important:
        print("  No high-priority assignments to add to Reminders.")
        return {"added": 0, "skipped": 0, "errors": 0}

    client = get_client()
    principal = client.principal()
    reminder_list = get_or_create_reminder_list(principal)
    existing_uids = get_existing_todo_uids(reminder_list)

    added = 0
    skipped = 0
    errors = 0

    for assignment in important:
        uid = assignment_to_uid(assignment)

        if uid in existing_uids:
            skipped += 1
            continue

        try:
            vtodo_data = build_vtodo(assignment)
            reminder_list.add_todo(vtodo_data.decode("utf-8"))
            added += 1
            print(f"  ✓ Reminder added: [{assignment['course_name']}] {assignment['title']} — {', '.join(assignment['reasons'])}")
        except Exception as e:
            errors += 1
            print(f"  ✗ Failed to add reminder for {assignment['title']}: {e}")

    return {"added": added, "skipped": skipped, "errors": errors}
