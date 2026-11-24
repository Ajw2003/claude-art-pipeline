// Frame sheets in Unity, Edit mode only (never Play): for each entry, a row per clip sampled at evenly spaced moments,
// from a three-quarter front view and a side view, with the rest pose on the top row. Run it through
// unity_frame_sheets.sh, which writes the config this reads and calls it until it prints "done".
// Config: <project>/Temp/art-pipeline-frame-sheets.txt, one setting per line:
//   run <id>             a new id starts again from the first entry
//   out <absolute dir>   sheets go to <dir>/raw/<name>.png and <dir>/raw/<name>.json
//   steps <n>            moments per clip (default 5)
//   cell, fov, pitch, yaws, fit, background, ambient, light: the shared camera, copied from frame_camera.txt
//   gap <boneA> <boneB>  optional: distance between two bones at each clip's first frame
//   dir <bone>           optional: where a bone points at each clip's first frame (toward its first child)
//   entry <asset>[=<clips>]  a prefab, a model file or a folder of prefabs; <clips> is a .controller or a clip file.
//                        Without <clips>: the Animator's controller, else the clips inside <asset> itself.
// Three things here were each found the hard way, keep them:
// - Humanoid clips are sampled with AnimationMode.SampleAnimationClip; clip.SampleAnimation and a PlayableGraph both
//   left the pose frozen in a preview scene.
// - SkinnedMeshRenderer.forceMatrixRecalculationPerRender: without it a skinned mesh re-skins once per Editor frame,
//   so every render in one call showed the first pose.
// - URP previews a portrait target with the field of view across its width (a 240x320 cell drew the model at 3/4
//   size, while camera.projectionMatrix said otherwise). A portrait cell is rendered square and its middle cut out.
// - One entry per call, resumed through SessionState: the Unity CLI stops a call after 5 s of main-thread time.
var cfgPath = System.IO.Path.Combine(System.IO.Path.GetDirectoryName(UnityEngine.Application.dataPath), "Temp/art-pipeline-frame-sheets.txt");
if (!System.IO.File.Exists(cfgPath)) return "FAIL no config at " + cfgPath + " (run unity_frame_sheets.sh)";
string runId = "", outDir = null, gapA = null, gapB = null, dirBone = null;
int Steps = 5, W = 240, H = 320;
float fov = 30f, pitch = 8f, fit = 1.4f;
var yaws = new System.Collections.Generic.List<float>();
var background = new UnityEngine.Color(0.22f, 0.22f, 0.25f);
var ambient = new UnityEngine.Color(0.7f, 0.7f, 0.75f);
var lightSpecs = new System.Collections.Generic.List<float[]>();
float[] Nums(string v)
{
    var parts = v.Split(new[] { ' ', '	' }, System.StringSplitOptions.RemoveEmptyEntries);
    var n = new float[parts.Length];
    for (int i = 0; i < parts.Length; i++) n[i] = float.Parse(parts[i], System.Globalization.CultureInfo.InvariantCulture);
    return n;
}
var entries = new System.Collections.Generic.List<string[]>();
foreach (var raw in System.IO.File.ReadAllLines(cfgPath))
{
    var line = raw.Trim();
    if (line.Length == 0) continue;
    int sp = line.IndexOf(' ');
    string key = sp < 0 ? line : line.Substring(0, sp), val = sp < 0 ? "" : line.Substring(sp + 1).Trim();
    if (key == "run") runId = val;
    else if (key == "out") outDir = val;
    else if (key == "steps") Steps = int.Parse(val);
    else if (key == "cell") { var n = Nums(val); W = (int)n[0]; H = (int)n[1]; }
    else if (key == "fov") fov = Nums(val)[0];
    else if (key == "pitch") pitch = Nums(val)[0];
    else if (key == "fit") fit = Nums(val)[0];
    else if (key == "yaws") { yaws.Clear(); yaws.AddRange(Nums(val)); }
    else if (key == "background") { var n = Nums(val); background = new UnityEngine.Color(n[0], n[1], n[2]); }
    else if (key == "ambient") { var n = Nums(val); ambient = new UnityEngine.Color(n[0], n[1], n[2]); }
    else if (key == "light") lightSpecs.Add(Nums(val));
    else if (key == "gap") { var p = val.Split(' '); gapA = p[0]; gapB = p[1]; }
    else if (key == "dir") dirBone = val;
    else if (key == "entry")
    {
        var p = val.Split('=');
        string asset = p[0].Trim(), clipSrc = p.Length > 1 ? p[1].Trim() : null;
        if (UnityEditor.AssetDatabase.IsValidFolder(asset))
        {
            var found = new System.Collections.Generic.List<string>();
            foreach (var g in UnityEditor.AssetDatabase.FindAssets("t:Prefab", new[] { asset })) found.Add(UnityEditor.AssetDatabase.GUIDToAssetPath(g));
            found.Sort(System.StringComparer.Ordinal);
            foreach (var f in found) entries.Add(new[] { f, clipSrc });
        }
        else entries.Add(new[] { asset, clipSrc });
    }
    else return "FAIL unknown config line: " + line;
}
if (outDir == null) return "FAIL the config has no out line";
if (yaws.Count == 0 || lightSpecs.Count == 0) return "FAIL the config has no camera (yaws, light): run unity_frame_sheets.sh, which copies frame_camera.txt in";
var rawDir = System.IO.Path.Combine(outDir, "raw");
System.IO.Directory.CreateDirectory(rawDir);
if (UnityEditor.SessionState.GetString("ArtPipelineFrameSheetRun", "") != runId)
{
    UnityEditor.SessionState.SetString("ArtPipelineFrameSheetRun", runId);
    UnityEditor.SessionState.SetInt("ArtPipelineFrameSheetNext", 0);
}
int next = UnityEditor.SessionState.GetInt("ArtPipelineFrameSheetNext", 0);
if (next >= entries.Count) return "done";
var report = new System.Text.StringBuilder();
string Vec(UnityEngine.Vector3 v) => $"[{v.x:F3}, {v.y:F3}, {v.z:F3}]";
string Esc(string s) => s.Replace("\\", "/").Replace("\"", "'");

