"""Generate HTML review reports."""

from __future__ import annotations

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

from ..analyzer.engine import ReviewReport

TEMPLATE_DIR = Path(__file__).parent.parent / "templates"


def generate_html_report(report: ReviewReport, output_path: Path) -> Path:
    """Generate an HTML report from the review results."""
    env = Environment(loader=FileSystemLoader(str(TEMPLATE_DIR)))
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
