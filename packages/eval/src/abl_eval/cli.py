"""``abeval`` command line. Exit codes: 0 ok, 1 failure, 2 invalid input."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from abl_eval import __version__
from innards.errors import InputError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="abeval",
        description="Tool-agnostic evaluation harness: score and report any model or edited checkpoint.",
    )
    parser.add_argument("--version", action="version", version=f"abeval {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    report = sub.add_parser("report", help="render summary.md from a completed run bundle (no model needed)")
    report.add_argument("--run", type=Path, required=True, help="run bundle directory")
    report.add_argument("--output", type=Path, help="where to write the summary (default: RUN/summary.md)")
    return parser


def _report(args: argparse.Namespace) -> int:
    from abl_eval.report import render_summary
    from innards.records import write_text_atomic

    text = render_summary(args.run)
    target = args.output or args.run / "summary.md"
    write_text_atomic(target, text)
    print(f"wrote {target}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return {"report": _report}[args.command](args)
    except InputError as exc:
        print(f"abeval: error: {exc}", file=sys.stderr)
        return 2
