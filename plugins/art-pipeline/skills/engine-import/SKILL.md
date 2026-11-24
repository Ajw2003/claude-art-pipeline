---
name: engine-import
description: Bring finished models and clips into Unity with every import setting owned by code (an AssetPostprocessor), a generated animator, and a check of the result in the engine. Use when adding or changing models or animation in a Unity project, when rig type, loop flags, animation events, materials or texture settings are being set by hand in the Inspector, or when a re-export lost its import settings. If this machine cannot run Unity, the work is reported as untested with the exact steps for the user.
---

# Engine import (Unity)

Needs reviewed models and clips (the model-build and rig-and-clips skills). Everything is set in
code, nothing in the Inspector:

- an import postprocessor: rig type and bone map by path, loop flags per clip, materials built from
  the baked maps, data textures imported linear;
- an editor menu that generates the animator (blend trees by speed, layers with masks) and installs
  the model on the prefab;
- a runtime driver that only sets animator parameters, reading what the body is doing; on a
  networked game, anything the movement does not show (crouch, cast) is synced by the owner;
- tests: classification, loop flags against the manifest, driver parameters from inputs.

**Gate:** frame sheets of the prefab with the controller the game uses, rendered again after any
import or controller change (the frame-sheet-compare skill, `../frame-sheet-compare/SKILL.md`), and
a capture in the engine. If this machine cannot run the engine, the work is labelled UNTESTED and
the user gets the exact menu item and what they should see.

## The importer pattern

One `AssetPostprocessor` per model folder. The seven rules:

1. **One postprocessor owns the import settings of a model folder.** A postprocessor, not edits to
   `.meta` files or a one-off pass: it runs on every import, so a re-export of the source file
   cannot quietly undo a setting.
2. **Rig type per model kind**, chosen in `OnPreprocessModel` from the asset path: Humanoid with an
   explicit bone map (engine bone name to your bone name, the same map the forge uses, checked by a
   test) for people, Generic with a named root bone for creatures, no animation for props. A
   Humanoid avatar needs the rest pose recorded: capture it in `OnPostprocessModel` and reimport
   once (a second pass finds it and returns, so no loop). A clip file can copy the avatar of its
   model so both share one rest pose.
3. **Clip loop flags come from the clip manifest** the exporter wrote, read in
   `OnPreprocessAnimation` over `defaultClipAnimations`. There is no second list to drift; a test
   compares the loop flags the importer applied with the manifest. Clip names come from the take
   name; root lock flags are set here too.
4. **Animation events by normalised time** (0 to 1 of the clip, so they survive a change of clip
   length): a table of clip name to (method name, time, string parameter), as a constant, because the
   importer must not read data files for it. A test checks the table against the manifest.
5. **Materials from the baked maps** in `OnPreprocessMaterialDescription`, the only hook that sees
   materials embedded in a model file: switch to the URP Lit shader, bind base colour, the
   metallic-gloss map (metallic in RGB, smoothness in alpha) and emission (scaled back up, as 8-bit
   maps clamp at 1.0), warn when a baked map is missing, and declare the map as a dependency so the
   model reimports when it changes. Data textures (metallic, roughness, masks) are imported with
   `sRGBTexture = false`; the check is by file-name suffix.
6. **`isReadable` and `bakeAxisConversion` only where runtime code needs them** (a mesh read for
   colliders or navigation, a model whose root rotation must come out upright). Default
   `isReadable` to false; say in a comment why each exception exists.
7. **`GetVersion()` and `GetPostprocessOrder()`.** Imported results live in the cache, not in git:
   bump `GetVersion()` whenever a rule changes so everything reimports. Order the postprocessor after
   the render pipeline's own material step (it fills defaults that would overwrite yours).

### Template

Replace the `<...>` placeholders; keep the classification pure so a test can call it without an import.

