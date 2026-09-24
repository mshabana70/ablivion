"""Config validation is total: placeholders, typos, and unresolved paths fail (guide §4)."""

from __future__ import annotations

import pytest

from ablivion.config import ConfigError, load_config

VALID = """
schema_version = 1
[model]
id = "Qwen/Qwen3-4B-Instruct-2507"
revision = "cdbee75f17c01a7cc42f958dc650907174af0554"
[data]
manifest = "data/splits.json"
"""


@pytest.fixture
def config_dir(tmp_path):
    (tmp_path / "data").mkdir()
    (tmp_path / "data" / "splits.json").write_text("{}")
    return tmp_path


def _write(directory, text):
    path = directory / "ablivion.toml"
    path.write_text(text)
    return path


def test_placeholder_revision_fails_naming_the_field(config_dir):
    path = _write(config_dir, VALID.replace("cdbee75f17c01a7cc42f958dc650907174af0554", "RESOLVE_AND_PIN"))

    with pytest.raises(ConfigError, match=r"model\.revision: .*'RESOLVE_AND_PIN'"):
        load_config(path)


def test_branch_name_is_not_a_revision(config_dir):
    with pytest.raises(ConfigError, match=r"model\.revision"):
        load_config(_write(config_dir, VALID.replace("cdbee75f17c01a7cc42f958dc650907174af0554", "main")))


def test_misspelled_key_fails_instead_of_defaulting(config_dir):
    path = _write(config_dir, VALID + "[artifacts]\nretain_respones = false\n")

    with pytest.raises(ConfigError, match=r"artifacts\.retain_respones: Extra inputs are not permitted"):
        load_config(path)


def test_section_of_a_later_stage_is_rejected(config_dir):
    with pytest.raises(ConfigError, match=r"capture: Extra inputs are not permitted"):
        load_config(_write(config_dir, VALID + '[capture]\nboundary = "x"\n'))


def test_data_path_resolves_against_config_dir_not_cwd(config_dir, tmp_path_factory, monkeypatch):
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))

    loaded = load_config(_write(config_dir, VALID))

    assert loaded.data_manifest_path == config_dir / "data" / "splits.json"


def test_missing_data_manifest_fails(config_dir):
    with pytest.raises(ConfigError, match="data.manifest: file not found: data/nope.json"):
        load_config(_write(config_dir, VALID.replace("data/splits.json", "data/nope.json")))


def test_absolute_data_path_is_rejected(config_dir):
    absolute = (config_dir / "data" / "splits.json").as_posix()

    with pytest.raises(ConfigError, match=r"data\.manifest: .*absolute path"):
        load_config(_write(config_dir, VALID.replace('"data/splits.json"', f'"{absolute}"')))


def test_malformed_toml_fails(config_dir):
    with pytest.raises(ConfigError, match="invalid TOML"):
        load_config(_write(config_dir, "schema_version = \n"))
