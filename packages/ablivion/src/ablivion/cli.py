"""``ablivion`` command line. Exit codes: 0 ok, 1 failure or failed check, 2 invalid input."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from ablivion import __version__
from innards.errors import InputError


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="ablivion",
        description="Abliteration research tool: produce and study edits using the innards core.",
    )
    parser.add_argument("--version", action="version", version=f"ablivion {__version__}")
    sub = parser.add_subparsers(dest="command", metavar="COMMAND", required=True)

    doctor = sub.add_parser("doctor", help="diagnose dependencies, device, disk, and config")
    doctor.add_argument("--config", type=Path, help="config to validate (TOML)")
    doctor.add_argument("--json", action="store_true", help="print checks as JSON")

    prepare = sub.add_parser("prepare", help="validate config and data, then write a run bundle with no edit")
    prepare.add_argument("--config", type=Path, required=True, help="config file (TOML)")
    prepare.add_argument("--output", type=Path, required=True, help="new or empty run directory")
    return parser


def _doctor(args: argparse.Namespace) -> int:
    from ablivion.doctor import as_dicts, render, run_doctor

    checks = run_doctor(args.config)
    print(json.dumps(as_dicts(checks), indent=2) if args.json else render(checks))
    return 1 if any(check.status == "fail" for check in checks) else 0


def _prepare(args: argparse.Namespace) -> int:
    from ablivion.prepare import prepare

    manifest = prepare(args.config, args.output)
    print(f"run {manifest.run_id} complete: {args.output}")
    return 0


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        return {"doctor": _doctor, "prepare": _prepare}[args.command](args)
    except InputError as exc:
        print(f"ablivion: error: {exc}", file=sys.stderr)
        return 2
