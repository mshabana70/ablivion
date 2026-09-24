# Labs

Phase C′ labs (guide §9): one directory per lab, `labs/<id>-<topic>/`, e.g. `labs/L1-logit-lens/`.

Import rule, enforced by `tools/check_labs_leaf.py` in CI:

- A lab may import `innards` and `abl_eval`, plus third-party libraries. It may not import `ablivion` or `abl_experiments`.
- Nothing outside `labs/` imports lab code. Any module or package name defined inside a lab directory is off limits everywhere else.

A lab's code moves into a package only when a second consumer needs it or an experiment depends on it; it is then rewritten there, not imported from here.
