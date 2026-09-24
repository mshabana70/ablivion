# Project status

Last updated: 24 September 2026. Repository notes take precedence over any harness memory (AGENTS.md §14).

## Current stage and task

- **Stage:** A0 (guide §7). The gate passes locally. The first commit is `27e0656` ("initial commit for repo setup at stage A0"). **One item open:** CI has never run, because there is no remote yet.
- **Next task:** Stage A1, starting with a guided exploration of the chat template and token positions. You then write the oracle test and type `prepare_prompt` / position resolution, which is learning core.
- **Working agreement (you, 24 September 2026):** from A1 on, you develop and I tutor. I keep my implementation stretches short and rare: small, reviewable infrastructure pieces only. Units in the learning core, and any units you reclassify, are typed by you.

## Guide version

`docs/Ablivion_Implementation_Guide.md` **v2.2**. It folds in the OBLITERATUS and Heretic source audit.

- Approved improvement groups A1–A13, B1–B7, C1–C9 and D1–D6 are all in the guide. §17.5 maps each group to the section where it landed.
- Every audited technique has a disposition in §17: T1 folded in, T2 labs (L1–L14), T3 reading list, or shelved.

## Decisions (24 September 2026, settled before Stage A0)

| Decision | Choice |
|---|---|
| Core package | import `innards`, distribution `innards` (replaces the working name `abl_core`) |
| Tool packages | `abl_eval` / `abl-eval`, `ablivion` / `ablivion`, `abl_experiments` / `abl-experiments` |
| Commands | `ablivion`, `abeval`, `abx` |
| License | Apache-2.0 (`LICENSE`, text from apache.org). It is defensible only while the specification-not-source rule holds. **Both** references are AGPL-3.0: OBLITERATUS and Heretic (Heretic checked in its `LICENSE` at `3521f86`). |
| Workspace / lock | uv workspace, one `uv.lock`. First-party names are pinned to the workspace in `[tool.uv.sources]` (they're unregistered on PyPI, which rules out dependency confusion). |
| Python | 3.12 (uv-managed cpython 3.12.12) |

**Recorded in the guide:** norm preservation is three operators (`normpres_row_exact_v1`, `normpres_row_lowrank_v1`, `normpres_frob_capped_v1`); OBLITERATUS presets are configurations, not a dose axis; labs live in `labs/<id>-<topic>/` and nothing imports them.

**Where the guide text is now stale** (the guide wins on intent; these are naming or placement updates for you to approve):

- §4 and §9 still say `abl_core`. The chosen name is `innards`.
- §4's package tree lists "splits" under eval. The split *roles* and the manifest *validation* (mechanism) are in `innards.data`, because `PromptRecord` carries the split and three packages consume it. The *policy* of grouping near-duplicates and assigning families stays in eval, when it is built.
- `ablivion prepare` (the no-edit pipeline) is not among §4's proposed CLI surfaces. It's the A0 run that A1+ commands extend.

## Completed work

| Item | Where |
|---|---|
| Workspace (4 members, virtual root, `uv.lock`, 21 packages) | `pyproject.toml`, `packages/{core,eval,ablivion,experiments}/`, `uv.lock` |
| Versioned records: `kind` + `schema_version`, atomic writes | `packages/core/src/innards/records.py` |
| `PromptRecord`, `SplitRole` (`fit`/`validation`/`final_test`), `SplitManifest`, `load_split`, `DataManifest` | `packages/core/src/innards/data.py` |
| `ModelIdentity` (40-hex SHA only), SHA-256 helpers | `packages/core/src/innards/identity.py` |
| `RunManifest`, `ResolvedConfig`, hardware/dependency/git provenance | `packages/core/src/innards/provenance.py` |
| Minimal `RunStore`: incomplete until finalized; readers check artifact hashes | `packages/core/src/innards/run_store.py` |
| Typed config (`extra="forbid"`; placeholder, typo and absolute-path rejection) | `packages/ablivion/src/ablivion/config.py` |
| `ablivion doctor` (python, packages, torch stack, device, disk, config) and `ablivion prepare` | `packages/ablivion/src/ablivion/{doctor,prepare,cli}.py` |
| `abeval report` → `summary.md` (escaped, tool-agnostic) | `packages/eval/src/abl_eval/{report,cli}.py` |
| `abx` entry point (`--help`/`--version` only; RQ subcommands in Phase D) | `packages/experiments/src/abl_experiments/cli.py` |
| Mechanical fixture: 12 synthetic prompts, 10 families; harmful rows are labeled placeholders | `data/fixtures/mechanical/` |
| Pinned config | `configs/ablivion.toml` |
| Import contract: import-linter (2 contracts) plus the labs leaf checker | `pyproject.toml [tool.importlinter]`, `tools/check_labs_leaf.py`, `labs/README.md` |
| CI (written, never run) | `.github/workflows/ci.yml` |
| `.gitattributes`: `data/** -text`, so git never rewrites hashed fixture bytes | `.gitattributes` |

## Verified results and artifact paths

| Check | Result | What it establishes |
|---|---|---|
| `uv run --locked pytest -ra` | 37 passed (6 contract, 10 E2E, 8 config, 4 run-store, 9 split) | See the gate table below. Runs on CPU only, with no model. |
| `uv run --locked lint-imports --no-cache` | 2 kept, 0 broken (17 files) | `innards` imports no tool package, and `abl_eval` doesn't import `ablivion`, statically and transitively within first-party code |
| `python tools/check_labs_leaf.py` | kept, 0 violations | Nothing imports lab code, and no lab imports `ablivion`/`abl_experiments`. `labs/` has no labs yet, so the negative test in `tests/contract` is what proves the checker detects violations. |
| Smoke: `ablivion doctor`, `prepare`, `abeval report` from the workspace venv | exit 0; bundle and `summary.md` inspected | torch/transformers/safetensors report `warn` (needed from A1); the driver sees the RTX 4090 (591.86) |
| Throwaway `code_state` check in a temporary git repo | untracked → None; no commits → None; clean → SHA/False; edited → SHA/True | Every provenance commit branch behaves |

**A0 E2E gate (`tests/e2e/test_stage_a0.py`):** wheels are built with `uv build --all-packages`. Each package is installed into a fresh venv under pytest's `/tmp` directory, at a path with spaces, with third-party dependencies pinned via `uv export --frozen`.

| Gate item | Test | Result |
|---|---|---|
| Each package installs outside the source tree | `test_package_installs_alone_outside_source_tree` ×4 | pass. Each venv contains only that package and its first-party dependencies; the module file is in the venv, not the repo. |
| `--help` and `doctor` work | `test_help_lists_commands`, `test_doctor_passes_on_the_pinned_config` | pass |
| Invalid config fails early | `test_invalid_config_fails_before_any_output` ×2 (placeholder revision, misspelled key) | pass: exit 2, the field is named, no traceback, no output directory; `doctor` exits 1. *Limit:* A0 has no model loader, so "before model load" holds by ordering in `prepare.py`. A1 must re-check it once a loader exists. |
| Split overlap rejected | `test_split_overlap_is_rejected` (E2E); `test_splits.py` (identical text across roles, unassigned families, stale prompts file, duplicate IDs) | pass |
| Import contract passes | `tests/contract` (the repo passes, and injected violations are detected for all 3 forbidden edges) | pass |
| Resolved config saved | `test_prepare_saves_resolved_config_and_report` | pass: `config.resolved.json` equals the TOML parsed with `tomllib`; manifest hashes are recomputed with `hashlib`; no absolute paths in the bundle; `summary.md` counts match the raw fixture |
| Path with spaces | all E2E tests (venvs, config, data, cwd, run directory) | pass |

**Stage A0 checklist (§7):**

- [~] Packages install outside the source tree ✓. The dependency rule is enforced in CI: the workflow is written, but it has **not run** and needs a remote.
- [x] Baseline revisions and scope recorded. The model is below. The tokenizer lives in the same repo at the same revision. The only dataset so far is the mechanical fixture, pinned by SHA-256 (`54942076…92c1`); research datasets aren't chosen yet.
- [x] Invalid inputs and split leakage fail clearly.

**Model pin:**

- `Qwen/Qwen3-4B-Instruct-2507` @ `cdbee75f17c01a7cc42f958dc650907174af0554`. This is `main` as returned by `https://huggingface.co/api/models/Qwen/Qwen3-4B-Instruct-2507` on 2026-09-24, with lastModified 2025-09-17.
- `config.json` at that revision: `tie_word_embeddings: true`, `attention_bias: false`, hidden size 2560, 36 layers, 32 heads × 128, 8 KV heads, intermediate size 9728, vocabulary 151936.
- Files total 8,060,917,568 bytes. Recorded in `configs/ablivion.toml`.

**Reference clones** (read only; nothing executed). Re-cloned 24 September 2026 after `/tmp` was cleared:

| Tool | Path | Commit | License |
|---|---|---|---|
| OBLITERATUS | `/tmp/obl` | `b847511776a2afa7ed076f676184a4abfef2b162` (2026-09-20) | AGPL-3.0 |
| Heretic | `/tmp/heretic` | `3521f8648a0dccf6e12a92666862632235fac7e6` (2026-09-05) | AGPL-3.0 |

## Environment (observed 24 September 2026)

WSL2 Linux x86_64 (kernel 6.18), RTX 4090 with 24 GiB (driver 591.86), 32 CPUs. System Python 3.10.12; the workspace uses uv-managed 3.12.12. **Earlier notes said macOS arm64; that was wrong for this machine.** You installed torch `2.14.0+cu130` (CUDA 13.0; `doctor` shows cuda:0 with bf16), transformers 5.17.0 and safetensors 0.8.0. They're in the root `dev` dependency group from the default index, and the change is **not committed yet**. When the core first imports torch, the dependency has to move into `innards`' own dependencies.

## Unresolved issues

- **CI has never run.** It needs a remote. Until you push, the local `pytest`, `lint-imports` and labs-checker runs are the only evidence.
- **Is this the same checkpoint the paper used?** The guide (§12, R22) asks whether the refusal-direction paper used this revision. That isn't checked, because I don't know which revision the paper used.
- **D1–D6 are unconfirmed.** They need torch and transformers (commands below).
- **References still marked Verify in guide §16:** R6, R8, R12–R16, R27–R31, R33–R35, R37–R39, R41–R43.
- **One open read of the Heretic source:** how its KL scorer (`src/heretic/scorers/kl_divergence.py`, first token only) reduces its result.
- **One open read of the OBLITERATUS source:** whether adaptive defaults query the Hugging Face repo even in local runs (`telemetry.py:529`).
- **Wheels don't include `LICENSE`.** They carry only the SPDX `license = "Apache-2.0"` metadata, because PEP 639 forbids license files outside a member's directory. Copy `LICENSE` into each member before any release.
- **Optional contract:** the guide doesn't forbid `abl_eval` from importing `abl_experiments`, but experiments consume eval, so that import would create a cycle. Adding the contract is a one-line decision for you.

## Next concrete action

1. Commit the torch/transformers/safetensors change to `pyproject.toml` and `uv.lock`. When you push to a remote, record the CI result here.
2. **A1, unit 1 (yours):** a scratch exploration of the chat template at the pinned revision, where you predict first and then observe. Then write the oracle test for prompt preparation and position resolution (`t_inst`, `t_post-inst`), then type the implementation.
3. The rest of A1 as agreed in the unit plan. Confirm D3 during the tied-parameter unit, and D1, D2 and D6 during A3's projection oracle. Record the verdicts in `DISCREPANCIES.md`.
