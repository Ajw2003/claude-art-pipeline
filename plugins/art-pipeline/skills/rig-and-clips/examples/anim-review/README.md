# Worked example: the review that made frame sheets mandatory

PlunderSpell, 2026-11-17. Every enemy clip had passed its import and its checks. Rendering every
clip as frame sheets, in Unity and in Blender, found two faults nobody had seen. `report.md` is the
review as written then; it names PlunderSpell's own paths and scripts, which are now the frame-sheet-compare skill's
`scripts/`.

| File | What it shows |
|---|---|
| `overview_1.png` to `overview_3.png` | Every enemy: rest pose, idle, two walk and two run frames. A weapon on a hand bone follows the empty-handed swing of the shared clips: the Pavisier's pavise sweeps through his legs, the Household Knight's shield turns edge-on, pole weapons go level through the chest at the start of the run. |
| `CrusaderBoss.png` | The Crusader Boss in Unity, a row per clip, three-quarter view on the left and side view on the right. His greatsword is level and pointing forward in every attack instead of raised over his right shoulder. |
| `CrusaderBoss_blender.png` | The same clips in Blender on his model's armature. They agree with Unity, so the fault is in the files, not the engine. |
| `approved/*.png` | The sheets approved on 2026-11-14: the look the clips were meant to have. |

What caught the Crusader: his clip file was exported on another rest pose than his model. The
bone names match, so Unity imported it without a word, and the sword on his hand bone turned by
the difference, 65 degrees. `blender_frame_sheets.py` now compares the two rest poses on every run.
On that clip file it reports 19 of 26 bones more than 5 degrees off, with the hands at 79 and 85
degrees. On the file re-exported on the model's own rest pose it reports none, and the model then
grips exactly as the clip file does: fists 0.24 m apart, blade (+0.55, +0.83, +0.10). The
reproduction, run from this plugin, is in this repository's `docs/examples/anim-frame-sheets/`.
