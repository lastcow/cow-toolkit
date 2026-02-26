"""Module 2: Course List Screen.

Fetches enrolled courses (as instructor) from Canvas API and
provides formatting for TUI display.
"""

from canvasapi import Canvas


def get_courses(canvas: Canvas) -> list:
    """Fetch all courses where the user is enrolled as a teacher.

    Returns a list of course objects.
    Raises RuntimeError on API failure.
    """
    try:
        courses = list(canvas.get_courses(
            enrollment_type="teacher",
            include=["term", "total_students"],
        ))
        return courses
    except Exception as e:
        raise RuntimeError(f"Failed to fetch courses: {e}") from e


def get_current_term_courses(courses: list) -> list:
    """Filter courses to only those in the most recent academic term.

    Ignores non-year terms like 'Default Term'. Detects the latest
    year+season term automatically (e.g. '2026 Spring').
    """
    import re

    season_order = {"intersession": 0, "spring": 1, "summer": 2, "fall": 3}

    def term_sort_key(course):
        term = getattr(course, "term", None)
        name = ""
        if term and isinstance(term, dict):
            name = term.get("name", "")
        elif hasattr(term, "name"):
            name = term.name or ""
        name = name.strip()
        m = re.match(r"(\d{4})\s+(\w+)", name, re.IGNORECASE)
        if m:
            year = int(m.group(1))
            season = season_order.get(m.group(2).lower(), -1)
            return (year, season)
        return (-1, -1)

    year_based = [c for c in courses if term_sort_key(c) != (-1, -1)]
    if not year_based:
        return courses

    best = max(term_sort_key(c) for c in year_based)
    return [c for c in year_based if term_sort_key(c) == best]


def format_course_info(course) -> dict:
    """Extract display-friendly info from a Canvas course object.

    Returns dict with keys: id, name, code, students, term.
    """
    # Handle missing term
    term = getattr(course, "term", None)
    if term and isinstance(term, dict):
        term_name = term.get("name", "N/A")
    else:
        term_name = "N/A"

    # Handle missing total_students
    total_students = getattr(course, "total_students", None)
    if total_students is None:
        total_students = 0

    return {
        "id": course.id,
        "name": course.name,
        "code": course.course_code,
        "students": total_students,
        "term": term_name,
    }
