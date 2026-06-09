"""AI API client with retry and provider adapters."""

from __future__ import annotations

import asyncio
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass

import anthropic
import httpx

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 3  # seconds
ANALYSIS_TIMEOUT = 300  # seconds
MAX_CONCURRENT_TASKS = 3  # limit parallel API calls
OPENAI_DEFAULT_BASE_URL = "https://api.openai.com/v1"
SUPPORTED_PROVIDERS = {"anthropic", "openai"}


@dataclass
class AnalysisTask:
    """A single analysis task to send to the AI."""

    name: str  # e.g. "summary", "risk", "review", "style"
    system_prompt: str
    user_prompt: str
    max_tokens: int = 4096


@dataclass
class AnalysisResult:
    """Result from an AI analysis task."""

    task_name: str
    success: bool
    data: dict | None = None
    error: str | None = None
    raw_response: str = ""


class AIClient:
    """Async AI API client with retry logic for Anthropic and OpenAI APIs."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str | None = None,
        provider: str = "anthropic",
    ) -> None:
        provider = provider.lower()
        if provider not in SUPPORTED_PROVIDERS:
            raise ValueError(
                f"Unsupported AI provider '{provider}'. "
                f"Supported providers: {', '.join(sorted(SUPPORTED_PROVIDERS))}"
            )

        self._provider = provider
        self._model = model
        self._http_client: httpx.AsyncClient | None = None

        if provider == "anthropic":
            kwargs: dict = {"api_key": api_key}
            if base_url:
                kwargs["base_url"] = base_url
            self._client = anthropic.AsyncAnthropic(**kwargs)
        else:
            self._client = None
            self._http_client = httpx.AsyncClient(
                base_url=(base_url or OPENAI_DEFAULT_BASE_URL).rstrip("/"),
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=ANALYSIS_TIMEOUT,
            )

    async def _call(self, system_prompt: str, user_prompt: str, max_tokens: int = 4096) -> str:
        """Async API call with retry."""
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                if self._provider == "anthropic":
                    return await self._call_anthropic(system_prompt, user_prompt, max_tokens)
                return await self._call_openai(system_prompt, user_prompt, max_tokens)
            except anthropic.RateLimitError as e:
                last_error = e
                delay = RETRY_BASE_DELAY * (2 ** attempt) * (1 + random.uniform(0, 0.5))
                logger.warning(f"Rate limited, retrying in {delay:.1f}s (attempt {attempt + 1})")
                await asyncio.sleep(delay)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    delay = RETRY_BASE_DELAY * (2 ** attempt) * (1 + random.uniform(0, 0.5))
                    logger.warning(f"Server error {e.status_code}, retrying in {delay:.1f}s")
                    await asyncio.sleep(delay)
                else:
                    raise
            except httpx.HTTPStatusError as e:
                if e.response.status_code == 429 or e.response.status_code >= 500:
                    last_error = e
                    delay = RETRY_BASE_DELAY * (2 ** attempt) * (1 + random.uniform(0, 0.5))
                    logger.warning(
                        f"OpenAI-compatible API error {e.response.status_code}, "
                        f"retrying in {delay:.1f}s"
                    )
                    await asyncio.sleep(delay)
                else:
                    raise
            except httpx.HTTPError as e:
                last_error = e
                delay = RETRY_BASE_DELAY * (2 ** attempt) * (1 + random.uniform(0, 0.5))
                logger.warning(f"OpenAI-compatible API request failed, retrying in {delay:.1f}s")
                await asyncio.sleep(delay)
        raise RuntimeError(f"API call failed after {MAX_RETRIES} retries: {last_error}")

    async def _call_anthropic(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        """Call Anthropic Messages API."""
        response = await self._client.messages.create(
            model=self._model,
            max_tokens=max_tokens,
            system=system_prompt,
            messages=[{"role": "user", "content": user_prompt}],
        )
        for block in response.content:
            if block.type == "text":
                return block.text
        # Fallback: extract from thinking blocks if no text block
        for block in response.content:
            thinking = getattr(block, "thinking", None)
            if thinking:
                return thinking
        raise RuntimeError("No text block in API response")

    async def _call_openai(self, system_prompt: str, user_prompt: str, max_tokens: int) -> str:
        """Call OpenAI-compatible Chat Completions API."""
        if self._http_client is None:
            raise RuntimeError("OpenAI HTTP client is not initialized")

        payload = {
            "model": self._model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "max_tokens": max_tokens,
        }
        response = await self._http_client.post("/chat/completions", json=payload)
        response.raise_for_status()
        data = response.json()
        choices = data.get("choices") or []
        if not choices:
            raise RuntimeError("No choices in OpenAI-compatible API response")
        message = choices[0].get("message") or {}
        content = message.get("content")
        if isinstance(content, str) and content:
            return content
        if isinstance(content, list):
            text_parts = [
                part.get("text", "")
                for part in content
                if isinstance(part, dict) and part.get("type") in (None, "text")
            ]
            text = "".join(text_parts)
            if text:
                return text
        raise RuntimeError("No text content in OpenAI-compatible API response")

    async def analyze(self, task: AnalysisTask) -> AnalysisResult:
        """Run a single analysis task asynchronously."""
        try:
            raw = await asyncio.wait_for(
                self._call(task.system_prompt, task.user_prompt, task.max_tokens),
                timeout=ANALYSIS_TIMEOUT,
            )
            from .parser import parse_json_response
            data = parse_json_response(raw)
            return AnalysisResult(task_name=task.name, success=True, data=data, raw_response=raw)
        except asyncio.TimeoutError:
            return AnalysisResult(task_name=task.name, success=False, error=f"Timeout after {ANALYSIS_TIMEOUT}s")
        except Exception as e:
            return AnalysisResult(task_name=task.name, success=False, error=str(e))

    async def analyze_batch(
        self,
        tasks: list[AnalysisTask],
        on_task_done: Callable[[str], None] | None = None,
    ) -> list[AnalysisResult]:
        """Run multiple analysis tasks in parallel with concurrency control."""
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_TASKS)

        async def _run(task: AnalysisTask) -> AnalysisResult:
            async with semaphore:
                result = await self.analyze(task)
            if on_task_done is not None:
                on_task_done(task.name)
            return result

        results = await asyncio.gather(*(_run(t) for t in tasks))
        return list(results)
