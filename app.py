"""Canvas Command Center — btop-style TUI.

All panels visible simultaneously, keyboard-driven, fully reactive.
Number keys 1-4 jump to each section instantly.
"""

import os
from pathlib import Path

# Auto-load .env
_env = Path(__file__).parent / ".env"
if _env.exists():
    for _line in _env.read_text().splitlines():
        _line = _line.strip()
        if _line and not _line.startswith("#") and "=" in _line:
            _k, _, _v = _line.partition("=")
            os.environ.setdefault(_k.strip(), _v.strip())

from textual.app import App, ComposeResult
from textual.binding import Binding
from textual.containers import Horizontal, Vertical, ScrollableContainer
from textual.coordinate import Coordinate
from textual.reactive import reactive
from textual.widgets import DataTable, Header, Input, Label, Static
from textual import work

def _grade_color(letter: str) -> str:
    """Map letter grade to a Rich color."""
    if not letter or letter == "—":
        return "dim"
    l = letter.upper()
    if l.startswith("A"):  return "bold green"
    if l.startswith("B"):  return "green"
    if l.startswith("C"):  return "yellow"
    if l.startswith("D"):  return "dark_orange"
    return "red"


from src.auth import get_api_token, create_canvas_connection
from src.courses import get_courses, get_current_term_courses, format_course_info
from src.students import get_students, format_student_grade
from src.assignments import list_assignments
from src.grading import list_submissions, format_submission
from src.grading_ai import (
    get_assignment_requirements, grade_one_submission, post_grades
)
from src.attachments import fetch_attachment_content, format_size


# ─────────────────────────────────────────────────────────────────────────────
# CSS
# ─────────────────────────────────────────────────────────────────────────────

CSS = """
Screen {
    background: #0d1117;
    layers: default;
}

/* ── rows ── */
#top-row {
    height: 35%;
    min-height: 8;
}
#bottom-row {
    height: 65%;
    min-height: 16;
}

/* ── panel base ── */
.panel {
    border: round #2a3a4a;
    background: #0d1117;
}
.panel:focus-within {
    border: round #00b4d8;
}

/* top panels */
#panel-courses    { width: 28%; min-width: 24; }
#panel-students   { width: 36%; min-width: 28; }
#panel-assignments{ width: 36%; min-width: 28; }

/* bottom panels */
#panel-submissions { width: 50%; min-width: 30; }
#panel-detail      { width: 50%; min-width: 30; }

/* ── panel titles ── */
.panel-title {
    text-style: bold;
    color: #58a6ff;
    background: #161b22;
    width: 100%;
    padding: 0 1;
    height: 1;
}
.panel:focus-within .panel-title {
    color: #f0f6fc;
    background: #00b4d8;
}

/* ── DataTable ── */
DataTable {
    background: #0d1117;
    height: 1fr;
}
DataTable > .datatable--header {
    background: #161b22;
    color: #58a6ff;
    text-style: bold;
}
DataTable > .datatable--cursor {
    background: #1f4068;
    color: #e6edf3;
    text-style: bold;
}
DataTable > .datatable--hover {
    background: #21262d;
}

/* ── detail pane ── */
#detail-scroll {
    height: 1fr;
    padding: 0 1;
}
.detail-key {
    color: #58a6ff;
    text-style: bold;
}
.detail-val {
    color: #c9d1d9;
}
.detail-body {
    color: #8b949e;
    margin-top: 1;
}

/* ── bars ── */
#status-bar {
    dock: bottom;
    height: 1;
    background: #161b22;
    color: #8b949e;
    padding: 0 2;
}
#key-bar {
    dock: bottom;
    height: 1;
    background: #0d1117;
    color: #484f58;
    padding: 0 1;
}
"""


# ─────────────────────────────────────────────────────────────────────────────
# App
# ─────────────────────────────────────────────────────────────────────────────

