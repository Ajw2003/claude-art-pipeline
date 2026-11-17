#!/usr/bin/env python3
"""approve.py - human approval of art specs. Shares artlib with the hooks. Stdlib only.

  approve.py check ID    validate docs/art/specs/ID.json, write its review sheet
                         (docs/art/specs/ID.sheet.html) and print the AskUserQuestion to send
  approve.py status      every spec, every approved item, and whether each can be built now
  approve.py grant ID    the HUMAN's route from a real terminal; refuses without one
Run from inside the repo."""

import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artlib  # noqa: E402
import sheet  # noqa: E402


def question(root, cfg, sid, spec):
    """Short on purpose: the sheet carries the detail, laid out the same way every time."""
    names = ", ".join(it["name"] for it in spec["items"])
    text = ("%s\nApprove \"%s\"? Review sheet: %s/%s.sheet.html\nItems: %s\nBudget: %d builds per item." % (
        artlib.spec_token(root, cfg, sid), spec["title"], cfg["spec_dir"], sid, names,
        spec.get("iterations", artlib.DEFAULT_ITERATIONS)))
    return {"questions": [{"question": text, "header": "Art spec", "multiSelect": False, "options": [
        {"label": "Approve", "description": "The reference and checks are right. Build within the budget."},
        {"label": "Revise", "description": "Do not build. Say what to change."}]}]}


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
                print("spec %s: %s" % (f[:-5], "ready to ask" if not probs else "INCOMPLETE"))
                for p in probs:
                    print("    - " + p)
        for sid, rec, pr in artlib.load_approvals(root, cfg, led):
            if rec is None or pr:
                print("approval %s: NOT USABLE: %s" % (sid, "; ".join(pr)))
                continue
            for it in rec["items"]:
                why = artlib.usable(root, rec, it, led)
                used = led["iter"].get(artlib.budget_key(rec, it), 0)
                print("approval %s / %s: %s" % (sid, it["name"], "usable, %d of %d builds used" % (used, rec["iterations"])
                                                 if not why else "waiting: " + "; ".join(why)))
        return 0
    sid = argv[2]
    spec, probs = artlib.validate_spec(root, cfg, sid)
    if probs:
        print("approve.py: spec %s is not ready for a human (%d problems):" % (sid, len(probs)), file=sys.stderr)
        for p in probs:
            print("  - " + p, file=sys.stderr)
        return 1
    if cmd == "check":
        try:
            page = sheet.render(root, cfg, sid, spec)
        except ValueError as exc:
            print("approve.py: " + str(exc), file=sys.stderr)
            return 1
        sp = artlib.sheet_path(root, cfg, sid)
        with open(sp, "w", encoding="utf-8") as fh:
            fh.write(page)
        print("Spec %s is complete. Review sheet: %s" % (sid, os.path.relpath(sp, root).replace(os.sep, "/")))
        print("1. Show the human the sheet (send the file, or publish it as a page) and commit it.")
        print("2. Ask with exactly this AskUserQuestion input (do not add \"answers\"):")
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
    if not sheet.is_current(root, cfg, sid, spec):
        print("The review sheet is missing or out of date: run approve.py check %s first, then open it." % sid)
        return 1
    print(question(root, cfg, sid, spec)["questions"][0]["question"])
    out, inp = (tty, tty) if tty else (sys.stdout, sys.stdin)
    out.write("\nOpen the review sheet first. Type the spec id (%s) to approve it, anything else to refuse: " % sid)
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
