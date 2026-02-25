"""Canvas Command Center — Main TUI entry point.

Ties together all 6 modules into a navigable Textual application
with a sidebar for Courses, Students, Assignments, and Grading screens.
"""

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Header, Footer, Static, Button, ListView, ListItem, Label


# ---------------------------------------------------------------------------
# Screen content panels
# ---------------------------------------------------------------------------

class CoursesPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("Courses — list enrolled courses (as instructor)")


class StudentsPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("Students — view students and grades per course")


class AssignmentsPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("Assignments — list, create, and update assignments")


class GradingPanel(Static):
    def compose(self) -> ComposeResult:
        yield Label("Grading — view submissions and grade with supportive logic")


PANELS = {
    "courses": CoursesPanel,
    "students": StudentsPanel,
    "assignments": AssignmentsPanel,
    "grading": GradingPanel,
}


# ---------------------------------------------------------------------------
# Main App
# ---------------------------------------------------------------------------

class CanvasCommandCenter(App):
    """A TUI Command Center for Canvas LMS."""

    TITLE = "Canvas Command Center"

    CSS = """
    #sidebar {
        width: 30;
        dock: left;
        background: $surface;
        padding: 1;
    }
    #sidebar Button {
        width: 100%;
        margin-bottom: 1;
    }
    #content {
        padding: 1 2;
    }
    """

    def compose(self) -> ComposeResult:
        yield Header()
        with Horizontal():
            with Vertical(id="sidebar"):
                yield Button("Courses", id="btn-courses", variant="primary")
                yield Button("Students", id="btn-students")
                yield Button("Assignments", id="btn-assignments")
                yield Button("Grading", id="btn-grading")
            with Vertical(id="content"):
                yield CoursesPanel()
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed) -> None:
        panel_key = event.button.id.replace("btn-", "")
        panel_class = PANELS.get(panel_key)
        if panel_class is None:
            return

        content = self.query_one("#content")
        content.remove_children()
        content.mount(panel_class())

        # Update button variants to highlight active
        for btn in self.query("#sidebar Button"):
            btn.variant = "default"
        event.button.variant = "primary"


if __name__ == "__main__":
    CanvasCommandCenter().run()
