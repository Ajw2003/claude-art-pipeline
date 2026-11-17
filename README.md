# art-pipeline

STATUS: v0.5. A Claude Code plugin, split out of
[Ajw2003/AjsClaudeCodeTools](https://github.com/Ajw2003/AjsClaudeCodeTools) (same shape as its
`house-rules` plugin: one `run.sh` shim, one stdlib Python file). Makes game art by code - models, animation, VFX, SFX, music, textures, sprites, UI art - and
makes nothing until a human has approved a spec with real-world reference, then never calls a model
done until someone has looked at it beside its concept. The skills (under
`plugins/art-pipeline/skills/`) carry the method; the hooks here carry the gate.

## Install

    claude plugin marketplace add Ajw2003/claude-art-pipeline
    claude plugin install art-pipeline@claude-art-pipeline

Update later with `claude plugin marketplace update claude-art-pipeline` then
`claude plugin update art-pipeline@claude-art-pipeline`. Restart Claude Code after either.

## Use

In any Claude Code session, type

    /art-pipeline:art-pipeline make a low-poly lantern prop for my game

or just ask for a model, character or prop - the skill also loads on its own when the request
fits. The renders it uses need Blender's Python module; the skill's
`scripts/setup_bpy.sh` installs it. The review gate (below) is always on once installed.

## The approval gate: nothing is made without reference and a human's approval

| Event | Handler | Does |
|---|---|---|
| `PreToolUse` (Write, Edit, MultiEdit, NotebookEdit, Bash, AskUserQuestion) | `pre` | Refuses a write to an art path, or a build command, unless an approved item covers it, one of that item's reference images was opened this session, and its build budget is not spent. Refuses any change to `docs/art/approvals/`, `.art-pipeline.json`, `.claude/settings.json`, `.claude/settings.local.json` or the session ledger (git may still commit them), `approve.py grant`, `plugin disable`, an approval question sent with its answers filled in, and one whose review sheet is missing or not exactly what the spec renders to. On an internal error it refuses calls that look like art and lets others through with a warning. |
| `PostToolUse` (Bash) | `after` | Right after every command: any art file it changed that no approved item covers, and any approval file no human grant wrote, is put back as it was at session start (a copy goes to `<git-dir>/art-pipeline/quarantine/`). Charges a build to an item whose files changed when the command was not a listed build tool. Art already changed when the session started, or changed outside the command's run, is left alone. About 0.05 s per command on a 9,600-file repo. |
| `PostToolUse` (AskUserQuestion) | `answered` | When the human answers "Approve" to a question carrying a spec's token, writes `docs/art/approvals/<id>.json` (hashes of the spec, its sheet and every reference) and records the grant in the session ledger. |

A spec is `docs/art/specs/<id>.json`
(`plugins/art-pipeline/skills/art-pipeline/references/spec-template.md`): one or more items, each
with parts (model, animation, texture, sound...) and real-world reference per part.
`approve.py check <id>` validates it, writes the review sheet `docs/art/specs/<id>.sheet.html`
(same layout every time, reference shown large) and prints the question to ask;
The builds spent under each grant are also written beside its approval,
`<approval_dir>/<id>.builds` (by the hooks only), and the Stop gate asks for that file to be
committed, so a new session or a fresh clone goes on from the same count.
`approve.py status` lists specs and approved items; `approve.py grant <id>` is the human's own
route from a real terminal. An approval counts only if this session's hook wrote it or it was
committed, unchanged, before the session started, and only while its spec and references are
unchanged. Each item allows `iterations` builds (default 5); then the hook refuses builds and
edits for it until the human approves again.

What counts as art: `production_paths` (default: models, audio, `*.anim`, `*.bvh`, shaders,
materials, layered image files, and anything under folders named art, audio, sound(s), sfx, music,
textures, sprites, icons, vfx, particles, shaders, materials, animations, models or fonts), minus
`production_exclude` (default `*.meta`, `docs/*`). Build commands: `producer_commands`, a list of
regular expressions (default: `blender`). The spec, reference, approval and review folders are
never art. The Stop gate also blocks on any changed art file no usable approval covers, and on any
approval file no human grant wrote; that block is never released by the loop guard.

