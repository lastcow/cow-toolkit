"""AI-powered auto-grading for Canvas submissions.

Flow:
  1. Fetch assignment requirements from Canvas (description + rubric)
  2. For each submitted student, extract submission text (body + attachments)
  3. Call Claude with requirement + submission → JSON {score, letter_grade, comments}
  4. Collect results, let professor review
  5. On confirmation, post grades back to Canvas via API
"""

import json
import re
import subprocess
from html.parser import HTMLParser

from canvasapi import Canvas


# ── HTML → plain text ────────────────────────────────────────────────────────

class _HTMLStripper(HTMLParser):
    def __init__(self):
        super().__init__()
        self.parts = []

    def handle_data(self, data):
        self.parts.append(data)

    def get_text(self) -> str:
        return re.sub(r"\s+", " ", " ".join(self.parts)).strip()


def strip_html(html: str) -> str:
    if not html:
        return ""
    s = _HTMLStripper()
    s.feed(html)
    return s.get_text()


# ── Fetch assignment requirements ────────────────────────────────────────────

def get_assignment_requirements(canvas: Canvas, course_id: int,
                                assignment_id: int) -> dict:
    """Return assignment details needed for grading.

    Returns:
        name            str
        description     str   (HTML stripped)
        points_possible float
        rubric_text     str   (formatted rubric criteria, or "")
    """
    try:
        course     = canvas.get_course(course_id)
        assignment = course.get_assignment(assignment_id)
    except Exception as e:
        raise RuntimeError(f"Failed to fetch assignment: {e}") from e

    name        = getattr(assignment, "name", "Untitled Assignment")
    raw_desc    = getattr(assignment, "description", "") or ""
    description = strip_html(raw_desc)
    points      = float(getattr(assignment, "points_possible", 100) or 100)

    # Optional rubric
    rubric_text = ""
    rubric = getattr(assignment, "rubric", None)
    if rubric:
        lines = []
        for criterion in rubric:
            crit_desc   = criterion.get("description", "")
            crit_pts    = criterion.get("points", "")
            crit_detail = strip_html(criterion.get("long_description", ""))
            lines.append(
                f"- {crit_desc} ({crit_pts} pts)"
                + (f": {crit_detail}" if crit_detail else "")
            )
        rubric_text = "\n".join(lines)

    return {
        "name":            name,
        "description":     description,
        "points_possible": points,
        "rubric_text":     rubric_text,
    }


# ── Grade a single submission ────────────────────────────────────────────────

_GRADE_SYSTEM = """You are a supportive professor's grading assistant with one guiding principle:
if a student addresses a key point with any reasonable detail, they earn FULL marks for that point.
Grading is about recognising understanding, not hunting for perfection."""

