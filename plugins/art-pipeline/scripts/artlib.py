"""artlib.py - the one place the art-pipeline gate logic lives. hook.py and review.py both
import it. Stdlib only."""

import fnmatch
import hashlib
import json
import os
import re
import subprocess
import time

DEFAULT_GLOBS = ["*.fbx", "*.glb", "*.gltf", "*.blend", "*.obj"]
DEFAULT_EXCLUDE = ["node_modules/", "Library/", "Temp/", ".git/"]
DEFAULT_REVIEW_DIR = "docs/art/reviews"
MIN_SEEN = 40
IMG_EXT = (".png", ".jpg", ".jpeg", ".webp")
AUDIO_EXT = (".wav", ".ogg", ".mp3", ".flac")
VIDEO_EXT = (".mp4", ".webm")
MAX_BLOCKS = 3
DOC_PATHS = ["docs/**", "**/*.json"]
DOC_TIMEOUT = 60
# Anything that makes art: meshes, clips, audio, textures, sprites, VFX, shaders, materials, UI art.
# Basename globs match the file name, globs with a slash the whole path.
DEFAULT_PRODUCTION = DEFAULT_GLOBS + [
    "*.wav", "*.ogg", "*.mp3", "*.flac", "*.aif", "*.aiff",
    "*.anim", "*.bvh", "*.vfx", "*.shadergraph", "*.shader", "*.hlsl", "*.mat",
    "*.psd", "*.kra", "*.aseprite", "*.ase", "*.tga", "*.exr", "*.dds", "*.hdr",
    "*/art/*", "*/audio/*", "*/sound/*", "*/sounds/*", "*/sfx/*", "*/music/*", "*/textures/*",
    "*/sprites/*", "*/icons/*", "*/vfx/*", "*/particles/*", "*/shaders/*", "*/materials/*",
    "*/animations/*", "*/models/*", "*/fonts/*"]
DEFAULT_PRODUCERS = [r"(^|[\s/;&|(])blender(\.exe)?(\s|$)"]
KINDS = ("animation", "model", "rig", "vfx", "sfx", "music", "texture", "sprite", "ui", "other")
AUDIO_KINDS = ("sfx", "music")
DEFAULT_ITERATIONS = 5
MAX_ITERATIONS = 20
HERE = os.path.dirname(os.path.abspath(__file__))


def git(cwd, *args):
    p = subprocess.run(["git", "-c", "core.quotepath=off"] + list(args), cwd=cwd,
                       stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if p.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args), p.stderr.decode("utf-8", "replace").strip()))
    return p.stdout.decode("utf-8", "replace")


def repo_info(start_dir):
    """(toplevel, absolute git dir) or None when start_dir is not in a git repo."""
    try:
        top = git(start_dir, "rev-parse", "--show-toplevel").strip()
        gd = git(start_dir, "rev-parse", "--absolute-git-dir").strip()
    except (RuntimeError, OSError):
        return None
    return os.path.normpath(top), os.path.normpath(gd)


def head_sha(root):
    try:
        return git(root, "rev-parse", "HEAD").strip()
    except RuntimeError:  # no commits yet
        return ""


def load_config(root):
    cfg = {"model_globs": DEFAULT_GLOBS, "exclude": DEFAULT_EXCLUDE, "review_dir": DEFAULT_REVIEW_DIR,
           "doc_check": "", "doc_check_paths": DOC_PATHS,
           "production_paths": DEFAULT_PRODUCTION, "production_exclude": ["*.meta", "docs/*"],
           "producer_commands": DEFAULT_PRODUCERS, "spec_dir": "docs/art/specs",
           "reference_dir": "docs/art/reference", "approval_dir": "docs/art/approvals"}
    path = os.path.join(root, ".art-pipeline.json")
    if os.path.exists(path):
        with open(path, "r", encoding="utf-8") as fh:
            user = json.load(fh)  # a bad config raises; callers announce it
        for k in cfg:
            if k in user:
                cfg[k] = user[k]
    return cfg


def excluded(rel, cfg):
    low = rel.lower()
    return any(low.startswith(ex.lower()) or ("/" + ex.lower()) in ("/" + low) for ex in cfg["exclude"])


def matches(rel, globs):
    low = rel.lower()
    base = low.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(base if "/" not in g else low, g.lower()) for g in globs)


