"""Terminal output renderer using Rich."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from ..analyzer.engine import ReviewFinding, ReviewReport

console = Console()

SEVERITY_COLORS = {
    "high": "red",
    "medium": "yellow",
    "low": "cyan",
}

SEVERITY_ICONS = {
    "high": "!!",
    "medium": "!",
    "low": "i",
}


def _severity_display(severity: str) -> Text:
    color = SEVERITY_COLORS.get(severity, "white")
    icon = SEVERITY_ICONS.get(severity, "?")
    return Text(f"{icon} {severity.upper()}", style=f"bold {color}")


def _render_summary_panel(report: ReviewReport) -> None:
    """Render the PR summary panel."""
    summary = report.summary
    if not summary:
        return

    content = Text()
    if summary.get("purpose"):
        content.append("Purpose: ", style="bold")
        content.append(summary["purpose"] + "\n")
    if summary.get("impact"):
        content.append("Impact:  ", style="bold")
        content.append(summary["impact"] + "\n")
    if summary.get("tech_details"):
        content.append("Details: ", style="bold")
        content.append(summary["tech_details"] + "\n")
    if summary.get("risk_areas"):
        content.append("Risk Areas:\n", style="bold")
        for area in summary["risk_areas"]:
            content.append(f"  - {area}\n")

    console.print(Panel(content, title="Summary", border_style="blue"))


def _render_findings_table(findings: list[ReviewFinding], title: str, color: str) -> None:
    """Render findings as a colored table."""
    if not findings:
        return

    table = Table(title=title, show_lines=True, expand=True)
    table.add_column("Severity", width=10, justify="center")
    table.add_column("File", min_width=20)
    table.add_column("Line", width=8, justify="center")
    table.add_column("Description", min_width=30)
    table.add_column("Suggestion", min_width=30)

    for f in findings:
        table.add_row(
            _severity_display(f.severity),
            f.file,
            f.line,
            f.description,
            f.suggestion,
        )

    console.print(table)


def _render_errors(errors: list[str]) -> None:
    """Render analysis errors."""
    if not errors:
        return
    console.print(Panel(
        "\n".join(f"  - {e}" for e in errors),
        title="Analysis Errors",
        border_style="red",
    ))


def render_report(report: ReviewReport, risk_level: str = "low") -> None:
    """Render the full review report to terminal."""
    # Header
    pr = report.pr_info
    console.print()
    console.print(Panel(
        f"[bold]{pr.title}[/bold]\n"
        f"#{pr.number} by {pr.author} | {pr.head_branch} → {pr.base_branch}\n"
        f"{pr.files_changed} files, +{pr.additions}/-{pr.deletions}",
        title="PR-Insight Review",
        border_style="green",
    ))

    # Stats
    stats = report.stats
    console.print(
        f"\n[bold]Found:[/bold] "
        f"[red]{stats['high_risk']} high[/red] / "
        f"[yellow]{stats['medium_risk']} medium[/yellow] / "
        f"[cyan]{stats['risks']} total risks[/cyan] | "
        f"{stats['suggestions']} suggestions | "
        f"{stats['style_issues']} style issues"
    )

    # Summary
    _render_summary_panel(report)

    # Risks (filtered by level)
    risks = [r for r in report.risks if _should_show(r.severity, risk_level)]
    _render_findings_table(risks, "Risks & Issues", "red")

    # Suggestions
    suggestions = [s for s in report.suggestions if _should_show(s.severity, risk_level)]
    _render_findings_table(suggestions, "Improvement Suggestions", "blue")

    # Style issues
    style = [s for s in report.style_issues if _should_show(s.severity, risk_level)]
    _render_findings_table(style, "Style Issues", "cyan")

    # Errors
    _render_errors(report.errors)

    console.print()


def _should_show(severity: str, min_level: str) -> bool:
    order = {"low": 1, "medium": 2, "high": 3}
    return order.get(severity, 0) >= order.get(min_level, 1)
