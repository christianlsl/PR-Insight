"""Tests for CLI module."""

import pytest
from click.testing import CliRunner
from unittest.mock import patch, MagicMock

from pr_insight.cli import cli


@pytest.fixture
def runner():
    return CliRunner()


class TestCliBasics:
    """Test basic CLI functionality."""

    def test_version(self, runner):
        result = runner.invoke(cli, ["--version"])
        assert result.exit_code == 0
        assert "pr-insight" in result.output

    def test_help(self, runner):
        result = runner.invoke(cli, ["--help"])
        assert result.exit_code == 0
        assert "review" in result.output
        assert "config" in result.output


class TestConfigCommands:
    """Test config subcommands."""

    def test_config_show(self, runner):
        result = runner.invoke(cli, ["config", "show"])
        assert result.exit_code == 0

    def test_config_set_and_show(self, runner):
        with runner.isolated_filesystem():
            result = runner.invoke(cli, ["config", "set", "model", "deepseek-chat"])
            assert result.exit_code == 0
            assert "model" in result.output


class TestReviewCommand:
    """Test review command with mocked dependencies."""

    def test_review_invalid_url(self, runner):
        result = runner.invoke(cli, ["review", "not-a-url"])
        assert result.exit_code == 1
        assert "Invalid PR URL" in result.output

    @patch("pr_insight.cli.Config")
    def test_review_missing_config(self, mock_config_cls, runner):
        mock_config = MagicMock()
        mock_config.github_token = None
        mock_config_cls.return_value = mock_config
        # The property raises ValueError
        type(mock_config).github_token = property(lambda self: (_ for _ in ()).throw(ValueError("not configured")))

        result = runner.invoke(cli, ["review", "https://github.com/o/r/pull/1"])
        assert result.exit_code == 1

    def test_review_help(self, runner):
        result = runner.invoke(cli, ["review", "--help"])
        assert result.exit_code == 0
        assert "--output" in result.output
        assert "--risk-level" in result.output
        assert "--focus" in result.output
