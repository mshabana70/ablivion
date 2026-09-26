# Learning log

This log records what I have understood about each concept and what shows it. It is kept separate from software evidence: a passing test is not evidence of understanding, and an explanation is not evidence that code is correct (AGENTS.md §13).

**Rules**

- Only record things I actually did: my own explanations, predictions, derivations, code I typed, and bugs I diagnosed. Approving a proposal, saying "looks good", or staying silent does not count (AGENTS.md §14).
- Use one of these levels: *introduced*, *completed with guidance*, *demonstrated independently*, *applied to a new case*.
- Revisit important concepts after other work has come in between.

## Entries

| Date | Concept | Evidence | Level | Remaining confusion | Review question |
|---|---|---|---|---|---|
| 2026-09-24 | Chat-template rendering and token positions (`t_inst`, `t_post-inst`) | Wrote `scratch/template_probe.py` from a spec, without code help. Predictions: (a) no default system prompt, which is correct; a BOS token, which is incorrect because Qwen adds none; the newline tokens were left out. (b) Expected `t_inst` and `t_post-inst` to be tokens the template inserts, a misconception now corrected: they are positions. (c) Answered "not always contiguous" because of subword splitting. That conflates splitting with boundary merges, and the answer wasn't tested: all three of the cases tried were in fact contiguous. | Script: completed with guidance. Concept: introduced. | (c) is still open: a challenge is pending on which template boundary allows a merge. | In a two-turn conversation, where is `t_post-inst`, and why is refusal read there rather than at `t_inst`? |
| 2026-09-24 | Token merges at template boundaries | Challenge (c). Found two contents that break contiguity by starting with `\n`: `'\n\nIs…'` gives `ĊĊĊ`, and `'\n \n this…'` gives `ĊĊ ĠĊ` where standalone tokenization gives `ĊĠĊ`. The explanation was their own and correct: the tokenizer groups the template's newline with leading content characters, so the content's first token can't be split out faithfully. Needed three hints; the third said to put `\n` at the front. Also fixed an off-by-one in `range(len - (n+1))` after review, and used a raw string after the `\f` escape was pointed out. | Completed with guidance | Not yet noticed: the second case also re-splits content tokens past the edge (`ĊĠĊ` becomes `ĊĊ` + `ĠĊ`). Not yet reasoned through: which position the ambiguity affects. | Why is `t_inst` immune to this merge while "first content token" is not? |
| 2026-09-24 | Position resolution design | Part 1 predicted that the left-edge merge affects both `t_inst` and `t_post-inst`. That is incorrect: the right edge touches a special token and `t_post-inst` is the final token, so neither moves. The reasoning given only holds for left-anchored counting. Correctly flagged that anchoring on the first `<|im_end|>` breaks under special-token injection. Part 2 chose character offsets (B), giving a sound reason. The failure mode offered was speed, which is not a real risk. The validation proposed, `start + len(content)`, is circular. | Introduced | Confuses the definition of a position with the method that resolves it. Doesn't yet see why `str.find` is unsafe for locating the content span. | Content `"user"`: where does `str.find` place it, and what does that do to `t_inst`? |

**24 September 2026 (audit of the guide and the reference tools):** nothing is recorded. I reviewed and approved the proposed changes to the guide. That is not evidence of understanding.

## Background I reported (AGENTS.md §7), not yet checked in this project

I say I have already implemented these in an earlier research codebase. Following AGENTS.md §7, each gets a quick prediction or derivation check when it first comes up, not an intuition-level lesson. A full lesson happens only if the check shows a gap. Each item stays unchecked until an entry above records the result.

| Concept | First comes up | Check question (answer when asked; answers are not recorded here) |
|---|---|---|
| Difference-of-means refusal direction | Stage A2 | Add the same vector `c` to every harmful and every harmless activation. What happens to the unnormalized direction, and why? |
| Removing and restoring a direction | Stage A3 | With `W′ = (I − u uᵀ) W`, what is `uᵀ W′ x` when `u` is a unit vector? What changes if `u` has norm 2? |
| Random-direction and off-layer controls | Stage B1 | In a 2560-dimensional residual stream, why does projecting out a random direction barely change behavior? What does that control fail to rule out? |
| Projection-AUC analysis | Stage B1 / RQ1 | Flip the sign of the probe direction. What happens to the AUC, and what does that mean for how results are reported? |
