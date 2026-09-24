"""Stage A0 E2E gate (guide §7).

Builds wheels from the workspace, installs each package into its own fresh venv
outside the source tree (paths contain spaces), and drives the *installed* CLIs
in fresh processes. Results are checked independently of the implementation:
with json/tomllib/hashlib and the raw fixture files, never with innards helpers.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import subprocess
import tomllib
from pathlib import Path

import pytest
from helpers import MECHANICAL, REPO_ROOT

pytestmark = pytest.mark.e2e

UV = shutil.which("uv")
PINNED = "cdbee75f17c01a7cc42f958dc650907174af0554"
DISTS = {  # dist name -> (import name, console script or None)
    "innards": ("innards", None),
    "abl-eval": ("abl_eval", "abeval"),
    "ablivion": ("ablivion", "ablivion"),
    "abl-experiments": ("abl_experiments", "abx"),
}


def _clean_env() -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k not in {"VIRTUAL_ENV", "PYTHONPATH", "PYTHONHOME"}}
    env["PYTHONDONTWRITEBYTECODE"] = "1"
    return env


def run(args: list, cwd: Path, check: bool = False) -> subprocess.CompletedProcess[str]:
    result = subprocess.run([str(a) for a in args], cwd=cwd, env=_clean_env(), capture_output=True, text=True, timeout=600)
    if check and result.returncode != 0:
        raise AssertionError(f"{args} exited {result.returncode}\n{result.stdout}\n{result.stderr}")
    return result


def _first_party_deps(dist: str) -> list[str]:
    folder = {"innards": "core", "abl-eval": "eval", "ablivion": "ablivion", "abl-experiments": "experiments"}[dist]
    project = tomllib.loads((REPO_ROOT / "packages" / folder / "pyproject.toml").read_text())["project"]
    return [dep for dep in project["dependencies"] if dep in DISTS]


@pytest.fixture(scope="session")
def gate_root(tmp_path_factory) -> Path:
    assert UV, "uv is required for the E2E gate (a missing tool is a failure, not a skip)"
    root = tmp_path_factory.mktemp("stage a0 gate")
    assert " " in str(root) and not root.is_relative_to(REPO_ROOT)
    return root


@pytest.fixture(scope="session")
def wheels(gate_root) -> dict[str, Path]:
    out = gate_root / "wheel house"
    run([UV, "build", "--all-packages", "--wheel", "--out-dir", out], cwd=REPO_ROOT, check=True)
    found = {}
    for dist in DISTS:
        matches = list(out.glob(f"{dist.replace('-', '_')}-*.whl"))
        assert len(matches) == 1, f"expected one wheel for {dist}, found {matches}"
        found[dist] = matches[0]
    return found


def make_venv(gate_root: Path, name: str, wheel_paths: list[Path], locked_for: list[str]) -> Path:
    """Fresh venv with the given wheels; third-party deps pinned from uv.lock."""
    venv = gate_root / "venvs" / f"{name} env"
    run([UV, "venv", "--python", "3.12", venv], cwd=gate_root, check=True)
    reqs = gate_root / f"{name} requirements.txt"
    export = [UV, "export", "--frozen", "--no-dev", "--no-emit-workspace", "--no-hashes", "--output-file", reqs]
    for dist in locked_for:
        export += ["--package", dist]
    run(export, cwd=REPO_ROOT, check=True)
    run([UV, "pip", "install", "--python", venv / "bin" / "python", "-r", reqs, *wheel_paths], cwd=gate_root, check=True)
    return venv / "bin"


@pytest.fixture(scope="session")
def full_bin(gate_root, wheels) -> Path:
    return make_venv(gate_root, "all", list(wheels.values()), list(DISTS))


@pytest.fixture(scope="session")
def project(gate_root) -> Path:
    """Copy of the shipped config and fixture data under a path with spaces."""
    target = gate_root / "my project"
    shutil.copytree(REPO_ROOT / "configs", target / "configs")
    shutil.copytree(MECHANICAL, target / "data" / "fixtures" / "mechanical")
    return target


@pytest.fixture
def workdir(tmp_path) -> Path:
    """Unrelated cwd, so relative paths must resolve against the config file."""
    cwd = tmp_path / "some other dir"
    cwd.mkdir()
    return cwd


# --- each package installs outside the source tree -------------------------


@pytest.mark.parametrize("dist", list(DISTS))
def test_package_installs_alone_outside_source_tree(gate_root, wheels, dist):
    needed = [dist, *_first_party_deps(dist)]
    bin_dir = make_venv(gate_root, dist, [wheels[d] for d in needed], [dist])
    module, script = DISTS[dist]

    where = run([bin_dir / "python", "-c", f"import {module}; print({module}.__file__)"], cwd=gate_root, check=True)
    installed = Path(where.stdout.strip())
    assert installed.is_relative_to(bin_dir.parent) and not installed.is_relative_to(REPO_ROOT)

    others = sorted(set(DISTS) - set(needed))
    present = run([bin_dir / "python", "-c", f"import importlib.util as u; print([m for m in {[DISTS[o][0] for o in others]} if u.find_spec(m)])"], cwd=gate_root, check=True)
    assert present.stdout.strip() == "[]", "venv should contain only the package and its first-party deps"

    if script:
        help_ = run([bin_dir / script, "--help"], cwd=gate_root)
        assert help_.returncode == 0 and f"usage: {script}" in help_.stdout


# --- --help and doctor -------------------------------------------------------


def test_help_lists_commands(full_bin, workdir):
    ablivion = run([full_bin / "ablivion", "--help"], cwd=workdir, check=True).stdout
    abeval = run([full_bin / "abeval", "--help"], cwd=workdir, check=True).stdout
    assert "doctor" in ablivion and "prepare" in ablivion
    assert "report" in abeval
    run([full_bin / "abx", "--help"], cwd=workdir, check=True)


def test_doctor_passes_on_the_pinned_config(full_bin, project, workdir):
    result = run([full_bin / "ablivion", "doctor", "--config", project / "configs" / "ablivion.toml", "--json"], cwd=workdir)

    checks = {c["name"]: c for c in json.loads(result.stdout)}
    assert result.returncode == 0, result.stdout
    assert checks["python"]["status"] == "ok"
    assert all(checks[f"package:{d}"]["status"] == "ok" for d in DISTS)
    assert checks["config"]["status"] == "ok" and PINNED[:12] in checks["config"]["detail"]
    assert {c["name"] for c in checks.values()} >= {"device", "disk"}


# --- invalid inputs fail early and leave nothing behind ---------------------


def _variant(project: Path, name: str, old: str, new: str) -> Path:
    source = (project / "configs" / "ablivion.toml").read_text()
    assert old in source
    path = project / "configs" / name
    path.write_text(source.replace(old, new))
    return path


@pytest.mark.parametrize(
    ("old", "new", "expected"),
    [
        (f'"{PINNED}"', '"RESOLVE_AND_PIN"', "model.revision"),
        ("retain_responses", "retain_respones", "artifacts.retain_respones"),
    ],
    ids=["placeholder-revision", "misspelled-key"],
)
def test_invalid_config_fails_before_any_output(full_bin, project, workdir, old, new, expected):
    config = _variant(project, f"invalid {expected}.toml", old, new)
    output = workdir / "run out"

    result = run([full_bin / "ablivion", "prepare", "--config", config, "--output", output], cwd=workdir)

    assert result.returncode == 2, result.stdout + result.stderr
    assert expected in result.stderr and "Traceback" not in result.stderr
    assert not output.exists()

    doctor = run([full_bin / "ablivion", "doctor", "--config", config, "--json"], cwd=workdir)
    assert doctor.returncode == 1
    assert next(c for c in json.loads(doctor.stdout) if c["name"] == "config")["status"] == "fail"


def test_split_overlap_is_rejected(full_bin, project, workdir):
    leaky = project / "data" / "leaky split"
    shutil.copytree(MECHANICAL, leaky)
    manifest = json.loads((leaky / "splits.json").read_text())
    manifest["assignments"]["fit"].append("fam-08")  # fam-08 is also in final_test
    (leaky / "splits.json").write_text(json.dumps(manifest))
    config = _variant(project, "leaky.toml", "data/fixtures/mechanical/splits.json", "data/leaky split/splits.json")
    output = workdir / "run out"

    result = run([full_bin / "ablivion", "prepare", "--config", config, "--output", output], cwd=workdir)

    assert result.returncode == 2
    assert "split overlap: family 'fam-08' is assigned to both fit and final_test" in result.stderr
    assert not output.exists()


# --- a no-edit run saves its resolved config and renders a report ----------


def test_prepare_saves_resolved_config_and_report(full_bin, project, workdir, gate_root):
    config_path = project / "configs" / "ablivion.toml"
    run_dir = workdir / "runs dir" / "run one"

    run([full_bin / "ablivion", "prepare", "--config", config_path, "--output", run_dir], cwd=workdir, check=True)

    manifest = json.loads((run_dir / "manifest.json").read_text())
    assert manifest["kind"] == "run_manifest" and manifest["schema_version"] == 1
    assert manifest["status"] == "complete"
    assert manifest["base_model"] == {"id": "Qwen/Qwen3-4B-Instruct-2507", "revision": PINNED}
    assert manifest["config_sha256"] == hashlib.sha256(config_path.read_bytes()).hexdigest()
    assert manifest["code"]["commit"] is None  # installed from a wheel: unknown, not invented
    assert set(manifest["artifacts"]) == {"config.resolved.json", "data_manifest.json"}
    for name, digest in manifest["artifacts"].items():
        assert hashlib.sha256((run_dir / name).read_bytes()).hexdigest() == digest

    resolved = json.loads((run_dir / "config.resolved.json").read_text())
    assert resolved["config"] == tomllib.loads(config_path.read_text())

    rows = [json.loads(line) for line in (MECHANICAL / "prompts.jsonl").read_text(encoding="utf-8").splitlines()]
    assignments = json.loads((MECHANICAL / "splits.json").read_text())["assignments"]
    data = json.loads((run_dir / "data_manifest.json").read_text())
    for role, families in assignments.items():
        expected_ids = [r["id"] for r in rows if r["family"] in families]
        assert list(data["roles"][role]["prompt_ids"]) == expected_ids

    for artifact in run_dir.iterdir():  # bundles must not embed private absolute paths
        text = artifact.read_text(encoding="utf-8")
        assert str(gate_root) not in text and str(REPO_ROOT) not in text and str(workdir) not in text

    run([full_bin / "abeval", "report", "--run", run_dir], cwd=workdir, check=True)
    summary = (run_dir / "summary.md").read_text(encoding="utf-8")
    assert f"# Run {manifest['run_id']}" in summary
    assert "**Interventions:** none" in summary
    for role, families in assignments.items():
        count = sum(r["family"] in families for r in rows)
        assert f"| {role} | {len(families)} | {count} |" in summary
