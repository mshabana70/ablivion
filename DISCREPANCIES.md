# Discrepancies

Divergences between our implementations and the reference tools, and suspected reference issues. Each entry records what differed, at which level, the evidence, and the verdict: our bug, reference bug, intentional deviation, or unresolved (AGENTS.md §6; guide Section 9).

A suspected reference bug is handled like a vulnerability report: confirm it, then draft an upstream issue before any public mention.

**Pinned references:** OBLITERATUS `b847511776a2afa7ed076f676184a4abfef2b162` (guide R21); Heretic `3521f8648a0dccf6e12a92666862632235fac7e6` (guide R20).

**Status of D1–D6:** found by reading the source during the 24 September 2026 audit. Nothing has been run yet, so every entry is unresolved.

---

## D1 — Projection side chosen by matrix shape; square residual writers get input-side projection

- **Tool:** OBLITERATUS
- **Level:** weights (source reading, before any parity run)
- **What:** the projection kernel decides which side of a matrix to project by comparing the matrix's shape with the direction's length, and it tests the input side first. For a residual writer whose input and output dimensions both equal `d_model`, such as a 4096×4096 attention output projection, it removes `d` from the input side (`W(I − ddᵀ)`) instead of the output side (`(I − ddᵀ)W`).
- **Evidence:** `obliteratus/analysis/numerical_contracts.py:210` (branch order). The contract test `tests/test_projection_math_contracts.py:49` builds its oracle with the same branch order, so it cannot catch this.
- **Affects Qwen3-4B:** no. Its attention output projection is 2560×4096.
- **Confirm by:** run `basic` on a tiny model with a square `o_proj`, then check whether `dᵀW′` or `W′d` is zero for that matrix.
- **Verdict:** unresolved.

## D2 — Reader projection ignores the RMSNorm gain

- **Tool:** OBLITERATUS
- **Level:** weights / mathematical specification
- **What:** residual readers act on `γ ⊙ x̂`, where `x̂` is the normalized residual and `γ` the RMSNorm gain. Since `W(γ ⊙ x̂) = W diag(γ) x̂`, removing the reader's dependence on `x̂`'s component along a direction `v` requires `W diag(γ) v = 0`. Enforcing `W d = 0` therefore removes dependence along `diag(γ)⁻¹ d`, not along `d`, unless `γ` is constant. [INFERENCE]
- **Evidence:** reader projection at `obliteratus/abliterate.py:4583-4591`; the derivation above.
- **Affects Qwen3-4B:** yes.
- **Confirm by:** a toy calculation with a non-constant `γ`; then, on Qwen3-4B, the cosine between `d` and `γ⁻¹ ⊙ d` for each layer's input norm.
- **Verdict:** unresolved; possibly an intentional deviation.

## D3 — Silent edit of a tied output head and input embedding

- **Tool:** OBLITERATUS
- **Level:** weights
- **What:**
  - The output head is projected with the last selected layer's subspace at full strength, or reflected in the inverting presets, regardless of the preset's strength setting.
  - On a checkpoint with tied embeddings, this also edits the input embedding matrix.
  - Nothing checks for the tie or records it.
- **Evidence:** `obliteratus/abliterate.py:4796-4841`. The only tie-related text in the file is a comment in the norm-capture helper (line 5547).
- **Affects Qwen3-4B:** yes (`tie_word_embeddings: true`).
- **Confirm by:** run any preset on Qwen3-4B or a tied tiny model, then compare `embed_tokens.weight` before and after.
- **Verdict:** unresolved.

## D4 — Capture position depends on free GPU memory through silent truncation

- **Tool:** OBLITERATUS
- **Level:** tokens / activations
- **What:** unless `max_seq_length` is set, the tokenizer's maximum length defaults to 256 and drops to 128 or 64 when free GPU memory is low. Truncation happens silently, so the "last token" whose activation is captured depends on hardware state.
- **Evidence:** `obliteratus/abliterate.py:2329-2348` (length adaptation), `2365-2367` (`truncation=True`).
- **Affects Qwen3-4B:** yes.
- **Mitigation for parity runs:** always pass `max_seq_length` explicitly (guide Section 9).
- **Confirm by:** capture the same long prompt with different amounts of free memory, then compare token counts and activations.
- **Verdict:** unresolved.

## D5 — Citation errors

- **Tool:** OBLITERATUS
- **Level:** documentation
- **What:**
  - Bias projection is described as a novel contribution, but Arditi et al. [R1] already orthogonalize output biases as part of weight orthogonalization.
  - The "Ouroboros effect" is attributed to McGrath et al. (2023), whose paper calls it the Hydra effect [R5].
- **Evidence:** docstring at `obliteratus/abliterate.py:5776`; module docstring of `obliteratus/analysis/anti_ouroboros.py`.
- **Affects Qwen3-4B:** not applicable.
- **Verdict:** reference citation error. It does not affect behavior. An optional upstream note falls under the reporting rule above.

## D6 — Norm restoration capped at 1.10

- **Tool:** OBLITERATUS
- **Level:** weights
- **What:** the rescaling ratio used for Frobenius norm restoration is capped at 1.10. When an edit removes more than about 17.4% of a matrix's squared norm (`1 − 1/1.10²`), the norm is only partly restored, and nothing reports this.
- **Evidence:** `obliteratus/analysis/numerical_contracts.py:229-235`; `obliteratus/runtime_contracts.py:151-174`.
- **Affects Qwen3-4B:** yes, whenever an edit removes that much energy.
- **Confirm by:** a toy matrix with a large component along `d`; compare the post-edit norm with the original.
- **Verdict:** unresolved; possibly intentional, as a guard against amplification.
