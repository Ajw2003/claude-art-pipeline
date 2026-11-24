#!/usr/bin/env bash
# Renders Unity frame sheets (unity_frame_sheets.cs) in the project's running Editor, in Edit mode, then labels them.
# The camera, light and layout come from frame_camera.txt, which blender_frame_sheets.py reads too.
# Usage:
#   bash unity_frame_sheets.sh --project <Unity project> --out <dir> [--steps 5] [--gap BoneA BoneB] [--dir Bone] \
#        <entry> [<entry> ...]
# An entry is a prefab, a model file or a folder of prefabs, project-relative (Assets/...), optionally followed by
# =<controller or clip file>. Writes <out>/<name>.png (labelled), <out>/raw/<name>.png and <out>/raw/<name>.json.
# Needs the `unity` CLI connected to that project's Editor. Never enters Play mode and never recompiles the project.
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
project="" out="" steps="" gap="" dir=""
entries=()
while [ $# -gt 0 ]; do
    case "$1" in
        --project) project="$2"; shift 2 ;;
        --out) out="$2"; shift 2 ;;
        --steps) steps="$2"; shift 2 ;;
        --gap) gap="$2 $3"; shift 3 ;;
        --dir) dir="$2"; shift 2 ;;
        -h|--help) sed -n 2,8p "$0"; exit 0 ;;
        *) entries+=("$1"); shift ;;
    esac
done
if [ -z "$project" ] || [ -z "$out" ] || [ ${#entries[@]} -eq 0 ]; then
    echo "usage: unity_frame_sheets.sh --project <Unity project> --out <dir> <entry> [...]" >&2; exit 2
fi
win() { if command -v cygpath >/dev/null 2>&1; then cygpath -m "$1"; else printf '%s' "$1"; fi; }
mkdir -p "$out" "$project/Temp"
project="$(cd "$project" && pwd)"; out="$(cd "$out" && pwd)"
cfg="$project/Temp/art-pipeline-frame-sheets.txt"
{
    echo "run $(date +%s)-$$"
    echo "out $(win "$out")"
    sed -e 's/#.*//' -e '/^[[:space:]]*$/d' "$HERE/frame_camera.txt"  # the camera both renderers share
    [ -n "$steps" ] && echo "steps $steps"
    [ -n "$gap" ] && echo "gap $gap"
    [ -n "$dir" ] && echo "dir $dir"
    for e in "${entries[@]}"; do echo "entry $e"; done
} > "$cfg"

PY=python3; "$PY" -c 1 >/dev/null 2>&1 || PY=python  # Windows ships a python3 stub that only opens the Store
# Each call renders one entry (the CLI stops a call after 5 s of main-thread time); keep calling until "done".
for _ in $(seq 1 500); do
    res="$(unity command eval_file --file "$(win "$HERE/unity_frame_sheets.cs")" --project-path "$(win "$project")" \
           --timeout 600 --no-banner --format json 2>&1 || true)"
    text="$(printf '%s' "$res" | "$PY" -c '
import json, sys
t = sys.stdin.read(); s = t.find("{")
if s < 0: print(t.strip()); sys.exit(0)
env, _ = json.JSONDecoder().raw_decode(t[s:])
r = (env.get("data") or {}).get("result")
if isinstance(r, str):
    try: r = json.loads(r)
    except Exception: pass
if isinstance(r, dict) and "result" in r:
    for d in r.get("diagnostics") or []: print("diag:", d)
    print(r.get("result"))
elif not env.get("success"): print("FAIL", json.dumps(env.get("errors"))[:3000])
else: print(r)
')"
    printf '%s\n' "$text"
    case "$text" in
        *FAIL*|*diag:*error*|*"error CS"*) echo "unity_frame_sheets: the Editor call failed (above); nothing more rendered." >&2; exit 1 ;;
    esac
    case "$text" in *done) break ;; esac
    case "$text" in *more) ;; *) echo "unity_frame_sheets: unexpected reply (above); stopping." >&2; exit 1 ;; esac
done
"$PY" "$(win "$HERE/frame_sheet_pages.py")" label "$(win "$out")"
