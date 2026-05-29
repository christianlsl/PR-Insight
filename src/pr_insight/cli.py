"""CLI entry point for PR-Insight — integrated with analysis engine."""

from __future__ import annotations

import asyncio
import logging
import sys
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel

from . import __version__
from .config import Config

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="pr-insight")
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging.")
@click.pass_context
def cli(ctx: click.Context, verbose: bool) -> None:
    """PR-Insight: AI-powered code review tool for GitHub Pull Requests."""
    level = logging.DEBUG if verbose else logging.WARNING
    logging.basicConfig(level=level, format="%(name)s: %(message)s")


@cli.command()
@click.argument("pr_url")
@click.option(
    "--output", "-o",
    default="terminal",
    help="Output: terminal, html, comment (comma-separated).",
)
@click.option("--output-dir", default="./reports", help="Directory for HTML reports.")
@click.option(
    "--risk-level", "-r",
    type=click.Choice(["low", "medium", "high"]),
    default="low",
    help="Minimum risk level to display.",
)
@click.option("--language", "-l", default="zh", help="Report language: zh or en.")
@click.option("--focus", "-f", default="all", help="Focus: security,performance,style,all.")
@click.option("--no-context", is_flag=True, help="Skip fetching surrounding code context.")
def review(
    pr_url: str,
    output: str,
    output_dir: str,
    risk_level: str,
    language: str,
    focus: str,
    no_context: bool,
) -> None:
    """Analyze a GitHub Pull Request with AI."""
    from .ai.client import AIClient
    from .analyzer.engine import analyze_pr
    from .github.client import GitHubClient, parse_pr_url
    from .output.terminal import render_report

    outputs = [o.strip() for o in output.split(",")]

    # Parse PR URL
    try:
        owner, repo, number = parse_pr_url(pr_url)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    # Load config
    cfg = Config()
    try:
        gh_token = cfg.github_token
        ai_key = cfg.anthropic_key
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    model = cfg.model
    base_url = cfg.base_url or None

    console.print(Panel(
        f"[bold]PR-Insight v{__version__}[/bold]\n"
        f"Analyzing: [cyan]{owner}/{repo}#{number}[/cyan]\n"
        f"Model: {model}",
        title="Starting Review",
        border_style="blue",
    ))

    # Step 1: Fetch PR data
    console.print("\n[bold blue]Step 1/4:[/bold blue] Fetching PR data from GitHub...")
    try:
        gh_client = GitHubClient(gh_token)
        pr_info = gh_client.get_pr(owner, repo, number)
    except Exception as e:
        console.print(f"[red]Error fetching PR:[/red] {e}")
        raise SystemExit(1)

    console.print(f"  Found [green]{pr_info.files_changed}[/green] changed files "
                  f"(+{pr_info.additions}/-{pr_info.deletions})")

    # Step 2: Prepare
    console.print("[bold blue]Step 2/4:[/bold blue] Preparing analysis...")
    console.print(f"  Languages: {', '.join(pr_info.languages) or 'unknown'}")

    # Step 3: AI Analysis
    console.print("[bold blue]Step 3/4:[/bold blue] Running AI analysis...")
    ai_client = AIClient(api_key=ai_key, model=model, base_url=base_url)

    try:
        report = asyncio.run(analyze_pr(
            pr_info=pr_info,
            ai_client=ai_client,
            language=language,
            focus=focus,
            no_context=no_context,
        ))
    except Exception as e:
        console.print(f"[red]Analysis error:[/red] {e}")
        raise SystemExit(1)

    stats = report.stats
    console.print(f"  Done! Found [red]{stats['high_risk']}[/red] high / "
                  f"[yellow]{stats['medium_risk']}[/yellow] medium risks, "
                  f"{stats['suggestions']} suggestions")

    # Step 4: Output
    console.print("[bold blue]Step 4/4:[/bold blue] Generating output...")

    if "terminal" in outputs:
        render_report(report, risk_level)

    if "html" in outputs:
        from .output.html_report import generate_html_report
        out_path = Path(output_dir) / f"pr-{number}-review.html"
        generate_html_report(report, out_path)
        console.print(f"  HTML report: [green]{out_path}[/green]")

    if "comment" in outputs:
        from .output.github_comment import post_review_comment
        try:
            post_review_comment(gh_client, report)
            console.print("  Posted review comment to PR.")
        except Exception as e:
            console.print(f"  [yellow]Failed to post comment:[/yellow] {e}")

    console.print("\n[green]Review complete![/green]")


@cli.group()
def config() -> None:
    """Manage PR-Insight configuration."""


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str) -> None:
    """Set a configuration value."""
    cfg = Config()
    cfg.set(key, value)
    masked = "***" if any(s in key.lower() for s in ("key", "token", "secret")) else value
    console.print(f"[green]Set[/green] {key} = {masked}")


@config.command("show")
def config_show() -> None:
    """Show current configuration."""
    cfg = Config()
    settings = cfg.show()
    table_data = "\n".join(f"  {k}: {v}" for k, v in settings.items())
    console.print(Panel(table_data, title="Configuration", border_style="blue"))


@config.command("models")
def config_models() -> None:
    """List supported AI models."""
    from .config import SUPPORTED_MODELS
    table_data = "\n".join(f"  {k}: {v}" for k, v in SUPPORTED_MODELS.items())
    console.print(Panel(table_data, title="Supported Models", border_style="blue"))


if __name__ == "__main__":
    cli()
