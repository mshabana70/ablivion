# Learning log

This log records what I have understood about each concept and what shows it. It is kept separate from software evidence: a passing test is not evidence of understanding, and an explanation is not evidence that code is correct (AGENTS.md §13).

**Rules**

- Only record things I actually did: my own explanations, predictions, derivations, code I typed, and bugs I diagnosed. Approving a proposal, saying "looks good", or staying silent does not count (AGENTS.md §14).
- Use one of these levels: *introduced*, *completed with guidance*, *demonstrated independently*, *applied to a new case*.
- Revisit important concepts after other work has come in between.

## Entries

| Date | Concept | Evidence | Level | Remaining confusion | Review question |
|---|---|---|---|---|---|
| — | — | No entries yet. | — | — | — |

**24 September 2026 (audit of the guide and the reference tools):** nothing is recorded. I reviewed and approved the proposed changes to the guide. That is not evidence of understanding.

## Background I reported (AGENTS.md §7), not yet checked in this project

I say I have already implemented these in an earlier research codebase. Following AGENTS.md §7, each gets a quick prediction or derivation check when it first comes up, not an intuition-level lesson. A full lesson happens only if the check shows a gap. Each item stays unchecked until an entry above records the result.

| Concept | First comes up | Check question (answer when asked; answers are not recorded here) |
|---|---|---|
| Difference-of-means refusal direction | Stage A2 | Add the same vector `c` to every harmful and every harmless activation. What happens to the unnormalized direction, and why? |
| Removing and restoring a direction | Stage A3 | With `W′ = (I − u uᵀ) W`, what is `uᵀ W′ x` when `u` is a unit vector? What changes if `u` has norm 2? |
| Random-direction and off-layer controls | Stage B1 | In a 2560-dimensional residual stream, why does projecting out a random direction barely change behavior? What does that control fail to rule out? |
| Projection-AUC analysis | Stage B1 / RQ1 | Flip the sign of the probe direction. What happens to the AUC, and what does that mean for how results are reported? |
