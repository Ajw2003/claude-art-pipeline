#!/usr/bin/env python3
"""hook.py - art-pipeline hook handlers (stdlib only). Gate logic lives in artlib.py.

  start (SessionStart)  fails LOUD: on an internal error says so in a systemMessage, exit 0.
                        Silent only when it looked and there is nothing to do (no git repo,
                        no art in the repo).
  seen  (PostToolUse/Read)  never blocks, never non-zero. A ledger it cannot write is announced
                        in a systemMessage.
  gate  (Stop)          fails OPEN, LOUD: any internal error -> systemMessage naming it, no
                        block. Blocks (decision:block) only on a definite unmet model, and
                        releases with a loud systemMessage on the 3rd identical block.
                        Off switch: ART_PIPELINE=off (announced in a systemMessage).

Ledger: <git-dir>/art-pipeline/<session_id>.json, so it is never committed.
JSON is emitted with separators=(",", ":"), like house-rules.
"""

import json
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artlib  # noqa: E402


def emit(obj):
    sys.stdout.write(json.dumps(obj, separators=(",", ":")))


_LAST = {}  # the payload, for pre_failed after an internal error


def payload():
    try:
        raw = sys.stdin.buffer.read().decode("utf-8", "replace").strip()
        _LAST.clear()
        _LAST.update(json.loads(raw) if raw else {})
        return dict(_LAST)
    except Exception as exc:
        sys.stderr.write("art-pipeline: unreadable hook payload: %s\n" % exc)
        return {}


def where(p):
    return p.get("cwd") or os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def event_start():
    p = payload()
    info = artlib.repo_info(where(p))
    if not info:
        return 0
    root, gitdir = info
    cfg = artlib.load_config(root)
    path = artlib.ledger_path(gitdir, p.get("session_id"))
    artlib.save_ledger(path, {"start": artlib.head_sha(root), "seen": [], "blocks": {}, "granted": [], "iter": {}})
    if not artlib.tracked_has_art(root, cfg):
        return 0
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
          "art-pipeline: no art asset (model, animation, VFX, SFX, music, texture, sprite, UI art) may be "
          "made or changed until a human has approved its spec and real-world reference; the hooks refuse "
          "the writes and builds until then, and each approval allows a fixed number of builds. Any model "
          "you change also needs a review sheet you opened and a review record before you stop. "
          "See the art-pipeline skill."}})
    return 0


def event_seen():
    p = payload()
    fp = (p.get("tool_input") or {}).get("file_path")
    if not isinstance(fp, str) or not fp.lower().endswith(artlib.IMG_EXT):
        return 0
    info = artlib.repo_info(where(p))
    if not info:
        return 0
    path = artlib.ledger_path(info[1], p.get("session_id"))
    led = artlib.load_ledger(path)
    base = p.get("cwd") or os.getcwd()
    led["seen"].append({"path": os.path.normpath(os.path.join(base, fp)), "t": artlib.now()})
    artlib.save_ledger(path, led)
    return 0


def event_gate():
    if os.environ.get("ART_PIPELINE", "").strip().lower() == "off":
        emit({"systemMessage": "art-pipeline: gate is OFF (ART_PIPELINE=off); models were not checked."})
        return 0
    p = payload()
    info = artlib.repo_info(where(p))
    if not info:
        return 0
    root, gitdir = info
    cfg, led, res, bad = artlib.evaluate(root, gitdir, p.get("session_id"))
    unmet = [(m, pr) for m, st, pr in res if st == "fail"]
    waived = [m for m, st, _ in res if st == "waived"]
    notes = ["art-pipeline: " + pr[0] for m, st, pr in res if st == "timeout"]
    if waived:
        notes.append("art-pipeline: WAIVED review for: " + ", ".join(waived))
    path = artlib.ledger_path(gitdir, p.get("session_id"))
    if not unmet:
        if led["blocks"]:
            led["blocks"] = {}
            artlib.save_ledger(path, led)
        if bad:
            notes.append("art-pipeline: unreadable review records ignored: " + "; ".join(bad))
        if notes:
            emit({"systemMessage": " | ".join(notes)})
        return 0
    key = "|".join(sorted(m for m, _ in unmet))
    n = led["blocks"].get(key, 0) + 1
    led["blocks"] = {key: n}
    artlib.save_ledger(path, led)
    if n >= artlib.MAX_BLOCKS:
        notes.append("art-pipeline: stopping with UNREVIEWED models: " + ", ".join(m for m, _ in unmet)
                     + " (blocked %d times with the same set; releasing the stop)" % (n - 1))
        emit({"systemMessage": " | ".join(notes)})
        return 0
    lines = ["art-pipeline: these models changed this session and are not reviewed:"]
    for m, pr in unmet:
        lines.append("- %s" % m)
        lines += ["    * " + x for x in pr]
    if bad:
        lines.append("Unreadable review records: " + "; ".join(bad))
    if any(m != "doc_check" for m, _ in unmet):
        lines.append("To fix models: " + artlib.fix_hint(cfg))
    lines += notes
    emit({"decision": "block", "reason": "\n".join(lines)})
    return 0


