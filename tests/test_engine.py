"""Tests for analysis engine."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch

from pr_insight.ai.client import AnalysisResult
from pr_insight.analyzer.engine import ReviewFinding, ReviewReport, analyze_pr, _extract_findings
from pr_insight.github.models import FileChange, FileStatus, PRInfo


def _make_pr(num_files: int = 3) -> PRInfo:
    files = [
        FileChange(f"src/file{i}.py", FileStatus.MODIFIED, 10, 5, f"diff{i}")
        for i in range(num_files)
    ]
    return PRInfo(
        owner="o", repo="r", number=1, title="Test PR", description="desc",
        author="user", state="open", base_branch="main", head_branch="feat",
        url="", files_changed=num_files, additions=30, deletions=15,
        file_changes=files,
    )


class TestReviewFinding:
    def test_defaults(self):
        f = ReviewFinding()
        assert f.severity == "low"
        assert f.confidence == "low"
        assert f.file == ""


class TestReviewReport:
    def test_stats(self):
        report = ReviewReport(pr_info=_make_pr())
        report.risks = [
            ReviewFinding(severity="high"),
            ReviewFinding(severity="medium"),
            ReviewFinding(severity="low"),
        ]
        report.suggestions = [ReviewFinding()]
        report.style_issues = [ReviewFinding(), ReviewFinding()]
        stats = report.stats
        assert stats["risks"] == 3
        assert stats["high_risk"] == 1
        assert stats["medium_risk"] == 1
        assert stats["suggestions"] == 1
        assert stats["style_issues"] == 2

    def test_filter_by_risk_level(self):
        report = ReviewReport(pr_info=_make_pr())
        report.risks = [
            ReviewFinding(severity="high"),
            ReviewFinding(severity="low"),
        ]
        filtered = report.filter_by_risk_level("medium")
        assert len(filtered) == 1
        assert filtered[0].severity == "high"

    def test_all_findings(self):
        report = ReviewReport(pr_info=_make_pr())
        report.risks = [ReviewFinding(description="risk")]
        report.suggestions = [ReviewFinding(description="suggestion")]
        report.style_issues = [ReviewFinding(description="style")]
        assert len(report.all_findings) == 3


class TestExtractFindings:
    def test_extract_risks(self):
        result = AnalysisResult(
            task_name="risk_0",
            success=True,
            data={"risks": [
                {"file": "main.py", "line": "10", "severity": "high",
                 "description": "bug", "suggestion": "fix it"}
            ]},
        )
        findings = _extract_findings(result, "risks")
        assert len(findings) == 1
        assert findings[0].file == "main.py"
        assert findings[0].severity == "high"

    def test_extract_empty(self):
        result = AnalysisResult(task_name="risk_0", success=True, data={})
        assert _extract_findings(result, "risks") == []

    def test_extract_failed(self):
        result = AnalysisResult(task_name="risk_0", success=False, error="timeout")
        assert _extract_findings(result, "risks") == []


@pytest.mark.asyncio
async def test_analyze_pr_mock():
    """Test full analysis pipeline with mocked AI client."""
    mock_client = AsyncMock()

    # Mock responses for each strategy
    summary_result = AnalysisResult(
        task_name="summary", success=True,
        data={"purpose": "Fix bug", "impact": "core module", "tech_details": "refactored"},
    )
    risk_result = AnalysisResult(
        task_name="risk_0", success=True,
        data={"risks": [{"file": "src/file0.py", "line": "5", "severity": "high",
                         "description": "null pointer", "suggestion": "add check"}]},
    )
    review_result = AnalysisResult(
        task_name="review_0", success=True,
        data={"suggestions": [{"file": "src/file1.py", "line": "10", "category": "readability",
                               "priority": "medium", "description": "rename var",
                               "improvement": "use descriptive name"}]},
    )
    style_result = AnalysisResult(
        task_name="style_0", success=True,
        data={"issues": []},
    )

    mock_client.analyze_batch.return_value = [summary_result, risk_result, review_result, style_result]

    pr_info = _make_pr(3)
    report = await analyze_pr(pr_info, mock_client, language="zh")

    assert report.summary["purpose"] == "Fix bug"
    assert len(report.risks) == 1
    assert report.risks[0].severity == "high"
    assert len(report.suggestions) == 1
    assert len(report.style_issues) == 0
    assert len(report.errors) == 0
