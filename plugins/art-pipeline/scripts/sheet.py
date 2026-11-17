"""sheet.py - renders a spec as its review sheet: one self-contained HTML page, laid out the same way
every time, with the reference shown large and as little text as the spec allows. Deterministic:
the hooks re-render and compare, so a hand-edited sheet counts as out of date. Stdlib only."""

import base64
import html
import mimetypes
import os

import artlib

# The order parts always appear in, so every sheet reads the same way.
ORDER = ("model", "rig", "texture", "sprite", "ui", "animation", "vfx", "sfx", "music", "other")
LABEL = {"model": "Model", "rig": "Rig", "texture": "Texture", "sprite": "Sprite", "ui": "UI art",
         "animation": "Animation", "vfx": "VFX", "sfx": "Sound", "music": "Music", "other": "Other"}
MAX_BYTES = 15 * 1024 * 1024
MIME = {".png": "image/png", ".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".webp": "image/webp",
        ".wav": "audio/wav", ".ogg": "audio/ogg", ".mp3": "audio/mpeg", ".flac": "audio/flac",
        ".mp4": "video/mp4", ".webm": "video/webm"}

CSS = """
:root{--bg:#f4f5f2;--card:#fff;--ink:#1c201e;--muted:#5f6964;--line:#d8ddd9;--accent:#2f6b62;--chip:#e3eeeb}
@media (prefers-color-scheme:dark){:root{--bg:#151917;--card:#1d2220;--ink:#e7ece9;--muted:#9ca7a2;--line:#323a35;--accent:#83c4b8;--chip:#22302c}}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}
main{max-width:980px;margin:0 auto;padding:28px max(16px,env(safe-area-inset-left)) 64px;display:grid;gap:28px}
h1{font-size:30px;margin:0 0 6px;line-height:1.15}
.meta{color:var(--muted);font-size:15px}
.how{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:14px 16px;font-size:15px}
.item{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:20px;display:grid;gap:22px}
.item>h2{font-size:24px;margin:0}
.part{display:grid;gap:12px;border-top:1px solid var(--line);padding-top:16px}
.part h3{margin:0;font-size:13px;letter-spacing:.1em;text-transform:uppercase;color:var(--accent)}
.refs{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:14px}
figure{margin:0;display:grid;gap:6px;align-content:start}
figure img,figure video{width:100%;height:min(380px,70vw);object-fit:contain;background:var(--bg);border-radius:6px}
figure audio{width:100%}
figcaption{font-size:15px}
.src{font-size:12px;color:var(--muted);overflow-wrap:anywhere}
.poses{display:grid;grid-template-columns:repeat(auto-fill,minmax(140px,1fr));gap:10px}
.pose{display:grid;gap:4px;font-size:14px}
.pose img{width:100%;aspect-ratio:1;object-fit:cover;border-radius:6px;background:var(--bg)}
.at{font:600 13px ui-monospace,monospace;color:var(--accent)}
.checks{margin:0;padding:0;list-style:none;display:grid;gap:6px}
.checks li{display:flex;gap:10px;align-items:flex-start;font-size:15px}
.checks input{margin-top:4px;width:18px;height:18px;flex:none}
details{font-size:13px;color:var(--muted)}
code{font:12px ui-monospace,monospace;overflow-wrap:anywhere}
"""


def _media(root, f, total):
    path = os.path.join(root, f)
    ext = os.path.splitext(f)[1].lower()
    data = open(path, "rb").read()
    total[0] += len(data)
    uri = "data:%s;base64,%s" % (MIME.get(ext) or mimetypes.guess_type(f)[0] or "application/octet-stream",
                                 base64.b64encode(data).decode("ascii"))
    if ext in artlib.IMG_EXT:
        return '<img src="%s" alt="%s">' % (uri, html.escape(os.path.basename(f)))
    if ext in artlib.AUDIO_EXT:
        return '<audio controls preload="none" src="%s"></audio>' % uri
    if ext in artlib.VIDEO_EXT:
        return '<video controls preload="metadata" src="%s"></video>' % uri
    return '<div class="src">%s (shown as a file name only)</div>' % html.escape(f)


def render(root, cfg, sid, spec):
    """The sheet's HTML. Raises ValueError when the embedded reference exceeds MAX_BYTES."""
    e = html.escape
    total = [0]
    token = artlib.spec_token(root, cfg, sid)
    items = spec["items"]
    nrefs = len(artlib.spec_refs(spec))
    out = ['<!doctype html><html lang="en"><head><meta charset="utf-8">',
           '<meta name="viewport" content="width=device-width,initial-scale=1">',
           '<title>%s</title><style>%s</style></head><body><main>' % (e(spec["title"]), CSS),
           '<header><h1>%s</h1><div class="meta">%d item%s &middot; %d reference%s &middot; %d builds per item</div></header>'
           % (e(spec["title"]), len(items), "" if len(items) == 1 else "s", nrefs, "" if nrefs == 1 else "s",
              spec.get("iterations", artlib.DEFAULT_ITERATIONS)),
           '<div class="how">Look at each reference. Read the checks under it. Then answer '
           '<b>Approve</b> or <b>Revise</b> in the chat. Nothing is built before you approve.</div>']
    for it in items:
        out.append('<section class="item"><h2>%s</h2>' % e(it["name"]))
        parts = it["parts"]
        for kind in [k for k in ORDER if k in parts]:
            part = parts[kind]
            out.append('<div class="part"><h3>%s</h3><div class="refs">' % LABEL[kind])
            for r in part["references"]:
                out.append('<figure>%s<figcaption>%s</figcaption><div class="src">%s</div></figure>'
                           % (_media(root, r["file"], total), e(r["shows"]), e(r["source"])))
            out.append('</div>')
            if part.get("key_poses"):
                out.append('<div class="poses">')
                for k in part["key_poses"]:
                    out.append('<div class="pose">%s<span class="at">%s</span><span>%s</span></div>'
                               % (_media(root, k["ref"], total), e(k["at"]), e(k["pose"])))
                out.append('</div>')
            if kind in artlib.AUDIO_KINDS:
                out.append('<div class="meta">Length: %s s</div>' % e(str(part["duration_s"])))
            out.append('<ul class="checks">%s</ul></div>' % "".join(
                '<li><input type="checkbox" aria-label="checked"><span>%s</span></li>' % e(c) for c in part["check"]))
        out.append('<details><summary>Files this item may write</summary><code>%s</code></details></section>'
                   % e(", ".join(it["paths"])))
    out.append('<details><summary>Approval token</summary><code>%s</code></details></main></body></html>\n' % token)
    if total[0] > MAX_BYTES:
        raise ValueError("the reference embedded in the sheet is %.1f MB; keep it under %d MB by saving "
                         "smaller reference files" % (total[0] / 1048576.0, MAX_BYTES // 1048576))
    return "".join(out)


def is_current(root, cfg, sid, spec):
    """True when the sheet on disk is exactly what the spec renders to now."""
    p = artlib.sheet_path(root, cfg, sid)
    if not os.path.isfile(p):
        return False
    with open(p, "r", encoding="utf-8") as fh:
        return fh.read() == render(root, cfg, sid, spec)