var entry = entries[next];
string assetPath = entry[0], clipsPath = entry[1];
var prefab = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.GameObject>(assetPath);
if (prefab == null) return "FAIL not a prefab or model: " + assetPath;
// Names must not collide: a prefab and its model file share a base name.
string NameOf(int i) => System.IO.Path.GetFileNameWithoutExtension(entries[i][0])
    + (entries[i][1] != null ? "+" + System.IO.Path.GetFileNameWithoutExtension(entries[i][1]) : "");
string name = NameOf(next);
for (int i = 0; i < next; i++)
    if (NameOf(i) == name) { name += "_" + System.IO.Path.GetExtension(assetPath).TrimStart('.'); break; }

var clips = new System.Collections.Generic.List<UnityEngine.AnimationClip>();
void AddFile(string p)
{
    foreach (var o in UnityEditor.AssetDatabase.LoadAllAssetsAtPath(p))
        if (o is UnityEngine.AnimationClip c && !c.name.StartsWith("__preview__") && !clips.Contains(c)) clips.Add(c);
}
var srcAnimator = prefab.GetComponentInChildren<UnityEngine.Animator>();
string clipsFrom;
if (clipsPath != null && clipsPath.EndsWith(".controller", System.StringComparison.OrdinalIgnoreCase))
{
    var ctrl = UnityEditor.AssetDatabase.LoadAssetAtPath<UnityEngine.RuntimeAnimatorController>(clipsPath);
    if (ctrl == null) return "FAIL not a controller: " + clipsPath;
    foreach (var c in ctrl.animationClips) if (!clips.Contains(c)) clips.Add(c);
    clipsFrom = clipsPath;
}
else if (clipsPath != null) { AddFile(clipsPath); clipsFrom = clipsPath; }
else if (srcAnimator != null && srcAnimator.runtimeAnimatorController != null)
{
    foreach (var c in srcAnimator.runtimeAnimatorController.animationClips) if (!clips.Contains(c)) clips.Add(c);
    clipsFrom = UnityEditor.AssetDatabase.GetAssetPath(srcAnimator.runtimeAnimatorController);
}
else { AddFile(assetPath); clipsFrom = assetPath; }

var preview = new UnityEditor.PreviewRenderUtility();
var go = (UnityEngine.GameObject)UnityEngine.Object.Instantiate(prefab);
preview.AddSingleGO(go);
go.transform.position = UnityEngine.Vector3.zero; go.transform.rotation = UnityEngine.Quaternion.identity;
var animator = go.GetComponentInChildren<UnityEngine.Animator>();
var sampleRoot = animator != null ? animator.gameObject : go;
var bounds = new UnityEngine.Bounds(go.transform.position, UnityEngine.Vector3.zero);
foreach (var r in go.GetComponentsInChildren<UnityEngine.Renderer>()) bounds.Encapsulate(r.bounds);
float height = UnityEngine.Mathf.Max(bounds.size.y, 1.5f);
var target = new UnityEngine.Vector3(0f, height * 0.5f, 0f);
preview.camera.fieldOfView = fov;
preview.camera.nearClipPlane = 0.05f; preview.camera.farClipPlane = 100f;
preview.camera.clearFlags = UnityEngine.CameraClearFlags.SolidColor;
preview.camera.backgroundColor = background;
for (int i = 0; i < preview.lights.Length; i++)
{
    var l = preview.lights[i];
    if (i >= lightSpecs.Count) { l.intensity = 0f; continue; }
    var spec = lightSpecs[i];
    l.transform.rotation = UnityEngine.Quaternion.Euler(spec[0], spec[1], 0f);
    l.color = new UnityEngine.Color(spec[2], spec[3], spec[4]);
    l.intensity = spec[5];
    l.shadows = UnityEngine.LightShadows.None;
}
preview.ambientColor = ambient;
float dist = height * 0.5f / UnityEngine.Mathf.Tan(fov * 0.5f * UnityEngine.Mathf.Deg2Rad) * fit;
var views = yaws.ToArray();
int RW = UnityEngine.Mathf.Max(W, H);  // render width: square when the cell is portrait (see the URP note at the top)

