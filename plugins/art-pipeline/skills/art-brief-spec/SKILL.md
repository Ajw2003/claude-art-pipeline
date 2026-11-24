---
name: art-brief-spec
description: Write the brief and style bible, find real-world reference, and get a per-asset spec approved by a human before any art (model, animation, texture, sprite, sound, music) is made or changed. Use when starting art for a project, when asked to make or change any art asset and no approved spec covers it yet, when a build is refused because there is no approval or the build budget is spent, or when art docs have drifted from the data. Also covers running unattended, with nobody to approve.
---

# Brief, reference and approved spec

Project-agnostic: work only in the project that is open. Never fetch, clone or attach another
repository for examples.

**Rule one: reference and a human-approved spec come first.** No art asset of any kind (model,
animation, VFX, SFX, music, texture, sprite, UI art) is made or changed until a human has approved
a spec that names real-world reference for it. What looks human, or right, is found in reference,
never reasoned out: a session once spent its whole budget tuning one musket aim by argument, and
the drill manual that shows the pose was never opened. The plugin's PreToolUse hook enforces this:
writes to art paths and runs of build commands are refused until an approval covers them, one of
its reference images has been opened this session, and its build budget is not spent.

## Unattended runs (the session context says "UNATTENDED run", `ART_PIPELINE=unattended`)

Nobody is there, so every "ask the human", "the human approves" and "show the human" below becomes
"decide, do it, and write it down", and the run never stops to wait. Specifically:

- **Approvals and the budget are off.** Write the brief and the spec yourself (still with the best
  real-world reference you can get) and build straight away; there is no approval to wait for and no
  build budget. `approve.py` and `AskUserQuestion` are not used (the question tool is refused).
- **Reference you cannot fetch:** use what the project and `docs/art/reference/` already hold; if
  there is none, build from your best knowledge, say "no reference available (unattended)" in the spec
  and in the log, and carry on. Do not stop.
- **Decisions that are the user's** (the look, a clash with an approved plan, an over-budget fix):
  take the most conservative, easiest-to-reverse option and record the question and your choice in
  `docs/art/UNATTENDED.md` (one entry each, committed) for the morning.
- **Still mandatory:** rule two (look at it; see the model-build and rig-and-clips skills). Open every
  review sheet and frame sheet yourself, write what you saw, fix and look again. The Stop gate still
  blocks on a missing review.
- **Engine work you cannot run** is marked UNTESTED in the log; do not wait for a person to run it.

## Steps

1. **Read the project first.** Find its art docs, scale doc and any existing forge before writing
   one. Extend what is there; when nothing is, `references/stages-0-3-8.md` gives the shape (stage 0
   protect the work, 1 brief and style bible from `references/style-bible-template.md`, 2 reference,
   concept and spec, 3 asset data).
2. **Find reference and get the spec approved before making anything.** Save real-world reference
   (photographs, period plates, video frames, mocap, recordings) under `docs/art/reference/<id>/`,
   write `docs/art/specs/<id>.json` from `references/spec-template.md`, then:

   ```bash
   python "${CLAUDE_PLUGIN_ROOT}/scripts/approve.py" check <id>
   ```

   One spec may hold several items (four enemies of one Age, say), each with its own reference
   for every part it makes: model, animation, texture, sound. The check names each missing piece
   by item and part. When it passes it writes the review sheet `docs/art/specs/<id>.sheet.html`,
   which shows every reference large in the same layout every time. Send the human that sheet
   (as a file or a published page) and commit it; never summarise it in its place. Then send the
   AskUserQuestion it prints, as printed and without `answers`: only the human's own "Approve"
   click writes the approval
   (`docs/art/approvals/<id>.json`, which you commit). A human at a terminal can approve with the
   script's grant command instead. Approval files and `.art-pipeline.json` cannot be written by
   your tools.
   If the reference cannot be fetched (a blocked host), stop and ask the human for it; never
   substitute your own drawing or reasoning.
3. **Respect the build budget.** Each approved item allows `iterations` build or render runs
   (default 5), counted whatever tool makes its output files. Editing the code or data an asset is
   made from (`source_paths`) is not a build, and neither is a check; the hook says what each build
   was charged for. When they are spent the hook refuses more,
   and art any command makes outside an approval is put back straight away (a copy is kept in
   `.git/art-pipeline/quarantine/`). Do not look for another route: show the human
   the last render beside its reference and ask whether to accept it, add reference, or re-approve.
   A fix that needs more than the budget is a sign that the reference or the spec is wrong.
   **Run the project's check before every render you judge and before any movie or export.** Where
   the project lists `checks`, movies and exports (`gated_commands`) are refused until the item has
   a passing check newer than its last edit, and the stop is blocked while a changed item has none.
   A render from the side cannot show a prop inside the body; the check can. When you report to the
   human, quote the check's verdict, and never describe a render you have not checked as matching.
   Where the project sets `clip_review_views`, a movie or export also needs a clip review: render
   stills of every key pose from those views (always including top), put them beside the
   reference, open the sheet with Read, and record what you saw with `review.py clip`.
4. **Decisions that are the user's go to the user**, with a proposal page or a question: the look,
   anything that contradicts an approved plan (for example a death animation when the plan says the
   body vanishes). Defaults that are just craft, you choose and say so.
5. **Keep the docs in step with the art.** Docs that describe art (a scale doc's roster, a brief's
   budgets, a tool's status line) drift the moment a roster changes. Give the project a drift check
   (a script comparing docs with the data and code, see `references/stages-0-3-8.md`, stage 8) and
   name it in `.art-pipeline.json` at the repo root, so the gate runs it before every stop that
   changed a model or a doc:

   ```json
   {"doc_check": "python3 tools/check_art_docs.py", "doc_check_paths": ["docs/**", "**/*.json"]}
   ```

   The same file can set `model_globs`, `exclude` and `review_dir` (default `docs/art/reviews`).

## References

- `references/stages-0-3-8.md`: stages 0, 1, 2, 3 and 8 in full.
- `references/style-bible-template.md`: the brief a project fills in before anything is drawn.
- `references/spec-template.md`: the per-asset spec a human approves, and what counts as reference.