def is_model(rel, cfg):
    return not excluded(rel, cfg) and matches(rel, cfg["model_globs"])


def _under(rel, d):
    d = d.strip("/")
    return rel == d or rel.startswith(d + "/")


def is_production(rel, cfg):
    """True when writing rel is making art. The spec, reference, approval and review folders never are."""
    if any(_under(rel, cfg[k]) for k in ("spec_dir", "reference_dir", "approval_dir", "review_dir")):
        return False
    return not excluded(rel, cfg) and not matches(rel, cfg["production_exclude"]) \
        and matches(rel, cfg["production_paths"])


def tracked_has_art(root, cfg):
    out = git(root, "ls-files", "--cached", "--others", "--exclude-standard")
    return any(is_model(f, cfg) for f in out.splitlines())


def changed_files(root, start):
    names = set()
    if start and start != head_sha(root):
        names.update(git(root, "diff", "--name-only", "%s..HEAD" % start).splitlines())
    toks = git(root, "status", "--porcelain", "-uall", "-z").split("\0")
    i = 0
    while i < len(toks):
        t = toks[i]
        i += 1
        if len(t) < 4:
            continue
        names.add(t[3:])
        if t[0] in "RC":
            i += 1  # skip the rename source
    return sorted(names)


def changed_models(root, start, cfg):
    return [n for n in changed_files(root, start) if is_model(n, cfg) and os.path.isfile(os.path.join(root, n))]


def _path_match(rel, pat):
    return fnmatch.fnmatch(rel, pat) or (pat.startswith("**/") and fnmatch.fnmatch(rel, pat[3:]))


def run_doc_check(root, cfg, names):
    """None when not configured / nothing relevant changed, else ('ok'|'fail'|'timeout', [detail])."""
    cmd = cfg.get("doc_check")
    if not cmd:
        return None
    pats = cfg.get("doc_check_paths") or DOC_PATHS
    if not any(is_model(n, cfg) or any(_path_match(n, g) for g in pats) for n in names):
        return None
    try:
        p = subprocess.run(cmd, shell=True, cwd=root, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=DOC_TIMEOUT)
    except subprocess.TimeoutExpired:
        return "timeout", ["doc_check `%s` timed out after %ds; not checked" % (cmd, DOC_TIMEOUT)]
    if p.returncode == 0:
        return "ok", []
    tail = p.stdout.decode("utf-8", "replace").strip().splitlines()[-20:]
    return "fail", ["doc_check `%s` exited %d:" % (cmd, p.returncode)] + tail


# --- ledger -----------------------------------------------------------------------------

def sha(path):
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for block in iter(lambda: fh.read(1 << 20), b""):
            h.update(block)
    return h.hexdigest()


def ledger_path(gitdir, session_id):
    sid = re.sub(r"[^A-Za-z0-9_.-]", "_", session_id or "") or "nosession"
    return os.path.join(gitdir, "art-pipeline", sid + ".json")


def load_ledger(path):
    if not os.path.exists(path):
        return new_ledger("")
    with open(path, "r", encoding="utf-8") as fh:
        led = json.load(fh)
    if not isinstance(led, dict) or not isinstance(led.get("seen"), list):
        raise ValueError("ledger %s has the wrong shape" % path)
    for k, v in new_ledger("").items():
        led.setdefault(k, v)
    return led


def new_ledger(start, known=None):
    """known: art file -> sha already accepted (dirty at session start, or built under an approval);
    t0: when the running Bash call started; counted: whether pre already charged it to a budget."""
    return {"start": start, "seen": [], "blocks": {}, "granted": [], "iter": {},
            "known": known or {}, "t0": 0, "counted": False}


def changed_art(root, cfg):
    """{art file: sha} for every art file that differs from HEAD or is untracked, and exists."""
    out = {}
    for n in changed_files(root, ""):
        a = os.path.join(root, n)
        if is_production(n, cfg) and os.path.isfile(a):
            out[n] = sha(a)
    return out


def save_ledger(path, led):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(led, separators=(",", ":")))


def norm(p):
    return os.path.normcase(os.path.realpath(p))


# --- review records ---------------------------------------------------------------------

def record_name(model):
    return model.replace("/", "__") + ".review.json"


