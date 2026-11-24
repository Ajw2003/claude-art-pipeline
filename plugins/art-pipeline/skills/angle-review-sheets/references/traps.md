# Traps found building this (all fixed in the scripts; keep them in mind for new rigs)

1. **Turns that are not in the clip.** `alert_turn`-style clips only start a turn; the game's navigation agent
   turns the body 90 degrees while the clip plays. Drawn raw, the top-down view shows nothing changing.
   Apply the same yaw (config `agent_yaw_file`). A hover-turn on a creature with no yaw function still shows
   almost no turn; note it rather than hiding it.
2. **Fixed framing crops things.** A halberd, a body lying down after a knock-down, or a stretched attack goes
   out of a fixed camera. Pass 1 measures reach and height over every frame of the clip; pass 2 draws with
   `body_ortho = max(2 * max(high - mid, reach) * 1.08, 0.9 * height)`. Zoom therefore differs between clips
   but not between the frames of one clip.
3. **Giant or odd rigs.** The camera sits `max(8, 3 * height)` away so a huge model cannot swallow it. A bone
   keyed with scale ~48 (an FBX unit slip) explodes the pose; any local scale above 5 is drawn as 1 and the
   run prints a `NOTE ... scale above 5 drawn as 1` line. Real scale keys (eye flames) are kept.
4. **Rigs without legs or a `Hips` bone.** Size ratio falls back to all shared bones; the camera follows the
   first root bone.
5. **Image size limits.** One PNG per character broke the 65,500 px limit at readable tile sizes, and viewers
   shrink it to mush. Use banded JPEG strips plus videos.
6. **Reading order.** Frames go down a column (8 per column), then the next column to the right. A row-major
   sheet was reported as the wrong order. Frame numbers are drawn at tile/5 pixels, at least 22.
7. **`python -I` hides user-site packages**, including `bpy`. Do not use isolated mode for the renderer.
8. **Viewing the page.** A sandboxed viewer blocks downloads, `confirm()`, and sometimes `localStorage`.
   The page wraps storage in try/catch, uses a two-click Clear all, and copies results to the clipboard.
   An HTML file moved without `strips/` and `videos/` shows broken pictures; publish them together.
9. **Do not judge by numbers.** A clip can have the right frame count and a jammed shield. Open the strips.
