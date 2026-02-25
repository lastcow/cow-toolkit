"""Tests for Module 1: Auth & Canvas Connection."""

import os
from unittest.mock import patch, MagicMock

import pytest

from src.auth import get_api_token, create_canvas_connection, verify_connection


class TestGetApiToken:
    """Tests for loading CANVAS_API_TOKEN from environment."""

    def test_returns_token_when_set(self):
        with patch.dict(os.environ, {"CANVAS_API_TOKEN": "test-token-123"}):
            token = get_api_token()
            assert token == "test-token-123"

    def test_raises_when_token_missing(self):
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(EnvironmentError, match="CANVAS_API_TOKEN"):
                get_api_token()

    def test_raises_when_token_empty(self):
        with patch.dict(os.environ, {"CANVAS_API_TOKEN": ""}):
            with pytest.raises(EnvironmentError, match="CANVAS_API_TOKEN"):
                get_api_token()


class TestCreateCanvasConnection:
    """Tests for establishing canvasapi connection."""

    @patch("src.auth.Canvas")
    def test_creates_canvas_with_correct_url_and_token(self, mock_canvas_cls):
        mock_canvas_cls.return_value = MagicMock()
        conn = create_canvas_connection("test-token")
        mock_canvas_cls.assert_called_once_with(
            "https://frostburg.instructure.com/", "test-token"
        )
        assert conn is mock_canvas_cls.return_value

    @patch("src.auth.Canvas")
    def test_returns_canvas_instance(self, mock_canvas_cls):
        mock_instance = MagicMock()
        mock_canvas_cls.return_value = mock_instance
        result = create_canvas_connection("token")
        assert result == mock_instance


class TestVerifyConnection:
    """Tests for verifying connection by fetching current user."""

    def test_verify_returns_user_info(self):
        mock_canvas = MagicMock()
        mock_user = MagicMock()
        mock_user.name = "Dr. Test"
        mock_user.id = 12345
        mock_canvas.get_current_user.return_value = mock_user

        user = verify_connection(mock_canvas)
        assert user.name == "Dr. Test"
        assert user.id == 12345
        mock_canvas.get_current_user.assert_called_once()

    def test_verify_raises_on_failure(self):
        mock_canvas = MagicMock()
        mock_canvas.get_current_user.side_effect = Exception("Unauthorized")

        with pytest.raises(ConnectionError, match="Failed to verify"):
            verify_connection(mock_canvas)
