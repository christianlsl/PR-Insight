"""Data models for GitHub PR information."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class FileStatus(str, Enum):
    ADDED = "added"
    MODIFIED = "modified"
    DELETED = "deleted"
    RENAMED = "renamed"


@dataclass
class DiffHunk:
    """A single diff hunk within a file change."""

    old_start: int
    old_lines: int
    new_start: int
    new_lines: int
    content: str  # raw diff content for this hunk
    context_before: str = ""  # surrounding code for AI context
    context_after: str = ""


@dataclass
class FileChange:
    """Represents a single file change in a PR."""

    path: str
    status: FileStatus
    additions: int
    deletions: int
    patch: str  # raw diff patch
    hunks: list[DiffHunk] = field(default_factory=list)
    old_path: str | None = None  # for renames
    language: str = ""  # file extension derived

    def __post_init__(self) -> None:
        if not self.language and self.path:
            ext = self.path.rsplit(".", 1)
            self.language = ext[-1] if len(ext) > 1 else ""


@dataclass
class PRInfo:
    """Metadata and changes for a Pull Request."""

    owner: str
    repo: str
    number: int
    title: str
    description: str
    author: str
    state: str
    base_branch: str
    head_branch: str
    url: str
    files_changed: int
    additions: int
    deletions: int
    file_changes: list[FileChange] = field(default_factory=list)
    labels: list[str] = field(default_factory=list)

    @property
    def total_changes(self) -> int:
        return self.additions + self.deletions

    @property
    def languages(self) -> set[str]:
        return {fc.language for fc in self.file_changes if fc.language}

    def summary_text(self) -> str:
        """One-line summary for prompts."""
        return (
            f"PR #{self.number}: {self.title} "
            f"(by {self.author}, {self.files_changed} files, "
            f"+{self.additions}/-{self.deletions})"
        )
