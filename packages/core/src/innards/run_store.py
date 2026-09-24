"""Run bundles on disk (guide §4 ``RunStore`` contract, minimal form).

Invariant: a partial bundle cannot masquerade as complete. ``manifest.json`` is
written first with status ``incomplete``; only ``finalize`` flips it to
``complete`` and records each artifact's SHA-256. Readers accept only complete
bundles whose artifacts still match those hashes. Tensor shards arrive with the
stages that produce them.
"""

from __future__ import annotations

import secrets
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path, PurePosixPath

from innards.errors import InputError
from innards.identity import sha256_file
from innards.provenance import RunManifest, utc_now
from innards.records import R, Record, read_record, write_record

MANIFEST_NAME = "manifest.json"


class RunStoreError(InputError):
    """The output location is unusable, or a bundle is incomplete or altered."""


def new_run_id() -> str:
    return f"{datetime.now(UTC):%Y%m%dT%H%M%SZ}-{secrets.token_hex(4)}"


def _check_name(name: str) -> None:
    path = PurePosixPath(name)
    if path.is_absolute() or ".." in path.parts or len(path.parts) != 1 or name == MANIFEST_NAME:
        raise ValueError(f"artifact name must be a plain file name other than {MANIFEST_NAME}: {name!r}")


class RunStore:
    """Writes one run bundle. Create with ``RunStore.create``."""

    def __init__(self, root: Path, manifest: RunManifest) -> None:
        self.root = root
        self._manifest = manifest
        self._written: set[str] = set()

    @classmethod
    def create(cls, root: Path, manifest: RunManifest) -> RunStore:
        if manifest.status != "incomplete":
            raise ValueError("a new run starts incomplete")
        if root.exists() and (not root.is_dir() or any(root.iterdir())):
            raise RunStoreError(f"output directory exists and is not empty (runs are never overwritten): {root}")
        root.mkdir(parents=True, exist_ok=True)
        write_record(root / MANIFEST_NAME, manifest)
        return cls(root, manifest)

    @property
    def manifest(self) -> RunManifest:
        return self._manifest

    def write_record(self, name: str, record: Record) -> None:
        _check_name(name)
        write_record(self.root / name, record)
        self._written.add(name)

    def _close(self, **update: object) -> RunManifest:
        self._manifest = self._manifest.model_copy(update={"finished_at": utc_now(), **update})
        write_record(self.root / MANIFEST_NAME, self._manifest)
        return self._manifest

    def finalize(self) -> RunManifest:
        artifacts = {name: sha256_file(self.root / name) for name in sorted(self._written)}
        return self._close(status="complete", artifacts=artifacts)

    def fail(self, error: str) -> RunManifest:
        return self._close(status="failed", error=error)


@dataclass(frozen=True)
class CompletedRun:
    root: Path
    manifest: RunManifest

    def has(self, name: str) -> bool:
        return name in self.manifest.artifacts

    def read(self, name: str, model: type[R]) -> R:
        if not self.has(name):
            raise RunStoreError(f"run {self.manifest.run_id} has no artifact {name!r}")
        return read_record(self.root / name, model)


def open_completed_run(root: Path) -> CompletedRun:
    """Open a bundle for reading; reject incomplete, failed, or altered bundles."""
    manifest = read_record(root / MANIFEST_NAME, RunManifest)
    if manifest.status != "complete":
        raise RunStoreError(f"run {manifest.run_id} is {manifest.status}; only complete runs can be read")
    for name, expected in manifest.artifacts.items():
        path = root / name
        if not path.is_file():
            raise RunStoreError(f"run {manifest.run_id}: artifact {name!r} is missing")
        if sha256_file(path) != expected:
            raise RunStoreError(f"run {manifest.run_id}: artifact {name!r} changed after the run completed")
    return CompletedRun(root=root, manifest=manifest)
