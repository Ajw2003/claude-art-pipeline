# Today

## 2026-11-24

- Fetched the default branch (`AjsAgent/standalone`; this repo has no `main`). It now holds PR #7 and the first split-out skill, `frame-sheet-compare`.
- Merged `AjsAgent/angle-review-skill` into the working branch `AjsAgent/admiring-mccarthy-n6sboz`. The merge was clean: it only adds `skills/angle-review-sheets/`.
- Wrote the proposal page `docs/plans/split-art-pipeline-proposal.html` for the remaining split. It waits on aj's approval and three choices (A front door, B Stop-gate rule for reviewer verdicts, C where the Blender-to-Unity import work lives).
- aj approved the plan with A (keep the front door), B (a `--reviewer` flag) and C (a generalised importer pattern). Issues #8 to #14 were filed, with the three house labels created.
- A builder created `art-brief-spec` (#9), `model-build` (#10), `rig-and-clips` (#11) and `engine-import` (#12). `verify.py` is 109 of 109 in my own run. Six links broken by the moves were fixed (commit `7714249`).
- A second builder is adding the `reviewer-agent` skill and the `--reviewer` flag (#13).
- aj asked for the house-rules reviewer to be extended into a copy tuned for art and visuals. Added `plugins/art-pipeline/agents/art-reviewer.md` (modes sheet, frames, angles, motion) and pointed the `reviewer-agent` skill at it. It loads in a new session, so it has not been spawned yet.
- The `engine-import` C# template has not been compiled: no Unity, `dotnet`, `mcs` or `csc` is on this machine.
- Slimmed `art-pipeline` to a front door (#14) and deleted `references/stages.md` and `references/tooling-and-traps.md`. `verify.py` still passes 109 of 109. The `plugin.json` version bump to 0.11.0 is refused until code edits open.
- Tried to spawn `art-pipeline:art-reviewer`: it does not exist in this session, because only the `house-rules` plugin is installed here, so the agent is still unexercised.
- The `--reviewer` flag (#13 code) still waits for aj to type `Build plan approved: reviewer-agent`.
- aj approved the build (`Build plan approved: reviewer-agent`). Logged the decision in `docs/6-decisions/Decisions.md`. Installed the plugin from this repo's marketplace; the agent still needs a new session. A builder is adding the `--reviewer` flag and its checks.
