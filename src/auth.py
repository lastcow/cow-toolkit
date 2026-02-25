"""Module 1: Auth & Canvas Connection.

Handles loading API token, establishing Canvas API connection,
and verifying the connection by fetching current user info.
"""

import os

from canvasapi import Canvas

BASE_URL = "https://frostburg.instructure.com/"


def get_api_token() -> str:
    """Load CANVAS_API_TOKEN from environment.

    Returns the token string.
    Raises EnvironmentError if not set or empty.
    """
    token = os.environ.get("CANVAS_API_TOKEN", "")
    if not token:
        raise EnvironmentError(
            "CANVAS_API_TOKEN environment variable is not set or empty. "
            "Set it with: export CANVAS_API_TOKEN='your-token-here'"
        )
    return token


def create_canvas_connection(token: str) -> Canvas:
    """Create and return a canvasapi Canvas instance."""
    return Canvas(BASE_URL, token)


def verify_connection(canvas: Canvas):
    """Verify the Canvas connection by fetching the current user.

    Returns the user object on success.
    Raises ConnectionError on failure.
    """
    try:
        user = canvas.get_current_user()
        return user
    except Exception as e:
        raise ConnectionError(f"Failed to verify Canvas connection: {e}") from e
