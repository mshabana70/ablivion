"""``ablivion doctor``: dependency, device, disk, and config diagnostics.

Statuses: ``ok``; ``warn`` (not needed yet at this stage, or degraded);
``fail`` (the tool cannot work); ``skip`` (not checked). Heavy imports (torch)
happen only inside the check that needs them, so ``--help`` stays fast.
"""

from __future__ import annotations

import importlib
import importlib.util
import os
import shutil
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

from ablivion.config import load_config
from innards.data import SplitRole, load_split
from innards.errors import InputError
from innards.provenance import FIRST_PARTY, dependency_versions, probe_nvidia_smi

Status = Literal["ok", "warn", "fail", "skip"]

# Qwen3-4B-Instruct-2507 at the pinned revision is 8,060,917,568 bytes of files
# (Hugging Face API, 2026-09-24). 16 GiB holds the base plus one exported edit.
MIN_FREE_CACHE_BYTES = 16 * 2**30
ML_STACK = ("torch", "transformers", "safetensors")


@dataclass(frozen=True)
class Check:
    name: str
    status: Status
    detail: str


def _python() -> Check:
    found = ".".join(map(str, sys.version_info[:3]))
    return Check("python", "ok" if sys.version_info >= (3, 12) else "fail", f"{found} (requires >= 3.12)")


def _packages() -> list[Check]:
    versions = dependency_versions((*FIRST_PARTY, "pydantic"))
    return [
        Check(f"package:{name}", "ok" if found else "fail", found or "not installed")
        for name, found in versions.items()
    ]


def _ml_stack() -> list[Check]:
    versions = dependency_versions(ML_STACK)
    return [
        Check(f"package:{name}", "ok" if found else "warn", found or "not installed (required from Stage A1)")
        for name, found in versions.items()
    ]


def _device() -> Check:
    if importlib.util.find_spec("torch") is not None:
        torch = importlib.import_module("torch")
        if torch.cuda.is_available():
            index = torch.cuda.current_device()
            bf16 = torch.cuda.is_bf16_supported()
            return Check("device", "ok", f"cuda:{index} {torch.cuda.get_device_name(index)}; bf16={'yes' if bf16 else 'no'}")
        return Check("device", "warn", f"torch {torch.__version__} sees no CUDA device; CPU only")
    devices, probe = probe_nvidia_smi()
    if devices:
        names = ", ".join(f"{d.name} ({d.memory_mib} MiB, driver {d.driver})" for d in devices)
        return Check("device", "warn", f"driver sees {names}; torch not installed, so usability is unverified")
    return Check("device", "warn", f"no GPU detected ({probe})")


def hf_hub_cache() -> Path:
    if cache := os.environ.get("HF_HUB_CACHE"):
        return Path(cache)
    if home := os.environ.get("HF_HOME"):
        return Path(home) / "hub"
    base = Path(os.environ.get("XDG_CACHE_HOME") or Path.home() / ".cache")
    return base / "huggingface" / "hub"


def _disk() -> Check:
    target = hf_hub_cache()
    probe = target
    while not probe.exists():
        probe = probe.parent
    free = shutil.disk_usage(probe).free
    status: Status = "ok" if free >= MIN_FREE_CACHE_BYTES else "warn"
    return Check("disk", status, f"{free / 2**30:.1f} GiB free at Hugging Face cache {target} (want >= 16 GiB)")


def _config(config_path: Path | None) -> Check:
    if config_path is None:
        return Check("config", "skip", "no --config given")
    try:
        loaded = load_config(config_path)
        split = load_split(loaded.data_manifest_path)
    except InputError as exc:
        return Check("config", "fail", str(exc))
    model = loaded.config.model
    counts = ", ".join(f"{role.value}={len(split.by_role(role))}" for role in SplitRole)
    return Check("config", "ok", f"valid; model {model.id}@{model.revision[:12]}; prompts {counts}")


def run_doctor(config_path: Path | None) -> list[Check]:
    return [_python(), *_packages(), *_ml_stack(), _device(), _disk(), _config(config_path)]


def as_dicts(checks: list[Check]) -> list[dict[str, str]]:
    return [asdict(check) for check in checks]


def render(checks: list[Check]) -> str:
    width = max(len(check.name) for check in checks)
    return "\n".join(f"[{check.status:>4}] {check.name:<{width}}  {check.detail}" for check in checks)
