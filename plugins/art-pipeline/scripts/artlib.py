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
        return {"start": "", "seen": [], "blocks": {}, "granted": [], "iter": {}}
    with open(path, "r", encoding="utf-8") as fh:
        led = json.load(fh)
    if not isinstance(led, dict) or not isinstance(led.get("seen"), list):
        raise ValueError("ledger %s has the wrong shape" % path)
    led.setdefault("start", "")
    led.setdefault("blocks", {})
    led.setdefault("granted", [])
    led.setdefault("iter", {})
    return led


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
        rel = "%s/%s.json" % (cfg["approval_dir"].strip("/"), sid)
        if rec is None and rel in names:
            res.append((rel, "fail", pr))
    for n in names:
        if is_production(n, cfg) and os.path.isfile(os.path.join(root, n)):
            if not any(not pr for _, _, pr in covering(n, approvals)):
                why = [x for _, _, pr in covering(n, approvals) for x in pr] or \
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
# A spec (<spec_dir>/<id>.json) says what will be made and what real-world reference it is made
# from. Only a human approves one: by answering "Approve" to an AskUserQuestion that carries the
# spec's token (hook.py records it), or with `approve.py grant` in a real terminal. Claude's tools
# cannot write the approval folder or the config. An approval counts only if this session's hook
# wrote it or it was committed, unchanged, before the session started.

TOKEN = re.compile(r"art-approve:([a-z0-9][a-z0-9_-]*)@([0-9a-f]{12})")
SLUG = re.compile(r"^[a-z0-9][a-z0-9_-]*$")


def spec_path(root, cfg, sid):
    return os.path.join(root, cfg["spec_dir"], sid + ".json")


def approval_path(root, cfg, sid):
    return os.path.join(root, cfg["approval_dir"], sid + ".json")


def _text(v, n):
    return isinstance(v, str) and len(v.strip()) >= n


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
    kind = s.get("kind")
    if kind not in KINDS:
        probs.append("\"kind\" must be one of %s" % ", ".join(KINDS))
    if not _text(s.get("summary"), 20):
        probs.append("\"summary\" must say what is being made (>= 20 chars)")
    refs = s.get("references")
    ref_files = []
    if not isinstance(refs, list) or not refs:
        probs.append("\"references\" must list at least one real-world reference: "
                     "{\"file\", \"source\", \"shows\"}")
        refs = []
    for i, r in enumerate(refs):
        r = r if isinstance(r, dict) else {}
        f = r.get("file") if isinstance(r.get("file"), str) else ""
        if not f or not _under(f, cfg["reference_dir"]):
            probs.append("references[%d].file must be a file under %s/" % (i, cfg["reference_dir"]))
        elif not os.path.isfile(os.path.join(root, f)):
            probs.append("references[%d].file %s does not exist" % (i, f))
        else:
            ref_files.append(f)
        if not _text(r.get("source"), 10):
            probs.append("references[%d].source must name where it came from: a URL or a citation (>= 10 chars)" % i)
        if not _text(r.get("shows"), 20):
            probs.append("references[%d].shows must say what it shows and what to take from it (>= 20 chars)" % i)
    if kind not in AUDIO_KINDS and not any(f.lower().endswith(IMG_EXT) for f in ref_files):
        probs.append("kind %s needs at least one image reference (%s) that can be opened and compared"
                     % (kind, "/".join(IMG_EXT)))
    acc = s.get("acceptance")
    if not isinstance(acc, list) or not acc or not all(_text(a, 10) for a in acc):
        probs.append("\"acceptance\" must list what the human will check against the reference (each >= 10 chars)")
    paths = s.get("paths")
    if not isinstance(paths, list) or not paths or not all(isinstance(g, str) and g for g in paths):
        probs.append("\"paths\" must list the globs of every file this work writes")
    match = s.get("match", [sid])
    if not isinstance(match, list) or not all(isinstance(t, str) and len(t) >= 3 for t in match):
        probs.append("\"match\" must list words (>= 3 chars) that name this asset in a build command")
    it = s.get("iterations", DEFAULT_ITERATIONS)
    if not isinstance(it, int) or isinstance(it, bool) or not 1 <= it <= MAX_ITERATIONS:
        probs.append("\"iterations\" must be a whole number from 1 to %d" % MAX_ITERATIONS)
    if kind == "animation":
        kp = s.get("key_poses")
        if not isinstance(kp, list) or not kp:
            probs.append("an animation needs \"key_poses\": [{\"at\", \"ref\", \"pose\"}], each taken from a reference")
        for i, k in enumerate(kp if isinstance(kp, list) else []):
            k = k if isinstance(k, dict) else {}
            if k.get("ref") not in ref_files:
                probs.append("key_poses[%d].ref must be one of the reference files" % i)
            if not _text(k.get("at"), 1) or not _text(k.get("pose"), 10):
                probs.append("key_poses[%d] needs \"at\" (time or frame) and \"pose\" (>= 10 chars, as seen in the reference)" % i)
    if kind in AUDIO_KINDS and not isinstance(s.get("duration_s"), (int, float)):
        probs.append("kind %s needs \"duration_s\"" % kind)
    return s, probs