def load_records(root, cfg):
    d = os.path.join(root, cfg["review_dir"])
    recs, bad = [], []
    if os.path.isdir(d):
        for f in sorted(os.listdir(d)):
            if f.endswith(".review.json"):
                try:
                    with open(os.path.join(d, f), "r", encoding="utf-8") as fh:
                        r = json.load(fh)
                    if not isinstance(r, dict):
                        raise ValueError("not an object")
                    recs.append(r)
                except Exception as exc:
                    bad.append("%s/%s (%s)" % (cfg["review_dir"], f, exc))
    return recs, bad


def check_model(root, model, recs, seen_paths, cfg):
    """('ok'|'waived'|'fail', [problems]). Passes if any record for the model is satisfied."""
    mine = [r for r in recs if r.get("model") == model]
    if not mine:
        return "fail", ["no review record in %s/ with \"model\": \"%s\"" % (cfg["review_dir"], model)]
    last = None
    for r in mine:
        probs = []
        verdict = r.get("verdict")
        seen_txt = r.get("seen") if isinstance(r.get("seen"), str) else ""
        sheet = r.get("sheet") if isinstance(r.get("sheet"), str) else ""
        sheet_abs = os.path.join(root, sheet) if sheet else ""
        if verdict not in ("pass", "fail", "waived"):
            probs.append("verdict must be pass, fail or waived (got %r)" % (verdict,))
        elif verdict == "fail":
            probs.append("the record's verdict is fail - fix the model, re-render the sheet, re-review")
        if len(seen_txt.strip()) < MIN_SEEN:
            probs.append("\"seen\" must say what the reviewer saw (>= %d chars)" % MIN_SEEN)
        if not sheet or not os.path.isfile(sheet_abs):
            probs.append("sheet %r does not exist" % sheet)
        else:
            if os.path.getmtime(sheet_abs) < os.path.getmtime(os.path.join(root, model)):
                probs.append("sheet %s is older than the model - re-render it" % sheet)
            if norm(sheet_abs) not in seen_paths:
                probs.append("sheet %s was not opened (Read) this session" % sheet)
        if not probs:
            return ("waived" if verdict == "waived" else "ok"), []
        last = probs
    return "fail", last


def evaluate(root, gitdir, session_id):
    """Shared by the Stop gate and `review.py status`. Returns (cfg, ledger, results, bad)
    where results = [(model, status, problems)]."""
    cfg = load_config(root)
    led = load_ledger(ledger_path(gitdir, session_id))
    seen = {norm(e["path"]) for e in led["seen"] if isinstance(e, dict) and "path" in e}
    recs, bad = load_records(root, cfg)
    res = []
    names = changed_files(root, led["start"])
    for m in names:
        if is_model(m, cfg) and os.path.isfile(os.path.join(root, m)):
            st, pr = check_model(root, m, recs, seen, cfg)
            res.append((m, st, pr))
    approvals = load_approvals(root, cfg, led)
    for sid, rec, pr in approvals:
        if rec is None:  # "forged" never releases the stop: a fake approval must be removed, not outlasted
            res.append(("%s/%s.json" % (cfg["approval_dir"].strip("/"), sid), "forged",
                        pr + ["remove it with git rm; only a human grant writes approvals"]))
    for n in names:
        if is_production(n, cfg) and os.path.isfile(os.path.join(root, n)):
            cov = covering(n, approvals)
            if not any(not pr for _, _, pr in cov):  # a spent budget does not undo what was built within it
                why = [x for _, _, pr in cov for x in pr] or \
                      ["no human-approved spec covers this file: " + approval_hint(cfg)]
                res.append((n, "fail", why))
    dc = run_doc_check(root, cfg, names)
    if dc:
        res.append(("doc_check", dc[0], dc[1]))
    return cfg, led, res, bad


def now():
    return time.strftime("%Y-%m-%dT%H:%M:%S%z")


def fix_hint(cfg):
    return ("make a review sheet PNG of the model beside its concept (art-pipeline skill), open it "
            "with Read, then: python \"%s\" record --model <model> --sheet <sheet.png> "
            "--verdict pass --seen \"<what you saw, >= %d chars>\"" % (os.path.join(HERE, "review.py"), MIN_SEEN))


