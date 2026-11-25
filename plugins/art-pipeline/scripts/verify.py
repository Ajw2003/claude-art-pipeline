#!/usr/bin/env python3
"""verify.py - proves art-pipeline's hooks do what they claim.

    python plugins/art-pipeline/scripts/verify.py

Numbered PASS/FAIL lines, exit 0 on all-pass / 1 on any failure. Stdlib only. Builds throwaway
git repos with subprocess git.
"""

import glob
import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import time

HERE = os.path.dirname(os.path.abspath(__file__))
HOOK = os.path.join(HERE, "hook.py")
RUN = os.path.join(HERE, "run.sh")
REVIEW = os.path.join(HERE, "review.py")
APPROVE = os.path.join(HERE, "approve.py")
HOOKS_JSON = os.path.join(HERE, "..", "hooks", "hooks.json")
SH = shutil.which("sh") or "sh"
STEP = FAILURES = 0
TMP = []
SEEN_TXT = "front and side views match the concept: horns, tail and the red cloak all present"


def report(ok, title):
    global STEP, FAILURES
    STEP += 1
    FAILURES += 0 if ok else 1
    print(f"{STEP:2d}. {'PASS' if ok else 'FAIL'}  {title}")


def sh_git(cwd, *a):
    subprocess.run(["git"] + list(a), cwd=cwd, check=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def commit_at(cwd, message, when):
    """Commits whatever is staged, dated `when` (an ISO date), so a test can say a commit was made before the session began."""
    env = dict(os.environ, GIT_AUTHOR_DATE=when, GIT_COMMITTER_DATE=when)
    subprocess.run(["git", "commit", "-qm", message], cwd=cwd, check=True, env=env, stdout=subprocess.PIPE, stderr=subprocess.PIPE)


def mkrepo(art=True, prod=False):
    """prod=False switches the approval gate off so the review-gate checks test only that gate."""
    d = tempfile.mkdtemp(prefix="art-pipeline-verify-")
    TMP.append(d)
    sh_git(d, "init", "-q")
    sh_git(d, "config", "user.name", "t")
    sh_git(d, "config", "user.email", "t@example.com")
    write(d, "README.md", "x")
    if not prod:
        write(d, ".art-pipeline.json", json.dumps({"production_paths": []}))
    if art:
        write(d, "art/old.fbx", "old")
    sh_git(d, "add", "-A")
    sh_git(d, "commit", "-qm", "init")
    return d


def write(d, rel, text="data", mtime=None):
    p = os.path.join(d, rel)
    os.makedirs(os.path.dirname(p), exist_ok=True)
    with open(p, "w") as f:
        f.write(text)
    if mtime:
        os.utime(p, (mtime, mtime))
    return p


FAKE_HOME = tempfile.mkdtemp(prefix="art-pipeline-home-")   # the per-user repo list stays out of ~
TMP.append(FAKE_HOME)


def run(args, payload="", env=None, cwd=None):
    e = dict(os.environ)
    e.pop("ART_PIPELINE", None)
    e["HOME"] = FAKE_HOME
    e["USERPROFILE"] = FAKE_HOME   # Windows expanduser("~") reads this, not HOME
    e["CLAUDE_CONFIG_DIR"] = os.path.join(FAKE_HOME, ".claude")   # the real typed-mode file must not leak in
    e.update(env or {})
    p = subprocess.run(args, input=payload.encode(), stdout=subprocess.PIPE, stderr=subprocess.PIPE, env=e, cwd=cwd)
    return p.returncode, p.stdout.decode("utf-8", "replace"), p.stderr.decode("utf-8", "replace")


def hook(event, d, extra=None, env=None, session="s1"):
    pl = {"session_id": session, "cwd": d}
    pl.update(extra or {})
    return run([sys.executable, HOOK, event], json.dumps(pl), env)


def gate(d, env=None):
    rc, out, _ = hook("gate", d, env=env)
    return rc, (json.loads(out) if out.strip() else {})


def see(d, path):
    return hook("seen", d, {"tool_input": {"file_path": path}})


def record(d, model, sheet, verdict="pass", seen=SEEN_TXT):
    return run([sys.executable, REVIEW, "record", "--model", model, "--sheet", sheet,
                "--verdict", verdict, "--seen", seen], cwd=d)


def good_setup(d, model="art/hero.fbx", verdict="pass"):
    """changed model + fresh seen sheet + record; returns the sheet path."""
    now = time.time()
    write(d, model, "m", mtime=now - 100)
    sheet = write(d, "docs/art/sheets/hero.png", "png", mtime=now - 50)
    record(d, model, "docs/art/sheets/hero.png", verdict)
    see(d, sheet)
    return sheet


print("\nart-pipeline hooks - verification (Python)\n" + "=" * 42)
print(f"Interpreter: {sys.executable}\n")

spec = importlib.util.spec_from_file_location("art_pipeline_hook", HOOK)
hm = importlib.util.module_from_spec(spec)
spec.loader.exec_module(hm)

try:
    # 1 hooks.json <-> EVENTS
    reg = set()
    for entries in json.load(open(HOOKS_JSON))["hooks"].values():
        for e in entries:
            for h in e["hooks"]:
                m = re.search(r'run\.sh"\s+(\w+)', h["command"])
                if m:
                    reg.add(m.group(1))
    report(reg == set(hm.EVENTS), f"hooks.json registers exactly hook.py's events {sorted(hm.EVENTS)}")

    # 2-3 start
    d = mkrepo(art=True)
    rc, out, _ = hook("start", d)
    ctx = json.loads(out)["hookSpecificOutput"]["additionalContext"]
    led = os.path.join(d, ".git", "art-pipeline", "s1.json")
    ok = rc == 0 and "review record" in ctx and os.path.exists(led) and json.load(open(led))["seen"] == []
    report(ok, "start in a repo with art: context emitted, ledger in .git/art-pipeline")
    d2 = mkrepo(art=False)
    rc, out, _ = hook("start", d2)
    report(rc == 0 and out == "" and os.path.exists(os.path.join(d2, ".git", "art-pipeline", "s1.json")),
           "start in a repo without art: silent, ledger armed (the first art there is gated too)")
    nogit = tempfile.mkdtemp(prefix="art-pipeline-nogit-")
    TMP.append(nogit)
    rc, out, _ = hook("start", nogit)
    rc2, out2, _ = hook("gate", nogit)
    report(rc == 0 and out == "" and rc2 == 0 and out2 == "", "start and gate outside a git repo: nothing")

    # 4 seen
    see(d, os.path.join(d, "a", "..", "x.png"))
    see(d, os.path.join(d, "Foo.cs"))
    seen = json.load(open(led))["seen"]
    report(len(seen) == 1 and seen[0]["path"] == os.path.join(d, "x.png"), "seen records a png (normalized) and ignores a .cs")

    # 5 gate no changes
    rc, o = gate(d)
    report(rc == 0 and o == {}, "gate passes silently with no changed models")

    # 6 untracked fbx no record
    write(d, "art/hero.fbx", "m")
    rc, o = gate(d)
    report(o.get("decision") == "block" and "art/hero.fbx" in o["reason"] and "no review record" in o["reason"]
           and "review.py" in o["reason"], "gate blocks a changed untracked .fbx with no record; reason names it")

    # 7 sheet older than model
    d = mkrepo(); hook("start", d)
    now = time.time()
    write(d, "art/hero.fbx", "m", mtime=now)
    sheet = write(d, "s.png", "p", mtime=now - 500)
    record(d, "art/hero.fbx", "s.png"); see(d, sheet)
    rc, o = gate(d)
    report(o.get("decision") == "block" and "older than the model" in o["reason"], "gate blocks when the sheet is older than the model")

    # 8 sheet not seen
    d = mkrepo(); hook("start", d)
    write(d, "art/hero.fbx", "m", mtime=now - 100)
    write(d, "s.png", "p", mtime=now - 50)
    record(d, "art/hero.fbx", "s.png")
    rc, o = gate(d)
    report(o.get("decision") == "block" and "not opened" in o["reason"], "gate blocks when the sheet was not opened this session")

    # 9 all good
    d = mkrepo(); hook("start", d); good_setup(d)
    rc, o = gate(d)
    report(rc == 0 and o == {}, "gate passes with record + fresh sheet + seen + pass")

    # 10 waived
    d = mkrepo(); hook("start", d); good_setup(d, verdict="waived")
    rc, o = gate(d)
    report("decision" not in o and "WAIVED" in o.get("systemMessage", "") and "art/hero.fbx" in o["systemMessage"],
           "waived passes, listed in a systemMessage")

    # 11 fail verdict
    d = mkrepo(); hook("start", d); good_setup(d, verdict="fail")
    rc, o = gate(d)
    report(o.get("decision") == "block" and "verdict is fail" in o["reason"], "fail verdict blocks")

    # 11b short seen rejected by the CLI and by the gate
    d = mkrepo(); hook("start", d)
    write(d, "art/hero.fbx", "m"); write(d, "s.png", "p")
    rc, _, err = record(d, "art/hero.fbx", "s.png", seen="looks ok")
    rc2, _, err2 = record(d, "art/nope.fbx", "s.png")
    report(rc == 1 and ">= 40" in err and rc2 == 1 and "does not exist" in err2, "review.py record rejects short --seen and missing files")

    # 12 loop guard
    d = mkrepo(); hook("start", d); write(d, "art/hero.fbx", "m")
    r = [gate(d)[1] for _ in range(3)]
    ok = r[0].get("decision") == "block" and r[1].get("decision") == "block" and "decision" not in r[2] \
        and "stopping with UNREVIEWED or UNAPPROVED art: art/hero.fbx" in r[2].get("systemMessage", "")
    report(ok, "loop guard: blocks twice, releases on the 3rd identical block with a systemMessage")

    # 13 off switch
    rc, o = gate(d, env={"ART_PIPELINE": "off"})
    report(rc == 0 and "decision" not in o and "OFF" in o.get("systemMessage", ""), "ART_PIPELINE=off: gate says it is off, does not block")

    # 14 override
    d = mkrepo(); hook("start", d)
    write(d, ".art-pipeline.json", json.dumps({"model_globs": ["*.ma"], "review_dir": "rev", "production_paths": []}))
    write(d, "art/a.fbx", "m"); write(d, "art/b.ma", "m")
    rc, o = gate(d)
    ok1 = "art/b.ma" in o.get("reason", "") and "art/a.fbx" not in o["reason"] and "rev/" in o["reason"]
    write(d, "node_modules/x/c.ma", "m")
    ok2 = "node_modules" not in gate(d)[1].get("reason", "")
    report(ok1 and ok2, ".art-pipeline.json overrides globs and review_dir; node_modules excluded")

    # 15 committed since start
    d = mkrepo(); hook("start", d)
    write(d, "art/new.glb", "m"); sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "model")
    rc, o = gate(d)
    report("art/new.glb" in o.get("reason", ""), "a model committed since session start is caught")

    # 16 corrupt ledger -> fail open with message
    d = mkrepo(); hook("start", d); write(d, "art/hero.fbx", "m")
    open(os.path.join(d, ".git", "art-pipeline", "s1.json"), "w").write("{not json")
    rc, out, _ = hook("gate", d)
    o = json.loads(out)
    report(rc == 0 and "decision" not in o and "internal error" in o["systemMessage"] and "NOT run" in o["systemMessage"],
           "gate fails open with a systemMessage on a corrupt ledger")

    # 17 status shares the logic
    d = mkrepo(); hook("start", d); good_setup(d); write(d, "art/other.obj", "m")
    rc, out, _ = run([sys.executable, REVIEW, "status"], cwd=d)
    report(rc == 0 and "PASS  art/hero.fbx" in out and "BLOCK  art/other.obj" in out, "review.py status reports per-model pass/block")

    # doc_check
    def dcrepo(cmd, **kw):
        d = mkrepo(); hook("start", d)
        write(d, ".art-pipeline.json", json.dumps(dict({"doc_check": cmd, "production_paths": []}, **kw)))
        sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "cfg")
        hook("start", d)
        return d
    d = dcrepo("echo ran > ran.txt"); write(d, "docs/scale.md", "x")
    rc, o = gate(d)
    report(o == {} and os.path.exists(os.path.join(d, "ran.txt")), "doc_check: configured check passes when docs changed (ran, silent)")
    d = dcrepo('"%s" -c "print(\'ROSTER-DRIFT\'); raise SystemExit(3)"' % sys.executable.replace("\\", "/")); write(d, "docs/scale.md", "x")
    rc, o = gate(d)
    report(o.get("decision") == "block" and "ROSTER-DRIFT" in o["reason"] and "exited 3" in o["reason"], "doc_check: failing check blocks with its output")
    d = dcrepo("echo ran > ran.txt exit 3"); write(d, "notes.txt", "x")
    rc, o = gate(d)
    report(o == {} and not os.path.exists(os.path.join(d, "ran.txt")), "doc_check: not run when nothing relevant changed")
    d = dcrepo("sleep 5"); write(d, "docs/a.md", "x")
    rc, out, _ = run([sys.executable, "-c", "import sys;sys.path.insert(0,%r);import artlib;artlib.DOC_TIMEOUT=1;import hook;sys.argv=['h','gate'];sys.exit(hook.main(sys.argv))" % HERE],
                     json.dumps({"session_id": "s1", "cwd": d}))
    o = json.loads(out)
    report(rc == 0 and "decision" not in o and "timed out" in o["systemMessage"], "doc_check: timeout fails open with a systemMessage")
    d = mkrepo(); hook("start", d); write(d, "docs/a.md", "x")
    rc, out, _ = hook("gate", d)
    report(rc == 0 and out == "", "doc_check: missing config is silent")
    d = dcrepo("exit 1", doc_check_paths=["data/*"]); write(d, "docs/a.md", "x")
    ok1 = gate(d)[1] == {}
    write(d, "data/x.csv", "x")
    report(ok1 and gate(d)[1].get("decision") == "block", "doc_check_paths overrides the default paths")

    # --- approval gate: no art without a human-approved spec and reference ------------------
    def pre(d, tool, ti, session="s1", env=None):
        rc, out, _ = hook("pre", d, {"tool_name": tool, "tool_input": ti}, session=session, env=env)
        o = json.loads(out) if out.strip() else {}
        h = o.get("hookSpecificOutput") or {}
        return h.get("permissionDecision"), h.get("permissionDecisionReason", "") or o.get("systemMessage", "")

    def after(d, session="s1", env=None):
        rc, out, _ = hook("after", d, {"tool_name": "Bash", "tool_input": {"command": "x"}}, session=session, env=env)
        return json.loads(out) if out.strip() else {}

    def bash(d, cmd, session="s1", env=None):
        """pre, then (if allowed) run the command for real, then after - as Claude Code would."""
        dec, why = pre(d, "Bash", {"command": cmd}, session, env)
        if dec == "deny":
            return dec, why, {}
        # Claude Code runs Bash commands in a POSIX shell; cmd.exe would break mkdir -p and quoting, and on Windows
        # python3 is often the Store stub, so it is swapped for the interpreter running this script.
        sh = shutil.which("bash") or shutil.which("sh")
        run_cmd = cmd.replace("python3", '"%s"' % sys.executable.replace("\\", "/"))
        subprocess.run([sh, "-c", run_cmd] if sh else run_cmd, shell=not sh, cwd=d, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        return dec, why, after(d, session, env)

    REF = "docs/art/reference/powder"

    def item(name, paths, match=None, sound=False):
        write(d, "%s/%s-plate.png" % (REF, name.lower()), "plate of " + name)
        parts = {"model": {"references": [{"file": "%s/%s-plate.png" % (REF, name.lower()),
                                           "source": "de Gheyn 1607, Wikimedia Commons",
                                           "shows": "kit, hat and bandolier of a %s" % name}],
                           "check": ["silhouette matches the plate"]},
                 "animation": {"references": [{"file": "%s/%s-plate.png" % (REF, name.lower()),
                                               "source": "de Gheyn 1607, plate 32",
                                               "shows": "the aim: barrel in the fork, butt at the cheek"}],
                               "key_poses": [{"at": "1.2 s", "ref": "%s/%s-plate.png" % (REF, name.lower()),
                                              "pose": "barrel in the fork, butt at the cheek"}],
                               "check": ["final frame matches the plate"]}}
        if sound:
            write(d, "%s/%s-shot.wav" % (REF, name.lower()), "RIFF")
            parts["sfx"] = {"references": [{"file": "%s/%s-shot.wav" % (REF, name.lower()),
                                            "source": "freesound.org/s/12345 (CC0)",
                                            "shows": "a matchlock firing outdoors"}],
                            "duration_s": 1.4, "check": ["crack then a long tail, as the recording"]}
        it = {"name": name, "paths": paths, "parts": parts}
        if match:
            it["match"] = match
        return it

    def spec(d, sid="powder", items=None, **over):
        sp = {"id": sid, "title": "Powder Age soldiers", "iterations": 2,
              "items": items if items is not None else [item("Musketeer", ["Assets/Anim/musk*"], ["musketeer"])]}
        sp.update(over)
        write(d, "docs/art/specs/%s.json" % sid, json.dumps(sp))
        return sp

    def check(d, sid="powder"):
        return run([sys.executable, APPROVE, "check", sid], cwd=d)

    def ask(d, sid="powder", answer="Approve", session="s1"):
        rc, out, err = check(d, sid)
        q = json.loads(out[out.index("{"):])
        text = q["questions"][0]["question"]
        return hook("answered", d, {"tool_name": "AskUserQuestion", "tool_input": q,
                                    "tool_response": {"questions": q["questions"], "answers": {text: answer}}},
                    session=session), q

    def look(d, name="musketeer", session="s1"):
        hook("seen", d, {"tool_input": {"file_path": os.path.join(d, REF, name + "-plate.png")}}, session=session)

    d = mkrepo(art=False, prod=True); hook("start", d)
    dec, why = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Anim/musk.anim")})
    report(dec == "deny" and "no human-approved item" in why and "approve.py" in why,
           "pre: writing an art asset with no approval is refused, and says how to get one")
    ok = all(pre(d, "Write", {"file_path": os.path.join(d, f)})[0] is None for f in
             ("src/Game.cs", "docs/art/specs/powder.json", "docs/art/reference/powder/a.png"))
    report(ok, "pre: code, specs and reference files are not gated")
    ok = all(pre(d, "Write", {"file_path": os.path.join(d, f)})[0] == "deny" for f in
             ("ui/icons/sword.png", "Assets/Audio/hit.wav", "game/sprites/coin.png", "Assets/VFX/spark.prefab",
              "Shaders/Glow.shader", "Assets/Models/a.fbx"))
    report(ok, "pre: every kind of art is gated by default - sprites, icons, SFX, VFX, shaders, models")

    rc, _, err = check(d)
    bad = item("Musketeer", ["x/*"])
    bad["parts"]["animation"]["key_poses"] = []
    bad["parts"]["model"]["references"] = []
    spec(d, items=[bad])
    rc2, _, err2 = check(d)
    report(rc == 1 and "no spec" in err and rc2 == 1 and "Musketeer model: needs real-world references" in err2
           and "Musketeer animation: needs \"key_poses\"" in err2,
           "check refuses a missing spec, and names the item and part that lack reference or key poses")
    bad = item("Musketeer", ["x/*"], sound=True)
    bad["parts"]["sfx"]["references"][0]["file"] = "%s/musketeer-plate.png" % REF
    bad["parts"]["model"]["check"] = ["a check that runs on far too long " * 5]
    spec(d, items=[bad])
    _, _, err = check(d)
    report("Musketeer sfx: needs at least one audio reference" in err and "10-100 chars" in err,
           "check: a sound needs an audio reference, and every text has a length limit")

    spec(d, items=[item("Musketeer", ["Assets/Anim/musk*"], ["musketeer"], sound=True),
                   item("Pikeman", ["Assets/Anim/pike*"], ["pikeman"])])
    rc, out, _ = check(d)
    sheet_file = os.path.join(d, "docs/art/specs/powder.sheet.html")
    page = open(sheet_file).read() if os.path.exists(sheet_file) else ""
    report(rc == 0 and "art-approve:powder@" in out and "powder.sheet.html" in out and '"Approve"' in out
           and len(json.loads(out[out.index("{"):])["questions"][0]["question"]) < 300,
           "check on a two-item spec writes the sheet and prints a short question that points to it")
    ok = page.count('<section class="item">') == 2 and page.count("data:image/png;base64,") == 6 \
        and "data:audio/wav;base64," in page and page.index(">Model<") < page.index(">Animation<") < page.index(">Sound<")
    report(ok, "sheet: one section per item, reference embedded, parts always in the same order")
    rc, out2, _ = check(d)
    report(open(sheet_file).read() == page, "sheet: the same spec renders the same sheet every time")

    q = json.loads(out[out.index("{"):])
    text = q["questions"][0]["question"]
    dec, why = pre(d, "AskUserQuestion", dict(q, answers={text: "Approve"}))
    report(dec == "deny" and "answered by the human" in why, "pre: an approval question pre-filled with answers is refused")
    open(sheet_file, "a").write("<!-- edited -->")
    dec, why = pre(d, "AskUserQuestion", q)
    check(d)
    dec2, _ = pre(d, "AskUserQuestion", q)
    report(dec == "deny" and "review sheet" in why and dec2 is None,
           "pre: a hand-edited or missing sheet stops the question; a fresh one lets it through")
    write(d, "docs/art/specs/powder.json", open(os.path.join(d, "docs/art/specs/powder.json")).read() + " ")
    dec, why = pre(d, "AskUserQuestion", q)
    report(dec == "deny" and "does not match" in why, "pre: a question whose token is stale is refused")

    check(d)
    (rc, out, _), q = ask(d, answer="Revise")
    report(not os.path.exists(os.path.join(d, "docs/art/approvals/powder.json")) and "NOT approved" in out,
           "answered: 'Revise' writes no approval")
    (rc, out, _), q = ask(d)
    ap = os.path.join(d, "docs/art/approvals/powder.json")
    rec = json.load(open(ap)) if os.path.exists(ap) else {}
    report("APPROVED by the human" in out and rec.get("approved_by") == "human via AskUserQuestion"
           and [i["name"] for i in rec["items"]] == ["Musketeer", "Pikeman"],
           "answered: the human's 'Approve' writes one approval covering both items")

    musk = {"file_path": os.path.join(d, "Assets/Anim/musk.anim")}
    dec, why = pre(d, "Write", musk)
    look(d)
    dec2, _ = pre(d, "Write", musk)
    dec3, why3 = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Anim/pike.anim")})
    report(dec == "deny" and "reference image of Musketeer" in why and dec2 is None and dec3 == "deny"
           and "Pikeman" in why3, "pre: each item unlocks only after one of its own reference images is opened")
    dec, _ = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Other/x.anim")})
    report(dec == "deny", "pre: an approval covers only the paths its items list")
    dec, why = pre(d, "Bash", {"command": "blender -b -P build.py -- --only knight"})
    report(dec == "deny" and "names no approved item" in why, "pre: a build command naming no approved item is refused")
    r = [bash(d, "blender -b -P build.py -- musketeer; mkdir -p Assets/Anim; echo x > Assets/Anim/musk%d.anim" % i)[0] for i in range(3)]
    dec, why = pre(d, "Write", musk)
    look(d, "pikeman")
    dec2, _ = pre(d, "Bash", {"command": "blender -b -P build.py -- pikeman"})
    report(r == [None, None, "deny"] and dec == "deny" and "used all 2 builds" in why and dec2 is None,
           "budget is per item: Musketeer's 2 builds run out, Pikeman's are untouched")
    ask(d)
    dec, _ = pre(d, "Bash", {"command": "blender -b -P build.py -- musketeer"})
    report(dec is None, "a fresh human approval of the same spec starts the budget again")

    dec, why, o = bash(d, "python3 -c \"open('Assets/Anim/pike-new.anim','w').write('x')\"")
    k = [v for kk, v in json.load(open(os.path.join(d, ".git/art-pipeline/s1.json")))["iter"].items() if kk.endswith(":pikeman")]
    note = (o.get("hookSpecificOutput") or {}).get("additionalContext", "")
    report(dec is None and "decision" not in o and os.path.exists(os.path.join(d, "Assets/Anim/pike-new.anim"))
           and sum(k) == 2 and "charged a build to Pikeman" in note and "pike-new.anim" in note,
           "after: a covered file made by an unlisted tool stays, spends that item's budget, and says so")
    dec, why, o = bash(d, "mkdir -p Assets/Audio && echo boom > Assets/Audio/boom.wav")
    q_copy = glob.glob(os.path.join(d, ".git/art-pipeline/quarantine/*/Assets/Audio/boom.wav"))
    report(dec is None and o.get("decision") == "block" and "Assets/Audio/boom.wav" in o.get("reason", "")
           and not os.path.exists(os.path.join(d, "Assets/Audio/boom.wav")) and len(q_copy) == 1,
           "after: art a command makes with no approval is undone at once, and a copy is kept")
    write(d, "Assets/Models/old.fbx", "v1"); sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "m")
    hook("start", d, session="s3"); look(d, session="s3")
    dec, why, o = bash(d, "echo v2 > Assets/Models/old.fbx", session="s3")
    report(o.get("decision") == "block" and open(os.path.join(d, "Assets/Models/old.fbx")).read() == "v1",
           "after: a changed tracked art file is put back to how it was at session start")

    for cmd in ("echo '{}' > docs/art/approvals/powder.json", "sed -i s/2/9/ .art-pipeline.json",
                "python approve.py grant powder", "echo x > .claude/settings.json",
                "claude plugin disable art-pipeline@claude-art-pipeline", "cat .git/art-pipeline/s1.json"):
        r = pre(d, "Bash", {"command": cmd})
        if r[0] != "deny":
            break
    gitok = pre(d, "Bash", {"command": "git add docs/art/approvals/powder.json"})[0] is None
    report(r[0] == "deny" and gitok,
           "pre: Bash cannot touch approvals, the config, plugin settings or the ledger, or disable plugins; git can commit")
    ok = all(pre(d, t, {"file_path": os.path.join(d, f)})[0] == "deny" for t, f in
             (("Edit", "docs/art/approvals/powder.json"), ("Write", ".art-pipeline.json"),
              ("Write", ".claude/settings.json"), ("Write", ".claude/settings.local.json"),
              ("Write", ".git/art-pipeline/s1.json")))
    report(ok, "pre: Write/Edit cannot touch approvals, the config, plugin settings or the ledger")
    rc, _, err = run([sys.executable, APPROVE, "grant", "powder"], cwd=d)
    report(rc == 1 and "real terminal" in err, "approve.py grant refuses without a real terminal")
    rc, o = gate(d)
    report("- Assets/Anim/musk0.anim\n" not in o.get("reason", "") + "\n",  # its frame-sheet line is a later test's
           "gate: art covered by an approval passes")
    write(d, "docs/art/specs/powder.json", open(os.path.join(d, "docs/art/specs/powder.json")).read() + " ")
    dec, why = pre(d, "Write", musk)
    rc, o = gate(d)
    report(dec == "deny" and "changed after it was approved" in why and "Assets/Anim/musk0.anim" in o.get("reason", ""),
           "editing a spec after approval voids it: writes refused, the gate blocks")

    d = mkrepo(art=False, prod=True); hook("start", d); spec(d); check(d)
    dec, why, o = bash(d, "python3 -c \"import os;p='docs/art/appr'+'ovals';os.makedirs(p);open(p+'/powder.json','w').write('{}')\"")
    report(o.get("decision") == "block" and "no human grant wrote it" in o.get("reason", "")
           and not os.path.exists(os.path.join(d, "docs/art/approvals/powder.json")),
           "after: an approval file a script writes is removed at once (copy kept)")
    write(d, "docs/art/approvals/powder.json", json.dumps({"id": "powder"}))
    sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "forged")
    r = [gate(d)[1] for _ in range(4)]
    report(all(x.get("decision") == "block" and "not written by a human grant" in x.get("reason", "") for x in r),
           "gate: a forged approval, even committed, blocks every time and is never released")
    o = after(d)
    report(not os.path.exists(os.path.join(d, "docs/art/approvals/powder.json")) and o.get("decision") == "block",
           "after: a forged approval that was committed is removed from the working tree too")

    d = mkrepo(art=False, prod=True); write(d, "Assets/Audio/wip.wav", "the person's own work")
    hook("start", d)
    dec, why, o = bash(d, "touch Assets/Audio/wip.wav; echo ok")
    report(os.path.exists(os.path.join(d, "Assets/Audio/wip.wav")) and o == {},
           "after: art already changed when the session started is the person's, and is never undone")

    d = mkrepo(art=False, prod=True); hook("start", d); spec(d); check(d); ask(d)
    sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "approved")
    hook("start", d, session="s2"); look(d, session="s2")
    dec, _ = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Anim/musk.anim")}, session="s2")
    report(dec is None, "an approval committed before a session starts is honoured in that session")

    d = mkrepo(art=False, prod=True); hook("start", d)
    open(os.path.join(d, ".git", "art-pipeline", "s1.json"), "w").write("{broken")
    dec, why = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Audio/x.wav")})
    dec2, why2 = pre(d, "Write", {"file_path": os.path.join(d, "src/x.cs")})
    report(dec == "deny" and "internal error" in why and dec2 is None and "UNCHECKED" in why2,
           "pre on an internal error: fails closed for art, open and loud for everything else")

    # the plugin can be installed twice (user and project scope), so each hook may run twice per call
    d = mkrepo(art=False, prod=True); hook("start", d); spec(d); check(d); ask(d); look(d)
    twice = []
    for n in (1, 2):
        cmd = {"command": "blender -b -P build.py -- musketeer"}
        for _ in range(2):
            rc, out, _ = hook("pre", d, {"tool_name": "Bash", "tool_input": cmd, "tool_use_id": "call%d" % n})
            twice.append(json.loads(out)["hookSpecificOutput"]["permissionDecision"] if out.strip() else None)
            hook("after", d, {"tool_name": "Bash", "tool_input": cmd, "tool_use_id": "call%d" % n})
    used = [v for k, v in json.load(open(os.path.join(d, ".git/art-pipeline/s1.json")))["iter"].items() if k.endswith(":musketeer")]
    report(twice == [None] * 4 and used == [2],
           "hooks running twice for one call charge one build, and the last build of a budget is not refused")

    # checks: a check is never a build; movies and exports need a fresh passing one; so does the stop
    def used_builds(d, name="musketeer"):
        led = json.load(open(os.path.join(d, ".git", "art-pipeline", "s1.json")))
        return sum(v for k, v in led["iter"].items() if k.endswith(":" + name))

    d = mkrepo(art=False, prod=True)
    write(d, ".art-pipeline.json", json.dumps({
        "checks": [{"command": r"clip_check\.py", "pass": r"^PASS\b", "fail": r"^FAIL\b"}],
        "gated_commands": [r"render\.py\s+movie"]}))
    sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "cfg")
    hook("start", d)
    spec(d, items=[item("Musketeer", ["Tools/anim/*", "Assets/Anim/musk*"], ["musketeer"])], iterations=3)
    check(d); ask(d); look(d)
    dec, why, o = bash(d, "mkdir -p Tools/anim && echo 'pose = 1' > Tools/anim/clip.py")
    report(dec is None and o == {} and used_builds(d) == 0 and os.path.exists(os.path.join(d, "Tools/anim/clip.py")),
           "after: a Bash edit of an approved item's source code is allowed and is not a build")
    dec, why, o = bash(d, "mkdir -p Assets/Anim && echo x > Assets/Anim/musk.anim")
    report(used_builds(d) == 1 and "charged a build to Musketeer" in (o.get("hookSpecificOutput") or {}).get("additionalContext", ""),
           "after: a command that changes an item's output is charged, and the charge is reported")
    movie = {"command": "python render.py movie musketeer"}
    dec, why = pre(d, "Bash", movie)
    report(dec == "deny" and "no check this session" in why and "clip_check" in why,
           "pre: a movie of an item no check has passed is refused, and names the check to run")

    def checked(cmd, output):
        pre(d, "Bash", {"command": cmd})
        rc, out, _ = hook("after", d, {"tool_name": "Bash", "tool_input": {"command": cmd},
                                       "tool_response": {"stdout": output, "stderr": ""}})
        return (json.loads(out) if out.strip() else {}).get("hookSpecificOutput", {}).get("additionalContext", "")

    note = checked("python clip_check.py musketeer reload", "FAIL  musketeer reload  crossing 41\n")
    dec, why = pre(d, "Bash", movie)
    report(dec == "deny" and "did not pass" in why and "FAIL" in note,
           "a failing check is recorded and reported, and the movie stays refused")
    checked("python clip_check.py musketeer reload", "PASS  musketeer reload\n")
    dec, _ = pre(d, "Bash", movie)
    report(dec is None and used_builds(d) == 1, "a passing check unlocks the movie, and the checks spent no builds")
    dec, why = pre(d, "Bash", {"command": "python render.py movie musketeer aim --res 480 | tail -3"})
    dec2, _ = pre(d, "Bash", {"command": "cd /tmp && python3 render.py movie musketeer reload --res 480 2>&1 | tail -3"})
    report(dec == "deny" and "did not cover aim" in why and dec2 is None,
           "a pass on one clip of an item does not unlock a movie of another clip; flags, paths and pipes are ignored")
    time.sleep(0.02)
    write(d, "Tools/anim/clip.py", "pose = 2")
    dec, why = pre(d, "Bash", movie)
    rc, g = gate(d)
    report(dec == "deny" and "changed after its last passing check" in why and g.get("decision") == "block"
           and "Musketeer (unchecked)" in g.get("reason", ""),
           "editing the source after a pass makes it stale: the movie is refused and the stop is blocked")
    checked("python clip_check.py musketeer reload", "PASS  musketeer reload\n")
    rc, g = gate(d)
    report("Musketeer (unchecked)" not in g.get("reason", ""), "gate: a fresh passing check releases the stop")
    pre(d, "Bash", {"command": "python clip_check.py musketeer reload"})   # exits non-zero: no `after` runs
    dec, why = pre(d, "Bash", movie)
    report(dec == "deny" and "did not finish with a passing result" in why,
           "a check that exits non-zero (no after hook runs) replaces an older pass and keeps the movie refused")
    note = checked("python clip_check.py musketeer reload &", "")
    report("UNKNOWN" in note and pre(d, "Bash", movie)[0] == "deny",
           "a check whose output was not captured counts as unknown, not as a pass")
    for i in range(2):
        bash(d, "echo %d > Assets/Anim/musk%d.anim" % (i, i))
    dec, why = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Anim/musk9.anim")})
    report(dec == "deny" and "charged for:" in why and "Assets/Anim/musk1.anim" in why,
           "a spent budget's refusal lists what each build was charged for")

    # the gate guards the repo a command acts in, not only the session's working directory
    elsewhere = tempfile.mkdtemp(prefix="art-pipeline-elsewhere-")
    TMP.append(elsewhere)

    def pre_from(cwd, tool, ti):
        rc, out, _ = hook("pre", d, {"tool_name": tool, "tool_input": ti, "cwd": cwd})
        o = json.loads(out) if out.strip() else {}
        return (o.get("hookSpecificOutput") or {}).get("permissionDecision")
    fd = d.replace("\\", "/")   # a POSIX shell eats backslashes, so commands name paths with forward slashes
    report(pre_from(elsewhere, "Bash", {"command": "cd %s && python render.py movie musketeer" % fd}) == "deny"
           and pre_from(elsewhere, "Bash", {"command": "python %s/render.py movie musketeer" % fd}) == "deny"
           and pre_from(elsewhere, "Bash", {"command": "git -C %s status" % fd}) is None,
           "pre: a command run from outside the repo (cd into it, or an absolute path) is judged by that repo's rules")
    report(pre_from(elsewhere, "Write", {"file_path": os.path.join(d, "Assets/Other/x.anim")}) == "deny",
           "pre: a Write to an art file in another repo than the working directory is gated by that repo")
    cmd = "cd %s && mkdir -p Assets/Audio && echo boom > Assets/Audio/sneak.wav" % fd
    subprocess.run([shutil.which("bash") or "sh", "-c", cmd], stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    rc, out, _ = hook("after", d, {"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": elsewhere})
    o = json.loads(out) if out.strip() else {}
    report(o.get("decision") == "block" and not os.path.exists(os.path.join(d, "Assets/Audio/sneak.wav")),
           "after: art made by a command that cd'd into the repo is still undone")
    time.sleep(0.02)
    write(d, "Tools/anim/clip.py", "pose = 3")   # stale check, edited while the session sits elsewhere
    rc, out, _ = hook("gate", d, {"cwd": elsewhere})
    o = json.loads(out) if out.strip() else {}
    report(o.get("decision") == "block" and "Musketeer (unchecked)" in o.get("reason", ""),
           "gate: a repo the session worked in from outside it is checked at the stop too")
    rc, out, _ = hook("pre", d, {"tool_name": "Write", "cwd": elsewhere,
                                 "tool_input": {"file_path": os.path.join(FAKE_HOME, ".claude/art-pipeline/s1.repos.json")}})
    report("deny" in out, "pre: the session's repo list cannot be edited")

    # clip reviews: with clip_review_views set, a movie also needs a passing review that shows them
    d = mkrepo(art=False, prod=True)
    write(d, ".art-pipeline.json", json.dumps({
        "checks": [{"command": r"clip_check\.py", "pass": r"^PASS\b", "fail": r"^FAIL\b"}],
        "gated_commands": [r"render\.py\s+movie"], "clip_review_views": ["top"]}))
    sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "cfg")
    hook("start", d)
    spec(d, items=[item("Musketeer", ["Tools/anim/*", "Assets/Anim/musk*"], ["musketeer"])], iterations=3)
    check(d); ask(d); look(d)
    write(d, "Tools/anim/clip.py", "pose = 1")
    checked("python clip_check.py musketeer reload", "PASS  musketeer reload\n")
    movie = {"command": "python render.py movie musketeer reload"}
    dec, why = pre(d, "Bash", movie)
    report(dec == "deny" and "no clip review" in why and "--views top" in why,
           "clip review: a checked clip still needs a review showing the top view before a movie")
    time.sleep(0.02)
    sheet = write(d, "docs/art/sheets/reload.png", "png")

    def clip_rec(*extra, views=("top", "side"), clips=("reload",)):
        return run([sys.executable, REVIEW, "clip", "--item", "Musketeer", "--clips"] + list(clips) + ["--views"]
                   + list(views) + ["--sheet", "docs/art/sheets/reload.png", "--verdict", "pass", "--seen", SEEN_TXT]
                   + list(extra), cwd=d)
    rc, _, err = clip_rec(views=("side", "front"))
    report(rc == 1 and "top view" in err, "review.py clip refuses a review without the views the project requires")
    clip_rec()
    dec, why = pre(d, "Bash", movie)
    see(d, sheet)
    dec2, _ = pre(d, "Bash", movie)
    dec3, why3 = pre(d, "Bash", {"command": "python render.py movie musketeer aim"})
    report(dec == "deny" and "was not opened" in why and dec2 is None and dec3 == "deny",
           "clip review: its sheet must be opened this session, and it covers only the clips it names")
    time.sleep(0.02)
    write(d, "Tools/anim/clip.py", "pose = 2")
    checked("python clip_check.py musketeer reload", "PASS  musketeer reload\n")
    dec, why = pre(d, "Bash", movie)
    report(dec == "deny" and "older than Musketeer's last source edit" in why,
           "clip review: an edit after the review needs a new render and review, even with a fresh check")

    # the build count survives the session: it is kept beside the approval and must be committed
    def gate_as(d, session):
        rc, out, _ = hook("gate", d, session=session)
        return json.loads(out) if out.strip() else {}
    d = mkrepo(art=False, prod=True); hook("start", d, session="s8")
    spec(d); check(d); ask(d, session="s8"); look(d, session="s8")
    sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "approved")
    bash(d, "blender -b -P build.py -- musketeer", session="s8")
    bfile = os.path.join(d, "docs/art/approvals/powder.builds")
    g = gate_as(d, "s8")
    report(os.path.isfile(bfile) and g.get("decision") == "block" and "powder.builds" in g.get("reason", ""),
           "the build count is written beside the approval, and the stop asks for it to be committed")
    sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "builds")
    g = gate_as(d, "s8")
    hook("start", d, session="s9"); look(d, session="s9")
    dec, why = pre(d, "Bash", {"command": "blender -b -P build.py -- musketeer"}, session="s9")
    dec2, why2 = pre(d, "Bash", {"command": "blender -b -P build.py -- musketeer"}, session="s9")
    report("powder.builds" not in g.get("reason", "") and dec is None and dec2 == "deny" and "used all 2" in why2,
           "a new session goes on from the committed count: the 2-build budget is not started again")
    dec, why = pre(d, "Write", {"file_path": bfile}, session="s9")
    report(dec == "deny", "pre: the build count file cannot be written by the agent")

    # a build tool named but not run (git add, grep, a commit message) is not a build
    sys.path.insert(0, HERE)
    import artlib as _al
    rp = _al.run_part
    report("render.py" not in rp("git add tools/render.py && git commit -m 'run render.py movie musketeer'")
           and "render.py" not in rp("grep -n x tools/render.py | head; sed -n 1,5p tools/render.py")
           and "render.py movie" in rp("cd /x && timeout 900 python3 tools/render.py movie musketeer 2>&1 | tail -3")
           and "render.py" in rp('python3 "tools/render.py" stills musketeer')
           and "render.py" in rp("FOO=1 nice python3 tools/render.py stills musketeer"),
           "run_part: only the parts of a command that run count; quoted paths still do, messages do not")
    d2 = mkrepo(art=False, prod=True); hook("start", d2)
    write(d2, ".art-pipeline.json", json.dumps({"producer_commands": [r"tools/render\.py"]}))
    rc, out, _ = hook("pre", d2, {"tool_name": "Bash", "tool_input": {"command": "git add tools/render.py"}})
    rc2, out2, _ = hook("pre", d2, {"tool_name": "Bash", "tool_input": {"command": "python3 tools/render.py stills x"}})
    report(out.strip() == "" and "deny" in out2,
           "pre: git add of a build tool is not a build; running it still is")

    # two sessions in one repo: each one's gate speaks only about the art that session made
    d = mkrepo()
    hook("start", d, session="castle"); hook("start", d, session="loot")
    pre(d, "Write", {"file_path": os.path.join(d, "art/castle.fbx")}, session="castle")
    write(d, "art/castle.fbx", "castle")
    bash(d, "echo tower > art/tower.fbx", session="castle")   # made by a command, not a Write
    pre(d, "Write", {"file_path": os.path.join(d, "art/sword.fbx")}, session="loot")
    write(d, "art/sword.fbx", "sword")
    gc, gl = gate_as(d, "castle").get("reason", ""), gate_as(d, "loot").get("reason", "")
    report("castle.fbx" in gc and "tower.fbx" in gc and "sword.fbx" not in gc,
           "two sessions: the castle session's gate lists only the castle's art")
    report("sword.fbx" in gl and "castle.fbx" not in gl and "tower.fbx" not in gl,
           "two sessions: the loot session's gate lists only the loot art, never the castle's")
    bash(d, "echo x", session="loot")
    report(os.path.isfile(os.path.join(d, "art/castle.fbx")) and os.path.isfile(os.path.join(d, "art/tower.fbx")),
           "two sessions: a command in one session does not undo the other session's art")
    # an approval one session's human grant wrote is not "forged" in the other session
    d = mkrepo(art=False, prod=True); hook("start", d, session="a1"); hook("start", d, session="b1")
    spec(d); check(d); ask(d, session="a1")
    rep = after(d, session="b1")
    report(os.path.isfile(os.path.join(d, "docs/art/approvals/powder.json")) and "no human grant" not in json.dumps(rep),
           "two sessions: another session's human-granted approval is not undone or called forged")

    rc, out, _ = run([sys.executable, APPROVE, "status"], cwd=mkrepo(art=False, prod=True))
    report(rc == 0 and "ledger:" in out, "approve.py status runs in a repo with no specs")

    # frame sheets: a changed clip file, controller or clip import setting needs a Unity and a Blender sheet, opened,
    # and a rest-pose comparison of the clip file against the model with no unexplained mismatch
    d = mkrepo(art=False)
    write(d, "Assets/Anim/hero.controller.meta", "guid 1")
    sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "meta")
    hook("start", d)
    t0 = time.time()
    write(d, "Assets/Anim/hero.controller", "ctrl", mtime=t0 - 100)
    write(d, "Assets/Anim/hero.controller.meta", "guid 1, loop on", mtime=t0 - 100)
    _, o = gate(d)
    r = o.get("reason", "")
    report(o.get("decision") == "block" and "hero.controller (frame sheets)" in r
           and "hero.controller.meta (frame sheets)" in r and "unity_frame_sheets.sh" in r,
           "frame sheets: a changed controller and its import settings block until sheets are rendered")
    us = write(d, "docs/art/sheets/hero.png", "png", mtime=t0 - 50)
    bs = write(d, "docs/art/sheets/hero_blender.png", "png", mtime=t0 - 50)
    write(d, "docs/art/sheets/hero_rest.json", json.dumps({"mismatch": [{"bone": "Hand.R", "deg": 84.9}]}))

    def frames(*extra, covers=("Assets/Anim/hero.controller",)):
        return run([sys.executable, REVIEW, "frames", "--covers"] + list(covers) + [
            "--unity-sheet", "docs/art/sheets/hero.png", "--blender-sheet", "docs/art/sheets/hero_blender.png",
            "--rest-pose", "docs/art/sheets/hero_rest.json", "--verdict", "pass", "--seen", SEEN_TXT] + list(extra), cwd=d)
    rc, _, err = frames()
    report(rc == 1 and "another rest pose" in err and "Hand.R 85 deg" in err,
           "review.py frames refuses a clip file exported on another rest pose than the model")
    rc, _, _ = frames("--rest-ok", "the hand bones differ but nothing is parented to them and Humanoid retargets them")
    see(d, us)
    _, o = gate(d)
    r = o.get("reason", "")
    report(rc == 0 and o.get("decision") == "block" and "blender sheet docs/art/sheets/hero_blender.png was not opened" in r
           and "hero.controller.meta (frame sheets)" in r,
           "frame sheets: the Blender sheet must be opened too, and a record covers only the files it names")
    see(d, bs)
    frames("--rest-ok", "x" * 45, covers=("Assets/Anim/hero.controller", "Assets/Anim/hero.controller.meta"))
    _, o = gate(d)
    # only this repo's files: s1 also stops on the other repos earlier checks worked in
    report("hero.controller" not in o.get("reason", ""), "frame sheets: both sheets opened and the rest pose explained pass")
    write(d, "Assets/Anim/hero.controller", "ctrl 2", mtime=t0 + 10)
    _, o = gate(d)
    report(o.get("decision") == "block" and "older than Assets/Anim/hero.controller" in o.get("reason", ""),
           "frame sheets: an edit after the sheets needs them rendered again")
    write(d, "docs/art/sheets/hero_rest.json", json.dumps({"mismatch": [{"bone": "Greatsword", "deg": 65}]}))
    for rp in glob.glob(os.path.join(d, "docs/art/reviews/*.frames.json")):
        with open(rp) as fh:
            data = json.load(fh)
        data["rest_ok"] = ""
        with open(rp, "w") as fh:
            json.dump(data, fh)
    for p in (us, bs):
        os.utime(p, (t0 + 20, t0 + 20))
    _, o = gate(d)
    report(o.get("decision") == "block" and "Greatsword 65 deg" in o.get("reason", ""),
           "frame sheets: a rest-pose mismatch blocks the stop unless the record explains it")
    d2 = mkrepo(art=False)
    with open(os.path.join(d2, ".art-pipeline.json"), "w", encoding="utf-8-sig") as fh:
        fh.write(json.dumps({"production_paths": [], "anim_globs": []}))
    hook("start", d2, session="bom")  # its own session: s1's other repos are checked at s1's stop too
    write(d2, "Assets/Anim/x.controller", "c")
    rc, out, err = hook("gate", d2, session="bom")
    report(rc == 0 and out.strip() == "" and not err.strip(),
           "a config saved with a byte-order mark loads, and anim_globs: [] turns frame sheets off")

    # --- unattended mode: no human to approve, so art needs no approval; the integrity guards stay ---
    UN = {"ART_PIPELINE": "unattended"}

    def ugate(d):
        rc, out, _ = hook("gate", d, env=UN, session="un1")
        return rc, (json.loads(out) if out.strip() else {})

    d = mkrepo(art=False, prod=True)
    rc, out, _ = hook("start", d, env=UN, session="un1")
    report("UNATTENDED run" in json.loads(out)["hookSpecificOutput"]["additionalContext"],
           "unattended: the session starts by saying nobody will approve or answer")
    musk = {"file_path": os.path.join(d, "Assets/Anim/musk.anim")}
    report(pre(d, "Write", musk, session="un1", env=UN)[0] is None and pre(d, "Write", musk, session="un1")[0] == "deny",
           "unattended: an art write no human approved is allowed, and is still refused without the mode")
    q = {"questions": [{"question": "Which hat?"}]}
    dec, why = pre(d, "AskUserQuestion", q, session="un1", env=UN)
    report(dec == "deny" and "nobody is there to answer" in why and pre(d, "AskUserQuestion", q, session="un1")[0] is None,
           "unattended: AskUserQuestion is refused (nothing waits for a person) and still works in a normal session")
    ok = all(pre(d, "Write", {"file_path": os.path.join(d, f)}, session="un1", env=UN)[0] == "deny" for f in
             ("docs/art/approvals/powder.json", ".art-pipeline.json", ".claude/settings.json"))
    ok = ok and all(pre(d, "Bash", {"command": c}, session="un1", env=UN)[0] == "deny" for c in
                    ("python approve.py grant powder", "sed -i s/2/9/ .art-pipeline.json",
                     "claude plugin disable art-pipeline"))
    report(ok, "unattended: approvals, the config, settings, a grant command and plugin disable stay refused")
    dec, why, o = bash(d, "mkdir -p Assets/Audio && echo boom > Assets/Audio/boom.wav", session="un1", env=UN)
    report(dec is None and not o and os.path.exists(os.path.join(d, "Assets/Audio/boom.wav")),
           "unattended: art a command makes is not undone")
    rc, g = ugate(d)
    report(rc == 0 and "decision" not in g and "UNATTENDED run" in g.get("systemMessage", "")
           and "Assets/Audio/boom.wav" in g["systemMessage"],
           "unattended: the Stop gate lists art made without an approved spec instead of blocking")
    write(d, "docs/art/approvals/powder.json", json.dumps({"id": "powder"}))
    r = [ugate(d)[1] for _ in range(4)]
    report(all(x.get("decision") == "block" and "not written by a human grant" in x.get("reason", "") for x in r),
           "unattended: a forged approval still blocks the stop every time")
    os.remove(os.path.join(d, "docs/art/approvals/powder.json"))
    write(d, "art/hero.fbx", "m")
    g = ugate(d)[1]
    report(g.get("decision") == "block" and "art/hero.fbx" in g.get("reason", ""),
           "unattended: a model with no review record still blocks the stop (the agent can do that alone)")

    # the same mode, switched on by the line `unattended on` typed in chat (house-rules' switch file)
    d = mkrepo(art=False, prod=True)
    cfgdir = tempfile.mkdtemp(prefix="art-pipeline-cfg-")
    TMP.append(cfgdir)
    CFG = {"CLAUDE_CONFIG_DIR": cfgdir}
    sw = {"file_path": os.path.join(d, "Assets/Anim/typed.anim")}
    report(pre(d, "Write", sw, session="ty1", env=CFG)[0] == "deny", "typed unattended: with no switch file art is refused")
    write(d, ".claude/house-rules-mode.json", json.dumps({"unattended": "on"}))
    report(pre(d, "Write", sw, session="ty1", env=CFG)[0] is None
           and pre(d, "AskUserQuestion", {"questions": [{"question": "Which hat?"}]}, session="ty1", env=CFG)[0] == "deny",
           "typed unattended: `unattended on` in the repo's switch file allows art and refuses questions")
    write(d, ".claude/house-rules-mode.json", json.dumps({"unattended": "off"}))
    write(cfgdir, "house-rules-mode.json", json.dumps({"unattended": "on"}))
    report(pre(d, "Write", sw, session="ty1", env=CFG)[0] == "deny",
           "typed unattended: this folder's `off` beats an everywhere `on`")
    os.remove(os.path.join(d, ".claude/house-rules-mode.json"))
    report(pre(d, "Write", sw, session="ty1", env=CFG)[0] is None,
           "typed unattended: an everywhere `on` applies in a folder with no file of its own")

    # 18-20 run.sh
    env_np = {"PATH": "", "ART_PIPELINE_PYTHON": ""}
    for ev, want in (("start", "NOT armed"), ("gate", "did NOT run")):
        rc, out, _ = run([SH, RUN, ev], "", env=env_np)
        try:
            ok = rc == 0 and want in json.loads(out)["systemMessage"]
        except Exception:
            ok = False
        report(ok, f"run.sh {ev}: no interpreter -> systemMessage, exit 0")
    rc, out, _ = run([SH, RUN, "seen"], "", env=env_np)
    report(rc == 0 and out == "", "run.sh seen: no interpreter -> exit 0 (start/gate already announce it)")
    d = mkrepo()
    rc, out, _ = run([SH, RUN, "start"], json.dumps({"session_id": "s1", "cwd": d}))
    report(rc == 0 and "art-pipeline:" in out, "run.sh start with a real interpreter reaches hook.py")

    # the frame-sheet comparison: one camera for both renderers, and compare scores what it lays side by side
    sdir = os.path.join(HERE, "..", "skills", "frame-sheet-compare", "scripts")
    texts = {f: open(os.path.join(sdir, f), encoding="utf-8").read()
             for f in ("unity_frame_sheets.sh", "blender_frame_sheets.py")}
    report(all("frame_camera.txt" in t for t in texts.values()) and os.path.isfile(os.path.join(sdir, "frame_camera.txt")),
           "frame sheets: the Unity and the Blender renderer both take their camera from frame_camera.txt")
    try:
        import numpy as np
        from PIL import Image
    except ImportError:
        print("    (skipped the compare check: it needs numpy and Pillow)")
    else:
        d = tempfile.mkdtemp(prefix="art-pipeline-cmp-")
        TMP.append(d)
        os.makedirs(os.path.join(d, "raw"))
        meta = {"cell": [16, 8], "steps": 1, "views": ["side"], "frame": {"height": 2.0},
                "rows": [{"label": "rest pose"}, {"label": "idle"}]}
        figure = np.full((16, 16, 3), 50, np.uint8)
        figure[2:6, 1:5] = figure[10:14, 1:5] = 200
        moved = figure.copy()
        moved[10:14] = 50
        moved[10:14, 10:14] = 200  # the idle pose's limb is 9 pixels away
        for name, img in (("u", figure), ("b", figure), ("m", moved)):
            Image.fromarray(img).save(os.path.join(d, "raw", name + ".png"))
            with open(os.path.join(d, "raw", name + ".json"), "w", encoding="utf-8") as fh:
                json.dump(dict(meta, name=name), fh)
        pages = os.path.join(sdir, "frame_sheet_pages.py")
        rc_same, out_same, _ = run([sys.executable, pages, "compare", d, "u", "b"])
        rc_diff, out_diff, _ = run([sys.executable, pages, "compare", d, "u", "m"])
        report(rc_same == 0 and "RESULT u vs b: PASS" in out_same and rc_diff == 1
               and "RESULT idle: FAIL worst overlap 0.000" in out_diff and "RESULT rest pose: PASS" in out_diff
               and os.path.isfile(os.path.join(d, "compare_u_1.png")),
               "frame sheets: compare passes identical sheets and fails a pose that moved, naming the clip")

    # reviewer records: skip only the Read requirement
    def reviewer_record(d, name="art-reviewer"):
        now = time.time()
        write(d, "art/hero.fbx", "m", mtime=now - 100)
        sheet = write(d, "docs/art/sheets/hero.png", "png", mtime=now - 50)
        rc, _, err = run([sys.executable, REVIEW, "record", "--model", "art/hero.fbx", "--sheet",
                          "docs/art/sheets/hero.png", "--reviewer", name, "--verdict", "pass", "--seen", SEEN_TXT], cwd=d)
        return rc, err, sheet

    def rv_gate(d):   # own session id: the per-user repo list of session s1 holds repos from earlier checks
        rc, out, _ = hook("gate", d, session="rv")
        return rc, (json.loads(out) if out.strip() else {})

    d = mkrepo(); hook("start", d, session="rv")
    rc_r, err_r, _s = reviewer_record(d)
    rc, o = rv_gate(d)
    report(rc_r == 0 and rc == 0 and o == {}, "reviewer record passes the gate with no Read of the sheet")

    d = mkrepo(); hook("start", d, session="rv")
    rc_r, err_r, sheet = reviewer_record(d)
    write(d, "docs/art/sheets/hero.png", "changed png", mtime=time.time() - 10)
    rc, o = rv_gate(d)
    report(rc_r == 0 and o.get("decision") == "block" and "changed since reviewer art-reviewer" in o["reason"],
           "reviewer record whose sheet changed afterwards is refused")

    d = mkrepo(); hook("start", d, session="rv")
    now = time.time()
    write(d, "art/hero.fbx", "m", mtime=now - 100)
    write(d, "docs/art/sheets/hero.png", "png", mtime=now - 50)
    record(d, "art/hero.fbx", "docs/art/sheets/hero.png")
    rc, o = rv_gate(d)
    report(o.get("decision") == "block" and "not opened" in o["reason"],
           "a record without a reviewer and without a Read is still refused")

    d = mkrepo(); hook("start", d, session="rv")
    now = time.time()
    write(d, "art/hero.fbx", "m", mtime=now - 100)
    write(d, "docs/art/sheets/hero.png", "png", mtime=now - 50)
    rc, _, err = run([sys.executable, REVIEW, "record", "--model", "art/hero.fbx", "--sheet", "docs/art/sheets/hero.png",
                      "--reviewer", "  ", "--verdict", "pass", "--seen", SEEN_TXT], cwd=d)
    report(rc != 0 and "--reviewer" in err and not glob.glob(os.path.join(d, "**", "*.review.json"), recursive=True),
           "an empty --reviewer name is rejected and writes no record")
    # the gate lists only what THIS session changed: art dirty before the session, or before a repo was first used in it,
    # is not this session's, but art written afterwards (or a baseline file changed again) is
    d = mkrepo(art=True, prod=True)
    write(d, "art/theirs.fbx", "someone else's work")
    hook("start", d, session="own")
    rc0, out0, _ = hook("gate", d, session="own")
    report(rc0 == 0 and out0.strip() == "", "gate: art that was already dirty when the session started is not listed")
    write(d, "art/mine.fbx", "made this session")
    rc1, out1, _ = hook("gate", d, session="own")
    report("art/mine.fbx" in out1 and "art/theirs.fbx" not in out1, "gate: art made after the start is listed, the earlier dirty art still is not")
    write(d, "art/theirs.fbx", "someone else changed it again")
    rc2, out2, _ = hook("gate", d, session="own")
    report("art/theirs.fbx" in out2, "gate: a file dirty at the start that changes again is listed")

    home, other = mkrepo(art=True, prod=True), mkrepo(art=True, prod=True)
    write(other, "art/theirs.fbx", "dirty before this session touched the repo")
    hook("start", home, session="two")
    hook("pre", home, {"tool_name": "Bash", "tool_input": {"command": 'git -C "%s" status' % other}}, session="two")
    rc3, out3, _ = hook("gate", home, session="two")
    report("theirs.fbx" not in out3, "gate: a repo first used mid-session is baselined, its earlier dirty art is not listed")
    write(other, "art/mine.fbx", "made after the baseline")
    rc4, out4, _ = hook("gate", home, session="two")
    report("art/mine.fbx" in out4 and "theirs.fbx" not in out4, "gate: art made in that repo afterwards is listed")

    # Commits that ARRIVE after the session starts (a merge, a fast-forward pull) are another branch's work, not this session's, however
    # many art files they carry. Only a commit the session itself makes is its work.
    OLD = "2020-01-01T12:00:00"
    d = mkrepo(art=True, prod=True)
    sh_git(d, "checkout", "-q", "-b", "other")
    write(d, "art/merged.fbx", "made on another branch, long before this session")
    sh_git(d, "add", "-A")
    commit_at(d, "other branch art", OLD)
    sh_git(d, "checkout", "-q", "-")
    hook("start", d, session="mrg")
    sh_git(d, "merge", "-q", "--no-ff", "-m", "merge other", "other")
    rc, out, _ = hook("gate", d, session="mrg")
    report("art/merged.fbx" not in out, "gate: art that arrives by merging a branch after the session starts is not listed")
    write(d, "art/own.fbx", "made this session")
    sh_git(d, "add", "-A")
    sh_git(d, "commit", "-qm", "own art")
    rc, out, _ = hook("gate", d, session="mrg")
    report("art/own.fbx" in out and "art/merged.fbx" not in out,
           "gate: art the session commits itself after a merge is listed, the merged-in art still is not")

    d = mkrepo(art=True, prod=True)
    sh_git(d, "checkout", "-q", "-b", "ahead")
    write(d, "art/pulled.fbx", "someone else's commit, fast-forwarded in")
    sh_git(d, "add", "-A")
    commit_at(d, "ahead art", OLD)
    sh_git(d, "checkout", "-q", "-")
    hook("start", d, session="ff")
    sh_git(d, "merge", "-q", "--ff-only", "ahead")
    rc, out, _ = hook("gate", d, session="ff")
    report("art/pulled.fbx" not in out, "gate: art that arrives by a fast-forward pull after the session starts is not listed")

    # a ledger written before `began` existed has no start time: a merge is still left out (first-parent), a commit of the session's own still counts
    d = mkrepo(art=True, prod=True)
    sh_git(d, "checkout", "-q", "-b", "other")
    write(d, "art/merged.fbx", "made on another branch")
    sh_git(d, "add", "-A")
    commit_at(d, "other branch art", OLD)
    sh_git(d, "checkout", "-q", "-")
    hook("start", d, session="oldled")
    ledger = glob.glob(os.path.join(d, ".git", "art-pipeline", "*.json"))[0]
    with open(ledger) as fh:
        led = json.load(fh)
    led.pop("began", None)
    with open(ledger, "w") as fh:
        json.dump(led, fh)
    sh_git(d, "merge", "-q", "--no-ff", "-m", "merge other", "other")
    write(d, "art/own.fbx", "made this session")
    sh_git(d, "add", "-A")
    sh_git(d, "commit", "-qm", "own art")
    rc, out, _ = hook("gate", d, session="oldled")
    report("art/own.fbx" in out and "art/merged.fbx" not in out,
           "gate: a ledger from before `began` existed still leaves merged-in art out and lists the session's own commit")
finally:
    for t in TMP:
        shutil.rmtree(t, ignore_errors=True)

print("\n" + "=" * 42)
if FAILURES:
    print(f"RESULT: {FAILURES} of {STEP} checks FAILED")
    sys.exit(1)
print(f"RESULT: all {STEP} checks passed")
