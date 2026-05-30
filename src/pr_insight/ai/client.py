"""Claude API client with retry and rate limiting."""

from __future__ import annotations

import asyncio
import json
import logging
import random
from collections.abc import Callable
from dataclasses import dataclass

import anthropic

logger = logging.getLogger(__name__)

MAX_RETRIES = 3
RETRY_BASE_DELAY = 3  # seconds
ANALYSIS_TIMEOUT = 120  # seconds
MAX_CONCURRENT_TASKS = 3  # limit parallel API calls


@dataclass
class AnalysisTask:
    """A single analysis task to send to the AI."""

    name: str  # e.g. "summary", "risk", "review", "style"
    system_prompt: str
    user_prompt: str


@dataclass
class AnalysisResult:
    """Result from an AI analysis task."""

    task_name: str
    success: bool
    data: dict | None = None
    error: str | None = None
    raw_response: str = ""


class AIClient:
    """Async Claude API client with retry logic."""

    def __init__(
        self,
        api_key: str,
        model: str = "claude-sonnet-4-20250514",
        base_url: str | None = None,
    ) -> None:
        kwargs: dict = {"api_key": api_key}
        if base_url:
            kwargs["base_url"] = base_url
        self._client = anthropic.Anthropic(**kwargs)
        self._model = model

    def _call_sync(self, system_prompt: str, user_prompt: str) -> str:
        """Synchronous API call with retry."""
        last_error: Exception | None = None
        for attempt in range(MAX_RETRIES):
            try:
                response = self._client.messages.create(
                    model=self._model,
                    max_tokens=4096,
                    system=system_prompt,
                    messages=[{"role": "user", "content": user_prompt}],
                )
                return response.content[0].text
            except anthropic.RateLimitError as e:
                last_error = e
                delay = RETRY_BASE_DELAY * (2 ** attempt) * (1 + random.uniform(0, 0.5))
                logger.warning(f"Rate limited, retrying in {delay:.1f}s (attempt {attempt + 1})")
                import time
                time.sleep(delay)
            except anthropic.APIStatusError as e:
                if e.status_code >= 500:
                    last_error = e
                    delay = RETRY_BASE_DELAY * (2 ** attempt) * (1 + random.uniform(0, 0.5))
                    logger.warning(f"Server error {e.status_code}, retrying in {delay:.1f}s")
                    import time
                    time.sleep(delay)
                else:
                    raise
        raise RuntimeError(f"API call failed after {MAX_RETRIES} retries: {last_error}")

    async def analyze(self, task: AnalysisTask) -> AnalysisResult:
        """Run a single analysis task asynchronously."""
        try:
            loop = asyncio.get_event_loop()
            raw = await asyncio.wait_for(
                loop.run_in_executor(None, self._call_sync, task.system_prompt, task.user_prompt),
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
