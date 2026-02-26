"""Module 4: Assignment/Quiz Engine.

List, create, and update assignments for a Canvas course.
"""

from canvasapi import Canvas


def list_assignments(canvas: Canvas, course_id: int) -> list:
    """Fetch all assignments for a course.

    Returns a list of dicts with keys:
        id, name, points_possible, due_at, description,
        submission_types, published.

    Raises RuntimeError on API failure.
    """
    try:
        course = canvas.get_course(course_id)
        assignments = list(course.get_assignments())
    except Exception as e:
        raise RuntimeError(
            f"Failed to fetch assignments for course {course_id}: {e}"
        ) from e

    result = []
    for a in assignments:
        result.append({
            "id": a.id,
            "name": a.name,
            "points_possible": getattr(a, "points_possible", None) or 0,
            "due_at": getattr(a, "due_at", None),
            "description": getattr(a, "description", None) or "",
            "submission_types": getattr(a, "submission_types", []),
            "published": getattr(a, "published", False),
            "needs_grading_count": getattr(a, "needs_grading_count", 0) or 0,
        })

    return result


def create_assignment(canvas: Canvas, course_id: int, data: dict):
    """Create a new assignment in a course.

    data should contain assignment fields (name, points_possible, etc.).
    Returns the created assignment object.
    Raises RuntimeError on API failure.
    """
    try:
        course = canvas.get_course(course_id)
        assignment = course.create_assignment(assignment=data)
    except Exception as e:
        raise RuntimeError(
            f"Failed to create assignment in course {course_id}: {e}"
        ) from e

    return assignment


def update_assignment(canvas: Canvas, course_id: int, assignment_id: int,
                      data: dict):
    """Update an existing assignment.

    data should contain the fields to update.
    Returns the updated assignment object.
    Raises RuntimeError on API failure.
    """
    try:
        course = canvas.get_course(course_id)
        assignment = course.get_assignment(assignment_id)
        updated = assignment.edit(assignment=data)
    except Exception as e:
        raise RuntimeError(
            f"Failed to update assignment {assignment_id} in course {course_id}: {e}"
        ) from e

    return updated
