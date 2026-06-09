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

    def test_json_with_reasoning_prefers_task_payload(self):
        text = (
            '先分析一个示例：{"title": "towel", "size": "XL"}。\n'
            "最终结果：\n"
            '{"issues": [{"file": "main.py", "line": "10", '
            '"description": "Bare `except Exception: pass` silently swallows errors", '
            '"suggestion": "Catch a specific exception"}]}'
        )
        result = parse_json_response(text)
        assert result["issues"][0]["file"] == "main.py"

    def test_json_code_block_with_spaced_uppercase_language(self):
        text = '``` JSON\n{"issues": []}\n```'
        result = parse_json_response(text)
        assert result == {"issues": []}

    def test_balanced_json_ignores_braces_inside_strings(self):
        text = (
            "Here is the JSON:\n"
            '{"issues": [{"description": "body changed from {\\"a\\": 1} to raw text", '
            '"suggestion": "Keep `{}` examples inside strings parseable"}]}'
        )
        result = parse_json_response(text)
        assert result["issues"][0]["description"].startswith("body changed")

    def test_prefers_parent_task_payload_over_nested_empty_array(self):
        text = '先看示例 {"x": 1}\n最终 {"issues": []}'
        result = parse_json_response(text)
        assert result == {"issues": []}

    def test_json_with_unescaped_newline_in_string(self):
        text = (
            '```json\n'
            '{"issues": [{"file": "main.py", '
            '"description": "first line\nsecond line", '
            '"suggestion": "extract helper"}]}\n'
            '```'
        )
        result = parse_json_response(text)
        assert result["issues"][0]["description"] == "first line\nsecond line"

    def test_python_literal_response_with_trailing_comma(self):
        text = (
            "Result:\n"
            "{'issues': [{'file': 'main.py', 'line': '10', "
            "'description': 'duplicate branch', 'suggestion': 'extract helper'}],}"
        )
        result = parse_json_response(text)
        assert result["issues"][0]["description"] == "duplicate branch"

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

    @patch("pr_insight.ai.client.httpx.AsyncClient")
    def test_init_openai_provider(self, mock_httpx_cls):
        from pr_insight.ai.client import AIClient

        AIClient(api_key="test-key", model="gpt-4o", provider="openai")

        mock_httpx_cls.assert_called_once()
        kwargs = mock_httpx_cls.call_args.kwargs
        assert str(kwargs["base_url"]) == "https://api.openai.com/v1"
        assert kwargs["headers"]["Authorization"] == "Bearer test-key"

    def test_init_unsupported_provider(self):
        from pr_insight.ai.client import AIClient

        with pytest.raises(ValueError, match="Unsupported AI provider"):
            AIClient(api_key="test-key", provider="unknown")

    @patch("pr_insight.ai.client.anthropic.AsyncAnthropic")
    async def test_call_success(self, mock_anthropic_cls):
        from pr_insight.ai.client import AIClient

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        mock_response = MagicMock()
        mock_block = MagicMock(text='{"result": "ok"}', type="text")
        mock_response.content = [mock_block]
        mock_client.messages.create = AsyncMock(return_value=mock_response)

        ai = AIClient(api_key="test-key")
        result = await ai._call("system", "user")

        assert result == '{"result": "ok"}'
        mock_client.messages.create.assert_called_once()

    @patch("pr_insight.ai.client.anthropic.AsyncAnthropic")
    @patch("pr_insight.ai.client.asyncio.sleep", new_callable=AsyncMock)
    async def test_call_retry_on_rate_limit(self, mock_sleep, mock_anthropic_cls):
        import anthropic
        from pr_insight.ai.client import AIClient

        mock_client = MagicMock()
        mock_anthropic_cls.return_value = mock_client

        # First call raises RateLimitError, second succeeds
        mock_response = MagicMock()
        mock_block = MagicMock(text='{"ok": true}', type="text")
        mock_response.content = [mock_block]
        mock_client.messages.create = AsyncMock(side_effect=[
            anthropic.RateLimitError(
                message="rate limited",
                response=MagicMock(status_code=429, headers={}),
                body=None,
            ),
            mock_response,
        ])

        ai = AIClient(api_key="test-key")
        result = await ai._call("system", "user")

        assert result == '{"ok": true}'
        assert mock_client.messages.create.call_count == 2
        mock_sleep.assert_called_once()

    @patch("pr_insight.ai.client.httpx.AsyncClient")
    async def test_call_openai_success(self, mock_httpx_cls):
        from pr_insight.ai.client import AIClient

        mock_http = MagicMock()
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "choices": [
                {"message": {"content": '{"result": "ok"}'}}
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_http.post = AsyncMock(return_value=mock_response)
        mock_httpx_cls.return_value = mock_http

        ai = AIClient(api_key="test-key", model="gpt-4o", provider="openai")
        result = await ai._call("system", "user", max_tokens=123)

        assert result == '{"result": "ok"}'
        mock_http.post.assert_called_once_with(
            "/chat/completions",
            json={
                "model": "gpt-4o",
                "messages": [
                    {"role": "system", "content": "system"},
                    {"role": "user", "content": "user"},
                ],
                "max_tokens": 123,
            },
        )