def grade_one_submission(
    req: dict,
    student_name: str,
    submission_text: str,
) -> dict:
    """Grade one submission with Claude.

    Args:
        req              dict from get_assignment_requirements()
        student_name     str
        submission_text  str  (full extracted text from body + attachments)

    Returns:
        score         float
        letter_grade  str
        comments      str   (≤ 15 words, empty if full score)
        error         str   (non-empty on failure)
    """
    points = req["points_possible"]
    desc   = (req["description"] or "")[:2500]
    rubric = req["rubric_text"] or ""
    text   = (submission_text or "")[:4000]

    if rubric:
        scoring_section = f"""RUBRIC (use these criteria — they define the score breakdown):
{rubric}

SCORING METHOD — rubric-based:
• For EACH rubric criterion: award FULL points for that criterion if the student addresses it
  with any reasonable detail or explanation. Partial credit only if the criterion is barely
  touched. Zero only if completely absent.
• Never deduct within a criterion for grammar, spelling, or writing quality.
• Sum the criterion scores to get the total."""
    else:
        scoring_section = f"""SCORING METHOD — key-point based (no rubric provided):
• Read the assignment description and identify ALL distinct key points / required topics.
• Divide {points} points EVENLY across those key points.
• For EACH key point: award its FULL share of points if the student addresses it with any
  reasonable detail. Partial credit only if barely mentioned. Zero only if completely absent.
• Never deduct for grammar, spelling, or writing quality.
• Sum across all key points to get the total."""

    prompt = f"""{_GRADE_SYSTEM}

ASSIGNMENT: {req['name']}
POINTS POSSIBLE: {points}

ASSIGNMENT DESCRIPTION:
{desc}

{scoring_section}

STUDENT: {student_name}

STUDENT SUBMISSION:
{text}

FINAL RULE: When in doubt, give the benefit of the doubt and award full points for that item.
A student who shows genuine effort and addresses the key points — even briefly — earns full marks.
For full-score submissions, write a short human-sounding comment a real professor might say — casual and warm, not stiff or corporate (e.g. "Really solid work here." / "You nailed it." / "This is exactly what I was looking for." / "Good stuff, keep it up.").
For partial scores, briefly describe only what was missing in plain, direct language (25 words max).

Respond ONLY with valid JSON (no other text):
{{"score": <number 0-{points}>, "letter_grade": "A+/A/A-/B+/B/B-/C+/C/C-/D+/D/D-/F", "comments": "<if full score: one casual human-sounding sentence a real professor would say (e.g. 'Really solid work.' / 'You nailed it.' / 'This is exactly what I was looking for.'); if not full score: plain description of what was missing, 25 words or fewer>"}}"""

    max_attempts = 3
    last_error = ""
    for attempt in range(1, max_attempts + 1):
        try:
            result = subprocess.run(
                [
                    "claude", "--print",
                    "--dangerously-skip-permissions",
                    "--model", "claude-haiku-4-5",
                    "--no-session-persistence",
                    prompt,
                ],
                capture_output=True, text=True, timeout=60,
            )
            raw = result.stdout.strip()

            # Extract JSON from output (may have surrounding text)
            match = re.search(r"\{[^{}]+\}", raw, re.DOTALL)
            if not match:
                raise ValueError(f"No JSON in response: {raw[:200]}")

            data = json.loads(match.group())
            score   = float(data.get("score", 0))
            score   = max(0.0, min(float(points), score))
            grade   = str(data.get("letter_grade", _score_to_letter(score, points)))
            comment = str(data.get("comments", "")).strip()

            # Enforce 25-word limit on comments
            words = comment.split()
            if len(words) > 25:
                comment = " ".join(words[:25]) + "…"

            # Ensure full-score submissions always get an encouraging message
            if score >= float(points) and not comment:
                import random
                comment = random.choice([
                    "Really solid work here.",
                    "This is exactly what I was looking for.",
                    "You nailed it — nice work.",
                    "Clear and well done, keep it up.",
                    "Good stuff, you clearly put in the effort.",
                    "Spot on, nothing missing here.",
                    "This came together really well.",
                    "You've got a good handle on this material.",
                ])

            return {
                "score":        score,
                "letter_grade": grade,
                "comments":     comment,
                "error":        "",
            }

        except subprocess.TimeoutExpired:
            last_error = f"AI timeout (attempt {attempt}/{max_attempts})"
            # Retry unless this was the last attempt
            continue
        except Exception as e:
            return {"score": 0, "letter_grade": "—", "comments": "", "error": str(e)}

    # All attempts exhausted
    return {"score": 0, "letter_grade": "—", "comments": "", "error": last_error}


def _score_to_letter(score: float, total: float) -> str:
    if total <= 0:
        return "—"
    pct = (score / total) * 100
    if pct >= 97: return "A+"
    if pct >= 93: return "A"
    if pct >= 90: return "A-"
    if pct >= 87: return "B+"
    if pct >= 83: return "B"
    if pct >= 80: return "B-"
    if pct >= 77: return "C+"
    if pct >= 73: return "C"
    if pct >= 70: return "C-"
    if pct >= 67: return "D+"
    if pct >= 63: return "D"
    if pct >= 60: return "D-"
    return "F"


# ── Post grades to Canvas ────────────────────────────────────────────────────

def post_grades(
    canvas: Canvas,
    course_id: int,
    assignment_id: int,
    grades: list[dict],
    progress_cb=None,
) -> dict:
    """Submit graded results to Canvas.

    grades is a list of:
        {user_id, student_name, score, letter_grade, comments}

    progress_cb(i, total, name) is called before each submission.

    Returns:
        ok      int   (number of successfully posted grades)
        errors  list  (list of error strings)
    """
    try:
        course     = canvas.get_course(course_id)
        assignment = course.get_assignment(assignment_id)
    except Exception as e:
        return {"ok": 0, "errors": [f"Failed to fetch assignment: {e}"]}

    ok_count = 0
    errors   = []

    for i, g in enumerate(grades):
        if progress_cb:
            progress_cb(i + 1, len(grades), g.get("student_name", "?"))
        try:
            sub = assignment.get_submission(g["user_id"])
            sub.edit(
                submission={
                    "posted_grade": g["score"],
                },
                comment={
                    "text_comment": g["comments"],
                } if g.get("comments") else {},
            )
            ok_count += 1
        except Exception as e:
            errors.append(f"{g.get('student_name', g['user_id'])}: {e}")

    return {"ok": ok_count, "errors": errors}
