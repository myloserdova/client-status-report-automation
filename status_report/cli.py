"""Command line entry point: python -m status_report"""
from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from .loader import DataError, load_project, load_tasks
from .metrics import build_summary
from .render import render_client_html, render_client_markdown, render_workload_markdown


def _iso_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError:
        raise argparse.ArgumentTypeError(f"'{value}' is not a valid date, use YYYY-MM-DD") from None


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="status_report",
        description="Generate a weekly client status report and an internal workload view "
        "from project.json and tasks.csv.",
    )
    parser.add_argument("--data-dir", type=Path, default=Path("data"), help="folder with project.json and tasks.csv")
    parser.add_argument("--out-dir", type=Path, default=Path("reports"), help="where to write the reports")
    parser.add_argument("--as-of", type=_iso_date, default=None, help="report date, YYYY-MM-DD (default: today)")
    parser.add_argument("--validate-only", action="store_true", help="check the input data and exit")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    as_of = args.as_of or date.today()

    try:
        project = load_project(args.data_dir / "project.json")
        tasks = load_tasks(args.data_dir / "tasks.csv", project)
    except DataError as exc:
        print(f"Data error: {exc}", file=sys.stderr)
        return 2

    print(f"Validated {len(tasks)} tasks across {len(project.milestones)} milestones.")
    if args.validate_only:
        return 0

    summary = build_summary(project, tasks, as_of)
    stamp = as_of.isoformat()
    outputs = {
        f"client_status_{stamp}.md": render_client_markdown(project, summary),
        f"client_status_{stamp}.html": render_client_html(project, summary),
        f"team_workload_{stamp}.md": render_workload_markdown(project, summary),
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    for name, content in outputs.items():
        (args.out_dir / name).write_text(content, encoding="utf-8")

    print(f"Overall status: {summary.rag} ({'; '.join(summary.rag_reasons)})")
    for name in outputs:
        print(f"  wrote {args.out_dir / name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
