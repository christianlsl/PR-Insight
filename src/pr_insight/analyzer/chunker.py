"""Chunking strategy for large PRs to fit within AI context limits."""

from __future__ import annotations

from dataclasses import dataclass

from ..github.models import FileChange, PRInfo

# Approximate token limits (conservative estimates)
MAX_FILES_PER_CHUNK = 15
MAX_DIFF_CHARS_PER_CHUNK = 80_000  # ~20K tokens
SMALL_PR_FILES = 20
SMALL_PR_CHANGES = 500  # lines


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


def _format_diff_for_chunk(file_changes: list[FileChange]) -> str:
    """Format file changes into a single diff text for AI analysis."""
    parts: list[str] = []
    for fc in file_changes:
        parts.append(f"### {fc.path} ({fc.status.value}, +{fc.additions}/-{fc.deletions})")
        if fc.patch:
            parts.append(fc.patch)
        parts.append("")
    return "\n".join(parts)


def chunk_pr(pr_info: PRInfo, no_context: bool = False) -> list[Chunk]:
    """Split PR changes into analyzable chunks.

    Strategy:
    - Small PR (< 20 files, < 500 changes): single chunk
    - Medium PR (20-100 files): group by ~15 files per chunk
    - Large PR (> 100 files): summary + grouped chunks by directory

    When *no_context* is True, skip binary files and context-dependent
    processing to speed up analysis.
    """
    files = [fc for fc in pr_info.file_changes if not _is_binary(fc)]
    total_files = len(files)
    total_changes = pr_info.total_changes

    if total_files == 0:
        return []

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
    start_idx = 0

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
        start_idx = 1

    # Group files into chunks
    # Sort by directory for better context grouping
    sorted_files = sorted(files, key=lambda f: f.path.rsplit("/", 1)[0] if "/" in f.path else f.path)

    current_chunk_files: list[FileChange] = []
    current_chunk_size = 0
    chunk_start_idx = len(chunks)

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