# --- specs and human approvals ----------------------------------------------------------
# A spec (<spec_dir>/<id>.json) lists one or more items (an enemy, a prop, a sound set), and for
# each item the parts to make (model, animation, texture, sfx...) with real-world reference per
# part. Only a human approves one: by answering "Approve" to an AskUserQuestion that carries the
# spec's token (hook.py records it), or with `approve.py grant` in a real terminal. An approval
# counts only if this session's hook wrote it or it was committed, unchanged, before the session
# started. Text limits keep the review sheet short enough to read the same way every time.

TOKEN = re.compile(r"art-approve:([a-z0-9][a-z0-9_-]*)@([0-9a-f]{12})")
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")
# Fixed on purpose, not per project: every review sheet keeps the same shape and length.
LIMITS = {"title": 60, "name": 40, "shows": 120, "pose": 100, "check": 100}
MAX_CHECKS = 3


def spec_path(root, cfg, sid):
    return os.path.join(root, cfg["spec_dir"], sid + ".json")


def sheet_path(root, cfg, sid):
    return os.path.join(root, cfg["spec_dir"], sid + ".sheet.html")


def approval_path(root, cfg, sid):
    return os.path.join(root, cfg["approval_dir"], sid + ".json")


def _text(v, lo, hi=10 ** 6):
    return isinstance(v, str) and lo <= len(v.strip()) <= hi


def slugify(name):
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")


def _check_part(root, cfg, where, kind, part, probs):
    """Validates one part of one item, appending to probs."""
    if kind not in KINDS:
        probs.append("%s: part %r must be one of %s" % (where, kind, ", ".join(KINDS)))
        return
    part = part if isinstance(part, dict) else {}
    w = "%s %s" % (where, kind)
    refs = part.get("references")
    files = []
    if not isinstance(refs, list) or not refs:
        probs.append("%s: needs real-world references [{file, source, shows}]" % w)
        refs = []
    for i, r in enumerate(refs):
        r = r if isinstance(r, dict) else {}
        f = r.get("file") if isinstance(r.get("file"), str) else ""
        if not f or not _under(f, cfg["reference_dir"]):
            probs.append("%s: reference %d must be a file under %s/" % (w, i + 1, cfg["reference_dir"]))
        elif not os.path.isfile(os.path.join(root, f)):
            probs.append("%s: reference %s does not exist" % (w, f))
        else:
            files.append(f)
        if not _text(r.get("source"), 10):
            probs.append("%s: reference %d needs \"source\", a URL or citation (>= 10 chars)" % (w, i + 1))
        if not _text(r.get("shows"), 10, LIMITS["shows"]):
            probs.append("%s: reference %d needs \"shows\", what to take from it (10-%d chars)" % (w, i + 1, LIMITS["shows"]))
    want = AUDIO_EXT if kind in AUDIO_KINDS else IMG_EXT
    if refs and not any(f.lower().endswith(want) for f in files):
        probs.append("%s: needs at least one %s reference (%s)" % (
            w, "audio" if kind in AUDIO_KINDS else "image", "/".join(want)))
    checks = part.get("check")
    if not isinstance(checks, list) or not 1 <= len(checks) <= MAX_CHECKS or \
            not all(_text(c, 10, LIMITS["check"]) for c in checks):
        probs.append("%s: needs \"check\", 1-%d things to compare with the reference (10-%d chars each)"
                     % (w, MAX_CHECKS, LIMITS["check"]))
    if kind == "animation":
        kp = part.get("key_poses")
        if not isinstance(kp, list) or not kp:
            probs.append("%s: needs \"key_poses\" [{at, ref, pose}], each taken from a reference image" % w)
        for i, k in enumerate(kp if isinstance(kp, list) else []):
            k = k if isinstance(k, dict) else {}
            ref = k.get("ref") if isinstance(k.get("ref"), str) else ""
            if ref not in files or not ref.lower().endswith(IMG_EXT):
                probs.append("%s: key pose %d \"ref\" must be one of this part's reference images" % (w, i + 1))
            if not _text(k.get("at"), 1, 20) or not _text(k.get("pose"), 10, LIMITS["pose"]):
                probs.append("%s: key pose %d needs \"at\" and \"pose\" (10-%d chars)" % (w, i + 1, LIMITS["pose"]))
    if kind in AUDIO_KINDS and not isinstance(part.get("duration_s"), (int, float)):
        probs.append("%s: needs \"duration_s\"" % w)


