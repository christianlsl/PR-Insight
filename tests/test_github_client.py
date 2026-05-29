"""Tests for GitHub client module."""

import pytest
from unittest.mock import MagicMock, patch

from pr_insight.github.client import GitHubClient, parse_pr_url, _parse_hunks
from pr_insight.github.models import FileStatus


class TestParsePrUrl:
    """Tests for parse_pr_url function."""

    def test_full_url(self):
        owner, repo, number = parse_pr_url("https://github.com/owner/repo/pull/123")
        assert owner == "owner"
        assert repo == "repo"
        assert number == 123

    def test_url_without_scheme(self):
        owner, repo, number = parse_pr_url("github.com/owner/repo/pull/456")
        assert owner == "owner"
        assert repo == "repo"
        assert number == 456

    def test_shorthand(self):
        owner, repo, number = parse_pr_url("owner/repo#789")
        assert owner == "owner"
        assert repo == "repo"
        assert number == 789

    def test_invalid_url_raises(self):
        with pytest.raises(ValueError, match="Invalid PR URL"):
            parse_pr_url("not-a-valid-url")

    def test_url_with_trailing_slash(self):
        owner, repo, number = parse_pr_url("https://github.com/o/r/pull/1/")
        assert owner == "o"
        assert repo == "r"
        assert number == 1


class TestParseHunks:
    """Tests for _parse_hunks function."""

    def test_single_hunk(self):
        patch = "@@ -10,3 +10,4 @@\n line1\n+line2\n line3"
        hunks = _parse_hunks(patch)
        assert len(hunks) == 1
        assert hunks[0].old_start == 10
        assert hunks[0].new_start == 10

    def test_multiple_hunks(self):
        patch = (
            "@@ -1,3 +1,4 @@\n old1\n+new1\n old2\n"
            "@@ -20,2 +21,3 @@\n old3\n+new4\n old4"
        )
        hunks = _parse_hunks(patch)
        assert len(hunks) == 2
        assert hunks[0].old_start == 1
        assert hunks[1].old_start == 20

    def test_empty_patch(self):
        assert _parse_hunks("") == []
        assert _parse_hunks(None) == []


class TestGitHubClient:
    """Tests for GitHubClient with mocked PyGithub."""

    @patch("pr_insight.github.client.Github")
    def test_get_pr(self, mock_github_cls):
        # Setup mock
        mock_gh = MagicMock()
        mock_github_cls.return_value = mock_gh

        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo

        mock_pr = MagicMock()
        mock_pr.title = "Test PR"
        mock_pr.body = "Test description"
        mock_pr.user.login = "testuser"
        mock_pr.state = "open"
        mock_pr.base.ref = "main"
        mock_pr.head.ref = "feature"
        mock_pr.html_url = "https://github.com/o/r/pull/1"
        mock_pr.changed_files = 2
        mock_pr.additions = 10
        mock_pr.deletions = 5
        mock_pr.labels = []

        mock_file = MagicMock()
        mock_file.filename = "src/main.py"
        mock_file.status = "modified"
        mock_file.additions = 8
        mock_file.deletions = 3
        mock_file.patch = "@@ -1,3 +1,6 @@\n line1\n+line2\n line3"
        mock_file.previous_filename = None

        mock_pr.get_files.return_value = [mock_file]
        mock_repo.get_pull.return_value = mock_pr

        client = GitHubClient("fake-token")
        pr_info = client.get_pr("o", "r", 1)

        assert pr_info.title == "Test PR"
        assert pr_info.author == "testuser"
        assert pr_info.files_changed == 2
        assert len(pr_info.file_changes) == 1
        assert pr_info.file_changes[0].path == "src/main.py"
        assert pr_info.file_changes[0].status == FileStatus.MODIFIED
        assert len(pr_info.file_changes[0].hunks) == 1

    @patch("pr_insight.github.client.Github")
    def test_post_review_comment(self, mock_github_cls):
        mock_gh = MagicMock()
        mock_github_cls.return_value = mock_gh
        mock_repo = MagicMock()
        mock_gh.get_repo.return_value = mock_repo
        mock_pr = MagicMock()
        mock_repo.get_pull.return_value = mock_pr

        client = GitHubClient("fake-token")
        client.post_review_comment("o", "r", 1, "Great work!")

        mock_pr.create_issue_comment.assert_called_once_with("Great work!")
