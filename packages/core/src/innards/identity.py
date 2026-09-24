"""Identities that must never be invented: commit SHAs and content hashes."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Annotated

from pydantic import AfterValidator, BaseModel, ConfigDict, Field

_COMMIT_SHA = re.compile(r"[0-9a-f]{40}")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def _check_commit_sha(value: str) -> str:
    if not _COMMIT_SHA.fullmatch(value):
        raise ValueError(
            f"must be a full 40-character lowercase commit SHA, got {value!r}; "
            "resolve it from the Hugging Face API (branches and tags move)"
        )
    return value


def _check_sha256(value: str) -> str:
    if not _SHA256.fullmatch(value):
        raise ValueError(f"must be a 64-character lowercase hex SHA-256, got {value!r}")
    return value


CommitSha = Annotated[str, AfterValidator(_check_commit_sha)]
Sha256Hex = Annotated[str, AfterValidator(_check_sha256)]


class ModelIdentity(BaseModel):
    """A checkpoint pinned to an immutable revision. Tokenizer files live in the same repo at the same revision."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str = Field(min_length=1)
    revision: CommitSha


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