UnityEngine.Transform Bone(string n)
{
    if (n == null) return null;
    foreach (var t in go.GetComponentsInChildren<UnityEngine.Transform>()) if (t.name == n) return t;
    return null;
}
UnityEngine.Transform ta = Bone(gapA), tb = Bone(gapB), td = Bone(dirBone);
string Probe()
{
    var parts = new System.Collections.Generic.List<string>();
    if (ta != null && tb != null) parts.Add($"\"gap\": {(ta.position - tb.position).magnitude:F3}");
    if (td != null)
    {
        var d = td.childCount > 0 ? (td.GetChild(0).position - td.position).normalized : td.up;
        parts.Add($"\"dir\": {Vec(d)}");
    }
    return "{" + string.Join(", ", parts) + "}";
}

foreach (var smr in go.GetComponentsInChildren<UnityEngine.SkinnedMeshRenderer>()) smr.forceMatrixRecalculationPerRender = true;
UnityEditor.AnimationMode.StartAnimationMode();
int cols = Steps, rows = clips.Count + 1;
var sheet = new UnityEngine.Texture2D(cols * W * views.Length, rows * H, UnityEngine.TextureFormat.RGB24, false);
var fill = new UnityEngine.Color[sheet.width * sheet.height];
for (int i = 0; i < fill.Length; i++) fill[i] = preview.camera.backgroundColor;
sheet.SetPixels(fill);
var rowJson = new System.Collections.Generic.List<string>();
for (int row = 0; row < rows; row++)
{
    var clip = row == 0 ? null : clips[row - 1];
    string probe = "{}";
    for (int col = 0; col < cols; col++)
    {
        if (clip == null && col > 0) break;
        float t = clip == null ? 0f : clip.length * col / (clip.isLooping ? Steps : Steps - 1);
        // On a whole key, as blender_frame_sheets.py samples: between keys each engine interpolates its own way.
        if (clip != null) t = UnityEngine.Mathf.Floor(t * clip.frameRate + 0.5f) / clip.frameRate;  // halves up, as Blender
        if (clip == null) { if (animator != null) { animator.Rebind(); animator.enabled = false; } }
        else
        {
            if (animator != null) animator.enabled = true;
            UnityEditor.AnimationMode.BeginSampling();
            UnityEditor.AnimationMode.SampleAnimationClip(sampleRoot, clip, t);
            UnityEditor.AnimationMode.EndSampling();
        }
        go.transform.position = UnityEngine.Vector3.zero; go.transform.rotation = UnityEngine.Quaternion.identity;
        if (col == 0) probe = Probe();
        for (int v = 0; v < views.Length; v++)
        {
            var rot = UnityEngine.Quaternion.Euler(pitch, 180f + views[v], 0f);
            preview.camera.transform.position = target - rot * UnityEngine.Vector3.forward * dist;
            preview.camera.transform.rotation = rot;
            preview.BeginStaticPreview(new UnityEngine.Rect(0, 0, RW, H));
            preview.Render(true);
            var tex = preview.EndStaticPreview();
            sheet.SetPixels((v * cols + col) * W, (rows - 1 - row) * H, W, H, tex.GetPixels((RW - W) / 2, 0, W, H));
            UnityEngine.Object.DestroyImmediate(tex);
        }
    }
    string label = clip == null ? "rest pose" : clip.name;
    rowJson.Add($"{{\"label\": \"{Esc(label)}\", \"length\": {(clip == null ? 0f : clip.length):F3}, \"loop\": {(clip != null && clip.isLooping ? "true" : "false")}, \"probe\": {probe}}}");
    report.AppendLine($"{name} row {row}: {label}{(clip == null ? "" : " " + clip.length.ToString("F2") + "s")}");
}
UnityEditor.AnimationMode.StopAnimationMode();
sheet.Apply();
System.IO.File.WriteAllBytes(System.IO.Path.Combine(rawDir, name + ".png"), sheet.EncodeToPNG());
UnityEngine.Object.DestroyImmediate(sheet);
preview.Cleanup();
var json = $"{{\"name\": \"{Esc(name)}\", \"engine\": \"unity\", \"asset\": \"{Esc(assetPath)}\", \"clips_from\": \"{Esc(clipsFrom)}\", " +
           $"\"cell\": [{W}, {H}], \"steps\": {Steps}, \"views\": [\"three-quarter\", \"side\"], \"axes\": \"x right, y up, z forward\", " +
           $"\"probe_bones\": {{\"gap\": \"{gapA} {gapB}\", \"dir\": \"{dirBone}\"}}, " +
           $"\"frame\": {{\"height\": {height.ToString("R", System.Globalization.CultureInfo.InvariantCulture)}}}, \"rows\": [\n  {string.Join(",\n  ", rowJson)}]}}\n";
System.IO.File.WriteAllText(System.IO.Path.Combine(rawDir, name + ".json"), json);
UnityEditor.SessionState.SetInt("ArtPipelineFrameSheetNext", next + 1);
return report.Append(next + 1 >= entries.Count ? "done" : "more").ToString();
