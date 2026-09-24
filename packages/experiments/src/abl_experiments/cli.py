"""``abx`` command line. Experiment subcommands (``rq1``, ``rq2``) arrive with Phase D."""

from __future__ import annotations

import argparse

from abl_experiments import __version__


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="abx",
        description="Research experiments (RQ1 harmfulness under abliteration, RQ2 abliteration forensics). "
        "No experiment subcommands exist yet; they arrive with Phase D.",
    )
    parser.add_argument("--version", action="version", version=f"abx {__version__}")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _parser()
    parser.parse_args(argv)
    parser.print_help()
    return 0
