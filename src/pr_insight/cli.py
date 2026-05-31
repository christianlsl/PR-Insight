"""CLI entry point for PR-Insight — integrated with analysis engine."""

from __future__ import annotations

import asyncio
import logging
from pathlib import Path

import click
from rich.console import Console
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn, TaskProgressColumn, TimeElapsedColumn

from . import __version__
from .config import Config

console = Console()


def _friendly_name(task_name: str) -> str:
    """Map task name to a human-readable label."""
    if task_name == "summary":
        return "Summary"
    for prefix, label in [("risk_", "Risk"), ("review_", "Review"), ("style_", "Style")]:
        if task_name.startswith(prefix):
            try:
                chunk_num = int(task_name[len(prefix):]) + 1
                return f"{label} (chunk {chunk_num})"
            except ValueError:
                return label
    return task_name


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
    help="Output: terminal, html, json, comment (comma-separated).",
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
@click.option("--dry-run", is_flag=True, help="Fetch PR data and show plan without AI analysis.")
def review(
    pr_url: str,
    output: str,
    output_dir: str,
    risk_level: str,
    language: str,
    focus: str,
    no_context: bool,
    dry_run: bool,
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

    # Dry-run: show chunking plan and exit
    if dry_run:
        from .analyzer.chunker import chunk_pr
        chunks = chunk_pr(pr_info)
        console.print(Panel(
            f"[bold]Dry Run — Chunking Plan[/bold]\n"
            f"Files changed: {pr_info.files_changed}\n"
            f"Chunks: {len(chunks)}\n"
            f"Language: {language}\n"
            f"Focus: {focus}\n"
            f"Context: {'off' if no_context else 'on'}",
            title="Plan",
            border_style="yellow",
        ))
        for chunk in chunks:
            label = " (summary only)" if chunk.is_summary_only else ""
            files = ", ".join(fc.path for fc in chunk.file_changes) or "(none)"
            console.print(f"  Chunk {chunk.index + 1}/{chunk.total}{label}: {files}")
        raise SystemExit(0)

    # Step 2: Prepare
    console.print("[bold blue]Step 2/4:[/bold blue] Preparing analysis...")
    console.print(f"  Languages: {', '.join(pr_info.languages) or 'unknown'}")

    # Step 3: AI Analysis
    console.print("[bold blue]Step 3/4:[/bold blue] Running AI analysis...")
    ai_client = AIClient(api_key=ai_key, model=model, base_url=base_url)

    def _fetch_file(path: str, ref: str) -> str:
        return gh_client.get_file_content(owner, repo, path, ref)

    try:
        with Progress(
            SpinnerColumn(),
            TextColumn("[bold green]{task.description}"),
            BarColumn(),
            TaskProgressColumn(),
            TimeElapsedColumn(),
            console=console,
        ) as progress:
            task_id = progress.add_task("Analyzing", total=None)

            def _on_task_done(task_name: str) -> None:
                progress.advance(task_id)
                progress.update(task_id, description=f"Analyzing ({_friendly_name(task_name)})")

            report = asyncio.run(analyze_pr(
                pr_info=pr_info,
                ai_client=ai_client,
                language=language,
                focus=focus,
                no_context=no_context,
                on_task_done=_on_task_done,
                file_content_fetcher=_fetch_file if not no_context else None,
            ))
            progress.update(task_id, description="Analysis complete")
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

    if "json" in outputs:
        from .output.json_report import generate_json_report
        out_path = Path(output_dir) / f"pr-{number}-review.json"
        generate_json_report(report, out_path)
        console.print(f"  JSON report: [green]{out_path}[/green]")

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


@config.command("unset")
@click.argument("key")
def config_unset(key: str) -> None:
    """Remove a configuration value."""
    cfg = Config()
    if cfg.unset(key):
        console.print(f"[green]Unset[/green] {key}")
    else:
        console.print(f"[yellow]Key[/yellow] {key} not found in config file")


def _mask(val: str | None) -> str:
    """Mask sensitive value for display."""
    if not val:
        return "not set"
    return val[:4] + "***" + val[-4:] if len(val) > 8 else "***"


@config.command("init")
def config_init() -> None:
    """Interactive configuration wizard."""
    cfg = Config()
    console.print(Panel(
        "[bold]PR-Insight Configuration Wizard[/bold]\n"
        "Press Enter to keep current value (shown in brackets).",
        border_style="blue",
    ))

    github_token = input(f"GitHub Token [{_mask(cfg.get('github_token'))}]: ").strip()
    if github_token:
        cfg.set("github_token", github_token)

    anthropic_key = input(f"API Key [{_mask(cfg.get('anthropic_key'))}]: ").strip()
    if anthropic_key:
        cfg.set("anthropic_key", anthropic_key)

    model = input(f"Model [{cfg.model}]: ").strip()
    if model:
        cfg.set("model", model)

    base_url = input(f"Base URL [{cfg.base_url or 'default (Anthropic)'}]: ").strip()
    if base_url:
        cfg.set("base_url", base_url)

    language = input(f"Language (zh/en) [{cfg.language}]: ").strip()
    if language:
        cfg.set("language", language)

    console.print("\n[green]Configuration saved![/green]")
    settings = cfg.show()
    table_data = "\n".join(f"  {k}: {v}" for k, v in settings.items())
    console.print(Panel(table_data, title="Configuration", border_style="blue"))


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
    cli.main()
