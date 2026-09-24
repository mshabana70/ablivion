"""Split roles are assigned per family and must not leak (guide §5)."""

from __future__ import annotations

import pytest
from helpers import THREE_ROLES, prompt, write_split

from innards.data import SplitError, SplitRole, load_split
from innards.records import RecordError


def test_roles_follow_families_and_ids_survive(tmp_path, three_role_rows):
    split = load_split(write_split(tmp_path, three_role_rows, THREE_ROLES))

    assert [(r.id, r.family, r.split) for r in split.records] == [
        ("p1", "f1", SplitRole.FIT),
        ("p2", "f1", SplitRole.FIT),
        ("p3", "f2", SplitRole.VALIDATION),
        ("p4", "f3", SplitRole.FINAL_TEST),
    ]


def test_family_in_two_roles_is_rejected(tmp_path, three_role_rows):
    leaky = {"fit": ["f1", "f3"], "validation": ["f2"], "final_test": ["f3"]}

    with pytest.raises(RecordError, match="split overlap: family 'f3' is assigned to both fit and final_test"):
        load_split(write_split(tmp_path, three_role_rows, leaky))


def test_identical_text_under_different_families_in_two_roles_is_rejected(tmp_path, three_role_rows):
    rows = [*three_role_rows, prompt("p5", "f4", "  ALPHA ")]  # copy of p1, case/space changed, new family
    roles = {"fit": ["f1"], "validation": ["f2"], "final_test": ["f3", "f4"]}

    with pytest.raises(SplitError, match=r"prompts 'p1' \(fit\) and 'p5' \(final_test\) have identical messages"):
        load_split(write_split(tmp_path, rows, roles))


def test_unassigned_and_empty_families_are_both_reported(tmp_path, three_role_rows):
    rows = [*three_role_rows, prompt("p5", "orphan", "delta")]
    roles = {"fit": ["f1", "ghost"], "validation": ["f2"], "final_test": ["f3"]}

    with pytest.raises(SplitError) as info:
        load_split(write_split(tmp_path, rows, roles))
    assert "families with no role: orphan" in str(info.value)
    assert "assigned families with no prompts: ghost" in str(info.value)


def test_prompt_file_edited_after_split_is_rejected(tmp_path, three_role_rows):
    manifest = write_split(tmp_path, three_role_rows, THREE_ROLES)
    with (tmp_path / "prompts.jsonl").open("a", encoding="utf-8") as handle:
        handle.write("\n")

    with pytest.raises(SplitError, match="changed since the split was made"):
        load_split(manifest)


def test_record_split_contradicting_manifest_is_rejected(tmp_path, three_role_rows):
    three_role_rows[3] = prompt("p4", "f3", "gamma", split="fit")

    with pytest.raises(SplitError, match="prompt 'p4' says split fit but family 'f3' is in final_test"):
        load_split(write_split(tmp_path, three_role_rows, THREE_ROLES))


def test_duplicate_prompt_id_is_rejected(tmp_path, three_role_rows):
    three_role_rows[1] = prompt("p1", "f1", "alpha, reworded")

    with pytest.raises(SplitError, match="prompt id 'p1' appears 2 times"):
        load_split(write_split(tmp_path, three_role_rows, THREE_ROLES))


def test_missing_role_is_rejected(tmp_path, three_role_rows):
    with pytest.raises(RecordError, match="missing: final_test"):
        load_split(write_split(tmp_path, three_role_rows, {"fit": ["f1"], "validation": ["f2", "f3"]}))


def test_newer_schema_version_is_named_not_half_read(tmp_path, three_role_rows):
    manifest = write_split(tmp_path, three_role_rows, THREE_ROLES, schema_version=2)

    with pytest.raises(RecordError, match="unsupported schema_version 2 for 'split_manifest'"):
        load_split(manifest)
