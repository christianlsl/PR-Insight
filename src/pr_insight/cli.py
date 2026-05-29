"""CLI entry point for PR-Insight."""

from __future__ import annotations

import click
from rich.console import Console
from rich.panel import Panel

from . import __version__
from .config import Config

console = Console()


@click.group()
@click.version_option(version=__version__, prog_name="pr-insight")
def cli() -> None:
    """PR-Insight: AI-powered code review tool for GitHub Pull Requests."""


@cli.command()
@click.argument("pr_url")
@click.option(
    "--output", "-o",
    default="terminal",
    help="Output format: terminal, html, comment (comma-separated).",
)
@click.option("--output-dir", default="./reports", help="Directory for HTML reports.")
@click.option(
    "--risk-level", "-r",
    type=click.Choice(["low", "medium", "high"]),
    default="low",
    help="Minimum risk level to display.",
)
@click.option("--language", "-l", default="zh", help="Report language: zh or en.")
@click.option("--focus", "-f", default="all", help="Analysis focus: security,performance,style,all.")
@click.option("--no-context", is_flag=True, help="Skip fetching surrounding code context (faster).")
@click.pass_context
def review(
    ctx: click.Context,
    pr_url: str,
    output: str,
    output_dir: str,
    risk_level: str,
    language: str,
    focus: str,
    no_context: bool,
) -> None:
    """Analyze a GitHub Pull Request with AI."""
    from .github.client import GitHubClient, parse_pr_url

    try:
        owner, repo, number = parse_pr_url(pr_url)
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    cfg = Config()
    try:
        gh_token = cfg.github_token
    except ValueError as e:
        console.print(f"[red]Error:[/red] {e}")
        raise SystemExit(1)

    console.print(Panel(
        f"[bold]PR-Insight v{__version__}[/bold]\n"
        f"Analyzing: [cyan]{owner}/{repo}#{number}[/cyan]",
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

    # Step 2: Chunk & prepare
    console.print("[bold blue]Step 2/4:[/bold blue] Preparing analysis chunks...")
    console.print(f"  Languages: {', '.join(pr_info.languages) or 'unknown'}")

    # Step 3: AI analysis (placeholder for Phase 2)
    console.print("[bold blue]Step 3/4:[/bold blue] AI analysis... [yellow](not yet implemented)[/yellow]")

    # Step 4: Output (placeholder for Phase 3)
    console.print("[bold blue]Step 4/4:[/bold blue] Generating output...")

    # Temporary: print basic PR info
    console.print("\n")
    console.print(Panel(
        f"[bold]{pr_info.title}[/bold]\n"
        f"Author: {pr_info.author} | State: {pr_info.state}\n"
        f"Branch: {pr_info.head_branch} → {pr_info.base_branch}\n"
        f"Changes: {pr_info.files_changed} files, +{pr_info.additions}/-{pr_info.deletions}\n"
        f"Labels: {', '.join(pr_info.labels) or 'none'}\n\n"
        f"[dim]Files changed:[/dim]\n" +
        "\n".join(f"  {fc.status.value:8s} {fc.path}" for fc in pr_info.file_changes[:20]) +
        (f"\n  ... and {len(pr_info.file_changes) - 20} more" if len(pr_info.file_changes) > 20 else ""),
        title=f"PR #{pr_info.number}: {pr_info.title}",
        border_style="green",
    ))

    console.print("\n[yellow]Full AI analysis will be implemented in Phase 2.[/yellow]")


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
    console.print(f"[green]Set[/green] {key} = {'***' if 'key' in key or 'token' in key else value}")


@config.command("show")
def config_show() -> None:
    """Show current configuration."""
    cfg = Config()
    settings = cfg.show()
    table_data = "\n".join(f"  {k}: {v}" for k, v in settings.items())
    console.print(Panel(table_data, title="Configuration", border_style="blue"))


if __name__ == "__main__":
    cli()
