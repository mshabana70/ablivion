"""A partial or altered bundle must never read as complete (guide §4, RunStore)."""

from __future__ import annotations

from typing import Literal

import pytest

from innards.provenance import CodeState, Hardware, RunManifest
from innards.records import Record
from innards.run_store import RunStore, RunStoreError, open_completed_run


class Note(Record):
    kind: Literal["note"] = "note"
    schema_version: Literal[1] = 1
    text: str


def _manifest() -> RunManifest:
    return RunManifest(
        run_id="r1",
        command="test",
        status="incomplete",
        created_at="2026-09-24T00:00:00+00:00",
        code=CodeState(commit=None, dirty=None, note="test"),
        base_model=None,
        config_sha256=None,
        hardware=Hardware(platform="p", machine="m", python="3.12", cpu_count=1, accelerators=(), accelerator_probe="none"),
        dependencies={},
    )


def _record() -> Note:
    return Note(text="hello")


def test_unfinalized_run_cannot_be_opened(tmp_path):
    store = RunStore.create(tmp_path / "run", _manifest())
    store.write_record("note.json", _record())

    with pytest.raises(RunStoreError, match="run r1 is incomplete"):
        open_completed_run(tmp_path / "run")


def test_failed_run_cannot_be_opened(tmp_path):
    RunStore.create(tmp_path / "run", _manifest()).fail("boom")

    with pytest.raises(RunStoreError, match="run r1 is failed"):
        open_completed_run(tmp_path / "run")


def test_artifact_altered_after_completion_is_detected(tmp_path):
    store = RunStore.create(tmp_path / "run", _manifest())
    store.write_record("note.json", _record())
    store.finalize()
    (tmp_path / "run" / "note.json").write_text('{"kind": "note", "schema_version": 1, "text": "edited"}')

    with pytest.raises(RunStoreError, match="'note.json' changed after the run completed"):
        open_completed_run(tmp_path / "run")


def test_existing_nonempty_output_is_refused_and_left_untouched(tmp_path):
    root = tmp_path / "run"
    root.mkdir()
    (root / "keep.txt").write_text("mine")

    with pytest.raises(RunStoreError, match="not empty"):
        RunStore.create(root, _manifest())
    assert [p.name for p in root.iterdir()] == ["keep.txt"]
