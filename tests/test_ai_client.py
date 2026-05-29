"""Tests for AI client and response parser."""

import pytest
from unittest.mock import patch, MagicMock

from pr_insight.ai.parser import parse_json_response


class TestParseJsonResponse:
    """Tests for parse_json_response function."""

    def test_valid_json(self):
        text = '{"key": "value", "num": 42}'
        result = parse_json_response(text)
        assert result == {"key": "value", "num": 42}

    def test_json_in_code_block(self):
        text = '```json\n{"key": "value"}\n```'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_json_in_code_block_no_lang(self):
        text = '```\n{"key": "value"}\n```'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_json_with_surrounding_text(self):
        text = 'Here is the result:\n{"key": "value"}\nDone.'
        result = parse_json_response(text)
        assert result == {"key": "value"}

    def test_json_array(self):
        text = '[1, 2, 3]'
        result = parse_json_response(text)
        assert result == [1, 2, 3]

    def test_invalid_json_fallback(self):
        text = "This is not JSON at all"
        result = parse_json_response(text)
        assert "raw_text" in result
        assert "parse_error" in result

    def test_nested_json(self):
        data = '{"risks": [{"file": "main.py", "severity": "high"}]}'
        result = parse_json_response(data)
        assert len(result["risks"]) == 1
        assert result["risks"][0]["severity"] == "high"


class TestAIClient:
    """Tests for AIClient (mocked Anthropic SDK)."""

    @patch("pr_insight.ai.client.anthropic.Anthropic")
    def test_init_with_base_url(self, mock_anthropic_cls):
        from pr_insight.ai.client import AIClient

        AIClient(api_key="test-key", model="deepseek-chat",
                 base_url="https://custom.api.com/anthropic")

        mock_anthropic_cls.assert_called_once_with(
            api_key="test-key", base_url="https://custom.api.com/anthropic"
        )

    @patch("pr_insight.ai.client.anthropic.Anthropic")
    def test_init_without_base_url(self, mock_anthropic_cls):
        from pr_insight.ai.client import AIClient

        AIClient(api_key="test-key")

        mock_anthropic_cls.assert_called_once_with(api_key="test-key")

    @patch("pr_insight.ai.client.anthropic.Anthropic")
    def test_call_sync_success(self, mock_anthropic_cls):
        from pr_insight.ai.client import AIClient

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"result": "ok"}')]
        mock_client.messages.create.return_value = mock_response

        ai = AIClient(api_key="test-key")
        result = ai._call_sync("system", "user")

        assert result == '{"result": "ok"}'
        mock_client.messages.create.assert_called_once()

    @patch("pr_insight.ai.client.anthropic.Anthropic")
    def test_call_sync_retry_on_rate_limit(self, mock_anthropic_cls):
        import anthropic
        from pr_insight.ai.client import AIClient

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call raises RateLimitError, second succeeds
        mock_response = MagicMock()
        mock_response.content = [MagicMock(text='{"ok": true}')]
        mock_client.messages.create.side_effect = [
            anthropic.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            ),
            mock_response,
        ]

        ai = AIClient(api_key="test-key")
        with patch("time.sleep"):  # skip delay
            result = ai._call_sync("system", "user")

        assert result == '{"ok": true}'
        assert mock_client.messages.create.call_count == 2
