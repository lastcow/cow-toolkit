# Canvas LMS TUI Command Center - Build Task (CONTINUING FROM MODULE 2)

## Status
- ✅ Module 1: Auth & Canvas Connection — DONE (src/auth.py, tests/test_auth.py, 7/7 tests pass)
- ◻ Module 2: Course List Screen — START HERE
- ◻ Module 3: Student & Grade Management
- ◻ Module 4: Assignment/Quiz Engine
- ◻ Module 5: Smart Grading Interface
- ◻ Module 6: Discord Notifier

## Project Overview
Python TUI Command Center for Canvas LMS.

## Technical Stack
- Python 3.10+
- Textual (TUI framework)
- Rich (formatting)
- canvasapi (Python wrapper for Canvas API)
- Base URL: https://frostburg.instructure.com/
- Auth: CANVAS_API_TOKEN environment variable (load from .env file using python-dotenv, already in .env)

## Modules to Build (start from Module 2)

### Module 2: Course List Screen
- List all enrolled courses (as instructor/teacher)
- Display: course name, course code, student count, term
- Navigable TUI list using Textual
- WRITE TESTS FIRST (TDD)

### Module 3: Student & Grade Management
- Per-course: list students with current grades
- Display grade summary per student
- WRITE TESTS FIRST (TDD)

### Module 4: Assignment/Quiz Engine
- List assignments per course
- Create new assignment (New)
- Update existing assignment
- WRITE TESTS FIRST (TDD)

### Module 5: Smart Grading Interface
- View submissions per assignment
- Grading logic: supportive, expert tone
- Do NOT deduct for syntax/grammar
- If student addresses all key points with sufficient detail → grade 100% or close to it
- WRITE TESTS FIRST (TDD)

### Module 6: Discord Notifier
- Background listener/check for new student submissions
- Send Discord notification when new submission detected
- Use openclaw CLI: `openclaw message send --channel discord --target "channel:1476308111034810482" --message "..."`
- WRITE TESTS FIRST (TDD)

## Workflow Rules (CRITICAL)
1. TDD: Write tests FIRST, then implement, then verify tests pass
2. After each module passes tests, send an approval request to Discord:
   openclaw message send --channel discord --target "channel:1476308111034810482" --message "✅ Module [N] [Name] complete — tests pass. Awaiting approval to proceed to Module [N+1]."
3. Wait for human input/approval in this terminal before proceeding to next module
4. Do NOT stop until all 6 modules are complete

## Project Structure
```
canvas-tui/
├── src/
│   ├── auth.py          ✅ DONE
│   ├── courses.py       ← build next
│   ├── students.py
│   ├── assignments.py
│   ├── grading.py
│   └── notifier.py
├── tests/
│   ├── test_auth.py     ✅ DONE
│   ├── test_courses.py  ← build next
│   ...
├── app.py
└── requirements.txt
```

## When ALL modules done
Run: openclaw system event --text "Done: Canvas TUI all 6 modules built and tested" --mode now

