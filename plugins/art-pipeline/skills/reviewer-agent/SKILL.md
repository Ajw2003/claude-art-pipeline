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

## 2. What the reviewer returns

- a verdict, `pass` or `fail`;
- a paragraph of at least 40 characters saying what it saw for each objective, naming concrete things;
- a list of mismatches.

## 3. Record it

The main session records the verdict with `--reviewer`, copying the reviewer's words unchanged:

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
