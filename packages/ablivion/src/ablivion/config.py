"""Typed schema for ``configs/ablivion.toml``.

Validation is total and happens before anything else runs: unknown keys are
errors (a typo must not silently fall back to a default), placeholders such as
``RESOLVE_AND_PIN`` fail, and referenced files must exist. Sections for later
stages (``[capture]``, ``[method]``, ``[search]``, ``[eval]``) are added with
the stage that implements them; until then they are rejected as unknown keys.

Relative paths resolve against the config file's directory, not the working
directory, so a config means the same thing from any shell.
"""

from __future__ import annotations

import tomllib
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from innards.errors import InputError
from innards.identity import CommitSha, ModelIdentity, sha256_file
from innards.records import format_validation_error


class ConfigError(InputError):
    """The config file is unreadable, malformed, or fails the schema."""


class _Section(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)


class ModelConfig(_Section):
    id: str = Field(min_length=1)
    revision: CommitSha
    representation: Literal["bf16", "fp16", "fp32"] = "bf16"

    @property
    def identity(self) -> ModelIdentity:
        return ModelIdentity(id=self.id, revision=self.revision)


class DataConfig(_Section):
    manifest: str  # split manifest, relative to the config file

    @field_validator("manifest")
    @classmethod
    def _relative(cls, value: str) -> str:
        if PurePosixPath(value).is_absolute() or Path(value).is_absolute():
            raise ValueError(
                f"must be relative to the config file, got absolute path {value!r} "
                "(bundles must not depend on a private absolute path)"
            )
        return value


class ArtifactsConfig(_Section):
    retain_responses: bool = True
    retain_full_activations: bool = False


class AblivionConfig(_Section):
    schema_version: Literal[1]
    model: ModelConfig
    data: DataConfig
    artifacts: ArtifactsConfig = ArtifactsConfig()


@dataclass(frozen=True)
class LoadedConfig:
    config: AblivionConfig
    path: Path
    sha256: str
    data_manifest_path: Path


def load_config(path: Path) -> LoadedConfig:
    """Parse, validate, and resolve a config. Raises ``ConfigError``; touches nothing else."""
    try:
        raw = path.read_bytes()
    except FileNotFoundError:
        raise ConfigError(f"config file not found: {path}") from None
    try:
        data = tomllib.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise ConfigError(f"{path.name}: invalid TOML: {exc}") from None
    try:
        config = AblivionConfig.model_validate(data)
    except ValidationError as exc:
        raise ConfigError(f"{path.name}: invalid config:\n{format_validation_error(exc)}") from None
    manifest_path = path.parent / config.data.manifest
    if not manifest_path.is_file():
        raise ConfigError(f"{path.name}: data.manifest: file not found: {config.data.manifest}")
    return LoadedConfig(config=config, path=path, sha256=sha256_file(path), data_manifest_path=manifest_path)
