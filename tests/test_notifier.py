"""Tests for Module 6: Discord Notifier."""

from unittest.mock import MagicMock, patch, call

import pytest

from src.notifier import (
    check_new_submissions,
    format_notification_message,
    send_discord_notification,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_submission(submission_id, user_id, body="Some answer",
                          submitted_at="2025-11-01T10:00:00Z",
                          workflow_state="submitted", score=None,
                          user_name="Jane Doe"):
    """Helper to create a mock Canvas submission object."""
    sub = MagicMock()
    sub.id = submission_id
    sub.user_id = user_id
    sub.body = body
    sub.submitted_at = submitted_at
    sub.workflow_state = workflow_state
    sub.score = score
    sub.user = {"id": user_id, "name": user_name}
    return sub


# ===========================================================================
# check_new_submissions
# ===========================================================================

class TestCheckNewSubmissions:
    """Tests for detecting new submissions not in last_seen_ids."""

    def test_returns_new_submissions_not_in_last_seen(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        subs = [
            _make_mock_submission(1, 101, user_name="Alice"),
            _make_mock_submission(2, 102, user_name="Bob"),
            _make_mock_submission(3, 103, user_name="Charlie"),
        ]
        mock_assignment.get_submissions.return_value = subs

        last_seen = {1}
        result = check_new_submissions(mock_canvas, 1001, 42, last_seen)
        assert len(result) == 2
        ids = {s["id"] for s in result}
        assert ids == {2, 3}

    def test_returns_empty_when_all_seen(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        subs = [
            _make_mock_submission(1, 101),
            _make_mock_submission(2, 102),
        ]
        mock_assignment.get_submissions.return_value = subs

        last_seen = {1, 2}
        result = check_new_submissions(mock_canvas, 1001, 42, last_seen)
        assert result == []

    def test_returns_all_when_none_seen(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        subs = [
            _make_mock_submission(1, 101, user_name="Alice"),
            _make_mock_submission(2, 102, user_name="Bob"),
        ]
        mock_assignment.get_submissions.return_value = subs

        result = check_new_submissions(mock_canvas, 1001, 42, set())
        assert len(result) == 2

    def test_empty_submissions_returns_empty(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment
        mock_assignment.get_submissions.return_value = []

        result = check_new_submissions(mock_canvas, 1001, 42, set())
        assert result == []

    def test_only_includes_submitted_submissions(self):
        """Unsubmitted entries (workflow_state='unsubmitted') should be skipped."""
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        subs = [
            _make_mock_submission(1, 101, workflow_state="submitted", user_name="Alice"),
            _make_mock_submission(2, 102, workflow_state="unsubmitted", user_name="Bob"),
            _make_mock_submission(3, 103, workflow_state="graded", user_name="Charlie"),
        ]
        mock_assignment.get_submissions.return_value = subs

        result = check_new_submissions(mock_canvas, 1001, 42, set())
        ids = {s["id"] for s in result}
        assert 2 not in ids
        assert 1 in ids
        assert 3 in ids

    def test_returns_dicts_with_expected_keys(self):
        mock_canvas = MagicMock()
        mock_course = MagicMock()
        mock_assignment = MagicMock()
        mock_canvas.get_course.return_value = mock_course
        mock_course.get_assignment.return_value = mock_assignment

        subs = [
            _make_mock_submission(
                10, 201, body="My essay",
                submitted_at="2025-11-05T08:30:00Z",
                workflow_state="submitted",
                user_name="Alice",
            ),
        ]
        mock_assignment.get_submissions.return_value = subs

        result = check_new_submissions(mock_canvas, 1001, 42, set())
        s = result[0]
        assert s["id"] == 10
        assert s["user_id"] == 201
        assert s["user_name"] == "Alice"
        assert s["submitted_at"] == "2025-11-05T08:30:00Z"

    def test_raises_on_api_error(self):
        mock_canvas = MagicMock()
        mock_canvas.get_course.side_effect = Exception("API failure")

        with pytest.raises(RuntimeError, match="Failed to check submissions"):
            check_new_submissions(mock_canvas, 1001, 42, set())


# ===========================================================================
# format_notification_message
# ===========================================================================

class TestFormatNotificationMessage:
    """Tests for formatting the Discord notification string."""

    def test_contains_student_name(self):
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}
        msg = format_notification_message(sub, "CS101", "Homework 1")
        assert "Alice" in msg

    def test_contains_course_name(self):
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}
        msg = format_notification_message(sub, "CS101", "Homework 1")
        assert "CS101" in msg

    def test_contains_assignment_name(self):
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}
        msg = format_notification_message(sub, "CS101", "Homework 1")
        assert "Homework 1" in msg

    def test_contains_submitted_at(self):
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}
        msg = format_notification_message(sub, "CS101", "Homework 1")
        assert "2025-11-01T10:00:00Z" in msg

    def test_returns_string(self):
        sub = {"id": 1, "user_id": 101, "user_name": "Bob",
               "submitted_at": "2025-11-01T10:00:00Z"}
        msg = format_notification_message(sub, "CS101", "Quiz 3")
        assert isinstance(msg, str)
        assert len(msg) > 0


# ===========================================================================
# send_discord_notification
# ===========================================================================

class TestSendDiscordNotification:
    """Tests for sending Discord notifications via openclaw CLI."""

    @patch("src.notifier.subprocess.run")
    def test_calls_openclaw_cli(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}

        send_discord_notification(sub, "CS101", "Homework 1")

        mock_run.assert_called_once()
        cmd = mock_run.call_args[0][0]
        assert cmd[0] == "openclaw"
        assert "message" in cmd
        assert "send" in cmd
        assert "--channel" in cmd
        assert "discord" in cmd
        assert "--target" in cmd
        assert "channel:1476308111034810482" in cmd
        assert "--message" in cmd

    @patch("src.notifier.subprocess.run")
    def test_message_contains_submission_info(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}

        send_discord_notification(sub, "CS101", "Homework 1")

        cmd = mock_run.call_args[0][0]
        message = cmd[cmd.index("--message") + 1]
        assert "Alice" in message
        assert "CS101" in message
        assert "Homework 1" in message

    @patch("src.notifier.subprocess.run")
    def test_returns_true_on_success(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}

        result = send_discord_notification(sub, "CS101", "Homework 1")
        assert result is True

    @patch("src.notifier.subprocess.run")
    def test_returns_false_on_nonzero_exit(self, mock_run):
        mock_run.return_value = MagicMock(returncode=1)
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}

        result = send_discord_notification(sub, "CS101", "Homework 1")
        assert result is False

    @patch("src.notifier.subprocess.run")
    def test_returns_false_on_subprocess_error(self, mock_run):
        mock_run.side_effect = FileNotFoundError("openclaw not found")
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}

        result = send_discord_notification(sub, "CS101", "Homework 1")
        assert result is False

    @patch("src.notifier.subprocess.run")
    def test_returns_false_on_timeout(self, mock_run):
        import subprocess
        mock_run.side_effect = subprocess.TimeoutExpired(cmd="openclaw", timeout=30)
        sub = {"id": 1, "user_id": 101, "user_name": "Alice",
               "submitted_at": "2025-11-01T10:00:00Z"}

        result = send_discord_notification(sub, "CS101", "Homework 1")
        assert result is False
