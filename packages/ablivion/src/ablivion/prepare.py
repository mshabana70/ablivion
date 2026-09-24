"""``ablivion prepare``: the no-edit pipeline (Stage A0).

Order is the contract: validate config, then validate data, and only then touch
the output directory. An invalid input therefore leaves no bundle behind, and
later stages insert model loading after these steps, never before them.
"""

from __future__ import annotations

import traceback
from pathlib import Path

from ablivion.config import load_config
from innards.data import DataManifest, load_split
from innards.provenance import (
    ResolvedConfig,
    RunManifest,
    code_state,
    collect_hardware,
    dependency_versions,
    utc_now,
)
from innards.run_store import RunStore, new_run_id

COMMAND = "ablivion prepare"


def prepare(config_path: Path, output: Path) -> RunManifest:
    loaded = load_config(config_path)
    split = load_split(loaded.data_manifest_path)

    store = RunStore.create(
        output,
        RunManifest(
            run_id=new_run_id(),
            command=COMMAND,
            status="incomplete",
            created_at=utc_now(),
            code=code_state(Path(__file__)),
            base_model=loaded.config.model.identity,
            config_sha256=loaded.sha256,
            hardware=collect_hardware(),
            dependencies=dependency_versions(),
        ),
    )
    try:
        store.write_record(
            "config.resolved.json",
            ResolvedConfig(tool="ablivion", source_sha256=loaded.sha256, config=loaded.config.model_dump(mode="json")),
        )
        store.write_record("data_manifest.json", DataManifest.from_split(split))
    except BaseException as exc:
        store.fail("".join(traceback.format_exception_only(exc)).strip())
        raise
    return store.finalize()
