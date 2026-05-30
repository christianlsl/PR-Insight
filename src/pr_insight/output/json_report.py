"""Generate JSON review reports."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path

from ..analyzer.engine import ReviewReport


def generate_json_report(report: ReviewReport, output_path: Path) -> Path:
    """Generate a JSON report from the review results."""
    data = {
        "pr": {
            "number": report.pr_info.number,
            "title": report.pr_info.title,
            "author": report.pr_info.author,
            "url": report.pr_info.url,
            "base_branch": report.pr_info.base_branch,
            "head_branch": report.pr_info.head_branch,
            "files_changed": report.pr_info.files_changed,
            "additions": report.pr_info.additions,
            "deletions": report.pr_info.deletions,
        },
        "summary": report.summary,
        "stats": report.stats,
        "risks": [asdict(r) for r in report.risks],
        "suggestions": [asdict(s) for s in report.suggestions],
        "style_issues": [asdict(s) for s in report.style_issues],
        "errors": report.errors,
    }

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    return output_path
