---
name: reviewer-agent
description: Get every art review judged by a separate reviewer agent with fresh context, then record its verdict. Use after any model sheet, frame sheet, compare page or angle-review sheet is made, so the verdict is not given by the agent that made the art. Works in any project.
---

# Reviewer agent: someone else looks

The agent that made a piece of art has already decided it is good. A reviewer that starts with
no context judges only what the picture shows, against the objectives the human approved.

## 1. Spawn the reviewer

Use the Agent tool with `subagent_type` `art-pipeline:art-reviewer` (the plugin's agent, extended from
`house-rules:reviewer` and tuned for pictures; `agents/art-reviewer.md`), which starts with a fresh context.
Name its mode in the prompt: `sheet`, `frames`, `angles` or `motion`. Give it only:

- the path of the sheet or sheets to open (model review sheet, frame sheet, compare page, angle sheet);
- the objectives and reference paths from the approved spec (`docs/art/specs/<id>.json`);
- this question: "Does the picture meet each stated objective? List what matches and what does not."

Never give it the maker's own claims, notes or reasoning.

**Objectives are the spec's `check` strings, copied word for word, one `O<n>` each** (the spec template
allows 1 to 3 per part). Do not paraphrase them, merge them, or invent a broader one such as "matches the
concept". Two reviewers given "matches the concept's silhouette and hat" returned FAIL and PASS on the same
sheet; a check that names what to compare ("the hat tip curls to the viewer's right in the front view",
"the band shows the name", "petard size against the 1.80 m figure") gives the same verdict every time. If
an approved `check` is too loose to judge, say so to the human and ask for a sharper one; do not tighten
it yourself, because the human approved those words.

## 2. What the reviewer returns

- one `O<n>: PASS|FAIL` line per objective, with what the image shows and the image path;
- `Mismatches:` one line each, with what to change (a question of taste comes as lettered options with
  one suggestion, and is for the human, not for the maker to settle);
- `seen:` a paragraph of at least 40 characters naming concrete things it saw;
- a last line `VERDICT: pass` or `VERDICT: fail`. Anything it could not see is `NOT SEEN`, never a pass.

## 3. Record it

The main session records the verdict with `--reviewer`, copying the reviewer's words unchanged. Use
`--verdict pass` only when the reviewer's last line is `VERDICT: pass`; otherwise record `--verdict fail`
(a fail record still shows the work was looked at, and the gate stays closed until a new reviewer passes it):

```bash
python "${CLAUDE_PLUGIN_ROOT}/scripts/review.py" record --model <model path> --sheet <sheet.png> \
    --reviewer <reviewer name> --verdict pass --seen "<the reviewer's paragraph>"
python "${CLAUDE_PLUGIN_ROOT}/scripts/review.py" clip --item <name> --clips <clips> --views top side \
    --sheet <sheet.png> --reviewer <reviewer name> --verdict pass --seen "<the reviewer's paragraph>"
python "${CLAUDE_PLUGIN_ROOT}/scripts/review.py" frames --covers <clip files> --unity-sheet <png> \
    --blender-sheet <png> --rest-pose <json> --reviewer <reviewer name> --verdict pass --seen "<the reviewer's paragraph>"
```

## 4. When it fails

Fix the art, render again, and spawn a new reviewer. Never ask the same reviewer to reconsider.
The main session must not edit the reviewer's verdict or its `seen` text.

## Trust

`--reviewer` is a claim the Stop gate cannot prove. The record stores the reviewer's name and the
hash of each sheet, so the verdict is tied to one exact image, and `review.py status` shows who
reviewed it.
