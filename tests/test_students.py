"""Tests for Module 3: Student & Grade Management."""

from unittest.mock import MagicMock

import pytest

from src.students import get_students, format_student_grade


def _make_mock_enrollment(user_id, user_name, sortable_name,
                          current_score=None, current_grade=None,
                          final_score=None, final_grade=None):
    """Helper to create a mock Canvas enrollment object with grade info."""
    enrollment = MagicMock()
    enrollment.user_id = user_id
    enrollment.type = "StudentEnrollment"

    # User info nested in enrollment
    enrollment.user = {"id": user_id, "name": user_name, "sortable_name": sortable_name}

    # Grades dict as returned by Canvas API
    enrollment.grades = {
        "current_score": current_score,
        "current_grade": current_grade,
        "final_score": final_score,
        "final_grade": final_grade,
    }

    return enrollment


class TestGetStudents:
    """Tests for fetching students with grades from a course."""

    def test_returns_list_of_students_with_grades(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        enrollments = [
            _make_mock_enrollment(1, "Alice Smith", "Smith, Alice", 95.0, "A", 92.0, "A-"),
            _make_mock_enrollment(2, "Bob Jones", "Jones, Bob", 82.5, "B", 80.0, "B-"),
        ]
        mock_course.get_enrollments.return_value = enrollments

        students = get_students(mock_canvas, 1001)
        assert len(students) == 2

    def test_fetches_course_by_id(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_enrollments.return_value = []

        get_students(mock_canvas, 9999)
        mock_canvas.get_course.assert_called_once_with(9999)

    def test_requests_student_enrollments_with_grades(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_enrollments.return_value = []

        get_students(mock_canvas, 1001)
        mock_course.get_enrollments.assert_called_once()
        call_kwargs = mock_course.get_enrollments.call_args[1]
        assert call_kwargs["type"] == ["StudentEnrollment"]
        assert "current_points" in call_kwargs["include"]

    def test_returns_dicts_with_expected_keys(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        enrollments = [
            _make_mock_enrollment(1, "Alice Smith", "Smith, Alice", 95.0, "A", 92.0, "A-"),
        ]
        mock_course.get_enrollments.return_value = enrollments

        students = get_students(mock_canvas, 1001)
        student = students[0]
        assert student["user_id"] == 1
        assert student["name"] == "Alice Smith"
        assert student["sortable_name"] == "Smith, Alice"
        assert student["current_score"] == 95.0
        assert student["current_grade"] == "A"
        assert student["final_score"] == 92.0
        assert student["final_grade"] == "A-"

    def test_returns_empty_list_when_no_students(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_enrollments.return_value = []

        students = get_students(mock_canvas, 1001)
        assert students == []

    def test_handles_missing_grades_gracefully(self):
        """Students with no grade data should get None values."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        enrollment = _make_mock_enrollment(
            3, "Charlie Brown", "Brown, Charlie",
            current_score=None, current_grade=None,
            final_score=None, final_grade=None,
        )
        mock_course.get_enrollments.return_value = [enrollment]

        students = get_students(mock_canvas, 1001)
        student = students[0]
        assert student["current_score"] is None
        assert student["current_grade"] is None
        assert student["final_score"] is None
        assert student["final_grade"] is None

    def test_handles_enrollment_with_no_grades_attribute(self):
        """Enrollment object missing the grades attribute entirely."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        enrollment = MagicMock()
        enrollment.user_id = 4
        enrollment.user = {"id": 4, "name": "Dana White", "sortable_name": "White, Dana"}
        del enrollment.grades

        mock_course.get_enrollments.return_value = [enrollment]

        students = get_students(mock_canvas, 1001)
        student = students[0]
        assert student["user_id"] == 4
        assert student["current_score"] is None
        assert student["current_grade"] is None
        assert student["final_score"] is None
        assert student["final_grade"] is None

    def test_raises_on_api_error(self):
        mock_canvas = MagicMock()
        mock_canvas.get_course.side_effect = Exception("API error")

        with pytest.raises(RuntimeError, match="Failed to fetch students"):
            get_students(mock_canvas, 1001)

    def test_raises_on_enrollment_api_error(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_enrollments.side_effect = Exception("Enrollment fetch failed")

        with pytest.raises(RuntimeError, match="Failed to fetch students"):
            get_students(mock_canvas, 1001)


class TestFormatStudentGrade:
    """Tests for formatting a student's grade summary for display."""

    def test_formats_student_with_full_grades(self):
        student = {
            "user_id": 1,
            "name": "Alice Smith",
            "sortable_name": "Smith, Alice",
            "current_score": 95.0,
            "current_grade": "A",
            "final_score": 92.0,
            "final_grade": "A-",
        }
        result = format_student_grade(student)
        assert result["name"] == "Alice Smith"
        assert result["sortable_name"] == "Smith, Alice"
        assert result["current_grade"] == "A"
        assert result["current_score"] == "95.0%"
        assert result["final_grade"] == "A-"
        assert result["final_score"] == "92.0%"

    def test_formats_student_with_no_current_grade(self):
        student = {
            "user_id": 2,
            "name": "Bob Jones",
            "sortable_name": "Jones, Bob",
            "current_score": None,
            "current_grade": None,
            "final_score": 80.0,
            "final_grade": "B-",
        }
        result = format_student_grade(student)
        assert result["current_grade"] is None
        assert result["current_score"] is None
        assert result["final_grade"] == "B-"
        assert result["final_score"] == "80.0%"

    def test_formats_student_with_no_final_grade(self):
        student = {
            "user_id": 3,
            "name": "Charlie Brown",
            "sortable_name": "Brown, Charlie",
            "current_score": 88.0,
            "current_grade": "B+",
            "final_score": None,
            "final_grade": None,
        }
        result = format_student_grade(student)
        assert result["current_grade"] == "B+"
        assert result["current_score"] == "88.0%"
        assert result["final_grade"] is None
        assert result["final_score"] is None

    def test_formats_student_with_no_grades_at_all(self):
        student = {
            "user_id": 4,
            "name": "Dana White",
            "sortable_name": "White, Dana",
            "current_score": None,
            "current_grade": None,
            "final_score": None,
            "final_grade": None,
        }
        result = format_student_grade(student)
        assert result["current_grade"] is None
        assert result["current_score"] is None
        assert result["final_grade"] is None
        assert result["final_score"] is None

    def test_formats_score_with_no_letter_grade(self):
        """Score exists but letter grade is None (pass/fail courses)."""
        student = {
            "user_id": 5,
            "name": "Eve Adams",
            "sortable_name": "Adams, Eve",
            "current_score": 75.0,
            "current_grade": None,
            "final_score": 70.0,
            "final_grade": None,
        }
        result = format_student_grade(student)
        assert result["current_score"] == "75.0%"
        assert result["current_grade"] is None
        assert result["final_score"] == "70.0%"
        assert result["final_grade"] is None

    def test_includes_user_id(self):
        student = {
            "user_id": 1,
            "name": "Alice Smith",
            "sortable_name": "Smith, Alice",
            "current_score": 95.0,
            "current_grade": "A",
            "final_score": 92.0,
            "final_grade": "A-",
        }
        result = format_student_grade(student)
        assert result["user_id"] == 1
