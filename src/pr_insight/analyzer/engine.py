"""Analysis engine — orchestrates chunking, AI calls, and result merging."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from dataclasses import dataclass, field

from ..ai.client import AIClient, AnalysisResult
from ..github.models import PRInfo
from .chunker import Chunk, chunk_pr
from .strategies import (
    build_review_tasks,
    build_risk_tasks,
    build_style_tasks,
    build_summary_tasks,
)

logger = logging.getLogger(__name__)

# Risk severity order for filtering
SEVERITY_ORDER = {"high": 3, "medium": 2, "low": 1}


@dataclass
class ReviewFinding:
    """A single finding from the review."""

    file: str = ""
    line: str = ""
    severity: str = "low"
    confidence: str = "low"
    category: str = ""
    description: str = ""
    suggestion: str = ""
    example: str = ""


@dataclass
class ReviewReport:
    """Complete analysis report for a PR."""

    pr_info: PRInfo
    summary: dict = field(default_factory=dict)
    risks: list[ReviewFinding] = field(default_factory=list)
    suggestions: list[ReviewFinding] = field(default_factory=list)
    style_issues: list[ReviewFinding] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)

    @property
    def all_findings(self) -> list[ReviewFinding]:
        return self.risks + self.suggestions + self.style_issues

    def filter_by_risk_level(self, level: str) -> list[ReviewFinding]:
        """Filter findings by minimum risk level."""
        min_val = SEVERITY_ORDER.get(level, 1)
        return [f for f in self.all_findings if SEVERITY_ORDER.get(f.severity, 0) >= min_val]

    @property
    def stats(self) -> dict:
        return {
            "risks": len(self.risks),
            "suggestions": len(self.suggestions),
            "style_issues": len(self.style_issues),
            "errors": len(self.errors),
            "high_risk": len([r for r in self.risks if r.severity == "high"]),
            "medium_risk": len([r for r in self.risks if r.severity == "medium"]),
        }


def _extract_findings(result: AnalysisResult, finding_key: str) -> list[ReviewFinding]:
    """Extract ReviewFinding list from an analysis result."""
    if not result.success or not result.data:
        return []

    items = result.data.get(finding_key, [])
    findings: list[ReviewFinding] = []
    for item in items:
        if not isinstance(item, dict):
            continue
        findings.append(ReviewFinding(
            file=item.get("file", ""),
            line=item.get("line", ""),
            severity=item.get("severity", item.get("priority", "low")),
            confidence=item.get("confidence", "medium"),
            category=item.get("type", item.get("category", "")),
            description=item.get("description", ""),
            suggestion=item.get("suggestion", item.get("improvement", "")),
            example=item.get("example", ""),
        ))
    return findings


async def analyze_pr(
    pr_info: PRInfo,
    ai_client: AIClient,
    language: str = "zh",
    focus: str = "all",
    no_context: bool = False,
    on_task_done: Callable[[str], None] | None = None,
    file_content_fetcher: Callable[[str, str], str] | None = None,
) -> ReviewReport:
    """Run full analysis pipeline on a PR.

    1. Chunk the PR
    2. Build tasks for each strategy
    3. Run all tasks in parallel
    4. Merge results into ReviewReport
    """
    report = ReviewReport(pr_info=pr_info)

    # Step 1: Chunk
    chunks = chunk_pr(pr_info, no_context, file_content_fetcher)
    if not chunks:
        report.summary = {"purpose": "No changes to analyze", "impact": "", "tech_details": ""}
        return report

    logger.info(f"PR split into {len(chunks)} chunk(s)")

    # Step 2: Build all tasks
    summary_tasks = build_summary_tasks(pr_info, chunks, language)
    risk_tasks = build_risk_tasks(pr_info, chunks, language, focus)
    review_tasks = build_review_tasks(pr_info, chunks, language)
    style_tasks = build_style_tasks(chunks, language, pr_info)

    all_tasks = summary_tasks + risk_tasks + review_tasks + style_tasks
    logger.info(f"Running {len(all_tasks)} analysis tasks in parallel")

    # Step 3: Execute all in parallel
    results = await ai_client.analyze_batch(all_tasks, on_task_done=on_task_done)

    # Step 4: Merge results
    for result in results:
        if not result.success:
            report.errors.append(f"{result.task_name}: {result.error}")
            continue

        if result.task_name == "summary":
            report.summary = result.data or {}
        elif result.task_name.startswith("risk_"):
            report.risks.extend(_extract_findings(result, "risks"))
        elif result.task_name.startswith("review_"):
            report.suggestions.extend(_extract_findings(result, "suggestions"))
        elif result.task_name.startswith("style_"):
            report.style_issues.extend(_extract_findings(result, "issues"))

    # Deduplicate findings (same file + line + description)
    seen: set[str] = set()
    for lst in [report.risks, report.suggestions, report.style_issues]:
        unique: list[ReviewFinding] = []
        for f in lst:
            key = f"{f.file}:{f.line}:{f.description[:50]}"
            if key not in seen:
                seen.add(key)
                unique.append(f)
        lst.clear()
        lst.extend(unique)

    return report
