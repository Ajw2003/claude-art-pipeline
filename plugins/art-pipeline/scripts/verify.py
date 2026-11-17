#!/usr/bin/env python3
"""verify.py - proves art-pipeline's hooks do what they claim.

    python plugins/art-pipeline/scripts/verify.py

Numbered PASS/FAIL lines, exit 0 on all-pass / 1 on any failure. Stdlib only. Builds throwaway
git repos with subprocess git.
"""

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


def run(args, payload="", env=None, cwd=None):
    e = dict(os.environ)
    e.pop("ART_PIPELINE", None)
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
        and "stopping with UNREVIEWED models: art/hero.fbx" in r[2].get("systemMessage", "")
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
    d = dcrepo("echo ROSTER-DRIFT; exit 3"); write(d, "docs/scale.md", "x")
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
    def pre(d, tool, ti, session="s1"):
        rc, out, _ = hook("pre", d, {"tool_name": tool, "tool_input": ti}, session=session)
        o = json.loads(out) if out.strip() else {}
        dec = (o.get("hookSpecificOutput") or {}).get("permissionDecision")
        return dec, (o.get("hookSpecificOutput") or {}).get("permissionDecisionReason", "") or o.get("systemMessage", "")

    def spec(d, sid="aim", **over):
        write(d, "docs/art/reference/%s/plate.png" % sid, "real plate")
        sp = {"id": sid, "kind": "animation", "summary": "musketeer brings the musket to the aim on a rest",
              "references": [{"file": "docs/art/reference/%s/plate.png" % sid, "source": "de Gheyn 1607, plate 32",
                              "shows": "the musket laid in the rest's fork, butt at the cheek"}],
              "key_poses": [{"at": "0.8 s", "ref": "docs/art/reference/%s/plate.png" % sid,
                             "pose": "left hand on the rest below the fork, right at the stock"}],
              "acceptance": ["barrel lies in the fork as in the plate"], "paths": ["Assets/Anim/*"],
              "match": ["musketeer"], "iterations": 2}
        sp.update(over)
        write(d, "docs/art/specs/%s.json" % sid, json.dumps(sp))
        return sp

    def ask(d, sid="aim", answer="Approve", session="s1"):
        rc, out, _ = run([sys.executable, APPROVE, "check", sid], cwd=d)
        q = json.loads(out[out.index("{"):])
        text = q["questions"][0]["question"]
        return hook("answered", d, {"tool_name": "AskUserQuestion", "tool_input": q,
                                    "tool_response": {"questions": q["questions"], "answers": {text: answer}}},
                    session=session), q

    d = mkrepo(art=False, prod=True); hook("start", d)
    dec, why = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Anim/aim.anim")})
    report(dec == "deny" and "no human-approved spec" in why and "approve.py" in why,
           "pre: writing an art asset with no approval is refused, and says how to get one")
    ok = all(pre(d, "Write", {"file_path": os.path.join(d, f)})[0] is None for f in
             ("src/Game.cs", "docs/art/specs/aim.json", "docs/art/reference/aim/plate.png"))
    report(ok, "pre: code, specs and reference files are not gated")
    ok = all(pre(d, "Write", {"file_path": os.path.join(d, f)})[0] == "deny" for f in
             ("ui/icons/sword.png", "Assets/Audio/hit.wav", "game/sprites/coin.png", "Assets/VFX/spark.prefab",
              "Shaders/Glow.shader", "Assets/Models/a.fbx"))
    report(ok, "pre: every kind of art is gated by default - sprites, icons, SFX, VFX, shaders, models")
    rc, _, err = run([sys.executable, APPROVE, "check", "aim"], cwd=d)
    spec(d, references=[], key_poses=[])
    rc2, _, err2 = run([sys.executable, APPROVE, "check", "aim"], cwd=d)
    report(rc == 1 and "no spec" in err and rc2 == 1 and "real-world reference" in err2 and "key_poses" in err2,
           "approve.py check refuses a missing spec and one without reference or key poses")
    spec(d, kind="sprite", references=[{"file": "docs/art/reference/aim/a.wav", "source": "freesound.org/x",
                                        "shows": "nothing visual at all here"}])
    write(d, "docs/art/reference/aim/a.wav", "w")
    _, _, err = run([sys.executable, APPROVE, "check", "aim"], cwd=d)
    report("image reference" in err, "approve.py check: a visual asset needs an image reference")
    spec(d)
    rc, out, _ = run([sys.executable, APPROVE, "check", "aim"], cwd=d)
    report(rc == 0 and "art-approve:aim@" in out and '"Approve"' in out, "approve.py check prints the approval question with its token")
    q = json.loads(out[out.index("{"):])
    text = q["questions"][0]["question"]
    dec, why = pre(d, "AskUserQuestion", dict(q, answers={text: "Approve"}))
    report(dec == "deny" and "answered by the human" in why, "pre: an approval question pre-filled with answers is refused")
    dec, _ = pre(d, "AskUserQuestion", q)
    write(d, "docs/art/specs/aim.json", open(os.path.join(d, "docs/art/specs/aim.json")).read() + " ")
    dec2, why2 = pre(d, "AskUserQuestion", q)
    report(dec is None and dec2 == "deny" and "does not match" in why2, "pre: a question whose token is stale is refused")
    spec(d)
    (rc, out, _), q = ask(d, answer="Revise")
    report(not os.path.exists(os.path.join(d, "docs/art/approvals/aim.json")) and "NOT approved" in out,
           "answered: 'Revise' writes no approval")
    (rc, out, _), q = ask(d)
    ap = os.path.join(d, "docs/art/approvals/aim.json")
    report(os.path.exists(ap) and "APPROVED by the human" in out and json.load(open(ap))["approved_by"] == "human via AskUserQuestion",
           "answered: the human's 'Approve' writes the approval record")
    target = {"file_path": os.path.join(d, "Assets/Anim/aim.anim")}
    dec, why = pre(d, "Write", target)
    see(d, os.path.join(d, "docs/art/reference/aim/plate.png"))
    dec2, _ = pre(d, "Write", target)
    report(dec == "deny" and "open a reference image" in why and dec2 is None,
           "pre: an approved asset is still refused until its reference image has been opened, then allowed")
    dec, _ = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Other/x.anim")})
    report(dec == "deny", "pre: an approval covers only the paths its spec lists")
    blend = {"command": "blender -b -P build.py -- --only knight"}
    dec, why = pre(d, "Bash", blend)
    report(dec == "deny" and "names no asset" in why, "pre: a build command naming no approved asset is refused")
    r = [pre(d, "Bash", {"command": "blender -b -P build.py -- --only musketeer"})[0] for _ in range(3)]
    dec, why = pre(d, "Write", target)
    report(r == [None, None, "deny"] and dec == "deny" and "used all 2 builds" in why,
           "pre: the build budget allows exactly its count, then refuses builds and edits until the human re-approves")
    ask(d)
    dec, _ = pre(d, "Bash", {"command": "blender -b -P build.py -- --only musketeer"})
    report(dec is None, "a fresh human approval of the same spec starts the budget again")
    for cmd in ("echo '{}' > docs/art/approvals/aim.json", "sed -i s/2/9/ .art-pipeline.json",
                "python approve.py grant aim"):
        r = pre(d, "Bash", {"command": cmd})
        if r[0] != "deny":
            break
    gitok = pre(d, "Bash", {"command": "git add docs/art/approvals/aim.json"})[0] is None
    report(r[0] == "deny" and gitok, "pre: Bash cannot write approvals or the config or run grant; git can still commit them")
    dec, _ = pre(d, "Edit", {"file_path": ap})
    dec2, _ = pre(d, "Write", {"file_path": os.path.join(d, ".art-pipeline.json")})
    report(dec == "deny" and dec2 == "deny", "pre: Write/Edit cannot touch approvals or the config, even to create it")
    rc, _, err = run([sys.executable, APPROVE, "grant", "aim"], cwd=d)
    report(rc == 1 and "real terminal" in err, "approve.py grant refuses without a real terminal")
    write(d, "Assets/Anim/aim.anim", "clip")
    rc, o = gate(d)
    report("decision" not in o or "Assets/Anim/aim.anim" not in o.get("reason", ""), "gate: an art file covered by a usable approval passes")
    write(d, "docs/art/specs/aim.json", open(os.path.join(d, "docs/art/specs/aim.json")).read() + " ")
    dec, why = pre(d, "Write", target)
    rc, o = gate(d)
    report(dec == "deny" and "changed after it was approved" in why and "Assets/Anim/aim.anim" in o.get("reason", ""),
           "editing a spec after approval voids it: writes refused, the gate blocks")

    d = mkrepo(art=False, prod=True); hook("start", d); spec(d)
    write(d, "docs/art/approvals/aim.json", json.dumps({"id": "aim"}))
    write(d, "Assets/Anim/aim.anim", "clip")
    see(d, os.path.join(d, "docs/art/reference/aim/plate.png"))
    dec, why = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Anim/aim.anim")})
    rc, o = gate(d)
    report(dec == "deny" and "not written by a human grant" in o.get("reason", "") and "Assets/Anim/aim.anim" in o["reason"],
           "a forged approval file is worthless: writes refused, the gate names it and the uncovered asset")

    d = mkrepo(art=False, prod=True); hook("start", d); spec(d); ask(d)
    sh_git(d, "add", "-A"); sh_git(d, "commit", "-qm", "approved")
    hook("start", d, session="s2")
    see2 = hook("seen", d, {"tool_input": {"file_path": os.path.join(d, "docs/art/reference/aim/plate.png")}}, session="s2")
    dec, _ = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Anim/aim.anim")}, session="s2")
    report(dec is None, "an approval committed before a session starts is honoured in that session")

    d = mkrepo(art=False, prod=True); hook("start", d)
    open(os.path.join(d, ".git", "art-pipeline", "s1.json"), "w").write("{broken")
    dec, why = pre(d, "Write", {"file_path": os.path.join(d, "Assets/Audio/x.wav")})
    dec2, why2 = pre(d, "Write", {"file_path": os.path.join(d, "src/x.cs")})
    report(dec == "deny" and "internal error" in why and dec2 is None and "UNCHECKED" in why2,
           "pre on an internal error: fails closed for art, open and loud for everything else")

    rc, out, _ = run([sys.executable, APPROVE, "status"], cwd=mkrepo(art=False, prod=True))
    report(rc == 0 and "ledger:" in out, "approve.py status runs in a repo with no specs")

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
finally:
    for t in TMP:
        shutil.rmtree(t, ignore_errors=True)

print("\n" + "=" * 42)
if FAILURES:
    print(f"RESULT: {FAILURES} of {STEP} checks FAILED")
    sys.exit(1)
print(f"RESULT: all {STEP} checks passed")