class CanvasCommandCenter(App):
    TITLE = "Canvas Command Center"
    CSS = CSS

    BINDINGS = [
        Binding("1",         "focus_courses",     "Courses",     show=False),
        Binding("2",         "focus_students",    "Students",    show=False),
        Binding("3",         "focus_assignments", "Assignments", show=False),
        Binding("4",         "focus_submissions", "Submissions", show=False),
        Binding("tab",       "focus_next",        "Next",        show=False),
        Binding("shift+tab", "focus_previous",    "Prev",        show=False),
        Binding("r",         "reload",            "Reload"),
        Binding("s",         "load_submissions",  "Submissions"),
        Binding("i",         "grade_all",         "AI Grade All"),
        Binding("y",         "confirm_grades",    "Confirm Submit", show=False),
        Binding("n",         "cancel_grades",     "Cancel",        show=False),
        Binding("e",         "edit_grade",        "Edit Grade",    show=False),
        Binding("q",         "quit",              "Quit"),
    ]

    # ── reactive state ────────────────────────────────────────────────────
    selected_course_id:   reactive[int | None] = reactive(None)
    selected_course_name: reactive[str]        = reactive("")
    selected_assign_id:   reactive[int | None] = reactive(None)
    selected_assign_name: reactive[str]        = reactive("")

    def __init__(self):
        super().__init__()
        self.canvas          = None
        self._grading_mode   = False          # True when pending confirm/cancel
        self._pending_grades: list[dict] = [] # graded results awaiting submit
        self._grade_req: dict | None = None   # current assignment requirements
        self._edit_state: str | None = None   # None / "select_student" / "enter_score"
        self._edit_idx: int = 0               # index into _pending_grades being edited

    # ── layout ───────────────────────────────────────────────────────────

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)

        # ── Top row: Courses | Students | Assignments ─────────────────
        with Horizontal(id="top-row"):
            with Vertical(id="panel-courses", classes="panel"):
                yield Label(" 📚 COURSES [1] ", classes="panel-title", id="title-courses")
                yield DataTable(id="tbl-courses", cursor_type="row")

            with Vertical(id="panel-students", classes="panel"):
                yield Label(" 👥 STUDENTS [2] ", classes="panel-title", id="title-students")
                yield DataTable(id="tbl-students", cursor_type="row")

            with Vertical(id="panel-assignments", classes="panel"):
                yield Label(" 📝 ASSIGNMENTS [3] ", classes="panel-title", id="title-assignments")
                yield DataTable(id="tbl-assignments", cursor_type="row")

        # ── Bottom row: Submissions list | Submission detail ──────────
        with Horizontal(id="bottom-row"):
            with Vertical(id="panel-submissions", classes="panel"):
                yield Label(" 🗂 SUBMISSIONS [4] ", classes="panel-title", id="title-submissions")
                yield DataTable(id="tbl-submissions", cursor_type="row")

            with Vertical(id="panel-detail", classes="panel"):
                yield Label(" 📄 SUBMISSION DETAIL ", classes="panel-title", id="title-detail")
                with ScrollableContainer(id="detail-scroll"):
                    yield Static("", id="detail-content")

        yield Static(" Connecting…", id="status-bar")
        yield Static(
            " [1] Courses  [2] Students  [3] Assignments  [4] Submissions"
            "  │  [↑↓] Navigate  [Enter] Select"
            "  │  [i] AI Grade All  [s] Subs  [r] Reload  [q] Quit",
            id="key-bar"
        )

    def on_mount(self) -> None:
        self.query_one("#tbl-courses", DataTable).add_columns("Code", "Course Name", "Stu")
        self.query_one("#tbl-students", DataTable).add_columns("Name", "Grade", "Score", "Final")
        self.query_one("#tbl-assignments", DataTable).add_columns("Assignment Name", "Pts", "Due", "⏳")
        self.query_one("#tbl-submissions", DataTable).add_columns(
            "Student", "Submitted", "State", "Score", "Attachments"
        )
        self.query_one("#tbl-courses").focus()
        self.connect_and_load()

    # ── helpers ───────────────────────────────────────────────────────────

    def _status(self, msg: str) -> None:
        try:
            self.query_one("#status-bar", Static).update(f" {msg}")
        except Exception:
            pass

    def _clear_detail(self, hint: str = "") -> None:
        self.query_one("#detail-content", Static).update(hint)
        self.query_one("#title-detail", Label).update(" 📄 SUBMISSION DETAIL ")

    # ── workers ───────────────────────────────────────────────────────────

    @work(thread=True)
    def connect_and_load(self) -> None:
        self.call_from_thread(self._status, "🔌 Connecting to Canvas LMS…")
        try:
            token = get_api_token()
            self.canvas = create_canvas_connection(token)
            self.call_from_thread(self._status, "📥 Fetching courses…")
            all_courses = get_courses(self.canvas)
            courses = get_current_term_courses(all_courses)
            term = "2026 Spring"
            if courses:
                t = getattr(courses[0], "term", None)
                if t and isinstance(t, dict):
                    term = t.get("name", term).strip()
            self.call_from_thread(self._populate_courses, courses, term)
            self.call_from_thread(
                self._status,
                f"✅ Connected  │  {len(courses)} courses  │  Term: {term}"
                "  │  Press [1] or use ↑↓+Enter to select a course"
            )
        except Exception as e:
            self.call_from_thread(self._status, f"❌  {e}")

    def _populate_courses(self, courses: list, term: str) -> None:
        tbl = self.query_one("#tbl-courses", DataTable)
        tbl.clear()
        self.query_one("#title-courses", Label).update(
            f" 📚 COURSES [1] — {term} ({len(courses)}) "
        )
        for c in courses:
            i = format_course_info(c)
            tbl.add_row(i["code"], i["name"][:36], str(i["students"]), key=str(i["id"]))

    @work(thread=True)
    def load_students(self, course_id: int, course_name: str) -> None:
        self.call_from_thread(self._status, f"📥 Loading students…")
        try:
            students = get_students(self.canvas, course_id)
            self.call_from_thread(self._populate_students, students, course_name)
            self.call_from_thread(
                self._status,
                f"✅ {len(students)} students  │  {course_name}"
                "  │  [2] focus students panel"
            )
        except Exception as e:
            self.call_from_thread(self._status, f"❌ Students: {e}")

    def _populate_students(self, students: list, course_name: str) -> None:
        tbl = self.query_one("#tbl-students", DataTable)
        tbl.clear()
        self.query_one("#title-students", Label).update(
            f" 👥 STUDENTS [2] — {course_name[:28]} ({len(students)}) "
        )
        if not students:
            tbl.add_row("No students", "—", "—", "—")
            return
        for s in students:
            i = format_student_grade(s)
            tbl.add_row(
                i.get("name", "?")[:28],
                i.get("current_grade") or "—",
                str(i.get("current_score") or "—"),
                i.get("final_grade") or "—",
                key=str(i.get("user_id", i.get("name", "?")))
            )

    @work(thread=True)
    def load_assignments(self, course_id: int, course_name: str) -> None:
        self.call_from_thread(self._status, f"📥 Loading assignments…")
        try:
            assignments = list_assignments(self.canvas, course_id)
            self.call_from_thread(self._populate_assignments, assignments, course_name)
            self.call_from_thread(
                self._status,
                f"✅ {len(assignments)} assignments  │  {course_name}"
                "  │  [3] focus assignments — Enter to load submissions"
            )
        except Exception as e:
            self.call_from_thread(self._status, f"❌ Assignments: {e}")

    def _populate_assignments(self, assignments: list, course_name: str) -> None:
        tbl = self.query_one("#tbl-assignments", DataTable)
        tbl.clear()
        self.query_one("#title-assignments", Label).update(
            f" 📝 ASSIGNMENTS [3] — {course_name[:26]} ({len(assignments)}) "
        )
        if not assignments:
            tbl.add_row("No assignments", "—", "—", "—")
            return
        for a in assignments:
            due = (a.get("due_at") or "—")[:16]
            ungraded = a.get("needs_grading_count", 0)
            ungraded_str = f"[red]{ungraded}[/]" if ungraded > 0 else "[dim]0[/]"
            tbl.add_row(
                a.get("name", "Untitled")[:36],
                str(a.get("points_possible") or "—"),
                due,
                ungraded_str,
                key=str(a.get("id", a.get("name", "?")))
            )

    @work(thread=True)
    def load_submissions(self, course_id: int, assign_id: int, assign_name: str) -> None:
        self.call_from_thread(self._status, f"📥 Loading submissions for {assign_name}…")
        self.call_from_thread(self.query_one("#tbl-submissions", DataTable).clear)
        self.call_from_thread(self._clear_detail, "Select a submission to view details →")
        try:
            subs = list_submissions(self.canvas, course_id, assign_id)
            self.call_from_thread(self._populate_submissions, subs, assign_name)
            self.call_from_thread(
                self._status,
                f"✅ {len(subs)} submission(s)  │  {assign_name}"
                "  │  [4] focus  │  Enter to view detail"
            )
        except Exception as e:
            self.call_from_thread(self._status, f"❌ Submissions: {e}")

    def _populate_submissions(self, subs: list, assign_name: str) -> None:
        tbl = self.query_one("#tbl-submissions", DataTable)
        tbl.clear()
        self.query_one("#title-submissions", Label).update(
            f" 🗂 SUBMISSIONS [4] — {assign_name[:36]} ({len(subs)}) "
        )
        if not subs:
            tbl.add_row("No submissions yet", "—", "—", "—")
            return
        for s in subs:
            info  = format_submission(s)
            name  = info.get("student") or s.get("user_name") or "?"
            atts  = s.get("attachments") or []
            if atts:
                att_label = f"📎 {len(atts)} file{'s' if len(atts) > 1 else ''}"
            else:
                att_label = "—"
            tbl.add_row(
                name[:24],
                (info.get("submitted_at") or "—")[:16],
                info.get("status", "—")[:14],
                str(info.get("score") or "—"),
                att_label,
                key=str(s.get("user_id", name))
            )
        # Store for detail lookup
        self._submissions_cache = {
            str(s.get("user_id", "?")): s for s in subs
        }

    # ── row selection ─────────────────────────────────────────────────────

    def on_data_table_row_selected(self, event: DataTable.RowSelected) -> None:
        tbl = event.data_table
        row = event.cursor_row

        if tbl.id == "tbl-courses":
            try:
                course_id   = int(event.row_key.value)
                course_name = str(tbl.get_cell_at(Coordinate(row, 1)))
                self.selected_course_id   = course_id
                self.selected_course_name = course_name
                self.selected_assign_id   = None
                self.query_one("#tbl-submissions", DataTable).clear()
                self._clear_detail(
                    "← Select an assignment then press Enter\n"
                    "   to load submissions"
                )
                self.load_students(course_id, course_name)
                self.load_assignments(course_id, course_name)
            except Exception as e:
                self._status(f"⚠️  {e}")

        elif tbl.id == "tbl-assignments":
            try:
                assign_id   = int(event.row_key.value)
                assign_name = str(tbl.get_cell_at(Coordinate(row, 0)))
                self.selected_assign_id   = assign_id
                self.selected_assign_name = assign_name
                if self.selected_course_id:
                    self.load_submissions(
                        self.selected_course_id, assign_id, assign_name
                    )
            except Exception as e:
                self._status(f"⚠️  {e}")

        elif tbl.id == "tbl-students":
            try:
                user_id = event.row_key.value
                student_name = str(tbl.get_cell_at(Coordinate(row, 0)))
                if self.selected_assign_id:
                    self.load_student_assignment_grade(int(user_id), student_name)
            except Exception as e:
                self._status(f"⚠️  {e}")

        elif tbl.id == "tbl-submissions":
            try:
                key = str(event.row_key.value)
                cache = getattr(self, "_submissions_cache", {})
                sub  = cache.get(key)
                if sub:
                    self._show_submission_detail(sub, tbl, row)
            except Exception as e:
                self._status(f"⚠️  {e}")

    def _show_submission_detail(self, sub: dict, tbl: DataTable, row: int) -> None:
        """Render submission detail + attachment content in right panel."""
        info   = format_submission(sub)
        name   = info.get("student") or sub.get("user_name", "Unknown")
        subat  = info.get("submitted_at") or "Not submitted"
        status = info.get("status", "—")
        score  = str(info.get("score") or "—")
        body   = sub.get("body") or ""
        atts   = sub.get("attachments") or []

        self.query_one("#title-detail", Label).update(f" 📄 DETAIL — {name} ")
        self.query_one("#detail-content", Static).update(
            f"[bold cyan]Student:[/]    {name}\n"
            f"[bold cyan]Submitted:[/]  {subat}\n"
            f"[bold cyan]Status:[/]     {status}\n"
            f"[bold cyan]Score:[/]      {score}\n"
            f"[bold cyan]Files:[/]      {len(atts)} attachment(s)\n"
            "\n[bold cyan]── Loading content… ──────────────────────────[/]"
        )
        # Fetch content in background thread
        self.load_submission_content(sub, name, subat, status, score, body, atts)

    @work(thread=True)
    def load_submission_content(
        self, sub: dict, name: str, subat: str,
        status: str, score: str, body: str, atts: list
    ) -> None:
        """Download & parse attachments, then render full detail."""
        lines = [
            f"[bold cyan]Student:[/]    {name}",
            f"[bold cyan]Submitted:[/]  {subat}",
            f"[bold cyan]Status:[/]     {status}",
            f"[bold cyan]Score:[/]      {score}",
            f"[bold cyan]Files:[/]      {len(atts)} attachment(s)",
        ]

        # ── Grader comments ──────────────────────────────────────────
        cmt_list = sub.get("submission_comments") or []
        if cmt_list:
            lines += [
                "",
                "[bold cyan]── 💬 Grader Comments ────────────────────────────[/]",
            ]
            for c in cmt_list:
                author = c.get("author", "?")
                date   = c.get("date", "")
                text   = c.get("text", "")
                lines.append(f"  [bold white]{author}[/] [dim]{date}[/]")
                lines += self._wrap_text(text, width=54)

        # ── Inline body ──────────────────────────────────────────────
        if body:
            lines += [
                "",
                "[bold cyan]── Text Body ─────────────────────────────────────[/]",
            ]
            lines += self._wrap_text(body, width=56)

        # ── Attachments ──────────────────────────────────────────────
        for i, att_meta in enumerate(atts):
            att_obj  = att_meta.get("_att_obj")
            fname    = att_meta.get("filename", "unknown")
            ctype    = att_meta.get("content_type", "")
            size_str = format_size(att_meta.get("size") or 0)

            lines += [
                "",
                f"[bold cyan]── 📎 Attachment {i+1}: {fname} ({size_str}) ─────────[/]",
            ]

            if att_obj is None:
                lines.append("[dim]  (attachment object unavailable)[/]")
                continue

            result = fetch_attachment_content(att_obj)
            if result["error"]:
                lines.append(f"[red]  ⚠ {result['error']}[/]")
            elif result["text"]:
                # Highlight embedded image OCR sections
                for seg in result["text"].split("\n── "):
                    if seg.startswith("Embedded Image"):
                        header, _, body = seg.partition(" ──\n")
                        lines.append(f"[bold yellow]── {header} ──[/]")
                        lines += self._wrap_text(body, width=54)
                    elif seg.startswith("Image in page"):
                        lines.append(f"[bold yellow]{seg}[/]")
                    else:
                        lines += self._wrap_text(seg, width=56)
            else:
                lines.append("[dim]  (no extractable text)[/]")

        self.call_from_thread(
            self.query_one("#detail-content", Static).update,
            "\n".join(lines)
        )

    @work(thread=True)
    def load_student_assignment_grade(self, user_id: int, student_name: str) -> None:
        """Fetch and display a student's grade for the selected assignment."""
        assign_name = self.selected_assign_name
        self.call_from_thread(
            self.query_one("#title-detail", Label).update,
            f" 📄 DETAIL — {student_name} "
        )
        self.call_from_thread(
            self.query_one("#detail-content", Static).update,
            f"[bold cyan]Loading grade for {student_name}…[/]"
        )

        # Check submissions cache first
        cache = getattr(self, "_submissions_cache", {})
        sub = cache.get(str(user_id))
        if sub:
            score = sub.get("score")
            state = sub.get("workflow_state", "unsubmitted")
            submitted_at = sub.get("submitted_at")
            pts = (self._grade_req or {}).get("points_possible", 100)
        else:
            try:
                course = self.canvas.get_course(self.selected_course_id)
                assignment = course.get_assignment(self.selected_assign_id)
                submission = assignment.get_submission(user_id)
                score = getattr(submission, "score", None)
                state = getattr(submission, "workflow_state", "unsubmitted")
                submitted_at = getattr(submission, "submitted_at", None)
                pts = getattr(assignment, "points_possible", 100) or 100
            except Exception as e:
                self.call_from_thread(
                    self.query_one("#detail-content", Static).update,
                    f"[red]❌ Failed to fetch grade: {e}[/]"
                )
                return

        if score is not None:
            letter = self._score_to_letter(float(score), float(pts))
            score_str = f"{score}/{pts}"
            color = _grade_color(letter)
            grade_line = f"[bold cyan]Grade:[/]      [{color}]{letter}[/]"
        else:
            score_str = "—"
            grade_line = "[bold cyan]Grade:[/]      —"

        lines = [
            f"[bold cyan]Student:[/]    {student_name}",
            f"[bold cyan]Assignment:[/] {assign_name}",
            f"[bold cyan]Score:[/]      {score_str}",
            grade_line,
            f"[bold cyan]Status:[/]     {state}",
            f"[bold cyan]Submitted:[/]  {submitted_at or 'N/A'}",
        ]
        self.call_from_thread(
            self.query_one("#detail-content", Static).update,
            "\n".join(lines)
        )

    @staticmethod
    def _wrap_text(text: str, width: int = 56) -> list[str]:
        """Word-wrap text into lines of `width` chars."""
        import re
        # Split into paragraphs first
        paragraphs = re.split(r"\n{2,}", text)
        result = []
        for para in paragraphs:
            para = para.replace("\n", " ").strip()
            words = para.split()
            buf, buf_len = [], 0
            for w in words:
                if buf_len + len(w) + 1 > width:
                    result.append("  " + " ".join(buf))
                    buf, buf_len = [w], len(w)
                else:
                    buf.append(w)
                    buf_len += len(w) + 1
            if buf:
                result.append("  " + " ".join(buf))
            result.append("")   # blank line between paragraphs
        return result

    # ── AI grading ────────────────────────────────────────────────────────

    def action_grade_all(self) -> None:
        """[i] AI-grade all submissions for the selected assignment."""
        if not self.selected_course_id or not self.selected_assign_id:
            self._status("⚠️  Select a course → assignment first, then press [i]")
            return
        cache = getattr(self, "_submissions_cache", {})
        submitted = [s for s in cache.values()
                     if s.get("workflow_state") not in ("unsubmitted", None)
                     or s.get("body") or s.get("attachments")]
        if not submitted:
            self._status("⚠️  No submissions found. Load submissions first [s]")
            return
        self._grading_mode   = False
        self._pending_grades = []
        self.grade_all_worker(
            self.selected_course_id,
            self.selected_assign_id,
            self.selected_assign_name,
        )

    @work(thread=True)
    def grade_all_worker(self, course_id: int,
                         assign_id: int, assign_name: str) -> None:
        """Fetch requirements, grade every submission, then show results."""
        cache = getattr(self, "_submissions_cache", {})

        # ── Step 1: Fetch requirements ────────────────────────────────
        self.call_from_thread(
            self.query_one("#title-detail", Label).update,
            f" 🤖 AI GRADING — {assign_name[:50]} "
        )
        self.call_from_thread(
            self.query_one("#detail-content", Static).update,
            "[bold cyan]Fetching assignment requirements…[/]"
        )
        self._status(f"🤖 Fetching requirements for: {assign_name}")

        try:
            req = get_assignment_requirements(
                self.canvas, course_id, assign_id
            )
        except Exception as e:
            self.call_from_thread(
                self.query_one("#detail-content", Static).update,
                f"[red]❌ Failed to fetch requirements: {e}[/]"
            )
            self._status(f"❌ {e}")
            return

        self._grade_req = req
        pts = req["points_possible"]

        # ── Step 2: Determine who to grade ───────────────────────────
        subs_to_grade = [
            s for s in cache.values()
            if s.get("workflow_state") not in ("unsubmitted", None)
            or s.get("body")
            or s.get("attachments")
        ]
        # Grade submitted ones; skip already-graded (score already posted)
        subs_to_grade = list(cache.values())
        already_graded = [
            s for s in subs_to_grade
            if s.get("workflow_state") == "graded" and s.get("score") is not None
        ]
        submitted_only = [
            s for s in subs_to_grade
            if (
                s.get("workflow_state") not in ("unsubmitted", None, "")
                or s.get("body") or s.get("attachments")
            )
            and not (
                s.get("workflow_state") == "graded"
                and s.get("score") is not None
            )
        ]

        total = len(submitted_only)
        skipped = len(already_graded)
        if total == 0:
            msg = "[yellow]No ungraded submissions found.[/]"
            if skipped:
                names = ", ".join(
                    s.get("user_name", "?") for s in already_graded[:5]
                )
                msg += (
                    f"\n\n[dim]{skipped} already graded (skipped): {names}"
                    + (" …" if skipped > 5 else "") + "[/]"
                )
            self.call_from_thread(
                self.query_one("#detail-content", Static).update, msg
            )
            self._status(
                f"⚠️  No ungraded submissions"
                + (f"  │  {skipped} already graded (skipped)" if skipped else "")
            )
            return

        # Track per-student status for live display
        import threading
        from concurrent.futures import ThreadPoolExecutor, as_completed

        status_lock  = threading.Lock()
        done_count   = 0
        status_lines: dict[int, str] = {}   # user_id → status string

        def _render_progress():
            skip_note = f"  [dim](skipped {skipped} already graded)[/]" if skipped else ""
            header = (
                f"[bold cyan]🤖 AI GRADING (parallel) — {assign_name[:40]}[/]\n"
                f"[dim]{req['description'][:120]}…[/]\n\n"
                f"[bold]Completed: {done_count}/{total}[/]{skip_note}\n"
            )
            rows = "\n".join(status_lines[s.get("user_id")] for s in submitted_only
                             if s.get("user_id") in status_lines)
            self.call_from_thread(
                self.query_one("#detail-content", Static).update,
                header + rows
            )
            self.call_from_thread(
                self._status,
                f"🤖 Grading in parallel… {done_count}/{total} done"
            )

        def _grade_one(sub: dict) -> dict:
            nonlocal done_count
            name    = sub.get("user_name") or "Unknown"
            state   = sub.get("workflow_state", "unsubmitted")
            user_id = sub.get("user_id")

            with status_lock:
                status_lines[user_id] = f"  [dim]⏳ {name[:28]}…[/]"
                _render_progress()

            # Build submission text
            if state in ("unsubmitted", None, ""):
                grade_result = {
                    "score": 0.0, "letter_grade": "—",
                    "comments": "No submission", "error": ""
                }
            else:
                text_parts = []
                if sub.get("body"):
                    text_parts.append(sub["body"])
                for att_meta in (sub.get("attachments") or []):
                    att_obj = att_meta.get("_att_obj")
                    if att_obj:
                        fetched = fetch_attachment_content(att_obj)
                        if fetched.get("text"):
                            text_parts.append(
                                f"[File: {att_meta['filename']}]\n"
                                + fetched["text"]
                            )
                full_text = "\n\n".join(text_parts)
                grade_result = grade_one_submission(req, name, full_text)

            with status_lock:
                done_count += 1
                sc  = grade_result["score"]
                gr  = grade_result["letter_grade"]
                col = _grade_color(gr)
                pts = req["points_possible"]
                status_lines[user_id] = (
                    f"  [{col}]✓ {name[:28]:<28} {sc:.0f}/{pts:.0f}  {gr}[/]"
                )
                _render_progress()

            return {
                "user_id":      user_id,
                "student_name": name,
                "score":        grade_result["score"],
                "letter_grade": grade_result["letter_grade"],
                "comments":     grade_result["comments"],
                "error":        grade_result["error"],
                "state":        state,
            }

        # ── Step 3: Grade ALL in parallel ─────────────────────────────
        # Initialise status board
        for sub in submitted_only:
            status_lines[sub.get("user_id")] = (
                f"  [dim]○ {(sub.get('user_name') or 'Unknown')[:28]}[/]"
            )
        _render_progress()

        results_map: dict = {}
        with ThreadPoolExecutor(max_workers=min(total, 8)) as pool:
            futures = {pool.submit(_grade_one, sub): sub for sub in submitted_only}
            for fut in as_completed(futures):
                r = fut.result()
                results_map[r["user_id"]] = r

        # Preserve original order
        results = [results_map[s.get("user_id")] for s in submitted_only
                   if s.get("user_id") in results_map]

        # ── Step 4: Render results table ──────────────────────────────
        self._pending_grades = results
        self._grading_mode   = True

        graded_scores = [r["score"] for r in results if not r["error"]
                         and r["letter_grade"] != "—"]
        avg = sum(graded_scores) / len(graded_scores) if graded_scores else 0

        sep   = "─" * 62
        lines = [
            f"[bold cyan]🤖 AI GRADING RESULTS — {assign_name[:45]}[/]",
            f"[dim]{sep}[/]",
            f"[bold]{'Student':<26} {'Score':>6} {'Grade':>6}  Comments[/]",
            f"[dim]{sep}[/]",
        ]
        for r in results:
            score_str = f"{r['score']:.0f}/{pts:.0f}" if r["letter_grade"] != "—" else "—"
            grade_str = r["letter_grade"]
            comment   = r["comments"] or ("✓ Full marks" if not r["error"] else r["error"])
            color     = _grade_color(r["letter_grade"])
            lines.append(
                f"[white]{r['student_name'][:26]:<26}[/] "
                f"[{color}]{score_str:>6}[/] "
                f"[{color}]{grade_str:>5}[/]  "
                f"[italic #aaaaaa]{comment}[/]"
            )

        lines += [
            f"[dim]{sep}[/]",
            f"[dim]{total} graded  │  avg: {avg:.1f}/{pts:.0f}  │  "
            f"{len([r for r in results if not r['error']])} successful[/]",
            "",
            "  [bold bright_cyan on #003344][ e ][/] edit grade   [bold bright_green on #003300][ y ][/] submit to Canvas   [bold bright_red on #330000][ n ][/] cancel",
        ]

        self.call_from_thread(
            self.query_one("#detail-content", Static).update,
            "\n".join(lines)
        )
        self.call_from_thread(
            self.query_one("#title-detail", Label).update,
            f" 🤖 GRADING RESULTS — {assign_name[:40]} ── [e]=Edit [y]=Submit [n]=Cancel "
        )
        self.call_from_thread(
            self._status,
            f"✅ Graded {total} submissions  │  avg {avg:.1f}/{pts:.0f}"
            "  │  [y] Submit to Canvas  [n] Cancel"
        )

    @work(thread=True)
    def _submit_grades_worker(self) -> None:
        """Post grades to Canvas and report results."""
        results  = self._pending_grades
        req      = self._grade_req
        pts      = req["points_possible"] if req else 100

        self.call_from_thread(
            self.query_one("#detail-content", Static).update,
            "[bold cyan]📤 Submitting grades to Canvas…[/]"
        )
        self._status("📤 Submitting grades…")

        def _progress(i, total, name):
            self.call_from_thread(
                self._status,
                f"📤 Posting {i}/{total}: {name}…"
            )

        outcome = post_grades(
            self.canvas,
            self.selected_course_id,
            self.selected_assign_id,
            results,
            progress_cb=_progress,
        )

        ok  = outcome["ok"]
        errs = outcome["errors"]

        final_lines = [
            f"[bold green]✅ Submitted {ok}/{len(results)} grades to Canvas[/]",
            "",
        ]
        if errs:
            final_lines += ["[bold red]Errors:[/]"] + [f"  [red]{e}[/]" for e in errs]

        for r in results:
            score_str = f"{r['score']:.0f}/{pts:.0f}"
            final_lines.append(
                f"[white]{r['student_name'][:26]:<26}[/]  "
                f"[{_grade_color(r['letter_grade'])}]{score_str}  {r['letter_grade']}[/]"
                + (f"\n    [italic #aaaaaa]{r['comments']}[/]" if r['comments'] else "")
            )

        self.call_from_thread(
            self.query_one("#detail-content", Static).update,
            "\n".join(final_lines)
        )
        self.call_from_thread(
            self.query_one("#title-detail", Label).update,
            f" ✅ GRADES SUBMITTED — {self.selected_assign_name[:45]} "
        )
        self.call_from_thread(
            self._status,
            f"✅ {ok} grades posted to Canvas"
            + (f"  │  {len(errs)} error(s)" if errs else "")
        )
        self._grading_mode   = False
        self._pending_grades = []

        # ── Sync cache & refresh panels ───────────────────────────────
        # Build set of failed student names so we don't wrongly update them
        failed_names = {e.split(":")[0].strip() for e in errs}
        cache = getattr(self, "_submissions_cache", {})
        for r in results:
            if r.get("student_name") in failed_names:
                continue
            uid = str(r.get("user_id", ""))
            if uid in cache:
                cache[uid]["score"]          = r["score"]
                cache[uid]["workflow_state"] = "graded"

        # Refresh submissions table with updated data
        assign_name = self.selected_assign_name
        updated_subs = list(cache.values())
        self.call_from_thread(self._populate_submissions, updated_subs, assign_name)

        # Reload assignments so needs_grading_count updates
        if self.selected_course_id and self.selected_course_name:
            self.load_assignments(self.selected_course_id, self.selected_course_name)

    def action_confirm_grades(self) -> None:
        """[y] Submit pending grades to Canvas."""
        if not self._grading_mode:
            return
        if not self._pending_grades:
            self._status("⚠️  No grades to submit")
            return
        self._submit_grades_worker()

    def action_cancel_grades(self) -> None:
        """[n] Cancel pending grade submission."""
        if not self._grading_mode:
            return
        self._grading_mode   = False
        self._pending_grades = []
        self._clear_detail("Grade submission cancelled.")
        self._status("❌ Grade submission cancelled")

    # ── grade editing ─────────────────────────────────────────────────────

    @staticmethod
    def _score_to_letter(score, pts):
        if pts == 0:
            return "—"
        pct = (score / pts) * 100
        if pct >= 90:
            return "A"
        if pct >= 80:
            return "B"
        if pct >= 70:
            return "C"
        if pct >= 60:
            return "D"
        return "F"

    def action_edit_grade(self) -> None:
        """[e] Edit a student's grade from the pending results."""
        if not self._grading_mode or not self._pending_grades:
            return
        self._edit_state = "select_student"
        pts = self._grade_req["points_possible"] if self._grade_req else 100
        lines = ["[bold cyan]── Edit a Grade ──[/]"]
        for i, r in enumerate(self._pending_grades):
            score_str = f"{r['score']:.0f}/{pts:.0f}"
            lines.append(
                f"[{i + 1}] {r['student_name'][:28]:<28} {score_str:>8}  {r['letter_grade']}"
            )
        lines.append("\nEnter student number to edit (or 0 to cancel):")
        self.query_one("#detail-content", Static).update("\n".join(lines))
        # Remove existing edit input if any
        try:
            self.query_one("#grade-edit-input").remove()
        except Exception:
            pass
        self.mount(
            Input(placeholder="Student number (0=cancel)", id="grade-edit-input"),
            after="#detail-content",
        )
        self.query_one("#grade-edit-input").focus()

    def on_input_submitted(self, event: Input.Submitted) -> None:
        """Handle Input widget submissions for grade editing."""
        value = event.value.strip()
        event.input.value = ""

        if self._edit_state == "select_student":
            try:
                num = int(value)
            except ValueError:
                return
            if num == 0 or num < 0 or num > len(self._pending_grades):
                # Cancel or invalid — redisplay results
                self._edit_state = None
                try:
                    self.query_one("#grade-edit-input").remove()
                except Exception:
                    pass
                self._redisplay_grading_results()
                return
            self._edit_idx = num - 1
            r = self._pending_grades[self._edit_idx]
            pts = self._grade_req["points_possible"] if self._grade_req else 100
            self.query_one("#detail-content", Static).update(
                f"[bold cyan]Editing: {r['student_name']}[/]\n"
                f"Current score: {r['score']:.0f}/{pts:.0f}\n\n"
                f"Enter new score (0-{pts:.0f}) or press Enter to keep:"
            )
            self._edit_state = "enter_score"

        elif self._edit_state == "enter_score":
            pts = self._grade_req["points_possible"] if self._grade_req else 100
            if value == "":
                # Keep current score
                pass
            else:
                try:
                    new_score = float(value)
                    new_score = max(0.0, min(float(pts), new_score))
                    self._pending_grades[self._edit_idx]["score"] = new_score
                    self._pending_grades[self._edit_idx]["letter_grade"] = (
                        self._score_to_letter(new_score, pts)
                    )
                except ValueError:
                    pass
            self._edit_state = None
            try:
                self.query_one("#grade-edit-input").remove()
            except Exception:
                pass
            self._redisplay_grading_results()

    def _redisplay_grading_results(self) -> None:
        """Re-render the grading results table after an edit."""
        results = self._pending_grades
        req = self._grade_req
        pts = req["points_possible"] if req else 100
        assign_name = self.selected_assign_name

        graded_scores = [r["score"] for r in results if not r.get("error")
                         and r["letter_grade"] != "—"]
        avg = sum(graded_scores) / len(graded_scores) if graded_scores else 0

        sep = "─" * 62
        lines = [
            f"[bold cyan]🤖 AI GRADING RESULTS — {assign_name[:45]}[/]",
            f"[dim]{sep}[/]",
            f"[bold]{'Student':<26} {'Score':>6} {'Grade':>6}  Comments[/]",
            f"[dim]{sep}[/]",
        ]
        for r in results:
            score_str = f"{r['score']:.0f}/{pts:.0f}" if r["letter_grade"] != "—" else "—"
            grade_str = r["letter_grade"]
            comment = r.get("comments") or ("✓ Full marks" if not r.get("error") else r.get("error", ""))
            color = _grade_color(r["letter_grade"])
            lines.append(
                f"[white]{r['student_name'][:26]:<26}[/] "
                f"[{color}]{score_str:>6}[/] "
                f"[{color}]{grade_str:>5}[/]  "
                f"[italic #aaaaaa]{comment}[/]"
            )
        lines += [
            f"[dim]{sep}[/]",
            f"[dim]{len(results)} graded  │  avg: {avg:.1f}/{pts:.0f}  │  "
            f"{len([r for r in results if not r.get('error')])} successful[/]",
            "",
            "  [bold bright_cyan on #003344][ e ][/] edit grade   [bold bright_green on #003300][ y ][/] submit to Canvas   [bold bright_red on #330000][ n ][/] cancel",
        ]
        self.query_one("#detail-content", Static).update("\n".join(lines))
        self.query_one("#title-detail", Label).update(
            f" 🤖 GRADING RESULTS — {assign_name[:40]} ── [e]=Edit [y]=Submit [n]=Cancel "
        )

    # ── keyboard actions ──────────────────────────────────────────────────

    def action_focus_courses(self) -> None:
        self.query_one("#tbl-courses").focus()

    def action_focus_students(self) -> None:
        self.query_one("#tbl-students").focus()

    def action_focus_assignments(self) -> None:
        self.query_one("#tbl-assignments").focus()

    def action_focus_submissions(self) -> None:
        self.query_one("#tbl-submissions").focus()

    def action_load_submissions(self) -> None:
        if self.selected_course_id and self.selected_assign_id:
            self.load_submissions(
                self.selected_course_id,
                self.selected_assign_id,
                self.selected_assign_name,
            )
        else:
            self._status("⚠️  Select a course → assignment first, then press [s]")

    def action_reload(self) -> None:
        for tid in ("tbl-courses", "tbl-students", "tbl-assignments",
                    "tbl-submissions"):
            self.query_one(f"#{tid}", DataTable).clear()
        self._clear_detail()
        self.connect_and_load()


if __name__ == "__main__":
    CanvasCommandCenter().run()
