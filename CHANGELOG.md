# Changelog

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
- `verify.py`: 72 checks.

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
