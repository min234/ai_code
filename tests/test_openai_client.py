"""Tests for core/openai_client.py — get_client, ask_model"""

import pytest
from unittest.mock import patch, MagicMock
import ai_code.core.openai_client as client_module


class TestGetClient:
    def test_raises_without_api_key(self):
        """API 키가 없으면 RuntimeError 발생"""
        # Reset singleton
        client_module._client = None
        with patch.dict("os.environ", {}, clear=True):
            # Also patch getenv to ensure no env vars
            with patch("os.getenv", return_value=None):
                with pytest.raises(RuntimeError, match="OPENAI_API_KEY"):
                    client_module.get_client()
        # Reset singleton after test
        client_module._client = None


class TestAskModel:
    def test_ask_model_returns_text(self):
        """mock으로 OpenAI 응답 확인"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = "Hello from mock"

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        client_module._client = mock_client
        try:
            result = client_module.ask_model(
                system_prompt="You are helpful.",
                user_prompt="Say hello",
                model="gpt-4o",
            )
            assert result == "Hello from mock"
        finally:
            client_module._client = None

    def test_ask_model_json_format(self):
        """response_format='json_object'일 때 dict 반환"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = '{"key": "value"}'

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        client_module._client = mock_client
        try:
            result = client_module.ask_model(
                system_prompt="Return JSON",
                user_prompt="Give me JSON",
                response_format="json_object",
            )
            assert isinstance(result, dict)
            assert result["key"] == "value"
        finally:
            client_module._client = None

    def test_ask_model_empty_response_raises(self):
        """빈 응답이면 ValueError 발생"""
        mock_response = MagicMock()
        mock_response.choices = [MagicMock()]
        mock_response.choices[0].message.content = None

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        client_module._client = mock_client
        try:
            with pytest.raises(ValueError, match="empty response"):
                client_module.ask_model(
                    system_prompt="test",
                    user_prompt="test",
                )
        finally:
            client_module._client = None
