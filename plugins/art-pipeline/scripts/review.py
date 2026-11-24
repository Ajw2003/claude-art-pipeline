#!/usr/bin/env python3
"""review.py - write review records and show gate status. Shares artlib with the Stop gate.

  review.py record --model PATH --sheet PNG --verdict pass|fail|waived --seen "TEXT"
  review.py clip --item NAME --clips C [C ...] --views top side ... --sheet PNG --verdict pass --seen "TEXT"
  review.py frames --covers CLIPFILE [...] --unity-sheet PNG --blender-sheet PNG --rest-pose JSON --verdict pass --seen "TEXT"
  review.py status
Run from inside the repo. Stdlib only."""

import argparse
import glob
import json
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artlib  # noqa: E402


def rel(root, p):
    return os.path.relpath(os.path.abspath(p), root).replace(os.sep, "/")


def main(argv):
    ap = argparse.ArgumentParser(prog="review.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    r = sub.add_parser("record")
    r.add_argument("--model", required=True)
    r.add_argument("--sheet", required=True)
    r.add_argument("--verdict", required=True, choices=["pass", "fail", "waived"])
    r.add_argument("--seen", required=True)
    r.add_argument("--reviewer", default=None, help="name of the separate reviewer agent that judged the sheet")
    c = sub.add_parser("clip", help="record a review of an animation clip (needed before a movie or "
                                     "export when the project sets clip_review_views)")
    c.add_argument("--item", required=True, help="the approved item's name, as in its spec")
    c.add_argument("--clips", nargs="+", required=True, help="the clips the sheet shows")
    c.add_argument("--views", nargs="+", required=True, help="the views the sheet shows, e.g. top side front")
    c.add_argument("--sheet", required=True)
    c.add_argument("--verdict", required=True, choices=["pass", "fail", "waived"])
    c.add_argument("--seen", required=True)
    c.add_argument("--reviewer", default=None, help="name of the separate reviewer agent that judged the sheet")
    f = sub.add_parser("frames", help="record a look at a clip file's frame sheets, Unity and Blender (needed at the "
                                       "stop for every changed clip file, controller or clip import setting)")
    f.add_argument("--covers", nargs="+", required=True, help="the clip files and controllers the sheets show")
    f.add_argument("--unity-sheet", required=True)
    f.add_argument("--blender-sheet", required=True)
    f.add_argument("--rest-pose", required=True, help="the <name>_rest.json blender_frame_sheets.py wrote")
    f.add_argument("--rest-ok", default="", help="why a rest-pose mismatch it reports does no harm")
    f.add_argument("--verdict", required=True, choices=["pass", "fail"])
    f.add_argument("--seen", required=True)
    f.add_argument("--reviewer", default=None, help="name of the separate reviewer agent that judged the sheets")
    sub.add_parser("status")
    a = ap.parse_args(argv[1:])
    if a.cmd != "status" and a.reviewer is not None and not a.reviewer.strip():
        print("review.py: --reviewer must be a non-empty name (got an empty or blank one); no record written",
              file=sys.stderr)
        return 1
    info = artlib.repo_info(os.getcwd())
    if not info:
        print("review.py: not inside a git repo", file=sys.stderr)
        return 2
    root, gitdir = info
    cfg = artlib.load_config(root)
    if a.cmd == "clip":
        sheet = rel(root, a.sheet)
        errs = []
        if not os.path.isfile(os.path.join(root, sheet)):
            errs.append("sheet %s does not exist" % sheet)
        if len(a.seen.strip()) < artlib.MIN_SEEN:
            errs.append("--seen must be >= %d chars (say what you saw)" % artlib.MIN_SEEN)
        lack = [v for v in cfg.get("clip_review_views") or [] if v.lower() not in {x.lower() for x in a.views}]
        if lack:
            errs.append("this project's clip reviews must show the %s view (--views)" % ", ".join(lack))
        if errs:
            print("review.py: " + "; ".join(errs), file=sys.stderr)
            return 1
        d = os.path.join(root, cfg["review_dir"])
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, artlib.clip_record_name(a.item, a.clips))
        with open(path, "w", encoding="utf-8") as fh:
            crec = {"item": a.item, "clips": a.clips, "views": a.views, "sheet": sheet, "verdict": a.verdict,
                    "seen": a.seen, "date": artlib.now()}
            if a.reviewer is not None:
                crec["reviewer"] = a.reviewer.strip()
                crec["sheet_sha256"] = artlib.file_sha256(os.path.join(root, sheet))
            json.dump(crec, fh, indent=2)
            fh.write("\n")
        print(path)
        return 0
    if a.cmd == "frames":
        rec = {"covers": [rel(root, c) for c in a.covers], "unity_sheet": rel(root, a.unity_sheet),
               "blender_sheet": rel(root, a.blender_sheet), "rest_pose": rel(root, a.rest_pose),
               "rest_ok": a.rest_ok, "verdict": a.verdict, "seen": a.seen, "date": artlib.now()}
        errs = ["%s does not exist" % p for p in rec["covers"] + [rec["unity_sheet"], rec["blender_sheet"]]
                if not os.path.isfile(os.path.join(root, p))]
        if len(a.seen.strip()) < artlib.MIN_SEEN:
            errs.append("--seen must be >= %d chars (say what you saw)" % artlib.MIN_SEEN)
        errs += artlib.rest_pose_problems(root, rec)
        if not errs and a.reviewer is not None:
            rec["reviewer"] = a.reviewer.strip()
            rec["unity_sheet_sha256"] = artlib.file_sha256(os.path.join(root, rec["unity_sheet"]))
            rec["blender_sheet_sha256"] = artlib.file_sha256(os.path.join(root, rec["blender_sheet"]))
        if errs:
            print("review.py: " + "; ".join(errs), file=sys.stderr)
            return 1
        d = os.path.join(root, cfg["review_dir"])
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, artlib.frames_record_name(rec["covers"]))
        with open(path, "w", encoding="utf-8") as fh:
            json.dump(rec, fh, indent=2)
            fh.write("\n")
        print(path)
        return 0
    if a.cmd == "record":
        model, sheet = rel(root, a.model), rel(root, a.sheet)
        errs = []
        if not os.path.isfile(os.path.join(root, model)):
            errs.append("model %s does not exist" % model)
        if not os.path.isfile(os.path.join(root, sheet)):
            errs.append("sheet %s does not exist" % sheet)
        if len(a.seen.strip()) < artlib.MIN_SEEN:
            errs.append("--seen must be >= %d chars (say what you saw)" % artlib.MIN_SEEN)
        if errs:
            print("review.py: " + "; ".join(errs), file=sys.stderr)
            return 1
        d = os.path.join(root, cfg["review_dir"])
        os.makedirs(d, exist_ok=True)
        path = os.path.join(d, artlib.record_name(model))
        with open(path, "w", encoding="utf-8") as fh:
            mrec = {"model": model, "sheet": sheet, "verdict": a.verdict, "seen": a.seen,
                    "date": artlib.now()}
            if a.reviewer is not None:
                mrec["reviewer"] = a.reviewer.strip()
                mrec["sheet_sha256"] = artlib.file_sha256(os.path.join(root, sheet))
            json.dump(mrec, fh, indent=2)
            fh.write("\n")
        print(path)
        return 0
    # status: newest ledger stands in for "this session"
    leds = glob.glob(os.path.join(gitdir, "art-pipeline", "*.json"))
    sid = os.path.basename(max(leds, key=os.path.getmtime))[:-5] if leds else ""
    _, _, res, bad = artlib.evaluate(root, gitdir, sid)
    print("ledger: %s" % (sid or "(none - nothing counts as seen)"))
    if not res:
        print("no changed models")
    who = {}
    for suf in (None, ".frames.json"):
        recs, _ = artlib.load_records(root, cfg, suffix=suf) if suf else artlib.load_records(root, cfg)
        for r in recs:
            if artlib.reviewer_of(r):
                for k in [r.get("model")] + list(r.get("covers") or []):
                    if isinstance(k, str):
                        who.setdefault(k, set()).add(artlib.reviewer_of(r))
    for m, st, pr in res:
        label = {"fail": "BLOCK", "timeout": "UNCHECKED", "unapproved": "UNAPPROVED"}.get(st, "PASS")
        print("%s  %s" % (label, m) + ("  [waived]" if st == "waived" else "")
              + ("  [reviewed by %s]" % ", ".join(sorted(who.get(m.replace(" (frame sheets)", ""), ()))) if not pr and who.get(m.replace(" (frame sheets)", "")) else ""))
        for p in pr:
            print("      - " + p)
    for b in bad:
        print("unreadable record: " + b)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
