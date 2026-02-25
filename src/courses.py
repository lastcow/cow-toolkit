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
