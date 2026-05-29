"""Tests for prompt templates."""

from pr_insight.analyzer.prompts import (
    build_review_prompt,
    build_risk_prompt,
    build_style_prompt,
    build_summary_prompt,
    get_system_prompt,
)


class TestSystemPrompt:
    def test_chinese(self):
        prompt = get_system_prompt("zh")
        assert len(prompt) > 100
        assert "JSON" in prompt

    def test_english(self):
        prompt = get_system_prompt("en")
        assert len(prompt) > 100
        assert "JSON" in prompt

    def test_default_is_chinese(self):
        assert get_system_prompt() == get_system_prompt("zh")


class TestSummaryPrompt:
    def test_contains_pr_info(self):
        prompt = build_summary_prompt("PR info here", "diff here", "zh")
        assert "PR info here" in prompt
        assert "diff here" in prompt

    def test_requests_json(self):
        prompt = build_summary_prompt("info", "diff", "zh")
        assert '"purpose"' in prompt
        assert '"impact"' in prompt

    def test_english_version(self):
        prompt = build_summary_prompt("info", "diff", "en")
        assert "purpose" in prompt.lower() or "Purpose" in prompt


class TestRiskPrompt:
    def test_contains_focus(self):
        prompt = build_risk_prompt("info", "diff", "zh", "security")
        assert "security" in prompt.lower() or "安全" in prompt

    def test_requests_risks_json(self):
        prompt = build_risk_prompt("info", "diff", "zh")
        assert '"risks"' in prompt
        assert '"severity"' in prompt
        assert '"confidence"' in prompt

    def test_default_focus_all(self):
        prompt = build_risk_prompt("info", "diff", "zh", "all")
        assert '"risks"' in prompt


class TestReviewPrompt:
    def test_requests_suggestions_json(self):
        prompt = build_review_prompt("info", "diff", "zh")
        assert '"suggestions"' in prompt
        assert '"category"' in prompt

    def test_english(self):
        prompt = build_review_prompt("info", "diff", "en")
        assert "suggestions" in prompt.lower() or "Suggestions" in prompt


class TestStylePrompt:
    def test_requests_issues_json(self):
        prompt = build_style_prompt("diff", "zh")
        assert '"issues"' in prompt
        assert '"type"' in prompt

    def test_includes_diff(self):
        prompt = build_style_prompt("some diff content", "zh")
        assert "some diff content" in prompt