def validate_spec(root, cfg, sid):
    """(spec dict or None, [problems]). Problems empty means a human may be asked to approve it."""
    p = spec_path(root, cfg, sid)
    if not SLUG.match(sid or ""):
        return None, ["spec id %r must be lowercase letters, digits, - or _" % sid]
    if not os.path.isfile(p):
        return None, ["no spec at %s/%s.json" % (cfg["spec_dir"], sid)]
    try:
        with open(p, "r", encoding="utf-8") as fh:
            s = json.load(fh)
    except Exception as exc:
        return None, ["spec %s is not valid JSON (%s)" % (sid, exc)]
    if not isinstance(s, dict):
        return None, ["spec %s must be a JSON object" % sid]
    probs = []
    if s.get("id") != sid:
        probs.append("\"id\" must equal the file name (%s)" % sid)
    if not _text(s.get("title"), 5, LIMITS["title"]):
        probs.append("\"title\" must name the batch (5-%d chars)" % LIMITS["title"])
    it = s.get("iterations", DEFAULT_ITERATIONS)
    if not isinstance(it, int) or isinstance(it, bool) or not 1 <= it <= MAX_ITERATIONS:
        probs.append("\"iterations\" (builds per item) must be a whole number from 1 to %d" % MAX_ITERATIONS)
    items = s.get("items")
    if not isinstance(items, list) or not items:
        probs.append("\"items\" must list at least one item: {name, parts, paths}")
        items = []
    names = set()
    for n, item in enumerate(items):
        item = item if isinstance(item, dict) else {}
        name = item.get("name")
        where = "item %d" % (n + 1)
        if not _text(name, 2, LIMITS["name"]):
            probs.append("%s: needs \"name\" (2-%d chars)" % (where, LIMITS["name"]))
            name = ""
        else:
            where = name
            if slugify(name) in names:
                probs.append("%s: two items have this name" % name)
            names.add(slugify(name))
        parts = item.get("parts")
        if not isinstance(parts, dict) or not parts:
            probs.append("%s: needs \"parts\", e.g. {\"model\": {...}, \"animation\": {...}, \"sfx\": {...}}" % where)
            parts = {}
        for kind, part in parts.items():
            _check_part(root, cfg, where, kind, part, probs)
        paths = item.get("paths")
        if not isinstance(paths, list) or not paths or not all(isinstance(g, str) and g for g in paths):
            probs.append("%s: needs \"paths\", the globs of every file it writes" % where)
        match = item.get("match", [slugify(name)])
        if not isinstance(match, list) or not match or not all(isinstance(t, str) and len(t) >= 3 for t in match):
            probs.append("%s: \"match\" must list words (>= 3 chars) that name it in a build command" % where)
    return s, probs


def spec_refs(spec):
    return sorted({r["file"] for item in spec["items"] for part in item["parts"].values() for r in part["references"]})


def spec_token(root, cfg, sid):
    return "art-approve:%s@%s" % (sid, sha(spec_path(root, cfg, sid))[:12])


def make_approval(root, cfg, sid, spec, by, answer):
    """The approval record a human grant writes: hashes lock the spec, the sheet and every reference."""
    sp = sheet_path(root, cfg, sid)
    return {"id": sid, "spec": "%s/%s.json" % (cfg["spec_dir"], sid),
            "spec_sha": sha(spec_path(root, cfg, sid)),
            "sheet_sha": sha(sp) if os.path.isfile(sp) else "",
            "references": {f: sha(os.path.join(root, f)) for f in spec_refs(spec)},
            "items": [{"name": it["name"], "match": it.get("match", [slugify(it["name"])]), "paths": it["paths"],
                       "images": sorted({r["file"] for p in it["parts"].values() for r in p["references"]
                                         if r["file"].lower().endswith(IMG_EXT)})}
                      for it in spec["items"]],
            "iterations": spec.get("iterations", DEFAULT_ITERATIONS),
            "approved_by": by, "answer": answer, "date": now(), "grant": os.urandom(8).hex()}


def write_approval(root, cfg, rec):
    """Writes the record and returns the sha of the bytes written, for the ledger."""
    p = approval_path(root, cfg, rec["id"])
    os.makedirs(os.path.dirname(p), exist_ok=True)
    data = (json.dumps(rec, indent=2) + "\n").encode("utf-8")
    with open(p, "wb") as fh:
        fh.write(data)
    return hashlib.sha256(data).hexdigest()