def deny(reason):
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": "art-pipeline: " + reason}})
    return 0


def _protected(cfg, rel):
    return rel == ".art-pipeline.json" or artlib._under(rel, cfg["approval_dir"])


def event_pre():
    """PreToolUse. Refuses art made without a usable human approval, and any write to the approvals."""
    if os.environ.get("ART_PIPELINE", "").strip().lower() == "off":
        return 0
    p = payload()
    info = artlib.repo_info(where(p))
    if not info:
        return 0
    root, gitdir = info
    tool, ti = p.get("tool_name", ""), p.get("tool_input") or {}
    cfg = artlib.load_config(root)
    path = artlib.ledger_path(gitdir, p.get("session_id"))
    led = artlib.load_ledger(path)
    if tool == "AskUserQuestion":
        qs = " ".join(q.get("question", "") for q in ti.get("questions") or [] if isinstance(q, dict))
        tokens = artlib.TOKEN.findall(qs)
        if tokens and ti.get("answers"):
            return deny("an approval question must be answered by the human; send it without \"answers\".")
        for sid, short in tokens:
            if not os.path.isfile(artlib.spec_path(root, cfg, sid)) or \
                    artlib.spec_token(root, cfg, sid) != "art-approve:%s@%s" % (sid, short):
                return deny("the token for %s does not match its spec as it is now; run approve.py check %s again." % (sid, sid))
        return 0
    if tool == "Bash":
        cmd = ti.get("command") or ""
        if re.search(r"approve\.py[\"']?\s+grant", cmd):
            return deny("approve.py grant is the human's terminal command; ask with AskUserQuestion instead.")
        if not cmd.lstrip().startswith("git ") and (".art-pipeline.json" in cmd or cfg["approval_dir"].strip("/") in cmd):
            return deny("%s and .art-pipeline.json are written only by a human grant or the human; "
                        "read them with Read, commit them with git." % cfg["approval_dir"])
        if not any(re.search(rx, cmd) for rx in cfg["producer_commands"]):
            return 0
        low = cmd.lower()
        approvals = artlib.load_approvals(root, cfg, led)
        named = [(sid, rec, pr) for sid, rec, pr in approvals if rec and any(t.lower() in low for t in rec["match"])]
        ready = [(sid, rec) for sid, rec, pr in named if not pr and not artlib.usable(root, rec, led)]
        if not ready:
            why = [x for sid, rec, pr in named for x in (pr or artlib.usable(root, rec, led))]
            return deny("this command builds art and cannot run yet: %s. %s" % (
                "; ".join(why) if why else "it names no asset with a human-approved spec (a word from a spec's \"match\")",
                "" if why else "To make art: " + artlib.approval_hint(cfg)))
        for sid, rec in ready:
            led["iter"][rec["_sha"]] = led["iter"].get(rec["_sha"], 0) + 1
        artlib.save_ledger(path, led)
        return 0
    fp = ti.get("file_path") or ti.get("notebook_path")
    if not isinstance(fp, str):
        return 0
    absf = os.path.normpath(os.path.join(p.get("cwd") or os.getcwd(), fp))
    rel = os.path.relpath(absf, root).replace(os.sep, "/")
    if rel.startswith("../"):
        return 0
    if _protected(cfg, rel):
        return deny("%s is written only by a human (approvals come from AskUserQuestion or approve.py grant)." % rel)
    if not artlib.is_production(rel, cfg):
        return 0
    cov = artlib.covering(rel, artlib.load_approvals(root, cfg, led))
    if any(not pr and not artlib.usable(root, rec, led) for _, rec, pr in cov):
        return 0
    why = [x for _, rec, pr in cov for x in (pr or artlib.usable(root, rec, led))]
    return deny("%s is an art asset and cannot be written yet: %s" % (rel, "; ".join(why) if why else
                "no human-approved spec covers it. To make it: " + artlib.approval_hint(cfg)))