Builds and checks. A build is a run of a `producer_commands` tool naming an item, or any command
that changes one of an item's output files. Changing an item's source files (`source_paths`,
default code and data: `*.py`, `*.cs`, `*.js`, `*.ts`, `*.json`, `*.md`, ...) still needs the
approval but is not a build. Every charge is reported after the command ("charged a build to X
for ..., 3 of 5 used"), and a spent budget's refusal lists what each build was charged for.

`checks` lists the project's verification commands, `{"command": regex, "pass": regex, "fail":
regex}`: a check is never a build. After one runs, its verdict (fail if the fail pattern is in its
output, pass if the pass pattern is, otherwise unknown) is kept for every item the command names,
with a fingerprint of the item's source files. `gated_commands` (movies, exports) are refused
unless every item they name has a passing check newer than its last source edit, and the Stop gate
blocks while an item changed this session has none (the loop guard releases it on the third block,
loudly). A gated command also needs the passing check to have named everything it names (a pass
of `check.py musketeer aim` does not unlock `render.py movie musketeer reload`). A check is
"pending" from the moment it starts: a failing one exits non-zero, Claude Code then runs no
PostToolUse hook, and the item simply stays unpassed. A check run in the background is not
captured and counts as unknown.

`clip_review_views` (e.g. `["top"]`) adds a review to the gate. A gated command then also needs,
for every item it names, a passing clip review written with
`review.py clip --item NAME --clips C... --views top side --sheet S.png --verdict pass --seen "..."`
that names every clip the command names, lists every required view, and points at a sheet that
was opened (Read) this session and is newer than the item's last source edit. A render from the
side cannot show a prop inside the body; a top view can. Records are
`<review_dir>/<item>.<clips>.clip-review.json`.

Every Bash hook acts on each repo the command can reach: the working directory, its `cd`, `pushd`
and `git -C` targets, and the repos of absolute paths it names. A Write or Edit is judged by the
repo of the file. The Stop gate checks the working directory's repo and every repo the session
acted in from outside (listed per session in `~/.claude/art-pipeline/`). Example:

    "checks": [{"command": "attack_check\\.py", "pass": "^PASS\\b", "fail": "^FAIL\\b"}],
    "gated_commands": ["attack\\.py\\s+(movie|export)"]

What is still open: a command started in the background that writes art after it returns is not
seen by `after`; the Stop gate catches the file. The approval channel relies on Claude Code
filling `answers` from the human's click, which has not been observed in a live session yet; if
the answer is missing, nothing is approved and the hook says so.

## The review gate

| Event | Handler | Does |
|---|---|---|
| `SessionStart` | `start` | In a git repo that has model files, records HEAD and an empty seen-list in `<git-dir>/art-pipeline/<session>.json` (never committed) and tells Claude the rule. Fails loud. |
| `PostToolUse` (Read) | `seen` | Appends any `.png/.jpg/.jpeg/.webp` Claude opens to the ledger. Never blocks. |
| `Stop` | `gate` | Models changed this session (committed since start, modified, added, untracked; `*.fbx *.glb *.gltf *.blend *.obj`) each need a review record. Blocks until they have one. Fails open, loudly. |

A record is `<review_dir>/*.review.json` (default `docs/art/reviews`):
`{"model","sheet","verdict":"pass|fail|waived","seen" (>= 40 chars),"date"}`. It counts only if
the sheet PNG exists, is at least as new as the model, and was opened this session. `fail` blocks;
`waived` passes but is announced. Write one with
`python scripts/review.py record --model M --sheet S.png --verdict pass --seen "..."`;
`review.py status` shows what would pass.

Override per project with `.art-pipeline.json` at the repo root:
`{"model_globs": [...], "exclude": [...], "review_dir": "...", "production_paths": [...],
"production_exclude": [...], "producer_commands": [...], "source_paths": [...], "checks": [...],
"gated_commands": [...], "clip_review_views": [...], "spec_dir": "...", "reference_dir": "...", "approval_dir": "..."}`. Only a human edits this file: the hooks refuse the agent's writes to it.

Doc-drift check: add `"doc_check": "<shell command>"` (run from the repo root, 60 s timeout) and
optionally `"doc_check_paths": [...]` (fnmatch on repo-relative paths, default
`["docs/**", "**/*.json"]`). At Stop it runs only when this session changed a model or a matching
path. Non-zero exit blocks with the last 20 lines of output; a timeout fails open with a
systemMessage; not configured is silent. It shares the loop guard (key `doc_check`) and shows in
`review.py status`.

Loop guard: the 3rd consecutive block for the same unmet set releases the stop with a loud
`UNREVIEWED models` systemMessage. Fail modes: start loud, seen never blocks, gate fails open
loudly.

## Off switch

`ART_PIPELINE=off` (set by the human in the environment Claude Code starts in) - the gates say
they are off and do not check. `ART_PIPELINE_PYTHON` picks the
interpreter, `ART_PIPELINE_DEBUG=1` traces `run.sh`.

Verify: `python plugins/art-pipeline/scripts/verify.py` (CI runs it on every push). Design
notes: `docs/offshoots-plan.md` in Ajw2003/AjsClaudeCodeTools.
