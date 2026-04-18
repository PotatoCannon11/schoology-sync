import sys
from src.schoology import SchoologyClient
from src.prioritize import prioritize_all, summarize
from src.calendar_sync import sync_to_calendar
from src.reminders_sync import sync_to_reminders


def main():
    print("=" * 50)
    print(f"Schoology Sync")
    print("=" * 50)

    # --- Step 1: Fetch from Schoology ---
    print("\n📚 Fetching assignments from Schoology...")
    try:
        client = SchoologyClient()
        client.get_me()
        assignments = client.get_all_assignments_with_grades()
        print(f"  Found {len(assignments)} upcoming assignments")
    except Exception as e:
        print(f"  ✗ Failed to fetch from Schoology: {e}")
        sys.exit(1)

    if not assignments:
        print("  Nothing to sync. Exiting.")
        return

    # --- Step 2: Prioritize ---
    print("\n🧠 Prioritizing assignments...")
    assignments = prioritize_all(assignments)
    print(summarize(assignments))

    high = sum(1 for a in assignments if a["priority"] == "high")
    medium = sum(1 for a in assignments if a["priority"] == "medium")
    low = sum(1 for a in assignments if a["priority"] == "low")
    print(f"\n  🔴 High: {high}  🟡 Medium: {medium}  🟢 Low: {low}")

    # --- Step 3: Sync to Apple Calendar ---
    print("\n📅 Syncing to Apple Calendar...")
    try:
        cal_result = sync_to_calendar(assignments)
        print(f"  Added: {cal_result['added']} | Skipped: {cal_result['skipped']} | Errors: {cal_result['errors']}")
    except Exception as e:
        print(f"  ✗ Calendar sync failed: {e}")

    # --- Step 4: Sync to Apple Reminders ---
    print("\n🔔 Syncing to Apple Reminders...")
    try:
        rem_result = sync_to_reminders(assignments)
        print(f"  Added: {rem_result['added']} | Skipped: {rem_result['skipped']} | Errors: {rem_result['errors']}")
    except Exception as e:
        print(f"  ✗ Reminders sync failed: {e}")

    print("\n✅ Done.")


if __name__ == "__main__":
    main()
