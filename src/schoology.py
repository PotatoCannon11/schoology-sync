import os
import requests
from requests_oauthlib import OAuth1
from datetime import datetime, timezone


class SchoologyClient:
    def __init__(self):
        self.consumer_key = os.environ["SCHOOLOGY_CONSUMER_KEY"]
        self.consumer_secret = os.environ["SCHOOLOGY_CONSUMER_SECRET"]
        self.domain = os.environ["SCHOOLOGY_DOMAIN"]
        self.base_url = f"https://{self.domain}/api/v1"
        self.auth = OAuth1(self.consumer_key, self.consumer_secret)
        self.user_id = None

    def _get(self, endpoint, params=None):
        url = f"{self.base_url}{endpoint}"
        response = requests.get(url, auth=self.auth, params=params)
        print(f"  GET {url} → {response.status_code}")
        if not response.ok:
            print(f"  Response body: {response.text[:500]}")
        response.raise_for_status()
        return response.json()

    def get_me(self):
        data = self._get("/users/me")
        self.user_id = data["id"]
        return data

    def get_sections(self):
        """Get all enrolled course sections."""
        data = self._get("/sections", params={"limit": 100})
        return data.get("section", [])

    def get_assignments(self, section_id):
        """Get all assignments for a section."""
        data = self._get(f"/sections/{section_id}/assignments", params={"limit": 100})
        return data.get("assignment", [])

    def get_grades(self):
        """Get grades for all sections."""
        if not self.user_id:
            self.get_me()
        data = self._get(f"/users/{self.user_id}/grades")
        return data.get("section", [])

    def get_all_assignments_with_grades(self):
        """
        Returns a list of assignments enriched with course name and current grade.
        [
            {
                "id": ...,
                "title": ...,
                "due": "2026-04-20 23:59:00",
                "description": ...,
                "max_points": ...,
                "course_name": ...,
                "section_id": ...,
                "current_grade": 82.5,   # None if not available
            },
            ...
        ]
        """
        sections = self.get_sections()
        grades_by_section = self._build_grades_map()

        all_assignments = []

        for section in sections:
            section_id = section["id"]
            course_title = section.get("course_title", "Unknown Course")
            current_grade = grades_by_section.get(str(section_id))

            try:
                assignments = self.get_assignments(section_id)
            except Exception as e:
                print(f"Warning: could not fetch assignments for section {section_id}: {e}")
                continue

            for a in assignments:
                due_raw = a.get("due", "")
                if not due_raw:
                    continue  # skip assignments with no due date

                all_assignments.append({
                    "id": a.get("id"),
                    "title": a.get("title", "Untitled"),
                    "due": due_raw,
                    "description": a.get("description", ""),
                    "max_points": a.get("max_points"),
                    "course_name": course_title,
                    "section_id": section_id,
                    "current_grade": current_grade,
                })

        # Filter to only upcoming assignments
        now = datetime.now(timezone.utc)
        upcoming = []
        for a in all_assignments:
            try:
                due_dt = datetime.strptime(a["due"], "%Y-%m-%d %H:%M:%S").replace(tzinfo=timezone.utc)
                if due_dt >= now:
                    a["due_dt"] = due_dt
                    upcoming.append(a)
            except ValueError:
                continue

        # Sort by due date
        upcoming.sort(key=lambda x: x["due_dt"])
        return upcoming

    def _build_grades_map(self):
        """Returns {section_id_str: grade_percent} from the grades endpoint."""
        grade_map = {}
        try:
            sections = self.get_grades()
            for section in sections:
                sid = str(section.get("section_id", ""))
                period = section.get("period", [])
                if period:
                    # Use the last grading period as current
                    latest = period[-1]
                    grade = latest.get("grade", {})
                    grade_val = grade.get("grade")
                    if grade_val is not None:
                        try:
                            grade_map[sid] = float(grade_val)
                        except (ValueError, TypeError):
                            pass
        except Exception as e:
            print(f"Warning: could not fetch grades: {e}")
        return grade_map
