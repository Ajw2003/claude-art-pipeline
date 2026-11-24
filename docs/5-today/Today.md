# Today

## 2026-11-24

- Fetched the default branch (`AjsAgent/standalone`; this repo has no `main`). It now holds PR #7 and the first split-out skill, `frame-sheet-compare`.
- Merged `AjsAgent/angle-review-skill` into the working branch `AjsAgent/admiring-mccarthy-n6sboz`. The merge was clean: it only adds `skills/angle-review-sheets/`.
- Wrote the proposal page `docs/plans/split-art-pipeline-proposal.html` for the remaining split. It waits on aj's approval and three choices (A front door, B Stop-gate rule for reviewer verdicts, C where the Blender-to-Unity import work lives).
- aj approved the plan with A (keep the front door), B (a `--reviewer` flag) and C (a generalised importer pattern). Issues #8 to #14 were filed, with the three house labels created.
- A builder created `art-brief-spec` (#9), `model-build` (#10), `rig-and-clips` (#11) and `engine-import` (#12). `verify.py` is 109 of 109 in my own run. Six links broken by the moves were fixed (commit `7714249`).
- A second builder is adding the `reviewer-agent` skill and the `--reviewer` flag (#13).
- The `engine-import` C# template has not been compiled: no Unity, `dotnet`, `mcs` or `csc` is on this machine.