def _committed_at(root, start, rel):
    if not start:
        return None
    try:
        return hashlib.sha256(subprocess.run(["git", "show", "%s:%s" % (start, rel)], cwd=root,
                              stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True).stdout).hexdigest()
    except subprocess.CalledProcessError:
        return None


def human_granted(root, led, rel):
    """True when the approval file at rel was written by a human grant: recorded this session, or
    committed unchanged before the session started."""
    h = sha(os.path.join(root, rel))
    return h in led["granted"] or _committed_at(root, led["start"], rel) == h


def load_approvals(root, cfg, led):
    """[(id, record or None, [problems])] for every file in the approval folder."""
    d = os.path.join(root, cfg["approval_dir"])
    out = []
    if not os.path.isdir(d):
        return out
    for f in sorted(os.listdir(d)):
        if not f.endswith(".json"):
            continue
        rel = "%s/%s" % (cfg["approval_dir"].strip("/"), f)
        sid = f[:-5]
        if not human_granted(root, led, rel):
            out.append((sid, None, ["%s was not written by a human grant: not recorded this session and "
                                    "not committed before it started" % rel]))
            continue
        probs = []
        try:
            with open(os.path.join(d, f), "r", encoding="utf-8") as fh:
                rec = json.load(fh)
            sp = os.path.join(root, rec["spec"])
            if not os.path.isfile(sp) or sha(sp) != rec["spec_sha"]:
                probs.append("spec %s changed after it was approved - ask the human again" % rec["spec"])
            for rf, rh in rec["references"].items():
                rp = os.path.join(root, rf)
                if not os.path.isfile(rp) or sha(rp) != rh:
                    probs.append("reference %s is missing or changed since approval" % rf)
            for it in rec["items"]:
                it["name"], it["paths"], it["match"], it["images"]  # noqa: B018 - shape check
        except Exception as exc:
            out.append((sid, None, ["%s is unreadable (%s)" % (rel, exc)]))
            continue
        rec["_sha"] = sha(os.path.join(d, f))  # the budget is counted per grant, so a re-approval starts it again
        out.append((sid, rec, probs))
    return out


def seen_paths(led):
    return {norm(e["path"]) for e in led["seen"] if isinstance(e, dict) and "path" in e}


def budget_key(rec, item):
    return "%s:%s" % (rec["_sha"], slugify(item["name"]))


def usable(root, rec, item, led):
    """Problems that stop an item of a valid approval being built right now."""
    probs = []
    seen = seen_paths(led)
    if item["images"] and not any(norm(os.path.join(root, f)) in seen for f in item["images"]):
        probs.append("open a reference image of %s with Read before building it (%s)" % (item["name"], item["images"][0]))
    if led["iter"].get(budget_key(rec, item), 0) >= rec["iterations"]:
        probs.append("%s has used all %d builds the human approved. Stop refining: show the human the "
                     "last render beside its reference and ask them to accept it, add reference, or "
                     "re-approve for more builds" % (item["name"], rec["iterations"]))
    return probs


def covering(rel, approvals):
    """[(rec, item, problems)] for every approved item whose paths include rel."""
    return [(rec, it, pr) for _, rec, pr in approvals if rec for it in rec["items"] if matches(rel, it["paths"])]


def named_in(cmd, approvals):
    """[(rec, item, problems)] for every approved item a word of whose "match" is in cmd."""
    low = cmd.lower()
    return [(rec, it, pr) for _, rec, pr in approvals if rec for it in rec["items"]
            if any(t.lower() in low for t in it["match"])]


def ready(root, cands, led):
    """Splits (rec, item, problems) into the usable (rec, item) pairs and the reasons the rest are not."""
    ok, why = [], []
    for rec, it, pr in cands:
        p = pr or usable(root, rec, it, led)
        if p:
            why.extend(p)
        else:
            ok.append((rec, it))
    return ok, why


def approval_hint(cfg):
    return ("write a spec at %s/<id>.json with real-world reference saved under %s/ (see the art-pipeline "
            "skill), run python \"%s\" check <id>, show the human the review sheet it writes, then ask "
            "with the AskUserQuestion it prints. Do not make the asset first." % (
                cfg["spec_dir"], cfg["reference_dir"], os.path.join(HERE, "approve.py")))
