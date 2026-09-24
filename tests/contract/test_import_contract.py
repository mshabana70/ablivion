"""The dependency rule (guide §4) holds, and both checkers actually detect violations."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest
from helpers import REPO_ROOT

LINT_IMPORTS = Path(sys.executable).parent / "lint-imports"
LABS_CHECKER = REPO_ROOT / "tools" / "check_labs_leaf.py"
PACKAGES = ("innards", "abl_eval", "ablivion", "abl_experiments")


def _run(args, cwd, env=None):
    return subprocess.run(args, cwd=cwd, env=env, capture_output=True, text=True, timeout=120)


def test_package_contracts_hold_on_the_repo():
    result = _run([str(LINT_IMPORTS), "--no-cache"], cwd=REPO_ROOT)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "Contracts: 2 kept, 0 broken" in result.stdout


@pytest.mark.parametrize(
    ("importer", "imported", "contract"),
    [
        ("innards", "abl_eval", "innards (core) imports none of the other packages"),
        ("innards", "abl_experiments", "innards (core) imports none of the other packages"),
        ("abl_eval", "ablivion", "abl_eval does not import ablivion"),
    ],
)
def test_package_contract_catches_a_violation(tmp_path, importer, imported, contract):
    # The repo's own pyproject (same contracts, verbatim), applied to throwaway
    # packages that shadow the real ones via PYTHONPATH.
    shutil.copy(REPO_ROOT / "pyproject.toml", tmp_path / "pyproject.toml")
    for package in PACKAGES:
        (tmp_path / "src" / package).mkdir(parents=True)
        body = f"import {imported}\n" if package == importer else ""
        (tmp_path / "src" / package / "__init__.py").write_text(body)

    env = {**os.environ, "PYTHONPATH": str(tmp_path / "src")}
    result = _run([str(LINT_IMPORTS), "--no-cache"], cwd=tmp_path, env=env)

    assert result.returncode == 1, result.stdout + result.stderr
    assert f"{contract} BROKEN" in result.stdout


def test_labs_leaf_holds_on_the_repo():
    result = _run([sys.executable, str(LABS_CHECKER)], cwd=REPO_ROOT)
    assert result.returncode == 0, result.stdout


def test_labs_checker_catches_each_kind_of_violation(tmp_path):
    lab = tmp_path / "labs" / "L1-toy"
    lab.mkdir(parents=True)
    (lab / "lab_toy.py").write_text("import innards\nimport abl_eval\nfrom ablivion.cli import main\n")
    (lab / "lab_pkg").mkdir()
    pkg = tmp_path / "packages" / "core" / "src" / "innards"
    pkg.mkdir(parents=True)
    (pkg / "a.py").write_text("from lab_toy import helper\n")
    (pkg / "b.py").write_text("import importlib\nimportlib.import_module('labs.L1')\n")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("import lab_pkg.sub\n")

    result = _run([sys.executable, str(LABS_CHECKER), "--root", str(tmp_path)], cwd=tmp_path)

    assert result.returncode == 1
    reported = sorted(line.split(":")[0] for line in result.stdout.splitlines()[:-1])
    assert reported == [
        "labs/L1-toy/lab_toy.py",
        "packages/core/src/innards/a.py",
        "packages/core/src/innards/b.py",
        "tests/test_x.py",
    ]
