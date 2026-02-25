"""Module 3: Student & Grade Management.

Fetches students enrolled in a course with their current grades
and provides formatting for TUI display.
"""

from canvasapi import Canvas


def get_students(canvas: Canvas, course_id: int) -> list:
    """Fetch all students in a course with their current grades.

    Returns a list of dicts with keys:
        user_id, name, sortable_name, current_score, current_grade,
        final_score, final_grade.

    Raises RuntimeError on API failure.
    """
    try:
        course = canvas.get_course(course_id)
        enrollments = list(course.get_enrollments(
            type=["StudentEnrollment"],
            include=["current_points"],
        ))
    except Exception as e:
        raise RuntimeError(f"Failed to fetch students for course {course_id}: {e}") from e

    students = []
    for enrollment in enrollments:
        user_info = enrollment.user
        grades = getattr(enrollment, "grades", None) or {}

        students.append({
            "user_id": user_info["id"],
            "name": user_info["name"],
            "sortable_name": user_info["sortable_name"],
            "current_score": grades.get("current_score"),
            "current_grade": grades.get("current_grade"),
            "final_score": grades.get("final_score"),
            "final_grade": grades.get("final_grade"),
        })

    return students


def format_student_grade(student: dict) -> dict:
    """Format a student's grade data for display.

    Returns dict with keys: user_id, name, sortable_name, current, final.
    """
    def _fmt_grade(score, letter):
        if score is None:
            return "N/A"
        if letter is not None:
            return f"{score}% ({letter})"
        return f"{score}%"

    return {
        "user_id": student["user_id"],
        "name": student["name"],
        "sortable_name": student["sortable_name"],
        "current": _fmt_grade(student["current_score"], student["current_grade"]),
        "final": _fmt_grade(student["final_score"], student["final_grade"]),
    }
