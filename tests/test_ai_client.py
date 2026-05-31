"""Tests for AI client and response parser."""

import pytest
from unittest.mock import patch, MagicMock, AsyncMock

from pr_insight.ai.parser import parse_json_response, ResponseParseError


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

    def test_invalid_json_raises_error(self):
        text = "This is not JSON at all"
        with pytest.raises(ResponseParseError, match="Could not extract structured JSON"):
            parse_json_response(text)

    def test_nested_json(self):
        data = '{"risks": [{"file": "main.py", "severity": "high"}]}'
        result = parse_json_response(data)
        assert len(result["risks"]) == 1
        assert result["risks"][0]["severity"] == "high"


def _make_mock_stream(text: str):
    """Create a mock for the streaming context manager."""

    class _MockStream:
        def __init__(self, text: str):
            self._text = text

        @property
        def text_stream(self):
            async def _gen():
                yield self._text
            return _gen()

    class _MockStreamCtx:
        def __init__(self, text: str):
            self._text = text

        async def __aenter__(self):
            return _MockStream(self._text)

        async def __aexit__(self, *args):
            pass

    return _MockStreamCtx(text)


class TestAIClient:
    """Tests for AIClient (mocked Anthropic SDK)."""

    @patch("pr_insight.ai.client.anthropic.AsyncAnthropic")
    def test_init_with_base_url(self, mock_anthropic_cls):
        from pr_insight.ai.client import AIClient

        AIClient(api_key="test-key", model="deepseek-chat",
                 base_url="https://custom.api.com/anthropic")

        mock_anthropic_cls.assert_called_once_with(
            api_key="test-key", base_url="https://custom.api.com/anthropic"
        )

    @patch("pr_insight.ai.client.anthropic.AsyncAnthropic")
    def test_init_without_base_url(self, mock_anthropic_cls):
        from pr_insight.ai.client import AIClient

        AIClient(api_key="test-key")

        mock_anthropic_cls.assert_called_once_with(api_key="test-key")

    @patch("pr_insight.ai.client.anthropic.AsyncAnthropic")
    async def test_call_success(self, mock_anthropic_cls):
        from pr_insight.ai.client import AIClient

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client
        mock_client.messages.stream = MagicMock(
            return_value=_make_mock_stream('{"result": "ok"}')
        )

        ai = AIClient(api_key="test-key")
        result = await ai._call("system", "user")

        assert result == '{"result": "ok"}'
        mock_client.messages.stream.assert_called_once()

    @patch("pr_insight.ai.client.anthropic.AsyncAnthropic")
    @patch("pr_insight.ai.client.asyncio.sleep", new_callable=AsyncMock)
    async def test_call_retry_on_rate_limit(self, mock_sleep, mock_anthropic_cls):
        import anthropic
        from pr_insight.ai.client import AIClient

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call raises RateLimitError, second succeeds
        mock_client.messages.stream = MagicMock(side_effect=[
            anthropic.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            ),
            _make_mock_stream('{"ok": true}'),
        ])

        ai = AIClient(api_key="test-key")
        result = await ai._call("system", "user")

        assert result == '{"ok": true}'
        assert mock_client.messages.stream.call_count == 2
        mock_sleep.assert_called_once()
