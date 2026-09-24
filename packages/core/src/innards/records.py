"""Versioned artifact records.

Every JSON artifact is a *record*: a frozen pydantic model that pins a ``kind``
and an integer ``schema_version``. Readers check both before validating the
body, so a file written under another schema fails with a message naming the
version instead of being half-understood. Bump ``schema_version`` on any change
an old reader would misread; a reader accepts exactly the version it declares.
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, TypeVar

from pydantic import BaseModel, ConfigDict, ValidationError

from innards.errors import InputError


class RecordError(InputError):
    """A record is missing, malformed, of the wrong kind, or of an unsupported version."""


class Record(BaseModel):
    """Base for persisted artifacts. Subclasses declare ``kind`` and ``schema_version`` as ``Literal`` defaults."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    @classmethod
    def expected_kind(cls) -> str:
        return cls.model_fields["kind"].default

    @classmethod
    def expected_version(cls) -> int:
        return cls.model_fields["schema_version"].default


R = TypeVar("R", bound=Record)


def format_validation_error(exc: ValidationError) -> str:
    """One ``dotted.location: message`` line per error."""
    lines = []
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"]) or "<root>"
        lines.append(f"  {loc}: {err['msg']}")
    return "\n".join(lines)


def parse_record(data: Any, model: type[R], *, where: str) -> R:
    if not isinstance(data, dict):
        raise RecordError(f"{where}: expected a JSON object, found {type(data).__name__}")
    kind, version = data.get("kind"), data.get("schema_version")
    if kind != model.expected_kind():
        raise RecordError(f"{where}: expected kind {model.expected_kind()!r}, found {kind!r}")
    if version != model.expected_version():
        raise RecordError(
            f"{where}: unsupported schema_version {version!r} for {kind!r} "
            f"(this build reads version {model.expected_version()})"
        )
    try:
        return model.model_validate(data)
    except ValidationError as exc:
        raise RecordError(f"{where}: invalid {kind!r} record:\n{format_validation_error(exc)}") from None


def _read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except FileNotFoundError:
        raise RecordError(f"file not found: {path}") from None


def read_record(path: Path, model: type[R]) -> R:
    try:
        data = json.loads(_read_text(path))
    except json.JSONDecodeError as exc:
        raise RecordError(f"{path.name}: invalid JSON at line {exc.lineno}: {exc.msg}") from None
    return parse_record(data, model, where=path.name)


def read_jsonl(path: Path, model: type[R]) -> list[R]:
    """Read one record per line; blank lines are skipped, errors cite ``file:line``."""
    records = []
    for lineno, line in enumerate(_read_text(path).splitlines(), start=1):
        if not line.strip():
            continue
        where = f"{path.name}:{lineno}"
        try:
            data = json.loads(line)
        except json.JSONDecodeError as exc:
            raise RecordError(f"{where}: invalid JSON: {exc.msg}") from None
        records.append(parse_record(data, model, where=where))
    return records


def write_text_atomic(path: Path, text: str) -> None:
    """Write via a temp file in the same directory, fsync, then rename.

    A reader sees either the old file or the complete new one, never a torn write.
    """
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=f".{path.name}.", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp, path)
    except BaseException:
        Path(tmp).unlink(missing_ok=True)
        raise


def write_record(path: Path, record: Record) -> None:
    write_text_atomic(path, record.model_dump_json(indent=2) + "\n")
