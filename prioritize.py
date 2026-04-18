from datetime import datetime, timezone


# --- Thresholds (tweak these to your liking) ---
GRADE_DANGER_THRESHOLD = 88       # below this = struggling in the class
GRADE_WARNING_THRESHOLD = 91      # below this = worth paying attention to
DUE_URGENT_DAYS = 2               # due within this many days = urgent
DUE_SOON_DAYS = 3                 # due within this many days = soon
HIGH_POINT_THRESHOLD = 40         # assignments worth this many points = major grade


def score_assignment(assignment: dict) -> dict:
    """
    Adds priority metadata to an assignment dict.

    Returns the same dict with added keys:
        priority        : "high" | "medium" | "low"
        is_reminder     : bool — should this go to Apple Reminders?
        reasons         : list[str] — human readable reasons for priority
    """
    now = datetime.now(timezone.utc)
    due_dt = assignment.get("due_dt")
    grade = assignment.get("current_grade")       # float or None
    max_points = assignment.get("max_points")     # float/int or None
    title = assignment.get("title", "").lower()

    reasons = []
    score = 0

    # --- Due date urgency ---
    if due_dt:
        days_left = (due_dt - now).total_seconds() / 86400
        if days_left <= DUE_URGENT_DAYS:
            score += 3
            reasons.append(f"due in {int(days_left * 24)}hrs")
        elif days_left <= DUE_SOON_DAYS:
            score += 1
            reasons.append(f"due in {int(days_left)} days")

    # --- Grade pressure ---
    if grade is not None:
        if grade < GRADE_DANGER_THRESHOLD:
            score += 3
            reasons.append(f"grade is {grade:.0f}% (danger)")
        elif grade < GRADE_WARNING_THRESHOLD:
            score += 1
            reasons.append(f"grade is {grade:.0f}% (watch)")

    # --- Point value (major grades) ---
    if max_points is not None:
        try:
            pts = float(max_points)
            if pts >= HIGH_POINT_THRESHOLD:
                score += 2
                reasons.append(f"worth {pts:.0f} pts")
        except (ValueError, TypeError):
            pass

    # --- Keyword signals in title ---
    major_keywords = ["test", "exam", "quiz", "final", "midterm", "project", "essay", "lab report"]
    for kw in major_keywords:
        if kw in title:
            score += 1
            reasons.append(f'keyword "{kw}"')
            break  # only count once

    # --- Map score to priority ---
    if score >= 4:
        priority = "high"
    elif score >= 2:
        priority = "medium"
    else:
        priority = "low"

    assignment["priority"] = priority
    assignment["priority_score"] = score
    assignment["is_reminder"] = priority == "high"
    assignment["reasons"] = reasons

    return assignment


def prioritize_all(assignments: list[dict]) -> list[dict]:
    """Score and sort a list of assignments. High priority first."""
    scored = [score_assignment(a) for a in assignments]
    scored.sort(key=lambda x: (-x["priority_score"], x["due_dt"]))
    return scored


def summarize(assignments: list[dict]) -> str:
    """Print a readable summary for logs."""
    lines = []
    for a in assignments:
        flag = "🔴" if a["priority"] == "high" else "🟡" if a["priority"] == "medium" else "🟢"
        reasons = ", ".join(a["reasons"]) if a["reasons"] else "no flags"
        due_str = a["due_dt"].strftime("%b %d %I:%M%p") if a.get("due_dt") else "no due date"
        lines.append(f"{flag} [{a['course_name']}] {a['title']} — due {due_str} ({reasons})")
    return "\n".join(lines)
