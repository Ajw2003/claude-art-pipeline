#!/usr/bin/env python3
"""Turns the raw frame sheets that unity_frame_sheets.cs and blender_frame_sheets.py write into pages to look at.

  frame_sheet_pages.py label <dir>      every <dir>/raw/<name>.png + .json -> <dir>/<name>.png with clip names
                                        down the left and the view and moment across the top
  frame_sheet_pages.py pages <dir> [--clips idle walk run] [--frames 0 2] [--per-page 6]
                                        <dir>/overview_<n>.png: per sheet, the rest pose and the chosen moments of
                                        the chosen clips (a clip is the first row whose name contains the word),
                                        three-quarter view, a few sheets per page so each reads at full size
  frame_sheet_pages.py probes <dir>     <dir>/probes.md: the bone gap and bone direction at each clip's first
                                        frame, from every sheet, Unity and Blender side by side
Needs Pillow.
"""
import argparse
import glob
import json
import os
import sys

from PIL import Image, ImageDraw

LEFT, TOP = 190, 36
BG, INK, DIM = (40, 40, 46), (232, 232, 232), (200, 200, 120)


def sheets(d):
    out = []
    for j in sorted(glob.glob(os.path.join(d, "raw", "*.json"))):
        with open(j, encoding="utf-8") as fh:
            meta = json.load(fh)
        meta["raw"] = j[:-5] + ".png"
        if not os.path.isfile(meta["raw"]):
            sys.exit("frame_sheet_pages: %s has no picture %s" % (j, meta["raw"]))
        out.append(meta)
    if not out:
        sys.exit("frame_sheet_pages: no sheets in %s/raw - render them first" % d)
    return out


def row_text(row):
    t = row["label"]
    if row.get("length"):
        t += "  %.2fs%s" % (row["length"], " loop" if row.get("loop") else "")
    elif row.get("frames"):
        t += "  f%d-%d" % tuple(row["frames"])
    return t


def label(d):
    for m in sheets(d):
        raw = Image.open(m["raw"]).convert("RGB")
        w, h = m["cell"]
        steps = m["steps"]
        out = Image.new("RGB", (raw.width + LEFT, raw.height + TOP), BG)
        out.paste(raw, (LEFT, TOP))
        dr = ImageDraw.Draw(out)
        dr.text((6, 4), "%s (%s)" % (m["name"], m["engine"]), fill=INK)
        for v, view in enumerate(m["views"]):
            for c in range(steps):
                dr.text((LEFT + (v * steps + c) * w + 6, 20), "%s %d/%d" % (view, c + 1, steps), fill=DIM)
            if v:
                x = LEFT + v * steps * w
                dr.line([(x, TOP), (x, out.height)], fill=DIM, width=2)
        for r, row in enumerate(m["rows"]):
            dr.text((6, TOP + r * h + h // 2 - 6), row_text(row), fill=INK)
            dr.line([(0, TOP + r * h), (out.width, TOP + r * h)], fill=(70, 70, 78))
        dst = os.path.join(d, m["name"] + ".png")
        out.save(dst)
        print("labelled", dst)


def pages(d, clips, frames, per_page, blender):
    ms = [m for m in sheets(d) if blender or m["engine"] != "blender"]
    w, h = ms[0]["cell"]
    cells_per = 1 + len(clips) * len(frames)
    rows_img = []
    for m in ms:
        raw = Image.open(m["raw"]).convert("RGB")
        img = Image.new("RGB", (LEFT + cells_per * w, h), BG)
        dr = ImageDraw.Draw(img)
        dr.text((6, h // 2 - 6), m["name"], fill=INK)
        picks = [(0, 0, "rest")]
        for word in clips:
            r = next((i for i, row in enumerate(m["rows"]) if i and word.lower() in row["label"].lower()), None)
            for f in frames:
                picks.append((r, f, "%s %d/%d" % (word, f + 1, m["steps"]) if r is not None else "no %s" % word))
        for j, (r, f, text) in enumerate(picks):
            if r is not None:
                img.paste(raw.crop((f * w, r * h, (f + 1) * w, (r + 1) * h)), (LEFT + j * w, 0))
            dr.text((LEFT + j * w + 6, 4), text, fill=DIM)
        rows_img.append(img)
    n = 0
    for p in range(0, len(rows_img), per_page):
        chunk = rows_img[p:p + per_page]
        page = Image.new("RGB", (chunk[0].width, h * len(chunk)), BG)
        for i, im in enumerate(chunk):
            page.paste(im, (0, i * h))
        n += 1
        dst = os.path.join(d, "overview_%d.png" % n)
        page.save(dst)
        print("page", dst, "-", ", ".join(m["name"] for m in ms[p:p + per_page]))


def fmt(p):
    bits = []
    if "gap" in p:
        bits.append("gap %.2f m" % p["gap"])
    if "dir" in p:
        bits.append("dir (%+.2f, %+.2f, %+.2f)" % tuple(p["dir"]))
    return ", ".join(bits) or "-"


def probes(d):
    ms = []
    for m in sheets(d):
        if any(row.get("probe") for row in m["rows"]):
            ms.append(dict(m, key="probe"))
        if any(row.get("probe_clip_rig") for row in m["rows"]):
            ms.append(dict(m, key="probe_clip_rig", engine="blender, the clip file's own skeleton"))
    # With a prop bone named, only the sheets that have it: every humanoid has hands, few carry that prop.
    if any("dir" in (row.get(m["key"]) or {}) for m in ms for row in m["rows"]):
        ms = [m for m in ms if any("dir" in (row.get(m["key"]) or {}) for row in m["rows"])]
    if not ms:
        sys.exit("frame_sheet_pages: no sheet has probes - render with --gap and/or --dir")
    labels = []
    for m in ms:
        for row in m["rows"]:
            if row["label"] not in labels:
                labels.append(row["label"])
    pb = ms[0].get("probe_bones") or {}
    lines = ["# Bone probes at each clip's first frame", "",
             "Gap: distance between %s. Dir: where %s points, %s." % (pb.get("gap") or "-", pb.get("dir") or "-",
                                                                     ms[0].get("axes", "")), "",
             "| Clip | " + " | ".join("%s (%s)" % (m["name"], m["engine"]) for m in ms) + " |",
             "|---" * (len(ms) + 1) + "|"]
    for lab in labels:
        cells = []
        for m in ms:
            row = next((r for r in m["rows"] if r["label"] == lab), None)
            cells.append(fmt(row.get(m["key"]) or {}) if row else "not in this sheet")
        lines.append("| %s | %s |" % (lab, " | ".join(cells)))
    text = "\n".join(lines) + "\n"
    with open(os.path.join(d, "probes.md"), "w", encoding="utf-8") as fh:
        fh.write(text)
    print(text)


def main(argv):
    ap = argparse.ArgumentParser(prog="frame_sheet_pages.py")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("label").add_argument("dir")
    p = sub.add_parser("pages")
    p.add_argument("dir")
    p.add_argument("--clips", nargs="+", default=["idle", "walk", "run"])
    p.add_argument("--frames", nargs="+", type=int, default=[0, 2])
    p.add_argument("--per-page", type=int, default=6)
    p.add_argument("--blender", action="store_true", help="include the Blender sheets too")
    sub.add_parser("probes").add_argument("dir")
    a = ap.parse_args(argv)
    if a.cmd == "label":
        label(a.dir)
    elif a.cmd == "pages":
        pages(a.dir, a.clips, a.frames, a.per_page, a.blender)
    else:
        probes(a.dir)


if __name__ == "__main__":
    main(sys.argv[1:])
