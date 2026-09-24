"""Prompt records, the three split roles, and split-manifest validation (guide §5).

Mechanism only: this module validates a partition someone else made. *How* to
group near-duplicates and assign families to roles is evaluation policy and
belongs outside the core.

Roles are assigned per **family** (a group of prompts that must not be split:
paraphrases, translations, shared templates), never per prompt. A family in two
roles, or identical prompt text in two roles, is leakage and is rejected.
"""

from __future__ import annotations

import json
from collections import Counter
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path, PurePosixPath
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, StringConstraints, field_validator, model_validator

from innards.errors import InputError
from innards.identity import Sha256Hex, sha256_file
from innards.records import Record, read_jsonl, read_record


class SplitError(InputError):
    """The split manifest and the prompt file disagree, or the partition leaks."""


class SplitRole(StrEnum):
    FIT = "fit"                # estimate directions, train probes
    VALIDATION = "validation"  # choose methods, parameters, monitor thresholds
    FINAL_TEST = "final_test"  # evaluate a frozen choice; opened only at a declared boundary


StableId = Annotated[str, StringConstraints(pattern=r"^[A-Za-z0-9][A-Za-z0-9._:-]*$")]


class Message(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    role: Literal["system", "user", "assistant"]
    content: str


class MediaRef(BaseModel):
    """Content-addressed attachment. Text-only prompts have none."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    sha256: Sha256Hex
    media_type: str = Field(min_length=1)


class PromptRecord(Record):
    """One prompt. ``id`` and ``family`` must survive every transformation unchanged."""

    kind: Literal["prompt"] = "prompt"
    schema_version: Literal[1] = 1
    id: StableId
    messages: tuple[Message, ...] = Field(min_length=1)
    category: StableId
    family: StableId
    split: SplitRole | None = None  # filled from the split manifest by load_split
    media: tuple[MediaRef, ...] = ()


class DatasetSource(BaseModel):
    """Where the prompts came from. ``revision`` stays None rather than being invented."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    name: str = Field(min_length=1)
    revision: str | None = None
    license: str | None = None
    note: str | None = None


class SplitManifest(Record):
    kind: Literal["split_manifest"] = "split_manifest"
    schema_version: Literal[1] = 1
    source: DatasetSource
    prompts: str  # POSIX path of the prompt JSONL, relative to this manifest
    prompts_sha256: Sha256Hex
    assignments: dict[SplitRole, tuple[StableId, ...]]  # role -> family IDs

    @field_validator("prompts")
    @classmethod
    def _relative(cls, value: str) -> str:
        path = PurePosixPath(value)
        if path.is_absolute() or ".." in path.parts or "\\" in value:
            raise ValueError(f"must be a relative POSIX path inside the manifest's directory, got {value!r}")
        return value

    @model_validator(mode="after")
    def _roles_disjoint(self) -> SplitManifest:
        missing = [role.value for role in SplitRole if role not in self.assignments]
        if missing:
            raise ValueError(f"assignments must list every role; missing: {', '.join(missing)}")
        empty = [role.value for role in SplitRole if not self.assignments[role]]
        if empty:
            raise ValueError(f"every role needs at least one family; empty: {', '.join(empty)}")
        seen: dict[str, SplitRole] = {}
        for role in SplitRole:
            for family in self.assignments[role]:
                if family not in seen:
                    seen[family] = role
                elif seen[family] is role:
                    raise ValueError(f"family {family!r} is listed twice in {role.value}")
                else:
                    raise ValueError(
                        f"split overlap: family {family!r} is assigned to both {seen[family].value} and {role.value}"
                    )
        return self

    def role_of(self) -> dict[str, SplitRole]:
        return {family: role for role, families in self.assignments.items() for family in families}


def _content_key(record: PromptRecord) -> str:
    """Messages with case and whitespace normalized. Catches copies, not paraphrases."""
    return json.dumps([(m.role, " ".join(m.content.casefold().split())) for m in record.messages])


@dataclass(frozen=True)
class LoadedSplit:
    manifest: SplitManifest
    manifest_sha256: str
    records: tuple[PromptRecord, ...]  # file order; every record has ``split`` set

    def by_role(self, role: SplitRole) -> tuple[PromptRecord, ...]:
        return tuple(r for r in self.records if r.split is role)


def load_split(manifest_path: Path) -> LoadedSplit:
    """Load a split manifest and its prompts, rejecting any disagreement or leakage.

    All problems are collected and reported together.
    """
    manifest = read_record(manifest_path, SplitManifest)
    prompts_path = manifest_path.parent / manifest.prompts
    if not prompts_path.is_file():
        raise SplitError(f"{manifest_path.name}: prompt file not found: {manifest.prompts}")
    actual = sha256_file(prompts_path)
    if actual != manifest.prompts_sha256:
        raise SplitError(
            f"{manifest_path.name}: {manifest.prompts} changed since the split was made "
            f"(manifest sha256 {manifest.prompts_sha256[:12]}…, file {actual[:12]}…)"
        )
    raw = read_jsonl(prompts_path, PromptRecord)
    role_of = manifest.role_of()
    problems: list[str] = []

    for prompt_id, count in Counter(r.id for r in raw).items():
        if count > 1:
            problems.append(f"prompt id {prompt_id!r} appears {count} times")

    unassigned = sorted({r.family for r in raw} - role_of.keys())
    if unassigned:
        problems.append(f"families with no role: {', '.join(unassigned)}")
    unknown = sorted(role_of.keys() - {r.family for r in raw})
    if unknown:
        problems.append(f"assigned families with no prompts: {', '.join(unknown)}")

    records: list[PromptRecord] = []
    first_by_content: dict[str, PromptRecord] = {}
    for record in raw:
        role = role_of.get(record.family)
        if role is None:
            continue
        if record.split is not None and record.split is not role:
            problems.append(
                f"prompt {record.id!r} says split {record.split.value} but family {record.family!r} is in {role.value}"
            )
        placed = record.model_copy(update={"split": role})
        other = first_by_content.setdefault(_content_key(placed), placed)
        if other.split is not role:
            problems.append(
                f"split overlap: prompts {other.id!r} ({other.split.value}) and {placed.id!r} ({role.value}) "
                "have identical messages"
            )
        records.append(placed)

    if problems:
        raise SplitError(f"{manifest_path.name}: invalid split:\n" + "\n".join(f"  {p}" for p in problems))
    return LoadedSplit(manifest=manifest, manifest_sha256=sha256_file(manifest_path), records=tuple(records))


class RoleSummary(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)

    families: tuple[str, ...]
    prompt_ids: tuple[str, ...]
    categories: dict[str, int]


class DataManifest(Record):
    """The ``data_manifest.json`` run artifact: which prompts, in which roles, from which files."""

    kind: Literal["data_manifest"] = "data_manifest"
    schema_version: Literal[1] = 1
    source: DatasetSource
    split_manifest_sha256: Sha256Hex
    prompts_sha256: Sha256Hex
    roles: dict[SplitRole, RoleSummary]

    @classmethod
    def from_split(cls, split: LoadedSplit) -> DataManifest:
        roles = {}
        for role in SplitRole:
            members = split.by_role(role)
            roles[role] = RoleSummary(
                families=split.manifest.assignments[role],
                prompt_ids=tuple(r.id for r in members),
                categories=dict(sorted(Counter(r.category for r in members).items())),
            )
        return cls(
            source=split.manifest.source,
            split_manifest_sha256=split.manifest_sha256,
            prompts_sha256=split.manifest.prompts_sha256,
            roles=roles,
        )
