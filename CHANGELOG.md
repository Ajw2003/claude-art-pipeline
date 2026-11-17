# Changelog

## 0.5.0 - 2026-11-17

- **Clip reviews.** New `clip_review_views` and `review.py clip`: when set, a movie or export of a
  clip also needs a passing review that names the clip, lists the required views (a top view shows
  a prop inside the body; a side view cannot), and points at a sheet opened this session and newer
  than the item's last source edit. The checks of 0.4.0 measure; this makes someone look.
- **Naming a build tool is not running it.** Build, check and gated patterns are matched only in
  the parts of a command that run something: quoted text with spaces (commit messages, `-c`
  programs) is dropped, and parts led by `git`, `cat`, `grep`, `sed`, `ls` and other read-only
  programs are left out. `git add Tools/ArtForge/attack.py` had been charged as a build.
- `verify.py`: 85 checks.

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
