"""Shared test helpers. Importable as ``helpers`` because pytest puts tests/ on sys.path."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
MECHANICAL = REPO_ROOT / "data" / "fixtures" / "mechanical"


def prompt(id: str, family: str, text: str, category: str = "harmless", **extra: object) -> dict:
    return {
        "kind": "prompt",
        "schema_version": 1,
        "id": id,
        "messages": [{"role": "user", "content": text}],
        "category": category,
        "family": family,
        **extra,
    }


def write_split(directory: Path, rows: list[dict], assignments: dict[str, list[str]], **overrides: object) -> Path:
    """Write prompts.jsonl and a split manifest that pins its hash; return the manifest path."""
    directory.mkdir(parents=True, exist_ok=True)
    prompts = directory / "prompts.jsonl"
    prompts.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    manifest = {
        "kind": "split_manifest",
        "schema_version": 1,
        "source": {"name": "test"},
        "prompts": "prompts.jsonl",
        "prompts_sha256": hashlib.sha256(prompts.read_bytes()).hexdigest(),
        "assignments": assignments,
        **overrides,
    }
    path = directory / "splits.json"
    path.write_text(json.dumps(manifest), encoding="utf-8")
    return path



THREE_ROLES = {"fit": ["f1"], "validation": ["f2"], "final_test": ["f3"]}
