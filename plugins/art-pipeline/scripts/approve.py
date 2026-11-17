#!/usr/bin/env python3
"""approve.py - human approval of art specs. Shares artlib with the hooks. Stdlib only.

  approve.py check ID    validate docs/art/specs/ID.json; print the AskUserQuestion that asks the human
  approve.py status      every spec and approval, and whether each can be built from right now
  approve.py grant ID    the HUMAN's route from a real terminal; refuses without one
Run from inside the repo."""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artlib  # noqa: E402


def question(root, cfg, sid, spec):
    refs = "; ".join("%s (%s): %s" % (r["file"], r["source"], r["shows"]) for r in spec["references"])
    poses = "".join("\nKey pose at %s, from %s: %s" % (k["at"], k["ref"], k["pose"]) for k in spec.get("key_poses", []))
    text = ("%s\nApprove this %s spec before anything is made?\n%s\nReference: %s%s\nYou will check: %s\n"
            "Writes: %s\nBuild budget: %d builds, then it comes back to you." % (
                artlib.spec_token(root, cfg, sid), spec["kind"], spec["summary"], refs, poses,
                "; ".join(spec["acceptance"]), ", ".join(spec["paths"]),
                spec.get("iterations", artlib.DEFAULT_ITERATIONS)))
    return {"questions": [{"question": text, "header": "Art spec", "multiSelect": False, "options": [
        {"label": "Approve", "description": "The reference and spec are right; build it within the budget."},
        {"label": "Revise", "description": "Do not build. Say what to change in the reference or spec."}]}]}


def latest_ledger(gitdir):
    leds = glob.glob(os.path.join(gitdir, "art-pipeline", "*.json"))
    return max(leds, key=os.path.getmtime) if leds else ""


def main(argv):
    if len(argv) < 2 or argv[1] not in ("check", "status", "grant") or (argv[1] != "status" and len(argv) != 3):
        print(__doc__.strip(), file=sys.stderr)
        return 2
    info = artlib.repo_info(os.getcwd())
    if not info:
        print("approve.py: not inside a git repo", file=sys.stderr)
        return 2
    root, gitdir = info
    cfg = artlib.load_config(root)
    cmd = argv[1]
    if cmd == "status":
        lp = latest_ledger(gitdir)
        led = artlib.load_ledger(lp) if lp else artlib.load_ledger("")
        print("ledger: %s" % (os.path.basename(lp)[:-5] if lp else "(none)"))
        d = os.path.join(root, cfg["spec_dir"])
        for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
            if f.endswith(".json"):
                _, probs = artlib.validate_spec(root, cfg, f[:-5])
                print("spec %-28s %s" % (f[:-5], "ready to ask" if not probs else "INCOMPLETE: " + "; ".join(probs)))
        for sid, rec, pr in artlib.load_approvals(root, cfg, led):
            pr = pr + (artlib.usable(root, rec, led) if rec else [])
            used = led["iter"].get(rec["_sha"], 0) if rec else 0
            print("approval %-24s %s" % (sid, ("usable, %d of %d builds used" % (used, rec["iterations"]))
                                            if not pr else "NOT USABLE: " + "; ".join(pr)))
        return 0
    sid = argv[2]
    spec, probs = artlib.validate_spec(root, cfg, sid)
    if probs:
        print("approve.py: spec %s is not ready for a human:" % sid, file=sys.stderr)
        for p in probs:
            print("  - " + p, file=sys.stderr)
        return 1
    if cmd == "check":
        print("Spec %s is complete. Ask the human with exactly this AskUserQuestion input "
              "(do not add \"answers\"):" % sid)
        print(json.dumps(question(root, cfg, sid, spec), indent=2))
        return 0
    # grant: a person at a real terminal types the id back
    try:
        tty = open("/dev/tty", "r+") if os.name != "nt" else None
    except OSError:
        tty = None
    if not sys.stdin.isatty() or (os.name != "nt" and tty is None):
        print("approve.py grant needs a real terminal: it is the human's command, not the agent's.", file=sys.stderr)
        return 1
    print(question(root, cfg, sid, spec)["questions"][0]["question"])
    out, inp = (tty, tty) if tty else (sys.stdout, sys.stdin)
    out.write("\nType the spec id (%s) to approve it, anything else to refuse: " % sid)
    out.flush()
    if inp.readline().strip() != sid:
        print("Not approved.")
        return 1
    h = artlib.write_approval(root, cfg, artlib.make_approval(root, cfg, sid, spec, "human at a terminal", "typed id"))
    for lp in glob.glob(os.path.join(gitdir, "art-pipeline", "*.json")):
        led = artlib.load_ledger(lp)
        led["granted"].append(h)
        artlib.save_ledger(lp, led)
    print("Approved: %s/%s.json. Commit it." % (cfg["approval_dir"], sid))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
