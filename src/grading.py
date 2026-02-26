"""Module 5: Smart Grading Interface.

View submissions per assignment and grade them using supportive
'Professor' logic that rewards key-point coverage without penalising
grammar or syntax errors.
"""

from canvasapi import Canvas


# ---------------------------------------------------------------------------
# list_submissions
# ---------------------------------------------------------------------------

def list_submissions(canvas: Canvas, course_id: int,
                     assignment_id: int) -> list:
    """Fetch all submissions for an assignment.

    Returns a list of dicts with keys:
        id, user_id, user_name, body, submitted_at,
        workflow_state, score.

    Raises RuntimeError on API failure.
    """
    try:
        course = canvas.get_course(course_id)
        assignment = course.get_assignment(assignment_id)
        submissions = list(assignment.get_submissions(include=["user", "submission_comments"]))
    except Exception as e:
        raise RuntimeError(
            f"Failed to fetch submissions for assignment {assignment_id} "
            f"in course {course_id}: {e}"
        ) from e

    result = []
    for sub in submissions:
        user_info  = getattr(sub, "user", None) or {}
        body       = getattr(sub, "body", None) or ""
        raw_atts   = getattr(sub, "attachments", None) or []

        # Summarise attachments (keep the raw objects for later download)
        att_summaries = []
        for att in raw_atts:
            att_summaries.append({
                "filename":     getattr(att, "filename", "unknown"),
                "content_type": getattr(att, "content-type", ""),
                "size":         getattr(att, "size", 0),
                "_att_obj":     att,   # keep raw object for download
            })

        # Extract submission comments (grader feedback)
        raw_comments = getattr(sub, "submission_comments", None) or []
        comments_list = []
        for c in raw_comments:
            if isinstance(c, dict):
                author = c.get("author_name", "?")
                text   = c.get("comment", "")
                date   = (c.get("created_at") or "")[:10]
            else:
                author = getattr(c, "author_name", "?")
                text   = getattr(c, "comment", "")
                date   = (getattr(c, "created_at", "") or "")[:10]
            if text:
                comments_list.append({"author": author, "text": text, "date": date})

        submitted_at = getattr(sub, "submitted_at", None)
        graded_at    = getattr(sub, "graded_at", None)
        attempt      = getattr(sub, "attempt", None) or 1

        # Resubmitted = submitted again after being graded
        resubmitted  = bool(
            submitted_at and graded_at and submitted_at > graded_at
        )

        result.append({
            "id":            sub.id,
            "user_id":       sub.user_id,
            "user_name":     user_info.get("name", "Unknown"),
            "body":          body,
            "submitted_at":  submitted_at,
            "graded_at":     graded_at,
            "attempt":       attempt,
            "resubmitted":   resubmitted,
            "workflow_state": getattr(sub, "workflow_state", "unsubmitted"),
            "score":         getattr(sub, "score", None),
            "attachments":   att_summaries,
            "submission_comments": comments_list,
        })

    return result


# ---------------------------------------------------------------------------
# calculate_grade  –  'Professor' grading logic
# ---------------------------------------------------------------------------

_LETTER_GRADES = [
    (97, "A+"),
    (93, "A"),
    (90, "A-"),
    (87, "B+"),
    (83, "B"),
    (80, "B-"),
    (77, "C+"),
    (73, "C"),
    (70, "C-"),
    (67, "D+"),
    (63, "D"),
    (60, "D-"),
    (0,  "F"),
]


def _score_to_letter(score: int) -> str:
    for threshold, letter in _LETTER_GRADES:
        if score >= threshold:
            return letter
    return "F"


def _coverage_ratio(text: str, key_points: list[str]) -> float:
    """Return the fraction of key_points found (case-insensitive) in text."""
    if not key_points:
        return 1.0
    text_lower = text.lower()
    matched = sum(1 for kp in key_points if kp.lower() in text_lower)
    return matched / len(key_points)


def calculate_grade(submission_text: str, key_points: list[str]) -> dict:
    """Grade a submission using supportive 'Professor' logic.

    Rules:
    - Do NOT deduct for syntax/grammar errors.
    - Score is driven by how many *key_points* the student addresses.
    - If all key points are covered → 95-100.
    - Partial coverage scales proportionally.
    - Empty submission → near-zero score.

    Returns dict with:
        score      (int 0-100)
        feedback   (str, supportive tone)
        letter_grade (str)
    """
    if not submission_text.strip():
        return {
            "score": 0,
            "feedback": (
                "It looks like no response was provided. "
                "Please reach out if you need help — I'm happy to assist!"
            ),
            "letter_grade": "F",
        }

    ratio = _coverage_ratio(submission_text, key_points)

    # Map ratio → score: full coverage → 95-100, partial scales down
    if ratio >= 1.0:
        score = 97
    elif ratio >= 0.75:
        score = int(85 + (ratio - 0.75) * 48)  # 85-97
    elif ratio >= 0.5:
        score = int(70 + (ratio - 0.5) * 60)   # 70-85
    elif ratio >= 0.25:
        score = int(50 + (ratio - 0.25) * 80)  # 50-70
    else:
        score = int(ratio * 200)                # 0-50

    score = max(0, min(100, score))

    # Supportive feedback
    if ratio >= 1.0:
        feedback = (
            "Excellent work! You addressed all the key points thoroughly. "
            "Keep up the great effort!"
        )
    elif ratio >= 0.75:
        feedback = (
            "Great job! You covered most of the key topics. "
            "A little more detail on the remaining points would make "
            "this even stronger."
        )
    elif ratio >= 0.5:
        feedback = (
            "Good effort! You've shown understanding of several concepts. "
            "Try to expand on the topics you haven't covered yet — "
            "you're on the right track!"
        )
    elif ratio > 0:
        feedback = (
            "Thank you for your submission! You've started to engage with "
            "the material. Revisiting the key topics will help strengthen "
            "your response. Don't hesitate to ask for guidance!"
        )
    else:
        feedback = (
            "Thank you for submitting. The response doesn't yet address "
            "the key topics. Please review the material and try again — "
            "I'm here to help!"
        )

    return {
        "score": score,
        "feedback": feedback,
        "letter_grade": _score_to_letter(score),
    }


# ---------------------------------------------------------------------------
# format_submission
# ---------------------------------------------------------------------------

_PREVIEW_MAX_LEN = 200


def format_submission(submission: dict) -> dict:
    """Format a submission dict for TUI display.

    Returns dict with keys:
        student, submitted_at, status, body_preview, score.
    """
    body = submission.get("body", "") or ""
    if body:
        body_preview = (body[:_PREVIEW_MAX_LEN] + "...") if len(body) > _PREVIEW_MAX_LEN else body
    else:
        body_preview = "[No submission text]"

    submitted_at = submission.get("submitted_at")
    score = submission.get("score")

    return {
        "student": submission.get("user_name", "Unknown"),
        "submitted_at": submitted_at if submitted_at else "Not submitted",
        "status": submission.get("workflow_state", "unsubmitted"),
        "body_preview": body_preview,
        "score": str(score) if score is not None else "N/A",
    }
