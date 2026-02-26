"""Tests for Module 4: Assignment/Quiz Engine."""

from unittest.mock import MagicMock

import pytest

from src.assignments import list_assignments, create_assignment, update_assignment


def _make_mock_assignment(assignment_id, name, points=100, due_at=None,
                          description="", submission_types=None,
                          published=True):
    """Helper to create a mock Canvas assignment object."""
    assignment = MagicMock()
    assignment.id = assignment_id
    assignment.name = name
    assignment.points_possible = points
    assignment.due_at = due_at
    assignment.description = description
    assignment.submission_types = submission_types or ["online_text_entry"]
    assignment.published = published
    return assignment


class TestListAssignments:
    """Tests for listing assignments in a course."""

    def test_returns_list_of_assignments(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        assignments = [
            _make_mock_assignment(1, "Homework 1", 100, "2025-10-01T23:59:00Z"),
            _make_mock_assignment(2, "Midterm Exam", 200, "2025-10-15T23:59:00Z"),
            _make_mock_assignment(3, "Final Project", 300, "2025-12-01T23:59:00Z"),
        ]
        mock_course.get_assignments.return_value = assignments

        result = list_assignments(mock_canvas, 1001)
        assert len(result) == 3

    def test_fetches_correct_course(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignments.return_value = []

        list_assignments(mock_canvas, 9999)
        mock_canvas.get_course.assert_called_once_with(9999)

    def test_returns_dicts_with_expected_keys(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        assignments = [
            _make_mock_assignment(
                42, "Essay 1", 50, "2025-11-01T23:59:00Z",
                description="Write an essay", submission_types=["online_upload"],
                published=True,
            ),
        ]
        mock_course.get_assignments.return_value = assignments

        result = list_assignments(mock_canvas, 1001)
        a = result[0]
        assert a["id"] == 42
        assert a["name"] == "Essay 1"
        assert a["points_possible"] == 50
        assert a["due_at"] == "2025-11-01T23:59:00Z"
        assert a["description"] == "Write an essay"
        assert a["submission_types"] == ["online_upload"]
        assert a["published"] is True

    def test_returns_empty_list_when_no_assignments(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignments.return_value = []

        result = list_assignments(mock_canvas, 1001)
        assert result == []

    def test_handles_missing_due_at(self):
        """Assignment with no due date should return None for due_at."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        assignment = _make_mock_assignment(1, "No Due Date HW", 100)
        assignment.due_at = None
        mock_course.get_assignments.return_value = [assignment]

        result = list_assignments(mock_canvas, 1001)
        assert result[0]["due_at"] is None

    def test_handles_missing_description(self):
        """Assignment with no description should return empty string."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        assignment = _make_mock_assignment(1, "HW1", 100)
        del assignment.description
        mock_course.get_assignments.return_value = [assignment]

        result = list_assignments(mock_canvas, 1001)
        assert result[0]["description"] == ""

    def test_handles_missing_points_possible(self):
        """Assignment with no points_possible should return 0."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        assignment = _make_mock_assignment(1, "Ungraded", 100)
        del assignment.points_possible
        mock_course.get_assignments.return_value = [assignment]

        result = list_assignments(mock_canvas, 1001)
        assert result[0]["points_possible"] == 0

    def test_raises_on_course_fetch_error(self):
        mock_canvas = MagicMock()
        mock_canvas.get_course.side_effect = Exception("Course not found")

        with pytest.raises(RuntimeError, match="Failed to fetch assignments"):
            list_assignments(mock_canvas, 1001)

    def test_raises_on_assignments_fetch_error(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignments.side_effect = Exception("API timeout")

        with pytest.raises(RuntimeError, match="Failed to fetch assignments"):
            list_assignments(mock_canvas, 1001)

    def test_includes_needs_grading_count(self):
        """Returned dicts should include needs_grading_count."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        assignment = _make_mock_assignment(1, "HW1", 100)
        assignment.needs_grading_count = 5
        mock_course.get_assignments.return_value = [assignment]

        result = list_assignments(mock_canvas, 1001)
        assert result[0]["needs_grading_count"] == 5

    def test_needs_grading_count_defaults_to_zero(self):
        """Missing needs_grading_count should default to 0."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        assignment = _make_mock_assignment(1, "HW1", 100)
        del assignment.needs_grading_count
        mock_course.get_assignments.return_value = [assignment]

        result = list_assignments(mock_canvas, 1001)
        assert result[0]["needs_grading_count"] == 0


class TestCreateAssignment:
    """Tests for creating a new assignment in a course."""

    def test_creates_assignment_with_required_fields(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course

        mock_new = _make_mock_assignment(10, "New HW", 100)
        mock_course.create_assignment.return_value = mock_new

        data = {"name": "New HW", "points_possible": 100}
        result = create_assignment(mock_canvas, 1001, data)

        assert result.id == 10
        assert result.name == "New HW"

    def test_passes_data_under_assignment_key(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.create_assignment.return_value = MagicMock()

        data = {
            "name": "Quiz 1",
            "points_possible": 50,
            "due_at": "2025-11-01T23:59:00Z",
            "submission_types": ["online_quiz"],
        }
        create_assignment(mock_canvas, 1001, data)

        mock_course.create_assignment.assert_called_once_with(
            assignment=data
        )

    def test_fetches_correct_course(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.create_assignment.return_value = MagicMock()

        create_assignment(mock_canvas, 5555, {"name": "Test"})
        mock_canvas.get_course.assert_called_once_with(5555)

    def test_creates_assignment_with_all_optional_fields(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.create_assignment.return_value = MagicMock()

        data = {
            "name": "Full Assignment",
            "points_possible": 100,
            "due_at": "2025-12-01T23:59:00Z",
            "description": "A detailed description",
            "submission_types": ["online_upload", "online_text_entry"],
            "published": False,
        }
        create_assignment(mock_canvas, 1001, data)
        mock_course.create_assignment.assert_called_once_with(assignment=data)

    def test_raises_on_course_fetch_error(self):
        mock_canvas = MagicMock()
        mock_canvas.get_course.side_effect = Exception("Course not found")

        with pytest.raises(RuntimeError, match="Failed to create assignment"):
            create_assignment(mock_canvas, 1001, {"name": "Test"})

    def test_raises_on_create_api_error(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.create_assignment.side_effect = Exception("Validation error")

        with pytest.raises(RuntimeError, match="Failed to create assignment"):
            create_assignment(mock_canvas, 1001, {"name": "Bad Assignment"})


class TestUpdateAssignment:
    """Tests for updating an existing assignment."""

    def test_updates_assignment_successfully(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment
        mock_assignment.edit.return_value = mock_assignment

        data = {"name": "Updated HW", "points_possible": 150}
        result = update_assignment(mock_canvas, 1001, 42, data)

        assert result == mock_assignment

    def test_fetches_correct_course_and_assignment(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment
        mock_assignment.edit.return_value = mock_assignment

        update_assignment(mock_canvas, 1001, 42, {"name": "Test"})
        mock_canvas.get_course.assert_called_once_with(1001)
        mock_course.get_assignment.assert_called_once_with(42)

    def test_passes_data_under_assignment_key(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment
        mock_assignment.edit.return_value = mock_assignment

        data = {"name": "Renamed", "due_at": "2025-12-15T23:59:00Z"}
        update_assignment(mock_canvas, 1001, 42, data)
        mock_assignment.edit.assert_called_once_with(assignment=data)

    def test_updates_single_field(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment
        mock_assignment.edit.return_value = mock_assignment

        data = {"published": True}
        update_assignment(mock_canvas, 1001, 42, data)
        mock_assignment.edit.assert_called_once_with(assignment={"published": True})

    def test_raises_on_course_fetch_error(self):
        mock_canvas = MagicMock()
        mock_canvas.get_course.side_effect = Exception("Course not found")

        with pytest.raises(RuntimeError, match="Failed to update assignment"):
            update_assignment(mock_canvas, 1001, 42, {"name": "Test"})

    def test_raises_on_assignment_fetch_error(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.side_effect = Exception("Assignment not found")

        with pytest.raises(RuntimeError, match="Failed to update assignment"):
            update_assignment(mock_canvas, 1001, 42, {"name": "Test"})

    def test_raises_on_edit_api_error(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment
        mock_assignment.edit.side_effect = Exception("Forbidden")

        with pytest.raises(RuntimeError, match="Failed to update assignment"):
            update_assignment(mock_canvas, 1001, 42, {"name": "Test"})
