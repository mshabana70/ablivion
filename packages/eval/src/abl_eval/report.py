"""Minimal run report: ``summary.md`` rendered from a completed bundle.

A pure artifact transformation: it reads only records defined in the core, so
it works for any tool's bundle and needs no model. Every string that came from
a config or dataset is escaped before it reaches Markdown.
"""

from __future__ import annotations

from pathlib import Path

from innards.data import DataManifest, SplitRole
from innards.provenance import ResolvedConfig
from innards.run_store import open_completed_run

# Artifacts (guide §5) whose presence would mean the run changed the model.
INTERVENTION_ARTIFACTS = ("directions.json", "trials.jsonl", "export_manifest.json")

# Values are always inline (never at line start), so only inline-significant characters need escaping.
_MD_SPECIAL = str.maketrans({c: f"\\{c}" for c in "\\`*_[]|~"} | {"<": "&lt;", ">": "&gt;", "&": "&amp;"})


def md(text: object) -> str:
    """Escape for inline Markdown and table cells; newlines collapse to spaces."""
    return " ".join(str(text).split()).translate(_MD_SPECIAL)


def render_summary(run_dir: Path) -> str:
    run = open_completed_run(run_dir)
    m = run.manifest
    lines = [
        f"# Run {md(m.run_id)}",
        "",
        f"- **Command:** {md(m.command)}",
        f"- **Status:** {md(m.status)} ({md(m.created_at)} → {md(m.finished_at)})",
    ]
    if m.code.commit:
        lines.append(f"- **Code:** {md(m.code.commit)}{' (dirty)' if m.code.dirty else ''}")
    else:
        lines.append(f"- **Code:** commit unknown: {md(m.code.note)}")
    if m.base_model:
        lines.append(f"- **Base model:** {md(m.base_model.id)} @ {md(m.base_model.revision)}")
    edits = [name for name in INTERVENTION_ARTIFACTS if run.has(name)]
    lines.append(
        f"- **Interventions:** {md(', '.join(edits))}"
        if edits
        else "- **Interventions:** none (no direction, trial, or export records in this bundle)"
    )
    if run.has("config.resolved.json"):
        resolved = run.read("config.resolved.json", ResolvedConfig)
        lines.append(f"- **Config:** {md(resolved.tool)} config, sha256 {md(resolved.source_sha256)}")

    if run.has("data_manifest.json"):
        data = run.read("data_manifest.json", DataManifest)
        src = data.source
        lines += [
            "",
            "## Data",
            "",
            f"Source: {md(src.name)}; revision {md(src.revision or 'none recorded')}; "
            f"license {md(src.license or 'none recorded')}. Prompts sha256 {md(data.prompts_sha256)}.",
            "",
            "| Role | Families | Prompts | Categories |",
            "|---|---:|---:|---|",
        ]
        for role in SplitRole:
            summary = data.roles[role]
            categories = ", ".join(f"{md(name)}: {count}" for name, count in summary.categories.items())
            lines.append(f"| {role.value} | {len(summary.families)} | {len(summary.prompt_ids)} | {categories} |")

    hw = m.hardware
    accelerators = "; ".join(f"{md(a.name)} ({a.memory_mib} MiB)" for a in hw.accelerators) or md(hw.accelerator_probe)
    lines += [
        "",
        "## Environment",
        "",
        f"- **Platform:** {md(hw.platform)}, Python {md(hw.python)}, {hw.cpu_count} CPUs",
        f"- **Accelerators:** {accelerators}",
        "",
        "| Dependency | Version |",
        "|---|---|",
        *(f"| {md(name)} | {md(found or 'not installed')} |" for name, found in m.dependencies.items()),
        "",
        "## Artifacts",
        "",
        "| File | sha256 |",
        "|---|---|",
        *(f"| {md(name)} | `{digest}` |" for name, digest in m.artifacts.items()),
        "",
    ]
    return "\n".join(lines)
