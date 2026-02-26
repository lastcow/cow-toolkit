"""Tests for Module 5: Smart Grading Interface."""

from unittest.mock import MagicMock

import pytest

from src.grading import list_submissions, calculate_grade, format_submission


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_submission(submission_id, user_id, body="Some answer",
                          submitted_at="2025-11-01T10:00:00Z",
                          workflow_state="submitted", score=None,
                          user_name="Jane Doe", graded_at=None, attempt=1):
    """Helper to create a mock Canvas submission object."""
    sub = MagicMock()
    sub.id = submission_id
    sub.user_id = user_id
    sub.body = body
    sub.submitted_at = submitted_at
    sub.workflow_state = workflow_state
    sub.score = score
    sub.graded_at = graded_at
    sub.attempt = attempt
    sub.user = {"id": user_id, "name": user_name}
    return sub


# ===========================================================================
# list_submissions
# ===========================================================================

class TestListSubmissions:
    """Tests for listing submissions for an assignment."""

    def test_returns_list_of_submissions(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        subs = [
            _make_mock_submission(1, 101, body="Answer 1"),
            _make_mock_submission(2, 102, body="Answer 2"),
            _make_mock_submission(3, 103, body="Answer 3"),
        ]
        mock_assignment.get_submissions.return_value = subs

        result = list_submissions(mock_canvas, 1001, 42)
        assert len(result) == 3

    def test_fetches_correct_course_and_assignment(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment
        mock_assignment.get_submissions.return_value = []

        list_submissions(mock_canvas, 9999, 55)
        mock_canvas.get_course.assert_called_once_with(9999)
        mock_course.get_assignment.assert_called_once_with(55)

    def test_returns_dicts_with_expected_keys(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        subs = [
            _make_mock_submission(
                10, 201, body="My essay text",
                submitted_at="2025-11-05T08:30:00Z",
                workflow_state="submitted", score=None,
                user_name="Alice",
            ),
        ]
        mock_assignment.get_submissions.return_value = subs

        result = list_submissions(mock_canvas, 1001, 42)
        s = result[0]
        assert s["id"] == 10
        assert s["user_id"] == 201
        assert s["body"] == "My essay text"
        assert s["submitted_at"] == "2025-11-05T08:30:00Z"
        assert s["workflow_state"] == "submitted"
        assert s["score"] is None
        assert s["user_name"] == "Alice"
        assert "attempt" in s
        assert "graded_at" in s
        assert "resubmitted" in s
        assert s["resubmitted"] is False  # not graded yet

    def test_returns_empty_list_when_no_submissions(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment
        mock_assignment.get_submissions.return_value = []

        result = list_submissions(mock_canvas, 1001, 42)
        assert result == []

    def test_handles_missing_body(self):
        """Submission with no body should return empty string."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        sub = _make_mock_submission(1, 101, body="placeholder")
        del sub.body
        mock_assignment.get_submissions.return_value = [sub]

        result = list_submissions(mock_canvas, 1001, 42)
        assert result[0]["body"] == ""

    def test_handles_none_body(self):
        """Submission with body=None should return empty string."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        sub = _make_mock_submission(1, 101, body=None)
        mock_assignment.get_submissions.return_value = [sub]

        result = list_submissions(mock_canvas, 1001, 42)
        assert result[0]["body"] == ""

    def test_handles_missing_submitted_at(self):
        """Submission with no submitted_at should return None."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        sub = _make_mock_submission(1, 101)
        del sub.submitted_at
        mock_assignment.get_submissions.return_value = [sub]

        result = list_submissions(mock_canvas, 1001, 42)
        assert result[0]["submitted_at"] is None

    def test_raises_on_course_fetch_error(self):
        mock_canvas = MagicMock()
        mock_canvas.get_course.side_effect = Exception("Course not found")

        with pytest.raises(RuntimeError, match="Failed to fetch submissions"):
            list_submissions(mock_canvas, 1001, 42)

    def test_raises_on_assignment_fetch_error(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.side_effect = Exception("Assignment not found")

        with pytest.raises(RuntimeError, match="Failed to fetch submissions"):
            list_submissions(mock_canvas, 1001, 42)

    def test_raises_on_submissions_fetch_error(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment
        mock_assignment.get_submissions.side_effect = Exception("API timeout")

        with pytest.raises(RuntimeError, match="Failed to fetch submissions"):
            list_submissions(mock_canvas, 1001, 42)


# ===========================================================================
# calculate_grade
# ===========================================================================

class TestCalculateGrade:
    """Tests for the 'Professor' grading logic."""

    def test_returns_dict_with_required_keys(self):
        result = calculate_grade(
            "The CPU processes instructions using the fetch-decode-execute cycle.",
            ["CPU", "fetch-decode-execute cycle"],
        )
        assert "score" in result
        assert "feedback" in result
        assert "letter_grade" in result

    def test_score_is_integer_in_range(self):
        result = calculate_grade(
            "Machine learning uses algorithms to learn patterns from data.",
            ["machine learning", "algorithms", "patterns"],
        )
        assert isinstance(result["score"], int)
        assert 0 <= result["score"] <= 100

    def test_all_key_points_addressed_gives_high_score(self):
        """When student covers all key points → score 90-100."""
        text = (
            "An operating system manages hardware resources. "
            "It provides process scheduling to share the CPU. "
            "Memory management allocates RAM to processes. "
            "File systems organize data on disk."
        )
        key_points = [
            "hardware resources",
            "process scheduling",
            "memory management",
            "file systems",
        ]
        result = calculate_grade(text, key_points)
        assert result["score"] >= 90

    def test_no_key_points_addressed_gives_low_score(self):
        """When student addresses none of the key points → low score."""
        text = "I really enjoyed this class. The lectures were great."
        key_points = [
            "binary search",
            "time complexity",
            "divide and conquer",
        ]
        result = calculate_grade(text, key_points)
        assert result["score"] < 50

    def test_partial_key_points_gives_proportional_score(self):
        """When student covers some key points → proportional score."""
        text = (
            "Encryption converts plaintext into ciphertext "
            "to protect sensitive data."
        )
        key_points = [
            "encryption",
            "ciphertext",
            "public key infrastructure",
            "digital signatures",
        ]
        result = calculate_grade(text, key_points)
        # 2 out of 4 key points → roughly 50-70 range
        assert 40 <= result["score"] <= 80

    def test_case_insensitive_matching(self):
        """Key point matching should be case-insensitive."""
        text = "RECURSION is a technique where a function calls itself."
        key_points = ["recursion"]
        result = calculate_grade(text, key_points)
        assert result["score"] >= 90

    def test_does_not_deduct_for_grammar_errors(self):
        """Grammar/syntax mistakes should NOT lower the score."""
        text = (
            "the cpu it do the fetch decode execute cycle thing "
            "and the alu does arithmatic. registers store data temporarly."
        )
        key_points = [
            "cpu",
            "fetch decode execute",
            "alu",
            "registers",
        ]
        result = calculate_grade(text, key_points)
        # All key points addressed despite poor grammar
        assert result["score"] >= 85

    def test_feedback_is_nonempty_string(self):
        result = calculate_grade("Some answer.", ["topic"])
        assert isinstance(result["feedback"], str)
        assert len(result["feedback"]) > 0

    def test_feedback_is_supportive_tone(self):
        """Feedback should be encouraging, not harsh."""
        result = calculate_grade(
            "I tried my best but couldn't explain it well.",
            ["data structures", "algorithms"],
        )
        feedback_lower = result["feedback"].lower()
        # Should not contain harsh/negative language
        assert "wrong" not in feedback_lower
        assert "terrible" not in feedback_lower
        assert "fail" not in feedback_lower

    def test_letter_grade_A_for_high_score(self):
        text = (
            "Polymorphism allows objects of different classes to be treated "
            "through the same interface. Inheritance lets subclasses extend "
            "parent classes. Encapsulation hides internal state."
        )
        key_points = ["polymorphism", "inheritance", "encapsulation"]
        result = calculate_grade(text, key_points)
        assert result["letter_grade"] in ("A+", "A", "A-")

    def test_letter_grade_F_for_very_low_score(self):
        text = "I don't know."
        key_points = ["sorting", "searching", "graph traversal", "dynamic programming"]
        result = calculate_grade(text, key_points)
        assert result["letter_grade"] == "F"

    def test_letter_grade_mapping_consistency(self):
        """Letter grade should match the numeric score."""
        # Test a range of scenarios
        # Score >= 93 → A
        result = calculate_grade(
            "TCP uses a three-way handshake for reliable connections. "
            "UDP is connectionless and faster but unreliable.",
            ["TCP", "three-way handshake", "UDP", "connectionless"],
        )
        score = result["score"]
        letter = result["letter_grade"]
        if score >= 93:
            assert letter in ("A+", "A")
        elif score >= 90:
            assert letter == "A-"
        elif score >= 87:
            assert letter == "B+"
        elif score >= 83:
            assert letter == "B"
        elif score >= 80:
            assert letter == "B-"
        elif score >= 77:
            assert letter == "C+"
        elif score >= 73:
            assert letter == "C"
        elif score >= 70:
            assert letter == "C-"
        elif score >= 67:
            assert letter == "D+"
        elif score >= 63:
            assert letter == "D"
        elif score >= 60:
            assert letter == "D-"
        else:
            assert letter == "F"

    def test_empty_submission_text(self):
        """Empty submission text should get a very low score."""
        result = calculate_grade("", ["topic1", "topic2"])
        assert result["score"] < 20

    def test_empty_key_points_list(self):
        """No key points means nothing to check → full marks."""
        result = calculate_grade("Any text here.", [])
        assert result["score"] >= 90

    def test_single_key_point_addressed(self):
        result = calculate_grade(
            "Arrays store elements in contiguous memory locations.",
            ["arrays"],
        )
        assert result["score"] >= 90


# ===========================================================================
# format_submission
# ===========================================================================

class TestFormatSubmission:
    """Tests for formatting a submission dict for display."""

    def test_returns_dict_with_display_keys(self):
        sub = {
            "id": 1,
            "user_id": 101,
            "user_name": "Alice",
            "body": "My answer here.",
            "submitted_at": "2025-11-01T10:00:00Z",
            "workflow_state": "submitted",
            "score": 95,
        }
        result = format_submission(sub)
        assert "student" in result
        assert "submitted_at" in result
        assert "status" in result
        assert "body_preview" in result
        assert "score" in result

    def test_student_name_displayed(self):
        sub = {
            "id": 1,
            "user_id": 101,
            "user_name": "Bob Smith",
            "body": "Answer",
            "submitted_at": "2025-11-01T10:00:00Z",
            "workflow_state": "submitted",
            "score": None,
        }
        result = format_submission(sub)
        assert result["student"] == "Bob Smith"

    def test_score_displayed_when_graded(self):
        sub = {
            "id": 1,
            "user_id": 101,
            "user_name": "Alice",
            "body": "Answer",
            "submitted_at": "2025-11-01T10:00:00Z",
            "workflow_state": "graded",
            "score": 88,
        }
        result = format_submission(sub)
        assert "88" in str(result["score"])

    def test_score_na_when_ungraded(self):
        sub = {
            "id": 1,
            "user_id": 101,
            "user_name": "Alice",
            "body": "Answer",
            "submitted_at": "2025-11-01T10:00:00Z",
            "workflow_state": "submitted",
            "score": None,
        }
        result = format_submission(sub)
        assert result["score"] == "N/A"

    def test_body_preview_truncated(self):
        """Long body text should be truncated in the preview."""
        long_body = "A" * 500
        sub = {
            "id": 1,
            "user_id": 101,
            "user_name": "Alice",
            "body": long_body,
            "submitted_at": "2025-11-01T10:00:00Z",
            "workflow_state": "submitted",
            "score": None,
        }
        result = format_submission(sub)
        assert len(result["body_preview"]) <= 203  # 200 + "..."

    def test_body_preview_not_truncated_when_short(self):
        sub = {
            "id": 1,
            "user_id": 101,
            "user_name": "Alice",
            "body": "Short answer.",
            "submitted_at": "2025-11-01T10:00:00Z",
            "workflow_state": "submitted",
            "score": None,
        }
        result = format_submission(sub)
        assert result["body_preview"] == "Short answer."

    def test_empty_body_shows_no_submission(self):
        sub = {
            "id": 1,
            "user_id": 101,
            "user_name": "Alice",
            "body": "",
            "submitted_at": None,
            "workflow_state": "unsubmitted",
            "score": None,
        }
        result = format_submission(sub)
        assert result["body_preview"] == "[No submission text]"

    def test_submitted_at_none_shows_not_submitted(self):
        sub = {
            "id": 1,
            "user_id": 101,
            "user_name": "Alice",
            "body": "",
            "submitted_at": None,
            "workflow_state": "unsubmitted",
            "score": None,
        }
        result = format_submission(sub)
        assert result["submitted_at"] == "Not submitted"

    def test_status_reflects_workflow_state(self):
        sub = {
            "id": 1,
            "user_id": 101,
            "user_name": "Alice",
            "body": "Answer",
            "submitted_at": "2025-11-01T10:00:00Z",
            "workflow_state": "graded",
            "score": 95,
        }
        result = format_submission(sub)
        assert result["status"] == "graded"
