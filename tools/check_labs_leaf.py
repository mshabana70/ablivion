"""Enforce that labs/ is a leaf (guide §9, Phase C′). Stdlib only.

1. No Python file outside labs/ imports ``labs`` or any top-level module or
   package name defined by a lab directory (the names that become importable
   when a lab directory is put on ``sys.path``).
2. No lab imports ``ablivion`` or ``abl_experiments``; labs may use innards and abl_eval.

Static imports and ``importlib.import_module`` / ``__import__`` calls with a
literal name are checked. Exit status 1 lists every violation.

Usage: python tools/check_labs_leaf.py [--root DIR]
"""

from __future__ import annotations

import argparse
import ast
import sys
from collections.abc import Iterator
from pathlib import Path

SKIP_DIRS = {".venv", "venv", "dist", "build", "__pycache__", "node_modules"}
LAB_FORBIDDEN = {"ablivion", "abl_experiments"}


def python_files(root: Path) -> Iterator[Path]:
    for path in sorted(root.rglob("*.py")):
        rel = path.relative_to(root).parts
        if not any(part in SKIP_DIRS or part.startswith(".") for part in rel[:-1]):
            yield path


def lab_names(labs: Path) -> set[str]:
    names = {"labs"}
    if not labs.is_dir():
        return names
    for lab in labs.iterdir():
        if not lab.is_dir() or lab.name in SKIP_DIRS or lab.name.startswith("."):
            continue
        if lab.name.isidentifier():
            names.add(lab.name)
        for child in lab.iterdir():
            if child.is_dir() and child.name.isidentifier() and child.name not in SKIP_DIRS:
                names.add(child.name)
            elif child.suffix == ".py" and child.stem.isidentifier():
                names.add(child.stem)
    return names


def imported_modules(tree: ast.AST) -> Iterator[tuple[int, str]]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield node.lineno, alias.name
        elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
            yield node.lineno, node.module
        elif (
            isinstance(node, ast.Call)
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and isinstance(node.args[0].value, str)
            and (
                (isinstance(node.func, ast.Attribute) and node.func.attr == "import_module")
                or (isinstance(node.func, ast.Name) and node.func.id in {"import_module", "__import__"})
            )
        ):
            yield node.lineno, node.args[0].value


def violations(root: Path) -> list[str]:
    labs = root / "labs"
    forbidden_outside = lab_names(labs)
    found = []
    for path in python_files(root):
        rel = path.relative_to(root)
        inside_labs = rel.parts[0] == "labs"
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(rel))
        except SyntaxError as exc:
            found.append(f"{rel.as_posix()}:{exc.lineno}: cannot parse: {exc.msg}")
            continue
        for lineno, module in imported_modules(tree):
            top = module.split(".")[0]
            if inside_labs and top in LAB_FORBIDDEN:
                found.append(f"{rel.as_posix()}:{lineno}: lab imports {module!r}; labs may use innards and abl_eval only")
            elif not inside_labs and top in forbidden_outside:
                found.append(f"{rel.as_posix()}:{lineno}: imports lab code {module!r}; nothing may import labs/")
    return found


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=Path(__file__).resolve().parents[1])
    args = parser.parse_args(argv)
    found = violations(args.root)
    for line in found:
        print(line)
    print(f"labs leaf contract: {'BROKEN' if found else 'kept'} ({len(found)} violation(s))")
    return 1 if found else 0


if __name__ == "__main__":
    sys.exit(main())
