"""Tests for analysis strategies."""

import pytest
from unittest.mock import MagicMock

from pr_insight.analyzer.strategies import (
    _format_summary_context,
    build_summary_tasks,
    build_risk_tasks,
    build_review_tasks,
    build_style_tasks,
)
from pr_insight.analyzer.chunker import Chunk
from pr_insight.github.models import FileChange, FileStatus, PRInfo


def _make_pr_info() -> PRInfo:
    return PRInfo(
        owner="test",
        repo="repo",
        number=1,
        title="Test PR",
        description="A test PR",
        author="tester",
        state="open",
        base_branch="main",
        head_branch="feature",
        url="https://github.com/test/repo/pull/1",
        files_changed=1,
        additions=10,
        deletions=5,
        file_changes=[
            FileChange(
                path="src/main.py",
                status=FileStatus.MODIFIED,
                additions=10,
                deletions=5,
                patch="@@ -1,5 +1,10 @@\n+new code",
            )
        ],
    )


def _make_chunks() -> list[Chunk]:
    return [
        Chunk(
            index=0,
            total=1,
            file_changes=[],
            diff_text="some diff",
        )
    ]


class TestFormatSummaryContext:
    def test_empty_dict(self):
        assert _format_summary_context({}) == ""

    def test_chinese_format(self):
        summary = {
            "purpose": "添加认证功能",
            "impact": "auth 模块",
            "tech_details": "使用 JWT",
            "risk_areas": ["token 安全"],
        }
        result = _format_summary_context(summary, "zh")
        assert "添加认证功能" in result
        assert "auth 模块" in result
        assert "JWT" in result
        assert "token 安全" in result

    def test_english_format(self):
        summary = {
            "purpose": "Add auth",
            "impact": "auth module",
        }
        result = _format_summary_context(summary, "en")
        assert "Purpose: Add auth" in result
        assert "Impact: auth module" in result


class TestBuildSummaryTasks:
    def test_returns_single_task(self):
        pr = _make_pr_info()
        chunks = _make_chunks()
        tasks = build_summary_tasks(pr, chunks, "zh")
        assert len(tasks) == 1
        assert tasks[0].name == "summary"

    def test_max_tokens_is_2048(self):
        pr = _make_pr_info()
        chunks = _make_chunks()
        tasks = build_summary_tasks(pr, chunks, "zh")
        assert tasks[0].max_tokens == 2048


class TestBuildRiskTasks:
    def test_one_task_per_chunk(self):
        pr = _make_pr_info()
        chunks = [
            Chunk(index=0, total=2, file_changes=[], diff_text="diff1"),
            Chunk(index=1, total=2, file_changes=[], diff_text="diff2"),
        ]
        tasks = build_risk_tasks(pr, chunks, "zh")
        assert len(tasks) == 2
        assert tasks[0].name == "risk_0"
        assert tasks[1].name == "risk_1"

    def test_skips_summary_only_chunks(self):
        pr = _make_pr_info()
        chunks = [
            Chunk(index=0, total=2, file_changes=[], diff_text="summary", is_summary_only=True),
            Chunk(index=1, total=2, file_changes=[], diff_text="diff"),
        ]
        tasks = build_risk_tasks(pr, chunks, "zh")
        assert len(tasks) == 1

    def test_injects_summary_context(self):
        pr = _make_pr_info()
        chunks = _make_chunks()
        tasks = build_risk_tasks(pr, chunks, "zh", summary_context="PR Summary here")
        assert "PR Summary here" in tasks[0].user_prompt

    def test_focus_filter(self):
        pr = _make_pr_info()
        chunks = _make_chunks()
        tasks = build_risk_tasks(pr, chunks, "zh", focus="security")
        assert "security" in tasks[0].user_prompt.lower() or "安全" in tasks[0].user_prompt


class TestBuildReviewTasks:
    def test_max_tokens_is_6096(self):
        pr = _make_pr_info()
        chunks = _make_chunks()
        tasks = build_review_tasks(pr, chunks, "zh")
        assert tasks[0].max_tokens == 6096


class TestBuildStyleTasks:
    def test_max_tokens_is_2048(self):
        chunks = _make_chunks()
        tasks = build_style_tasks(chunks, "zh")
        assert tasks[0].max_tokens == 2048

    def test_injects_pr_info(self):
        pr = _make_pr_info()
        chunks = _make_chunks()
        tasks = build_style_tasks(chunks, "zh", pr_info=pr)
        assert "Test PR" in tasks[0].user_prompt
