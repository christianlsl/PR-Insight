"""Tests for PR chunking logic."""

from pr_insight.analyzer.chunker import chunk_pr, format_pr_info
from pr_insight.github.models import FileChange, FileStatus, PRInfo


def _make_file(path: str, additions: int = 10, deletions: int = 5, patch: str = "diff") -> FileChange:
    return FileChange(path=path, status=FileStatus.MODIFIED, additions=additions, deletions=deletions, patch=patch)


def _make_pr(files: list[FileChange]) -> PRInfo:
    total_add = sum(f.additions for f in files)
    total_del = sum(f.deletions for f in files)
    return PRInfo(
        owner="o", repo="r", number=1, title="Test PR", description="desc",
        author="user", state="open", base_branch="main", head_branch="feat",
        url="https://github.com/o/r/pull/1", files_changed=len(files),
        additions=total_add, deletions=total_del, file_changes=files,
    )


class TestChunkPr:
    def test_empty_pr(self):
        pr = _make_pr([])
        assert chunk_pr(pr) == []

    def test_small_pr_single_chunk(self):
        files = [_make_file(f"src/file{i}.py") for i in range(10)]
        pr = _make_pr(files)
        chunks = chunk_pr(pr)
        assert len(chunks) == 1
        assert chunks[0].index == 0
        assert chunks[0].total == 1
        assert len(chunks[0].file_changes) == 10

    def test_medium_pr_multiple_chunks(self):
        files = [_make_file(f"src/dir{i % 5}/file{i}.py") for i in range(40)]
        pr = _make_pr(files)
        chunks = chunk_pr(pr)
        assert len(chunks) > 1
        # All chunks should have correct total
        for chunk in chunks:
            assert chunk.total == len(chunks)

    def test_large_pr_has_summary_chunk(self):
        files = [_make_file(f"src/dir{i % 20}/file{i}.py") for i in range(150)]
        pr = _make_pr(files)
        chunks = chunk_pr(pr)
        # First chunk should be summary-only
        assert chunks[0].is_summary_only
        assert len(chunks) > 2  # summary + at least 2 code chunks

    def test_chunk_diff_text_contains_file_path(self):
        files = [_make_file("src/important.py", patch="@@ -1,3 +1,4 @@\n+new line")]
        pr = _make_pr(files)
        chunks = chunk_pr(pr)
        assert "src/important.py" in chunks[0].diff_text

    def test_chunks_ordered_by_directory(self):
        # Need > 20 files to trigger medium PR path (which sorts by directory)
        files = [_make_file(f"src/z_dir/file{i}.py") for i in range(12)]
        files += [_make_file(f"src/a_dir/file{i}.py") for i in range(12)]
        pr = _make_pr(files)
        chunks = chunk_pr(pr)
        assert len(chunks) > 1
        # Find a chunk that contains both directories
        for chunk in chunks:
            a_files = [f for f in chunk.file_changes if "a_dir" in f.path]
            z_files = [f for f in chunk.file_changes if "z_dir" in f.path]
            if a_files and z_files:
                a_idx = min(i for i, f in enumerate(chunk.file_changes) if "a_dir" in f.path)
                z_idx = min(i for i, f in enumerate(chunk.file_changes) if "z_dir" in f.path)
                assert a_idx < z_idx
                return
        # If no chunk has both, ordering is still correct (all a_dir in earlier chunks)
        all_a = [c.index for c in chunks for f in c.file_changes if "a_dir" in f.path]
        all_z = [c.index for c in chunks for f in c.file_changes if "z_dir" in f.path]
        if all_a and all_z:
            assert min(all_a) <= min(all_z)


class TestFormatPrInfo:
    def test_basic_format(self):
        pr = _make_pr([_make_file("src/main.py")])
        text = format_pr_info(pr)
        assert "Test PR" in text
        assert "user" in text
        assert "main" in text

    def test_with_labels(self):
        pr = _make_pr([_make_file("src/main.py")])
        pr.labels = ["bug", "urgent"]
        text = format_pr_info(pr)
        assert "bug" in text
