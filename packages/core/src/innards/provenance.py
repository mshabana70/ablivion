"""Run provenance: the ``manifest.json`` and ``config.resolved.json`` records (guide §5).

Every field is observed, never guessed: an unknown commit is ``None`` with a
note, not a placeholder string. Nothing here stores an absolute path, so a
bundle can be shared without leaking or depending on a private directory.
"""

from __future__ import annotations

import os
import platform
import shutil
import subprocess
from datetime import UTC, datetime
from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from innards.identity import ModelIdentity, Sha256Hex
from innards.records import Record

FIRST_PARTY = ("innards", "abl-eval", "ablivion", "abl-experiments")
TRACKED_DEPENDENCIES = (*FIRST_PARTY, "pydantic", "numpy", "torch", "transformers", "safetensors")

RunStatus = Literal["incomplete", "complete", "failed"]


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")


class _Frozen(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class CodeState(_Frozen):
    commit: str | None
    dirty: bool | None
    note: str | None = None


class Accelerator(_Frozen):
    name: str
    memory_mib: int | None
    driver: str | None


class Hardware(_Frozen):
    platform: str
    machine: str
    python: str
    cpu_count: int | None
    accelerators: tuple[Accelerator, ...]
    accelerator_probe: str  # how ``accelerators`` was obtained, or why it is empty


class RunManifest(Record):
    kind: Literal["run_manifest"] = "run_manifest"
    schema_version: Literal[1] = 1
    run_id: str
    command: str
    status: RunStatus
    created_at: str
    finished_at: str | None = None
    error: str | None = None
    code: CodeState
    base_model: ModelIdentity | None
    config_sha256: Sha256Hex | None
    hardware: Hardware
    dependencies: dict[str, str | None]
    seeds: dict[str, int] = {}
    artifacts: dict[str, Sha256Hex] = {}  # relative name -> sha256, written only at completion


class ResolvedConfig(Record):
    """The validated config with defaults filled in. ``config`` is tool-specific; the core does not interpret it."""

    kind: Literal["resolved_config"] = "resolved_config"
    schema_version: Literal[1] = 1
    tool: str
    source_sha256: Sha256Hex
    config: dict[str, Any]


def dependency_versions(names: tuple[str, ...] = TRACKED_DEPENDENCIES) -> dict[str, str | None]:
    found: dict[str, str | None] = {}
    for name in names:
        try:
            found[name] = version(name)
        except PackageNotFoundError:
            found[name] = None
    return found


def _run(args: list[str], cwd: Path | None = None) -> subprocess.CompletedProcess[str] | None:
    try:
        return subprocess.run(args, cwd=cwd, capture_output=True, text=True, timeout=10, check=False)
    except (OSError, subprocess.TimeoutExpired):
        return None


def probe_nvidia_smi() -> tuple[tuple[Accelerator, ...], str]:
    """Query the driver directly, so hardware is recorded even before torch is installed."""
    exe = shutil.which("nvidia-smi")
    if exe is None:
        return (), "nvidia-smi not found"
    result = _run([exe, "--query-gpu=name,memory.total,driver_version", "--format=csv,noheader,nounits"])
    if result is None or result.returncode != 0:
        return (), "nvidia-smi failed"
    devices = []
    for line in result.stdout.strip().splitlines():
        name, memory, driver = (part.strip() for part in line.split(","))
        devices.append(Accelerator(name=name, memory_mib=int(memory) if memory.isdigit() else None, driver=driver))
    return tuple(devices), "nvidia-smi"


def collect_hardware() -> Hardware:
    accelerators, probe = probe_nvidia_smi()
    return Hardware(
        platform=platform.platform(),
        machine=platform.machine(),
        python=platform.python_version(),
        cpu_count=os.cpu_count(),
        accelerators=accelerators,
        accelerator_probe=probe,
    )


def code_state(anchor: Path) -> CodeState:
    """Commit of the repository that *tracks* ``anchor`` (a module file of the running tool).

    Requiring the file to be tracked avoids reporting a repository's HEAD for code
    that was actually installed from a wheel into a directory inside it.
    """
    if shutil.which("git") is None:
        return CodeState(commit=None, dirty=None, note="git not installed")
    where = anchor.resolve().parent
    tracked = _run(["git", "ls-files", "--error-unmatch", anchor.name], cwd=where)
    if tracked is None or tracked.returncode != 0:
        return CodeState(commit=None, dirty=None, note="code is not tracked by a git work tree (no repository, or installed from a wheel)")
    head = _run(["git", "rev-parse", "HEAD"], cwd=where)
    if head is None or head.returncode != 0:
        return CodeState(commit=None, dirty=None, note="git repository has no commits")
    status = _run(["git", "status", "--porcelain", "--untracked-files=no"], cwd=where)
    dirty = None if status is None or status.returncode != 0 else bool(status.stdout.strip())
    return CodeState(commit=head.stdout.strip(), dirty=dirty)
