# Next session: restructure art-pipeline (aj's direction, 2026-11-24)

aj asked that the next session picking up art-pipeline changes do these two things:

1. **Split it into separate skills.** The parts are not inherently linked. Today one `art-pipeline` skill
   holds the brief, spec and approval steps, model building, rigging, clip authoring, engine import and the
   Unity/Blender frame-sheet comparison. Each should be its own skill that can be used alone; the
   `angle-review-sheets` skill on branch `AjsAgent/angle-review-skill` is already one such piece.
   Done: the matched Unity/Blender frame-sheet comparison is now the `frame-sheet-compare` skill
   (0.10.0, aj asked for it 2026-11-24).
2. **Reviews by a separate agent.** Every review (model sheets, frame sheets, the compare pages) is done by
   a separate reviewer agent with fresh context, as the house-rules design loop will soon do, so the
   verdict is unbiased and judged against stated objectives, not by the agent that made the art.

Before starting, ask aj how to cut the skills; don't settle that alone.

Known state: `verify.py` fails 16 older checks on aj's Windows machine; they fail on an untouched
`AjsAgent/standalone` too, so they come from the environment.