```csharp
using System; using System.Collections.Generic; using System.IO; using System.Linq;
using UnityEditor; using UnityEngine;

public class <Name>ModelImporter : AssetPostprocessor
{
    const string ModelRoot = "<ModelRoot>/";            // e.g. the folder this importer owns
    const string ManifestPath = ModelRoot + "<clip manifest>.json";
    public enum Kind { Humanoid, Generic, Prop }
    [Serializable] class Manifest { public FileEntry[] fbx; }
    [Serializable] class FileEntry { public string file; public ClipEntry[] clips; }
    [Serializable] class ClipEntry { public string clip; public bool loop; }
    static readonly Dictionary<string, (string fn, float t, string arg)[]> Events = new() {
        ["<clip>"] = new[] { ("<Method>", 0.5f, "<param>") } };   // normalised time

    public static Kind? KindOf(string path) =>                  // pure: testable without an import
        !path.StartsWith(ModelRoot, StringComparison.OrdinalIgnoreCase) ? null
        : path.Contains("/<props>/") ? Kind.Prop : path.Contains("/<creatures>/") ? Kind.Generic : Kind.Humanoid;

    void OnPreprocessModel() {
        if (KindOf(assetPath) is not Kind kind) return;
        var m = (ModelImporter)assetImporter;
        m.isReadable = false; m.materialImportMode = ModelImporterMaterialImportMode.ImportViaMaterialDescription;
        if (kind == Kind.Prop) { m.importAnimation = false; return; }
        m.animationType = kind == Kind.Humanoid ? ModelImporterAnimationType.Human : ModelImporterAnimationType.Generic;
        m.avatarSetup = ModelImporterAvatarSetup.CreateFromThisModel;
        if (kind == Kind.Humanoid) m.humanDescription = WithBoneMap(m.humanDescription);   // <BoneMap> rows
    }
    void OnPreprocessAnimation() {
        var m = (ModelImporter)assetImporter; var loops = LoopsIn(assetPath);
        var clips = m.defaultClipAnimations;
        foreach (var c in clips) {
            c.name = c.takeName.Substring(c.takeName.LastIndexOf('|') + 1);
            c.loopTime = loops.Contains(c.name);
            c.events = Events.TryGetValue(c.name, out var e) ? e.Select(x => new AnimationEvent
                { functionName = x.fn, time = x.t, stringParameter = x.arg }).ToArray() : Array.Empty<AnimationEvent>();
        }
        m.clipAnimations = clips;
    }
    void OnPreprocessMaterialDescription(UnityEditor.AssetImporters.MaterialDescription d, Material mat, AnimationClip[] a) {
        if (KindOf(assetPath) == null) return;
        mat.shader = Shader.Find("Universal Render Pipeline/Lit");   // then bind <Name>_BaseMap, _MetallicGloss, _Emission
    }
    void OnPreprocessTexture() {
        if (!assetPath.StartsWith(ModelRoot, StringComparison.OrdinalIgnoreCase)) return;
        ((TextureImporter)assetImporter).sRGBTexture = !new[] { "_MetallicGloss", "_Mask" }.Any(Path.GetFileNameWithoutExtension(assetPath).EndsWith);
    }
    public override uint GetVersion() => 1;            // bump when a rule changes
    public override int GetPostprocessOrder() => 100;  // after the render pipeline's own material step
    // WithBoneMap(...) and LoopsIn(...) read the shared bone map and ManifestPath; omitted here.
}
```

## Notes

- A Humanoid avatar needs the rest pose recorded on first import; record it in `OnPostprocessModel`
  and reimport once.
- Generate animator controllers and prefab installs from an Editor menu (`AnimatorController`,
  `BlendTree`, `AvatarMask`, `PrefabUtility.LoadPrefabContents`); never wire them by hand.
- First-person games: draw the local player's own body as shadows only.
- `Renderer.bounds` lies about skinned meshes (padded import bounds); measure baked vertices
  (`BakeMesh(useScale: true)` through `localToWorldMatrix`) when deciding heights or feet.
- A cloud session without Unity cannot run any of this: say UNTESTED, hand over the menu item and
  what the user should see.
