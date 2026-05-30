"""Chunking strategy for large PRs to fit within AI context limits."""

from __future__ import annotations

import logging
from collections.abc import Callable
from dataclasses import dataclass

from ..github.models import DiffHunk, FileChange, FileStatus, PRInfo

logger = logging.getLogger(__name__)

# Approximate token limits (conservative estimates)
MAX_FILES_PER_CHUNK = 15
MAX_DIFF_CHARS_PER_CHUNK = 80_000  # ~20K tokens
SMALL_PR_FILES = 20
SMALL_PR_CHANGES = 500  # lines
CONTEXT_LINES = 20  # lines of context before/after each hunk
MAX_HUNKS_PER_FILE = 10  # split files with more hunks across chunks


@dataclass
class Chunk:
    """A chunk of PR changes to be analyzed together."""

    index: int
    total: int
    file_changes: list[FileChange]
    diff_text: str
    is_summary_only: bool = False  # for very large PRs, summary chunk


def _is_binary(fc: FileChange) -> bool:
    """Detect binary files from diff content."""
    if not fc.patch:
        return False
    return "Binary files" in fc.patch or fc.patch.startswith("GIT binary patch")


def _split_large_files(file_changes: list[FileChange]) -> list[FileChange]:
    """Split files with many hunks into multiple virtual file changes."""
    result: list[FileChange] = []
    for fc in file_changes:
        if len(fc.hunks) <= MAX_HUNKS_PER_FILE:
            result.append(fc)
            continue
        # Split hunks into groups
        for i in range(0, len(fc.hunks), MAX_HUNKS_PER_FILE):
            chunk_hunks = fc.hunks[i:i + MAX_HUNKS_PER_FILE]
            patch = "\n".join(h.content for h in chunk_hunks)
            result.append(FileChange(
                path=fc.path,
                status=fc.status,
                additions=sum(h.new_lines for h in chunk_hunks),
                deletions=sum(h.old_lines for h in chunk_hunks),
                patch=patch,
                hunks=chunk_hunks,
                old_path=fc.old_path,
                language=fc.language,
            ))
    return result


def _populate_hunk_context(hunks: list[DiffHunk], file_lines: list[str]) -> None:
    """Fill context_before / context_after for each hunk from full file content."""
    total = len(file_lines)
    for hunk in hunks:
        # new_start is 1-based
        start = max(0, hunk.new_start - 1 - CONTEXT_LINES)
        end = min(total, hunk.new_start - 1 + hunk.new_lines + CONTEXT_LINES)
        hunk.context_before = "\n".join(file_lines[start:hunk.new_start - 1])
        hunk.context_after = "\n".join(file_lines[hunk.new_start - 1 + hunk.new_lines:end])


def _fetch_file_context(
    file_changes: list[FileChange],
    fetcher: Callable[[str, str], str],
    head_ref: str,
) -> None:
    """Fetch file content and populate hunk context for modified files."""
    for fc in file_changes:
        if fc.status in (FileStatus.DELETED, FileStatus.ADDED):
            continue
        if not fc.hunks:
            continue
        try:
            content = fetcher(fc.path, head_ref)
            if content:
                _populate_hunk_context(fc.hunks, content.splitlines())
        except Exception as e:
            logger.warning(f"Failed to fetch context for {fc.path}: {e}")


def _format_diff_for_chunk(file_changes: list[FileChange]) -> str:
    """Format file changes into a single diff text for AI analysis."""
    parts: list[str] = []
    for fc in file_changes:
        parts.append(f"### {fc.path} ({fc.status.value}, +{fc.additions}/-{fc.deletions})")
        if fc.hunks and any(h.context_before or h.context_after for h in fc.hunks):
            # Include context from hunks
            for hunk in fc.hunks:
                if hunk.context_before:
                    parts.append(f"```  // context before line {hunk.new_start}")
                    parts.append(hunk.context_before)
                parts.append(hunk.content)
                if hunk.context_after:
                    parts.append(f"```  // context after line {hunk.new_start + hunk.new_lines - 1}")
                    parts.append(hunk.context_after)
                parts.append("")
        elif fc.patch:
            parts.append(fc.patch)
        parts.append("")
    return "\n".join(parts)


