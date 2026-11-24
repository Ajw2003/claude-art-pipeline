#!/usr/bin/env python3
"""Render every character in the config, one after another, each in its own process.

    python run_all.py --config angle-review.json --out DIR [--tile 160] [--only Name ...] [--skip-done]

A character that fails (an error, a crash, a timeout) is logged as FAIL and the run goes on to the next one,
so one bad rig never costs the others. Every line is printed as it happens, so a Terminal panel shows live
progress. Per-character logs go to <out>/logs/<Character>.log, the summary to <out>/run-summary.txt, and the
review page is rebuilt at the end from whatever characters succeeded. The exit code is 0 only if all passed.
"""

import argparse
import json
import os
import subprocess
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--tile", default="160")
    ap.add_argument("--only", nargs="*", default=None, help="characters to render (default: all in the config)")
    ap.add_argument("--clips", nargs="*", default=None, help="limit each character to these clip names (for a quick test)")
    ap.add_argument("--skip-done", action="store_true", help="skip a character whose <Character>.json already exists")
    ap.add_argument("--timeout", type=int, default=3600, help="seconds allowed per character")
    args = ap.parse_args()

    names = list(json.load(open(args.config, encoding="utf-8"))["characters"])
    if args.only:
        names = [n for n in names if n in args.only]
    os.makedirs(os.path.join(args.out, "logs"), exist_ok=True)
    results, started = [], time.time()
    print(f"RUN START: {len(names)} characters -> {args.out}", flush=True)

    for i, name in enumerate(names, 1):
        if args.skip_done and os.path.exists(os.path.join(args.out, name + ".json")):
            print(f"[{i}/{len(names)}] {name}: SKIP (already rendered)", flush=True)
            results.append((name, "SKIP", 0, "already rendered"))
            continue
        print(f"[{i}/{len(names)}] {name}: starting", flush=True)
        cmd = [sys.executable, os.path.join(HERE, "angle_sheets.py"), "--config", args.config, name,
               "--out", args.out, "--tile", args.tile]
        if args.clips:
            cmd += ["--only", *args.clips]
        t0, log_path, status, note = time.time(), os.path.join(args.out, "logs", name + ".log"), "FAIL", ""
        try:
            with open(log_path, "w", encoding="utf-8") as log:
                proc = subprocess.run(cmd, stdout=log, stderr=subprocess.STDOUT, timeout=args.timeout)
            text = open(log_path, encoding="utf-8", errors="replace").read()
            result = [l for l in text.splitlines() if l.startswith("RESULT ")]
            if proc.returncode == 0 and result:
                status, note = "PASS", result[-1][7:]
            else:
                tail = [l for l in text.splitlines() if l.strip()][-1:] or ["no output"]
                note = f"exit {proc.returncode}, {'no RESULT line, ' if not result else ''}last line: {tail[0][:200]}"
            notes = [l for l in text.splitlines() if l.startswith("NOTE ")]
            if notes:
                note += "  | " + " ".join(notes)
        except subprocess.TimeoutExpired:
            note = f"timed out after {args.timeout}s"
        except Exception as e:    # one character's problem must never stop the run
            note = f"runner error: {e}"
        secs = time.time() - t0
        print(f"[{i}/{len(names)}] {name}: {status} in {secs:.0f}s  {note}", flush=True)
        results.append((name, status, secs, note))

    lines = [f"{s:5} {n:22} {t:6.0f}s  {note}" for n, s, t, note in results]
    passed = sum(1 for r in results if r[1] == "PASS")
    failed = [r[0] for r in results if r[1] == "FAIL"]
    summary = "\n".join(lines) + f"\nSUMMARY: {passed} passed, {len(failed)} failed" + (f" ({', '.join(failed)})" if failed else "") \
        + f", {len(results) - passed - len(failed)} skipped, {time.time() - started:.0f}s total"
    open(os.path.join(args.out, "run-summary.txt"), "w", encoding="utf-8").write(summary + "\n")
    print("\n" + summary, flush=True)
    page = subprocess.run([sys.executable, os.path.join(HERE, "review_page.py"), args.out], capture_output=True, text=True)
    print(page.stdout.strip().splitlines()[-1] if page.stdout.strip() else f"review page failed: {page.stderr[-300:]}", flush=True)
    sys.exit(1 if failed else 0)


if __name__ == "__main__":
    main()
