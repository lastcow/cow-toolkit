"""Tests for Module 2: Course List Screen."""

from unittest.mock import MagicMock, patch, PropertyMock

import pytest

from src.courses import get_courses, format_course_info


def _make_mock_course(name, code, term_name, enrollments_count=25):
    """Helper to create a mock Canvas course object."""
    course = MagicMock()
    course.name = name
    course.course_code = code
    course.id = 1001

    # Term is a dict attribute on the course object
    course.term = {"name": term_name}

    # total_students is an attribute returned when include[]=total_students
    course.total_students = enrollments_count

    return course


class TestGetCourses:
    """Tests for fetching courses from Canvas API."""

    def test_returns_list_of_courses(self):
        mock_canvas = MagicMock()
        mock_courses = [
            _make_mock_course("Intro to CS", "CS101", "Fall 2025", 30),
            _make_mock_course("Data Structures", "CS201", "Fall 2025", 22),
        ]
        mock_canvas.get_courses.return_value = mock_courses

        courses = get_courses(mock_canvas)
        assert len(courses) == 2

    def test_calls_canvas_api_with_teacher_enrollment(self):
        mock_canvas = MagicMock()
        mock_canvas.get_courses.return_value = []

        get_courses(mock_canvas)
        mock_canvas.get_courses.assert_called_once()
        call_kwargs = mock_canvas.get_courses.call_args[1]
        assert call_kwargs["enrollment_type"] == "teacher"

    def test_requests_term_and_student_count(self):
        mock_canvas = MagicMock()
        mock_canvas.get_courses.return_value = []

        get_courses(mock_canvas)
        call_kwargs = mock_canvas.get_courses.call_args[1]
        includes = call_kwargs["include"]
        assert "term" in includes
        assert "total_students" in includes

    def test_returns_empty_list_when_no_courses(self):
        mock_canvas = MagicMock()
        mock_canvas.get_courses.return_value = []

        courses = get_courses(mock_canvas)
        assert courses == []

    def test_raises_on_api_error(self):
        mock_canvas = MagicMock()
        mock_canvas.get_courses.side_effect = Exception("API error")

        with pytest.raises(RuntimeError, match="Failed to fetch courses"):
            get_courses(mock_canvas)


class TestFormatCourseInfo:
    """Tests for formatting course data for display."""

    def test_formats_single_course(self):
        course = _make_mock_course("Intro to CS", "CS101", "Fall 2025", 30)
        info = format_course_info(course)

        assert info["name"] == "Intro to CS"
        assert info["code"] == "CS101"
        assert info["students"] == 30
        assert info["term"] == "Fall 2025"

    def test_handles_missing_term(self):
        course = _make_mock_course("Intro to CS", "CS101", "Fall 2025", 30)
        # Simulate missing term attribute
        del course.term
        course.term = None

        info = format_course_info(course)
        assert info["term"] == "N/A"

    def test_handles_missing_total_students(self):
        course = _make_mock_course("Intro to CS", "CS101", "Fall 2025", 30)
        del course.total_students
        course.total_students = None

        info = format_course_info(course)
        assert info["students"] == 0

    def test_includes_course_id(self):
        course = _make_mock_course("Intro to CS", "CS101", "Fall 2025", 30)
        info = format_course_info(course)
        assert info["id"] == 1001
