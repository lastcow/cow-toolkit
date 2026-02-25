"""Module 6: Discord Notifier.

Checks for new student submissions on Canvas and sends
Discord notifications via the openclaw CLI.
"""

import subprocess

from canvasapi import Canvas


DISCORD_CHANNEL = "channel:1476308111034810482"


def check_new_submissions(canvas: Canvas, course_id: int,
                          assignment_id: int,
                          last_seen_ids: set) -> list:
    """Check for new submissions not in last_seen_ids.

    Skips unsubmitted entries (workflow_state == 'unsubmitted').

    Returns a list of dicts with keys:
        id, user_id, user_name, submitted_at.

    Raises RuntimeError on API failure.
    """
    try:
        course = canvas.get_course(course_id)
        assignment = course.get_assignment(assignment_id)
        submissions = list(assignment.get_submissions())
    except Exception as e:
        raise RuntimeError(
            f"Failed to check submissions for assignment {assignment_id} "
            f"in course {course_id}: {e}"
        ) from e

    new_submissions = []
    for sub in submissions:
        workflow = getattr(sub, "workflow_state", "unsubmitted")
        if workflow == "unsubmitted":
            continue
        if sub.id in last_seen_ids:
            continue

        user_info = getattr(sub, "user", None) or {}
        new_submissions.append({
            "id": sub.id,
            "user_id": sub.user_id,
            "user_name": user_info.get("name", "Unknown"),
            "submitted_at": getattr(sub, "submitted_at", None),
        })

    return new_submissions


def format_notification_message(submission: dict, course_name: str,
                                assignment_name: str) -> str:
    """Format a notification message for Discord.

    Returns a human-readable string with submission details.
    """
    return (
        f"New submission: {submission['user_name']} submitted "
        f"'{assignment_name}' in {course_name} "
        f"at {submission['submitted_at']}"
    )


def send_discord_notification(submission: dict, course_name: str,
                              assignment_name: str) -> bool:
    """Send a Discord notification about a new submission via openclaw CLI.

    Returns True on success, False on failure.
    """
    message = format_notification_message(submission, course_name,
                                          assignment_name)
    cmd = [
        "openclaw", "message", "send",
        "--channel", "discord",
        "--target", DISCORD_CHANNEL,
        "--message", message,
    ]

    try:
        result = subprocess.run(cmd, timeout=30)
        return result.returncode == 0
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return False
