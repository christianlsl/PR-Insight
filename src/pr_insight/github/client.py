"""GitHub API client for fetching PR data."""

from __future__ import annotations

import re
from urllib.parse import urlparse

from github import Github
from github.PullRequest import PullRequest

from .models import DiffHunk, FileChange, FileStatus, PRInfo

_PR_URL_PATTERN = re.compile(
    r"(?:https?://)?github\.com/(?P<owner>[^/]+)/(?P<repo>[^/]+)/pull/(?P<number>\d+)"
)


def parse_pr_url(url: str) -> tuple[str, str, int]:
    """Parse a GitHub PR URL into (owner, repo, number).

    Accepts formats:
      - https://github.com/owner/repo/pull/123
      - github.com/owner/repo/pull/123
      - owner/repo#123
    """
    # owner/repo#number shorthand
    shorthand = re.match(r"^([A-Za-z0-9_.-]+)/([A-Za-z0-9_.-]+)#(\d+)$", url)
    if shorthand:
        return shorthand.group(1), shorthand.group(2), int(shorthand.group(3))

    m = _PR_URL_PATTERN.search(url)
    if not m:
        raise ValueError(
            f"Invalid PR URL: {url}\n"
            "Expected: https://github.com/owner/repo/pull/123 or owner/repo#123"
        )
    return m.group("owner"), m.group("repo"), int(m.group("number"))


def _parse_hunks(patch: str) -> list[DiffHunk]:
    """Parse a unified diff patch into DiffHunk objects."""
    if not patch:
        return []

    hunks: list[DiffHunk] = []
    hunk_header = re.compile(r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@")
    current_lines: list[str] = []
    old_start = old_lines = new_start = new_lines = 0

    def _flush() -> None:
        if current_lines:
            hunks.append(DiffHunk(
                old_start=old_start,
                old_lines=old_lines,
                new_start=new_start,
                new_lines=new_lines,
                content="\n".join(current_lines),
            ))

    for line in patch.split("\n"):
        m = hunk_header.match(line)
        if m:
            _flush()
            current_lines = []
            old_start = int(m.group(1))
            old_lines = int(m.group(2)) if m.group(2) else 1
            new_start = int(m.group(3))
            new_lines = int(m.group(4)) if m.group(4) else 1
            continue
        current_lines.append(line)

    _flush()
    return hunks


_STATUS_MAP = {
    "added": FileStatus.ADDED,
    "modified": FileStatus.MODIFIED,
    "deleted": FileStatus.DELETED,
    "renamed": FileStatus.RENAMED,
}


class GitHubClient:
    """Fetches PR information from GitHub."""

    def __init__(self, token: str) -> None:
        self._gh = Github(token)

    def get_pr(self, owner: str, repo: str, number: int) -> PRInfo:
        """Fetch full PR info including file changes and diffs."""
        gh_repo = self._gh.get_repo(f"{owner}/{repo}")
        pr: PullRequest = gh_repo.get_pull(number)

        file_changes: list[FileChange] = []
        for f in pr.get_files():
            status = _STATUS_MAP.get(f.status, FileStatus.MODIFIED)
            hunks = _parse_hunks(f.patch or "")
            file_changes.append(FileChange(
                path=f.filename,
                status=status,
                additions=f.additions,
                deletions=f.deletions,
                patch=f.patch or "",
                hunks=hunks,
                old_path=f.previous_filename if status == FileStatus.RENAMED else None,
            ))

        return PRInfo(
            owner=owner,
            repo=repo,
            number=number,
            title=pr.title,
            description=pr.body or "",
            author=pr.user.login,
            state=pr.state,
            base_branch=pr.base.ref,
            head_branch=pr.head.ref,
            url=pr.html_url,
            files_changed=pr.changed_files,
            additions=pr.additions,
            deletions=pr.deletions,
            file_changes=file_changes,
            labels=[l.name for l in pr.labels],
        )

    def get_file_content(self, owner: str, repo: str, path: str, ref: str) -> str:
        """Get the full content of a file at a given ref (branch/commit)."""
        gh_repo = self._gh.get_repo(f"{owner}/{repo}")
        try:
            content_file = gh_repo.get_contents(path, ref=ref)
            if isinstance(content_file, list):
                return ""
            return content_file.decoded_content.decode("utf-8", errors="replace")
        except Exception:
            return ""

    def post_review_comment(self, owner: str, repo: str, number: int, body: str) -> None:
        """Post a review comment on a PR."""
        gh_repo = self._gh.get_repo(f"{owner}/{repo}")
        pr = gh_repo.get_pull(number)
        pr.create_issue_comment(body)
