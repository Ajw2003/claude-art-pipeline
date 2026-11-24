# Enemy animation review, 2026-11-17

What was checked: every enemy prefab that has an Animator (16 of them: 14 on the shared body controller,
the Crusader Boss and its Varsity variant). Each was posed in the Unity Editor at five moments of every clip
its controller plays, from a three-quarter front view and from its right side. Nothing was changed in the game.
Not checked: how the clips blend into each other, the Lantern Warden (it has its own controller), co-op.

## The pictures

| File | What it shows |
|---|---|
| `overview_1.png` to `overview_3.png` | Every enemy: rest pose, idle, two walk frames, two run frames. Start here. |
| `<Enemy>.png` | One enemy in full: a row per clip, five moments each; left half three-quarter view, right half side view. Top row is the rest pose. |
| `CrusaderBoss_blender.png` | The Crusader's six clips rendered in Blender on his model's skeleton, rows in this order: death, chop, idle, sweep, thrust, roar. |
| `approved/crusader_*.png` | The Crusader review sheets approved on 2026-11-14 (branch `agent/amazing-edison-fo85hr`), the target look. |

Remake them all: `bash Tools/Unity/eval.sh --file Tools/Unity/eval/enemy_anim_sheets.cs` repeated until it prints
`done` (one enemy per call; the Editor stops a call after 5 s), then `python Tools/Unity/eval/enemy_anim_overview.py`.

## Finding 1 - the Crusader Boss: his clips were exported on a different skeleton pose from his model

His clip file `Crusader_Signature.fbx` was exported with a rest pose in which the hands and sword already sit in
the raised-blade stance. His model `CrusaderBoss.fbx` rests with the sword hanging down. The bone names match, so
Unity accepts the clips, but the sword hangs off the right hand bone at the model's angle while the hand turns as
the clip file's hand did. Measured at the first frame of every Crusader clip:

| Where | Gap between his fists | Blade direction (x right, y up, z forward) |
|---|---|---|
| Approved look, and the clips on their own skeleton (Unity and Blender agree) | 0.24 m, both fists on the grip | (+0.55, +0.83, +0.10): up, over his right shoulder |
| The boss prefab in the game | 0.39 m, left fist off the grip | (+0.74, -0.06, +0.67): level, pointing forward and to his right |

Measured by `Tools/Unity/eval/crusader_grip_unity.cs` and `crusader_grip_blender.py`.

That is why every Crusader clip looks wrong: the blade is 65 degrees off for the whole clip (angle between the two directions above), and the left
hand never reaches it. The attacks still move the body as approved (compare rows 5 to 7 of `CrusaderBoss.png`
with `approved/crusader_greatsword_chop.png`); only the grip is broken.

Second Crusader problem: walking and running use the shared walk and run with nothing holding the sword, so it
swings one-handed by his leg (rows 2 to 4 of `CrusaderBoss.png`). The approved walk (`approved/crusader_walk.png`)
is the same shared walk with a "crusader_carry" override that holds both arms and the sword in his rest pose.
That override was never brought into Unity.

Third: his feet will slide. The approved walk sheet records that, at 3.00 m tall, the shared walk covers 3.24 m per
second on him; the Unity blend tree plays it at 2.0 m per second (`EnemyAnimatorForge.cs`, the speeds beside the
clip names), so his feet travel 1.6 times slower than his body moves. Not checked in Play mode.

**Suggested fixes, in order:**

1. Re-export `Crusader_Signature.fbx` on the model's own rest pose: a Blender script that loads both files,
   copies every bone's world pose from the clip skeleton onto the model skeleton frame by frame, and exports the
   model skeleton with the six actions. The existing `crusader_grip_unity.cs` is the check: the prefab must then
   read 0.24 m and (+0.55, +0.83, +0.10). This is new work in Blender, about one script; the forge that made the
   clips is not on this branch.
2. Add an arms layer to `CrusaderBoss.controller`: an Avatar Mask of both arms, both hands and the sword bone,
   playing `greatsword_idle` over the Move blend tree, switched off during the three attack states. That is the
   approved "crusader_carry" design.
3. Scale his blend-tree speeds by his size, 1.62 times (walk_slow 1.78, walk 3.24, run 6.80 m/s), or set
   `Animator.speed` from it; then check the feet in Play mode.

## Finding 2 - everyone else: the shared clips were made for an empty-handed person

The shared idle, walk and run were made on a reference human with nothing in his hands. On our enemies every
weapon and shield is a bone fixed to a hand, so it goes wherever the hand goes, and an empty hand swings, turns
and hangs loose. The legs and body look right on all 14; it is only what they hold. What each one shows:

| Enemy | What goes wrong | How bad |
|---|---|---|
| Pavisier | The pavise turns flat and points backward in idle; it sweeps through his legs walking and running | Bad |
| Castle Crossbowman | The crossbow points backward from the hip in idle and walk; it swings across him running | Bad |
| Household Knight | The shield turns edge-on beside him in idle; running, the sword swings up toward his own helm | Bad |
| Palace Levy | The figure-of-eight shield turns edge-on in idle and flies out level at head height running | Bad |
| Sallet Halberdier, Palace Guard, Gothic Man-at-Arms, Musketeer | The pole weapon or musket is upright in idle and walk, but goes level through the chest at the start of the run | Medium |
| Dendra Champion | Same as the pole weapons, smaller | Medium |
| Wall Slinger, Keeper of the Flame | The sling and the censer chain stick out stiffly when running | Small |
| Handgunner, Petardier, Cuirassier | Nothing held in a swinging hand; look right | None |

**Suggested fix:** an arms layer in `EnemyBody.controller`, the same idea as the Crusader's carry.

1. The forge (`EnemyAnimatorForge`) makes, for each enemy, a one-frame "carry" clip of that enemy's own rest pose
   arms, read from the model with Unity's `HumanPoseHandler`. Each model's rest pose is the art-bible pose, which
   already holds the weapon the way it was designed, so no new art is needed.
2. The shared controller gets a second layer masked to the weapon arm (or both arms, for the crossbow, pole
   weapons, musket and pavise), playing a placeholder carry state. Each enemy gets an `AnimatorOverrideController`
   that swaps in its own carry clip.
3. The layer runs at about 0.85 weight, so a little of the walk's arm swing shows through; the free arm still
   swings fully. The weight is a field on the forge, to tune by eye.
4. Re-render with `enemy_anim_sheets.cs` and compare against these pictures.

Cost: one forge change, one mask asset, one override controller per enemy (made by the forge). No new clips.
Not covered by this fix: attacks (the per-enemy `*_Attacks.fbx` files are still not wired) and the polearm clips.

## Smaller things noticed

- The Crusader's Humanoid bone map sets his Head to the `Helm` bone and leaves Chest empty, unlike the Household
  Knight (Head to `Head`, Chest to `Chest`). The shared clips' chest movement therefore lands on his spine, and
  his helm moves as if it were his head. Small on its own; worth fixing in the same pass as the re-export.
- Every enemy uses the shared speeds (walk at 2.0 m/s) whatever its height, so the taller ones (Household
  Knight 1.95 m) slide a little too. Only the Crusader's figure was measured.
