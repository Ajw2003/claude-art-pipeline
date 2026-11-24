# Changelog

## Unreleased

- **Why edits to the agent did not show up.** An installed plugin runs from a cached copy made at install time, not from the repo, so a repo edit reaches the agent only after `claude plugin update art-pipeline@claude-art-pipeline` and a restart (found in issue #13; the cache held 0.10.0 until the update copied 0.11.0).

- **The `reviewer-agent` skill is sharper.** A reviewer's objectives are now the spec's `check` strings, copied word for word, so two reviewers judge the same thing; the skill also lists the reviewer's four-part reply and says a `VERDICT: fail` is recorded as `--verdict fail` (issue #13).

- **Finding: reviewers disagree on a loose objective.** The real `art-reviewer` graded "the render matches the concept's silhouette and hat" FAIL twice, and a stand-in reading the same file graded it PASS on the same sheet. Objectives given to a reviewer should be measurable (issue #13). The `reviewer-agent` skill now says the objectives are the spec's `check` strings copied word for word, lists the reviewer's four-part reply, and says to record `--verdict fail` when the reviewer's last line is `VERDICT: fail`.

- **The `art-reviewer` agent's output rule is stricter.** Its report must be exactly the four parts, with no opening sentence and no `Commands run`, `Files written` or `Could not do` sections (seen in its first trial, issue #13). A second and third trial still added process notes, but a check showed the running agent did not contain the new sentences (agent files are read when the session starts), so those trials tested the old wording. The verdict line is now stated to end the reply. A stand-in run (a general-purpose agent told to follow the file text from disk) obeyed the new rule: no extra sections. It is not the real agent, so a new session must still try that.

## 0.11.0 - 2026-11-24

- **`--reviewer NAME` on `review.py record`, `clip` and `frames` (issue #13).** The record stores the reviewer
  and the sha256 of each sheet; an empty name is refused. For a record with a reviewer the Stop gate no longer
  asks that the sheet was opened (Read) this session, but still needs a pass verdict, a record newer than the
  change, an existing sheet, and a sheet whose current sha256 equals the recorded one (a record with no
  recorded hash is refused too). A record without a reviewer keeps every check. `review.py status` prints
  `[reviewed by NAME]`. Four new `verify.py` checks: 113 of 113.

- **`art-pipeline` is a front door (issue #14).** `skills/art-pipeline/SKILL.md` shrank from 212 lines to
  about 60: rule one, rule two, the stage map and a pointer to every stage skill. `references/stages.md` and
  `references/tooling-and-traps.md` are deleted; every part of them already lives in `art-brief-spec`,
  `model-build`, `rig-and-clips` and `engine-import`. Plugin version raised to 0.11.0.

- **`art-reviewer` agent for art and visuals** (`agents/art-reviewer.md`, issue #13). A copy of the house-rules
  `reviewer`, kept read-only and findings-only, retuned for pictures: modes `sheet`, `frames`, `angles` and
  `motion`; opens every image beside its reference; one `O<n>: PASS|FAIL` line per objective in the shape the
  visual loop uses; `NOT SEEN` is never a pass. Loads in a new session. The `reviewer-agent` skill now spawns it.

- **art-pipeline is being split into single-purpose skills (issue #8).** Four new skills each work alone:
  `art-brief-spec` (stages 0 to 3 and 8), `model-build` (stage 4), `rig-and-clips` (stages 5 and 6) and
  `engine-import` (stage 7, a project-agnostic Unity importer pattern). `angle-review-sheets` is merged in beside
  `frame-sheet-compare`. Files moved with `git mv`; links fixed; `verify.py` stays at 109 of 109. `art-pipeline`
  still holds the moved text until it is slimmed to a front door. Plan: `docs/plans/split-art-pipeline-proposal.html`.

## 0.10.0 - 2026-11-24

- **`frame-sheet-compare` is its own skill.** The Unity/Blender frame-sheet renderers, `frame_camera.txt` and
  `frame_sheet_pages.py` moved from `skills/art-pipeline/scripts/` to `skills/frame-sheet-compare/scripts/`, with
  their own SKILL.md (steps, why the comparison is controlled, the renderer traps). The art-pipeline skill and the
  Stop gate's hint point there; the gate itself is unchanged. First step of splitting art-pipeline into one skill
  per operation (docs/NEXT-SESSION.md).

## 0.9.0 - 2026-11-24

From PlunderSpell's Generic-rig check, where the Unity and Blender frame sheets of the same clip file
could not be compared: Blender's side view showed the model's other side, its lens was 40 degrees
against Unity's 30, its camera sat lower, its rows were in another order and it sampled other moments.

- **One camera for both renderers**: `scripts/frame_camera.txt` holds the field of view, pitch, yaws,
  framing, background, ambient and lights; `unity_frame_sheets.sh` copies it into the Unity config and
  `blender_frame_sheets.py` reads it, turned into Blender's axes. Blender now renders with EEVEE, the
  Standard view transform, two shadowless suns and the flat ambient, so the two sheets look alike.
- **`blender_frame_sheets.py --match <Unity raw .json>`**: the Unity sheet's framing height, row order
  and loop flags. Both renderers sample on whole keys.
- **`frame_sheet_pages.py compare`**: Unity, Blender and the two silhouettes laid over each other for
  every row, each cell scored (share of each silhouette within 2 pixels of the other); one RESULT
  line per clip, exit 1 under `--min-overlap` (default 0.95). Matched sheets score 0.99 or more.
- Unity trap fixed: URP previews a portrait target with the field of view across its width, so every
  Unity sheet drew the model at three quarters of its size. Portrait cells now render square and crop.
- `verify.py`: 109 checks.

## 0.8.0 - 2026-11-22

- **Unattended mode can be switched on by typing `unattended on`** (the house-rules plugin saves it
  in its `house-rules-mode.json`; this plugin reads the same file, the repo's own beating the Claude
  config folder's). `unattended off` switches it back. `ART_PIPELINE=unattended` still works. The skill
  has an "Unattended runs" section: decide, build and log instead of asking or waiting.
- `verify.py`: 107 checks.

## 0.7.0 - 2026-11-22

- **Unattended mode** (`ART_PIPELINE=unattended`) for overnight runs: art needs no human-approved
  spec (writes and builds allowed, nothing undone), `AskUserQuestion` is refused so nothing waits for
  a person, and the Stop gate lists art made without approval instead of blocking. Approval, config,
  settings and ledger protection, forged-approval blocking and the model and frame-sheet reviews are
  unchanged. `review.py status` shows such files as `UNAPPROVED`.
- New `scripts/overnight.sh`: one launcher that sets this mode, switches house-rules' feature groups
  off (autosave and handoff stay on), shortens its prompt timeout to 30 s and starts Claude Code in
  bypass mode.
- `verify.py`: 103 checks.

## 0.6.0 - 2026-11-17

From PlunderSpell's enemy animation review, where frame sheets of every clip found what every
earlier check passed: weapons on 14 enemies following an empty-handed arm swing, and the Crusader
Boss's clip file exported on another rest pose, his greatsword 65 degrees off in game.

- **Frame sheets are a required step for animation and engine import.** New renderers in the
  skill's `scripts/`: `unity_frame_sheets.sh` + `.cs` (Edit mode, a row per clip, five moments,
  three-quarter and side views, rest pose on top, one entry per Editor call),
  `blender_frame_sheets.py` (the clip file's actions on the model's armature, same layout) and
  `frame_sheet_pages.py` (labels, overview pages, a bone-probe table: the gap between two bones and
  where a prop bone points, Unity beside Blender). The Stop gate blocks a changed clip file,
  controller or clip `.meta` (`anim_globs`) until `review.py frames` records both sheets, newer than
  the change and opened this session.
- **Rest-pose comparison.** `blender_frame_sheets.py` writes `<name>_rest.json`, every bone's rest
  orientation in the clip file against the model's; a bone more than 5 degrees off blocks the record
  and the stop unless `--rest-ok` explains it.
- **Worked example:** `skills/art-pipeline/examples/anim-review/`, the PlunderSpell sheets and report.
- `.art-pipeline.json` saved with a byte-order mark now loads (PlunderSpell's had one, and every hook
  failed on it).
- `verify.py`: 95 checks.

## 0.5.0 - 2026-11-17

- **Clip reviews.** New `clip_review_views` and `review.py clip`: when set, a movie or export of a
  clip also needs a passing review that names the clip, lists the required views (a top view shows
  a prop inside the body; a side view cannot), and points at a sheet opened this session and newer
  than the item's last source edit. The checks of 0.4.0 measure; this makes someone look.
- **Naming a build tool is not running it.** Build, check and gated patterns are matched only in
  the parts of a command that run something: quoted text with spaces (commit messages, `-c`
  programs) is dropped, and parts led by `git`, `cat`, `grep`, `sed`, `ls` and other read-only
  programs are left out. `git add Tools/ArtForge/attack.py` had been charged as a build.
- **The build count survives the session.** It was kept only in the session's ledger, so a new or
  restarted session (or a fresh clone) started every budget again. The hooks now also write it
  beside the approval, `<approval_dir>/<id>.builds` (closed to the agent like the approval), the
  budget uses the larger of the two, and the Stop gate asks for the file to be committed.
- `verify.py`: 88 checks.

## 0.4.0 - 2026-11-17

From a live run in PlunderSpell, where a Musketeer reload clip reached the owner's review with the
gun inside the body: the gate checked permission but never the result, and the budget charged
the wrong things without saying so.

- **Checks gate movies, exports and the stop.** New `checks` (verification commands with pass and
  fail patterns) and `gated_commands`. A check is never a build; its verdict is kept per item with
  a fingerprint of the item's source files. A gated command is refused unless every item it names
  has a passing check newer than its last edit; the Stop gate blocks while a changed item has none.
- **Editing source is not a build.** New `source_paths` (default code and data files): a Bash edit
  of an approved item's source no longer spends its budget. In that run every `sed` of the clip's
  code was charged, so most of the aim's 13 "builds" were edits, while the same edit made with the
  Edit tool cost nothing.
- **Every charge is reported**, after the command and in the refusal when a budget is spent, so
  the agent never has to guess what was counted. (It guessed "checks count" and then skipped them.)
- Found by testing 0.4.0 live in a session, all fixed:
  - **A command was judged by the wrong repo.** Hooks took the repo from the session's working
    directory when the call started, so `cd other-repo && render movie` ran under the first repo's
    rules (none) and was let through; a Write to an art file in another repo was never gated, and
    the Stop gate only looked at the working directory. Now `pre` and `after` act on every repo a
    command can reach (its `cd`/`pushd`/`git -C` targets and the repos of the absolute paths it
    names), a written file is judged by its own repo, and the Stop gate also checks every repo the
    session worked in from outside (a per-user list in `~/.claude/art-pipeline/`, protected).
  - **A failing check left no record.** Claude Code runs no PostToolUse hook for a command that exits
    non-zero, so a failing check never reached `after`, and an older pass could stand. A check now
    marks its items "pending" before it runs; only a passing output turns that into a pass.
  - **A pass on one clip unlocked another.** Verdicts are per item, and an item can have many clips.
    A movie or export now needs a passing check that named everything it names (paths, flags,
    numbers and pipes ignored).
- `verify.py`: 79 checks.

## 0.3.1 - 2026-11-17

- A build is charged once per tool call even when the plugin is installed twice (user and project
  scope, as in cloud sessions that install it from a setup script), so the last build of a budget
  is no longer refused by the second copy. `verify.py`: 63 checks.

## 0.3.0 - 2026-11-17

- A spec can cover several items (four enemies of one Age, say), each with its own real-world
  reference for every part it makes: model, animation, texture, sound. Budgets and unlocking are
  per item.
- `approve.py check` writes a review sheet, `docs/art/specs/<id>.sheet.html`: the same layout every
  time, reference shown large, at most three checks per part, fixed text limits. The approval
  question is short and points to it; the hooks refuse a question whose sheet is missing or edited.
- New `PostToolUse` (Bash) hook: art a command makes outside an approval, and approval files no
  human wrote, are put back right after the command (a copy is kept). Builds by tools missing from
  `producer_commands` still spend the budget.
- The plugin's settings files and the session ledger are protected; `plugin disable` is refused;
  a forged approval blocks the stop every time.
- `verify.py` grows from 53 to 62 checks.

## 0.2.0 - 2026-11-17

- Approval gate: no art asset of any kind (model, animation, VFX, SFX, music, texture, sprite, UI
  art) can be written or built until a human approves a spec with real-world reference. New
  `PreToolUse` and `PostToolUse` (AskUserQuestion) hooks, `scripts/approve.py`, and
  `references/spec-template.md`.
- Each approval carries a build budget; when it is spent, builds and edits stop until the human
  approves again.
- The skill puts reference before concept, and animation takes its motion from mocap or reference
  frames, never from reasoning.
- `verify.py` grows from 29 to 53 checks.

## 0.1.2 - 2026-11-16

- The skill is project-agnostic. The repo stands as its own marketplace.

## 0.1.0 - 2026-10-08

- Stop-hook review gate, render and review-sheet scripts, the skill and its references.