def spec_token(root, cfg, sid):
    return "art-approve:%s@%s" % (sid, sha(spec_path(root, cfg, sid))[:12])


def make_approval(root, cfg, sid, spec, by, answer):
    """The approval record a human grant writes: hashes lock the spec and every reference."""
    return {"id": sid, "kind": spec["kind"], "spec": "%s/%s.json" % (cfg["spec_dir"], sid),
            "spec_sha": sha(spec_path(root, cfg, sid)),
            "references": {r["file"]: sha(os.path.join(root, r["file"])) for r in spec["references"]},
            "paths": spec["paths"], "match": spec.get("match", [sid]),
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
        probs = []
        h = sha(os.path.join(d, f))
        if h not in led["granted"] and _committed_at(root, led["start"], rel) != h:
            out.append((sid, None, ["%s was not written by a human grant: not recorded this session and "
                                    "not committed before it started" % rel]))
            continue
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
        except Exception as exc:
            out.append((sid, None, ["%s is unreadable (%s)" % (rel, exc)]))
            continue
        rec["_sha"] = h  # the build budget is counted per grant, so a re-approval starts it again
        out.append((sid, rec, probs))
    return out


def seen_paths(led):
    return {norm(e["path"]) for e in led["seen"] if isinstance(e, dict) and "path" in e}


def usable(root, rec, led):
    """Problems that stop a valid approval being used right now (reference not looked at, budget spent)."""
    probs = []
    imgs = [f for f in rec["references"] if f.lower().endswith(IMG_EXT)]
    seen = seen_paths(led)
    if imgs and not any(norm(os.path.join(root, f)) in seen for f in imgs):
        probs.append("open a reference image with Read before building %s (%s)" % (rec["id"], imgs[0]))
    used = led["iter"].get(rec["_sha"], 0)
    if used >= rec["iterations"]:
        probs.append("%s has used all %d builds the human approved. Stop refining: show the human the "
                     "last render beside its reference and ask them to accept it, add reference, or "
                     "re-approve for more builds" % (rec["id"], rec["iterations"]))
    return probs


def covering(rel, approvals):
    return [(sid, rec, pr) for sid, rec, pr in approvals if rec and matches(rel, rec["paths"])]


def approval_hint(cfg):
    return ("write a spec at %s/<id>.json with real-world reference saved under %s/ (see the art-pipeline "
            "skill, stage 2), run python \"%s\" check <id>, then ask the human with the AskUserQuestion it "
            "prints. Do not make the asset first." % (cfg["spec_dir"], cfg["reference_dir"],
                                                      os.path.join(HERE, "approve.py")))
