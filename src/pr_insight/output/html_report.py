"""Generate HTML review reports."""

from __future__ import annotations

import re
from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..analyzer.engine import ReviewReport

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def _md_to_html(text: str) -> str:
    """Convert simple markdown patterns to HTML."""
    if not text:
        return ""
    # Escape HTML special chars
    text = text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
    # Bold: **text**
    text = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", text)
    # Inline code: `text`
    text = re.sub(r"`([^`]+)`", r"<code>\1</code>", text)
    # Newlines to <br>
    text = text.replace("\n", "<br>")
    return text


def generate_html_report(report: ReviewReport, output_path: Path) -> Path:
    """Generate an HTML report from the review results."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
    env.filters["md"] = _md_to_html
    template = env.get_template("report.html.j2")

    html = template.render(
        pr=report.pr_info,
        summary=report.summary,
        risks=report.risks,
        suggestions=report.suggestions,
        style_issues=report.style_issues,
        errors=report.errors,
        stats=report.stats,
    )

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(html, encoding="utf-8")
    return output_path
