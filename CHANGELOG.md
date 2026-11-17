# Changelog

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
