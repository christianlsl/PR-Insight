"""Tests for terminal output renderer."""

from unittest.mock import patch

from pr_insight.analyzer.engine import ReviewFinding, ReviewReport
from pr_insight.github.models import FileChange, FileStatus, PRInfo
from pr_insight.output.terminal import _should_show, render_report


def _make_report() -> ReviewReport:
    pr = PRInfo(
        owner="o", repo="r", number=1, title="Test PR", description="desc",
        author="user", state="open", base_branch="main", head_branch="feat",
        url="", files_changed=1, additions=10, deletions=5,
        file_changes=[FileChange("src/main.py", FileStatus.MODIFIED, 10, 5, "diff")],
    )
    report = ReviewReport(pr_info=pr)
    report.summary = {"purpose": "Fix bug", "impact": "core", "tech_details": "refactored"}
    report.risks = [
        ReviewFinding(file="src/main.py", line="10", severity="high", description="bug", suggestion="fix"),
        ReviewFinding(file="src/main.py", line="20", severity="low", description="minor", suggestion="ignore"),
    ]
    report.suggestions = [
        ReviewFinding(file="src/main.py", line="15", severity="medium", description="rename", suggestion="use better name"),
    ]
    return report


class TestShouldShow:
    def test_low_shows_all(self):
        assert _should_show("low", "low")
        assert _should_show("medium", "low")
        assert _should_show("high", "low")

    def test_medium_hides_low(self):
        assert not _should_show("low", "medium")
        assert _should_show("medium", "medium")
        assert _should_show("high", "medium")

    def test_high_only_shows_high(self):
        assert not _should_show("low", "high")
        assert not _should_show("medium", "high")
        assert _should_show("high", "high")


class TestRenderReport:
    def test_renders_without_error(self, capsys):
        report = _make_report()
        render_report(report, risk_level="low")
        # Should not raise any exception

    def test_renders_with_high_filter(self, capsys):
        report = _make_report()
        render_report(report, risk_level="high")
        # Should not raise, and low-risk items should be filtered

    def test_renders_empty_report(self, capsys):
        pr = PRInfo(
            owner="o", repo="r", number=1, title="Empty PR", description="",
            author="user", state="open", base_branch="main", head_branch="feat",
            url="", files_changed=0, additions=0, deletions=0,
        )
        report = ReviewReport(pr_info=pr)
        render_report(report)
