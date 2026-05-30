"""Analysis strategies that build prompts for different review aspects."""

from __future__ import annotations

from ..ai.client import AnalysisTask
from .chunker import Chunk, format_pr_info
from .prompts import (
    build_review_prompt,
    build_risk_prompt,
    build_style_prompt,
    build_summary_prompt,
    get_system_prompt,
)
from ..github.models import PRInfo


def build_summary_tasks(
    pr_info: PRInfo,
    chunks: list[Chunk],
    language: str = "zh",
) -> list[AnalysisTask]:
    """Build summary analysis task. Uses full diff for small PRs, chunk summaries for large ones."""
    system = get_system_prompt(language)
    pr_text = format_pr_info(pr_info)

    # For large PRs with summary-only chunk, use that
    summary_chunks = [c for c in chunks if c.is_summary_only]
    if summary_chunks:
        diff_text = summary_chunks[0].diff_text
    else:
        # Combine all diffs (truncated if too long)
        all_diff = "\n".join(c.diff_text for c in chunks)
        diff_text = all_diff[:60_000] + "\n...(truncated)" if len(all_diff) > 60_000 else all_diff

    return [AnalysisTask(
        name="summary",
        system_prompt=system,
        user_prompt=build_summary_prompt(pr_text, diff_text, language),
    )]


def build_risk_tasks(
    pr_info: PRInfo,
    chunks: list[Chunk],
    language: str = "zh",
    focus: str = "all",
) -> list[AnalysisTask]:
    """Build risk analysis tasks — one per chunk (excluding summary-only)."""
    system = get_system_prompt(language)
    pr_text = format_pr_info(pr_info)
    tasks: list[AnalysisTask] = []

    for chunk in chunks:
        if chunk.is_summary_only:
            continue
        files_text = chunk.diff_text
        if chunk.total > 1:
            files_text = f"[Chunk {chunk.index + 1}/{chunk.total}]\n{files_text}"
        tasks.append(AnalysisTask(
            name=f"risk_{chunk.index}",
            system_prompt=system,
            user_prompt=build_risk_prompt(pr_text, files_text, language, focus),
        ))

    return tasks


def build_review_tasks(
    pr_info: PRInfo,
    chunks: list[Chunk],
    language: str = "zh",
) -> list[AnalysisTask]:
    """Build review suggestion tasks — one per chunk (excluding summary-only)."""
    system = get_system_prompt(language)
    pr_text = format_pr_info(pr_info)
    tasks: list[AnalysisTask] = []

    for chunk in chunks:
        if chunk.is_summary_only:
            continue
        files_text = chunk.diff_text
        if chunk.total > 1:
            files_text = f"[Chunk {chunk.index + 1}/{chunk.total}]\n{files_text}"
        tasks.append(AnalysisTask(
            name=f"review_{chunk.index}",
            system_prompt=system,
            user_prompt=build_review_prompt(pr_text, files_text, language),
        ))

    return tasks


def build_style_tasks(
    chunks: list[Chunk],
    language: str = "zh",
    pr_info: PRInfo | None = None,
) -> list[AnalysisTask]:
    """Build style check tasks — one per chunk (excluding summary-only)."""
    system = get_system_prompt(language)
    pr_text = format_pr_info(pr_info) if pr_info else ""
    tasks: list[AnalysisTask] = []

    for chunk in chunks:
        if chunk.is_summary_only:
            continue
        tasks.append(AnalysisTask(
            name=f"style_{chunk.index}",
            system_prompt=system,
            user_prompt=build_style_prompt(chunk.diff_text, language, pr_text),
        ))

    return tasks
