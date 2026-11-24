# Frame sheets reproduced from the plugin, against PlunderSpell (2026-11-17)

These were made by the skill's own scripts, not PlunderSpell's, to show that they reproduce the
review in `plugins/art-pipeline/skills/rig-and-clips/examples/anim-review/`. The Unity Editor was the
main PlunderSpell checkout's. That checkout already held an uncommitted re-export of
`Crusader_Signature.fbx`, so the Unity sheets show the clips after the fix. The first Blender run
used the committed (broken) file.

Unity, Edit mode, 27 entries (the Crusader's clip file on its own skeleton, his prefab playing those
clips, and every prefab under `Assets/_Project/Prefabs/Enemies`), about 25 seconds:

```bash
bash plugins/art-pipeline/skills/frame-sheet-compare/scripts/unity_frame_sheets.sh --project <PlunderSpell> \
     --out <out> --gap Hand.L Hand.R --dir Greatsword \
     Assets/Models/ArtBible/Animations/Crusader_Signature.fbx \
     "Assets/_Project/Prefabs/Enemies/HighMedieval/CrusaderBoss.prefab=Assets/Models/ArtBible/Animations/Crusader_Signature.fbx" \
     Assets/_Project/Prefabs/Enemies
```

Blender 5.2, once on the committed clip file (`CrusaderBoss`), once on the re-export
(`CrusaderBoss_reexport`), about 12 seconds each:

```bash
blender -b --factory-startup -P plugins/art-pipeline/skills/frame-sheet-compare/scripts/blender_frame_sheets.py -- \
     --model <PlunderSpell>/Assets/Models/ArtBible/Enemies/High/CrusaderBoss/CrusaderBoss.fbx \
     --clips <PlunderSpell>/Assets/Models/ArtBible/Animations/Crusader_Signature.fbx \
     --out <out> --name CrusaderBoss --gap Hand.L Hand.R --dir Greatsword
python plugins/art-pipeline/skills/frame-sheet-compare/scripts/frame_sheet_pages.py label <out>
python plugins/art-pipeline/skills/frame-sheet-compare/scripts/frame_sheet_pages.py pages <out>
python plugins/art-pipeline/skills/frame-sheet-compare/scripts/frame_sheet_pages.py probes <out>
```

What it shows:

- `CrusaderBoss_rest.json`: the committed clip file is on another rest pose, with 19 of 26 bones
  more than 5 degrees off and the hands at 79 and 85 degrees. `CrusaderBoss_reexport_rest.json`:
  none.
- `probes.md`: on the committed file the model's sword points (+0.29, -0.36, +0.89), forward and
  down, while the clip file's own skeleton points it (+0.55, +0.83, +0.10). This matches the review's
  `crusader_grip_*` measurements. After the re-export, the model, the prefab in Unity and the clip
  file all read 0.24 m and (+0.55, +0.83, +0.10). His walk and run still hold the sword one-handed
  (fists 0.9 to 1.1 m apart), which is the review's second Crusader finding.
- `overview_1.png` to `overview_5.png`: the same weapon faults as the review's overview pages.
  `--clips walk` picks the first clip named with "walk", here `walk_slow`.
- `CrusaderBoss_blender.png`, `CrusaderBoss_reexport_blender.png`, `Crusader_Signature.png`,
  `CrusaderBoss+Crusader_Signature.png`, `CrusaderBoss.png`: the Crusader's sheets in full.

Only the Crusader's sheets, two enemies' full sheets (`HouseholdKnight.png`, `Pavisier.png`) and the
overview pages are kept here, to keep the plugin's clone small. Every sheet's `raw/*.json` row data
is kept.
