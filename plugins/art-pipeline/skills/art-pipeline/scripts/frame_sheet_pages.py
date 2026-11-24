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
  frame_sheet_pages.py compare <dir> <unity name> <blender name> [--min-overlap 0.95] [--tolerance-px 2]
                                        [--rows-per-page 4]
                                        the controlled comparison, for a Blender sheet rendered with --match on that
                                        Unity sheet: every row three times, Unity, Blender, then both silhouettes laid
                                        over each other (red only Unity, cyan only Blender, white both) with their
                                        overlap in each cell: the share of each silhouette within --tolerance-px of
                                        the other, the lower of the two (edge smoothing differs between renderers;
                                        a limb or prop in another place does not hide in 2 pixels). Writes
                                        <dir>/compare_<unity name>_<n>.png pages and compare_<unity name>.json, prints
                                        one RESULT line per row and one for the sheet; exit 1 if any cell is under
                                        --min-overlap or a clip is missing on either side
Needs Pillow.
"""
import argparse
import glob
import json
import os
import sys

import numpy as np
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


def silhouette(cell, bg):
    """Pixels that are not the cleared background: the model, from either renderer. Both clear to one exact colour,
    so the threshold sits low: at 18, black armour shaded near the background dropped out of one sheet and not the
    other (the Cuirassier scored 0.92 on poses that matched)."""
    return np.abs(cell.astype(np.int16) - bg).max(axis=2) > 6


def near(mask, r):
    """Every pixel within r pixels (a square) of the mask."""
    out = mask.copy()
    for dy in range(-r, r + 1):
        for dx in range(-r, r + 1):
            shifted = np.zeros_like(mask)
            shifted[max(dy, 0):mask.shape[0] + min(dy, 0), max(dx, 0):mask.shape[1] + min(dx, 0)] =                 mask[max(-dy, 0):mask.shape[0] + min(-dy, 0), max(-dx, 0):mask.shape[1] + min(-dx, 0)]
            out |= shifted
    return out


def overlap(us, bs, r):
    """The lower of: the share of Unity's silhouette within r pixels of Blender's, and the other way round."""
    if not us.any() and not bs.any():
        return 1.0
    if not us.any() or not bs.any():
        return 0.0
    return float(min((us & near(bs, r)).sum() / us.sum(), (bs & near(us, r)).sum() / bs.sum()))


def compare(d, unity_name, blender_name, min_overlap, rows_per_page, tolerance):
    metas = {}
    for name in (unity_name, blender_name):
        path = os.path.join(d, "raw", name + ".json")
        if not os.path.isfile(path):
            sys.exit("frame_sheet_pages: no %s - render it first" % path)
        with open(path, encoding="utf-8") as fh:
            metas[name] = json.load(fh)
    um, bm = metas[unity_name], metas[blender_name]
    if (um["cell"], um["steps"], um["views"]) != (bm["cell"], bm["steps"], bm["views"]):
        sys.exit("frame_sheet_pages: the two sheets differ in cell, steps or views; render Blender with --match")
    if abs(um.get("frame", {}).get("height", -1) - bm.get("frame", {}).get("height", -2)) > 1e-4:
        sys.exit("frame_sheet_pages: the two sheets are framed on different heights; render Blender with --match %s"
                 % os.path.join(d, "raw", unity_name + ".json"))
    ua = np.asarray(Image.open(os.path.join(d, "raw", unity_name + ".png")).convert("RGB"))
    ba = np.asarray(Image.open(os.path.join(d, "raw", blender_name + ".png")).convert("RGB"))
    w, h = um["cell"]
    steps, nviews = um["steps"], len(um["views"])
    ubg, bbg = ua[0, 0].astype(np.int16), ba[0, 0].astype(np.int16)
    b_rows = {r["label"]: i for i, r in enumerate(bm["rows"]) if not r.get("missing")}
    labels = [r["label"] for r in um["rows"]] + [r["label"] for r in bm["rows"]
                                                  if r["label"] not in {x["label"] for x in um["rows"]}]
    u_rows = {r["label"]: i for i, r in enumerate(um["rows"])}
    report, bands, failed = [], [], 0
    for label in labels:
        ui, bi = u_rows.get(label), b_rows.get(label)
        cols = [v * steps for v in range(nviews)] if label == "rest pose" else range(steps * nviews)
        row = {"label": label, "overlap": {}}
        strips = {k: Image.new("RGB", (w * steps * nviews, h), BG) for k in ("Unity", "Blender", "overlay")}
        for c in cols:
            box = (c * w, 0)
            uc = ua[ui * h:(ui + 1) * h, c * w:(c + 1) * w] if ui is not None else None
            bc = ba[bi * h:(bi + 1) * h, c * w:(c + 1) * w] if bi is not None else None
            if uc is not None:
                strips["Unity"].paste(Image.fromarray(uc), box)
            if bc is not None:
                strips["Blender"].paste(Image.fromarray(bc), box)
            if uc is None or bc is None:
                continue
            us, bs = silhouette(uc, ubg), silhouette(bc, bbg)
            iou = overlap(us, bs, tolerance)
            row["overlap"][str(c)] = round(iou, 3)
            over = np.full((h, w, 3), BG, dtype=np.uint8)
            over[us | bs] = (225, 225, 225)
            over[us & ~near(bs, tolerance)] = (230, 70, 70)
            over[bs & ~near(us, tolerance)] = (70, 200, 230)
            img = Image.fromarray(over)
            ImageDraw.Draw(img).text((6, h - 18), "overlap %.2f" % iou, fill=(255, 255, 120) if iou < min_overlap else INK)
            strips["overlay"].paste(img, box)
        if ui is None or bi is None:
            row["missing"] = "Unity" if ui is None else "Blender"
            verdict = "FAIL missing in %s" % row["missing"]
        else:
            worst = min(row["overlap"].values())
            row["worst"] = worst
            verdict = ("PASS" if worst >= min_overlap else "FAIL") + " worst overlap %.3f" % worst
        if verdict.startswith("FAIL"):
            failed += 1
        row["verdict"] = verdict
        report.append(row)
        print("RESULT %s: %s" % (label, verdict))
        bands.append((label, verdict, strips))
    pages = []
    for p in range(0, len(bands), rows_per_page):
        chunk = bands[p:p + rows_per_page]
        page = Image.new("RGB", (LEFT + w * steps * nviews, TOP + len(chunk) * 3 * h), BG)
        dr = ImageDraw.Draw(page)
        dr.text((6, 4), "%s (Unity) vs %s (Blender)" % (unity_name, blender_name), fill=INK)
        for v, view in enumerate(um["views"]):
            for c in range(steps):
                dr.text((LEFT + (v * steps + c) * w + 6, 20), "%s %d/%d" % (view, c + 1, steps), fill=DIM)
        for i, (label, verdict, strips) in enumerate(chunk):
            for k, kind in enumerate(("Unity", "Blender", "overlay")):
                y = TOP + (i * 3 + k) * h
                page.paste(strips[kind], (LEFT, y))
                dr.text((6, y + h // 2 - 14), label, fill=INK)
                dr.text((6, y + h // 2 + 2), kind, fill=DIM)
                if kind == "overlay":
                    dr.text((6, y + h // 2 + 18), verdict, fill=(255, 255, 120) if verdict.startswith("FAIL") else INK)
                dr.line([(0, y), (page.width, y)], fill=(90, 90, 100) if k == 0 else (60, 60, 68), width=3 if k == 0 else 1)
            for v in range(1, nviews):
                x = LEFT + v * steps * w
                dr.line([(x, TOP), (x, page.height)], fill=DIM, width=2)
        dst = os.path.join(d, "compare_%s_%d.png" % (unity_name, p // rows_per_page + 1))
        page.save(dst)
        pages.append(dst)
    with open(os.path.join(d, "compare_%s.json" % unity_name), "w", encoding="utf-8") as fh:
        json.dump({"unity": unity_name, "blender": blender_name, "min_overlap": min_overlap,
                   "tolerance_px": tolerance, "pages": pages,
                   "rows": report}, fh, indent=1)
        fh.write("\n")
    print("pages: %s" % ", ".join(pages))
    print("RESULT %s vs %s: %s, %d of %d rows under %.2f overlap or missing"
          % (unity_name, blender_name, "FAIL" if failed else "PASS", failed, len(report), min_overlap))
    return failed == 0


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
    p = sub.add_parser("compare")
    p.add_argument("dir")
    p.add_argument("unity")
    p.add_argument("blender")
    p.add_argument("--min-overlap", type=float, default=0.95)
    p.add_argument("--tolerance-px", type=int, default=2)
    p.add_argument("--rows-per-page", type=int, default=4)
    a = ap.parse_args(argv)
    if a.cmd == "label":
        label(a.dir)
    elif a.cmd == "pages":
        pages(a.dir, a.clips, a.frames, a.per_page, a.blender)
    elif a.cmd == "compare":
        sys.exit(0 if compare(a.dir, a.unity, a.blender, a.min_overlap, a.rows_per_page, a.tolerance_px) else 1)
    else:
        probes(a.dir)


if __name__ == "__main__":
    main(sys.argv[1:])
