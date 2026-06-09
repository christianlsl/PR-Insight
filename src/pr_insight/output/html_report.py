"""Generate HTML review reports."""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..analyzer.engine import ReviewFinding, ReviewReport, SEVERITY_ORDER
from ..github.models import FileChange

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _md_to_html(text) -> str:
    """Convert simple markdown patterns to HTML."""
    if isinstance(text, list):
        text = "\n".join(str(item) for item in text)
    if not text:
        return ""
    # Escape HTML special chars
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Code blocks: ```...```
    text = re.sub(
        r"```(\w*)\n(.*?)```",
        lambda m: f'<pre><code class="language-{m.group(1)}">{m.group(2)}</code></pre>',
        text,
        flags=re.DOTALL,
    )
    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Inline code: `text`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Links: [text](url)
    text = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2">\1</a>', text)
    # Unordered lists: - item
    text = re.sub(r"(?:^|\n)- (.+?)(?=\n(?!- )|\Z)", lambda m: f"\n<ul><li>{m.group(1)}</li></ul>", text, flags=re.DOTALL)
    # Merge adjacent <ul> tags
    text = re.sub(r"</ul>\s*<ul>", "", text)
    # Newlines to <br> (but not inside <pre>)
    parts = re.split(r"(<pre>.*?</pre>)", text, flags=re.DOTALL)
    for i, part in enumerate(parts):
        if not part.startswith("<pre>"):
            parts[i] = part.replace("\n", "<br>")
    return "".join(parts)


def _split_patch_views(file_change: FileChange) -> dict[str, str]:
    """Build original/modified snippets and raw diff text from a unified patch."""
    original_lines: list[str] = []
    modified_lines: list[str] = []
    diff_lines: list[str] = []

    for line in (file_change.patch or "").splitlines():
        diff_lines.append(line)

        if line.startswith("@@"):
            original_lines.append(line)
            modified_lines.append(line)
            continue
        if line.startswith("---") or line.startswith("+++"):
            continue
        if line.startswith("-"):
            original_lines.append(line[1:])
            continue
        if line.startswith("+"):
            modified_lines.append(line[1:])
            continue
        if line.startswith(" "):
            original_lines.append(line[1:])
            modified_lines.append(line[1:])
            continue
        if line:
            original_lines.append(line)
            modified_lines.append(line)

    return {
        "file": file_change.path,
        "old_path": file_change.old_path or "",
        "status": file_change.status.value,
        "language": file_change.language,
        "additions": str(file_change.additions),
        "deletions": str(file_change.deletions),
        "original": "\n".join(original_lines).strip(),
        "modified": "\n".join(modified_lines).strip(),
        "diff": "\n".join(diff_lines).strip(),
    }


def _build_code_views(report: ReviewReport) -> dict[str, dict[str, str]]:
    """Build file-path keyed code views for HTML issue drill-downs."""
    views: dict[str, dict[str, str]] = {}
    for file_change in report.pr_info.file_changes:
        views[file_change.path] = _split_patch_views(file_change)
        if file_change.old_path:
            views[file_change.old_path] = views[file_change.path]
    return views


def _filter_findings(findings: list[ReviewFinding], risk_level: str) -> list[ReviewFinding]:
    """Filter findings using the same minimum severity rule as terminal output."""
    min_value = SEVERITY_ORDER.get(risk_level, SEVERITY_ORDER["low"])
    return [
        finding
        for finding in findings
        if SEVERITY_ORDER.get(finding.severity, 0) >= min_value
    ]


def generate_html_report(
    report: ReviewReport,
    output_path: Path,
    risk_level: str = "low",
) -> Path:
    """Generate an HTML report from the review results."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env.filters["md"] = _md_to_html
    template = env.get_template("report.html.j2")
    code_views: dict[str, dict[str, str]] = _build_code_views(report)
    risks = _filter_findings(report.risks, risk_level)
    suggestions = _filter_findings(report.suggestions, risk_level)
    style_issues = _filter_findings(report.style_issues, risk_level)

    html = template.render(
        pr=report.pr_info,
        summary=report.summary,
        risks=risks,
        suggestions=suggestions,
        style_issues=style_issues,
        errors=report.errors,
        stats={
            **report.stats,
            "risks": len(risks),
            "suggestions": len(suggestions),
            "style_issues": len(style_issues),
            "high_risk": len([r for r in risks if r.severity == "high"]),
            "medium_risk": len([r for r in risks if r.severity == "medium"]),
        },
        code_views=code_views,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