def pre_failed(detail):
    """Fail closed for anything that looks like art (by the default rules), open and loud otherwise,
    so a broken ledger or config cannot stop ordinary work but cannot let art through either."""
    ti = (_LAST.get("tool_input") or {})
    cmd, fp = ti.get("command") or "", ti.get("file_path") or ti.get("notebook_path") or ""
    looks_art = any(re.search(rx, cmd) for rx in artlib.DEFAULT_PRODUCERS) or (
        isinstance(fp, str) and artlib.matches(fp.replace(os.sep, "/"), artlib.DEFAULT_PRODUCTION))
    if looks_art:
        return deny("the approval check hit an internal error (%s), so this art write is refused. "
                    "Run approve.py status to see why; the human can set ART_PIPELINE=off." % detail)
    emit({"systemMessage": "art-pipeline: the approval check hit an internal error (%s); this call "
                           "did not look like art and was let through UNCHECKED." % detail})
    return 0


def _answers(p):
    for src in (p.get("tool_response"), p.get("tool_input")):
        if isinstance(src, dict) and isinstance(src.get("answers"), dict):
            return src["answers"]
    return {}


def event_answered():
    """PostToolUse on AskUserQuestion: a human "Approve" on a question carrying a spec token is the grant."""
    p = payload()
    info = artlib.repo_info(where(p))
    if not info:
        return 0
    root, gitdir = info
    cfg = artlib.load_config(root)
    answers = _answers(p)
    path = artlib.ledger_path(gitdir, p.get("session_id"))
    notes = []
    for q in (p.get("tool_input") or {}).get("questions") or []:
        text = q.get("question", "") if isinstance(q, dict) else ""
        for sid, short in artlib.TOKEN.findall(text):
            ans = answers.get(text)
            if not isinstance(ans, str) or ans.strip() != "Approve":
                notes.append("%s NOT approved (the human answered %r)" % (sid, ans))
                continue
            spec, probs = artlib.validate_spec(root, cfg, sid)
            if not probs and artlib.spec_token(root, cfg, sid) != "art-approve:%s@%s" % (sid, short):
                probs = ["the spec changed while the question was open"]
            if probs:
                notes.append("%s NOT approved: %s" % (sid, "; ".join(probs)))
                continue
            h = artlib.write_approval(root, cfg, artlib.make_approval(root, cfg, sid, spec, "human via AskUserQuestion", ans))
            led = artlib.load_ledger(path)
            led["granted"].append(h)
            artlib.save_ledger(path, led)
            notes.append("%s APPROVED by the human: %s/%s.json written; commit it" % (sid, cfg["approval_dir"], sid))
    if notes:
        emit({"systemMessage": "art-pipeline: " + " | ".join(notes)})
    return 0


EVENTS = {"start": event_start, "seen": event_seen, "gate": event_gate, "pre": event_pre, "answered": event_answered}


def main(argv):
    event = argv[1] if len(argv) > 1 else ""
    h = EVENTS.get(event)
    if h is None:
        return 0
    try:
        return h()
    except BaseException as exc:
        detail = "%s: %s" % (type(exc).__name__, exc)
        if event == "pre":
            return pre_failed(detail)
        extra = {"start": "The review gate may not be armed.", "seen": "A viewed sheet may not have been recorded.",
                 "answered": "A human approval may NOT have been recorded; ask again.",
                 "gate": "The gate did NOT run; changed models are UNREVIEWED (failing open)."}[event]
        emit({"systemMessage": "art-pipeline plugin: the %s hook hit an internal error (%s). %s" % (event, detail, extra)})
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
