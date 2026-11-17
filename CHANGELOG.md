# Changelog

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