def chunk_pr(
    pr_info: PRInfo,
    no_context: bool = False,
    file_content_fetcher: Callable[[str, str], str] | None = None,
) -> list[Chunk]:
    """Split PR changes into analyzable chunks.

    Strategy:
    - Small PR (< 20 files, < 500 changes): single chunk
    - Medium PR (20-100 files): group by ~15 files per chunk
    - Large PR (> 100 files): summary + grouped chunks by directory

    When *no_context* is False and *file_content_fetcher* is provided,
    fetch surrounding code context for each hunk to help AI understand
    the full picture.
    """
    files = _split_large_files([fc for fc in pr_info.file_changes if not _is_binary(fc)])
    total_files = len(files)
    total_changes = pr_info.total_changes

    if total_files == 0:
        return []

    # Fetch context for hunks if enabled
    if not no_context and file_content_fetcher is not None:
        _fetch_file_context(files, file_content_fetcher, pr_info.head_branch)

    # Small PR: single chunk
    if total_files <= SMALL_PR_FILES and total_changes <= SMALL_PR_CHANGES:
        return [Chunk(
            index=0,
            total=1,
            file_changes=files,
            diff_text=_format_diff_for_chunk(files),
        )]

    # Large PR: add summary chunk first
    chunks: list[Chunk] = []

    if total_files > 100:
        # Summary chunk with just file list
        summary_text = f"PR modifies {total_files} files across these directories:\n"
        dirs: dict[str, int] = {}
        for fc in files:
            d = fc.path.rsplit("/", 1)[0] if "/" in fc.path else "."
            dirs[d] = dirs.get(d, 0) + 1
        for d, count in sorted(dirs.items(), key=lambda x: -x[1]):
            summary_text += f"  {d}/ ({count} files)\n"
        chunks.append(Chunk(
            index=0,
            total=0,  # will be updated
            file_changes=[],
            diff_text=summary_text,
            is_summary_only=True,
        ))

    # Group files into chunks
    # Sort by directory for better context grouping
    sorted_files = sorted(files, key=lambda f: f.path.rsplit("/", 1)[0] if "/" in f.path else f.path)

    current_chunk_files: list[FileChange] = []
    current_chunk_size = 0

    for fc in sorted_files:
        fc_size = len(fc.patch)
        # Check if adding this file would exceed limits
        if (
            current_chunk_files
            and (
                len(current_chunk_files) >= MAX_FILES_PER_CHUNK
                or current_chunk_size + fc_size > MAX_DIFF_CHARS_PER_CHUNK
            )
        ):
            chunks.append(Chunk(
                index=len(chunks),
                total=0,
                file_changes=current_chunk_files,
                diff_text=_format_diff_for_chunk(current_chunk_files),
            ))
            current_chunk_files = []
            current_chunk_size = 0

        current_chunk_files.append(fc)
        current_chunk_size += fc_size

    # Flush remaining
    if current_chunk_files:
        chunks.append(Chunk(
            index=len(chunks),
            total=0,
            file_changes=current_chunk_files,
            diff_text=_format_diff_for_chunk(current_chunk_files),
        ))

    # Update total count
    for chunk in chunks:
        chunk.total = len(chunks)

    return chunks


def format_pr_info(pr_info: PRInfo) -> str:
    """Format PR metadata into a text summary for prompts."""
    return (
        f"Title: {pr_info.title}\n"
        f"Author: {pr_info.author}\n"
        f"Branch: {pr_info.head_branch} → {pr_info.base_branch}\n"
        f"Changes: {pr_info.files_changed} files, +{pr_info.additions}/-{pr_info.deletions}\n"
        f"Languages: {', '.join(pr_info.languages) or 'unknown'}\n"
        f"Labels: {', '.join(pr_info.labels) or 'none'}\n"
        f"\nDescription:\n{pr_info.description or '(no description)'}"
    )
