#!/usr/bin/env python3
"""hook.py - art-pipeline hook handlers (stdlib only). Gate logic lives in artlib.py.

  start (SessionStart)  fails LOUD: on an internal error says so in a systemMessage, exit 0.
                        Arms the ledger in every git repo; speaks only where there is art.
  seen  (PostToolUse/Read)  never blocks, never non-zero.
  pre   (PreToolUse)    refuses art writes and builds no usable human approval covers, and any
                        write to approvals, the config, the plugin's settings or the ledger.
                        Fails CLOSED for calls that look like art, open and loud otherwise.
  after (PostToolUse/Bash)  undoes, right after the call, any art file it changed that no
                        approval covers and any approval file no human grant wrote; a copy of
                        each goes to <git-dir>/art-pipeline/quarantine/. Charges a build to the
                        items whose files changed when the command was not a listed build tool.
  answered (PostToolUse/AskUserQuestion)  the human's "Approve" writes the approval.
  gate  (Stop)          fails OPEN, LOUD. Blocks on unreviewed models, uncovered art and forged
                        approvals. Releases on the 3rd identical block, except for a forged
                        approval, which must be removed. Off switch: ART_PIPELINE=off.

Ledger: <git-dir>/art-pipeline/<session_id>.json, so it is never committed.
JSON is emitted with separators=(",", ":"), like house-rules.
"""

import json
import os
import re
import shutil
import subprocess
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import artlib  # noqa: E402
import sheet  # noqa: E402


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


def off():
    return os.environ.get("ART_PIPELINE", "").strip().lower() == "off"


def event_start():
    p = payload()
    info = artlib.repo_info(where(p))
    if not info:
        return 0
    root, gitdir = info
    cfg = artlib.load_config(root)
    path = artlib.ledger_path(gitdir, p.get("session_id"))
    # art already changed when the session starts is the person's, never undone by this session
    artlib.save_ledger(path, artlib.new_ledger(artlib.head_sha(root), artlib.changed_art(root, cfg)))
    if artlib.unattended(root):
        emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
              "art-pipeline: UNATTENDED run (ART_PIPELINE=unattended). Nobody is there to approve or answer, so "
              "art needs no approved spec and AskUserQuestion is refused: decide, prototype and keep going. Still "
              "enforced: models need a review sheet you opened and a review record, animation needs frame sheets, "
              "and approvals, .art-pipeline.json, the plugin settings and the ledger cannot be edited. Keep a log "
              "in docs/art/UNATTENDED.md of every question you would have asked and the choice you took, and "
              "commit it; the Stop gate lists the art made without an approved spec for the morning."}})
        return 0
    if not artlib.tracked_has_art(root, cfg):
        return 0
    emit({"hookSpecificOutput": {"hookEventName": "SessionStart", "additionalContext":
          "art-pipeline: no art asset (model, animation, VFX, SFX, music, texture, sprite, UI art) may be "
          "made or changed until a human has approved a spec with real-world reference for it; the hooks "
          "refuse the writes and builds until then, undo art a command makes without approval, and allow "
          "each approved item a fixed number of builds. Any model you change also needs a review sheet "
          "you opened and a review record before you stop. See the art-pipeline skill."}})
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
    if off():
        emit({"systemMessage": "art-pipeline: gate is OFF (ART_PIPELINE=off); art was not checked."})
        return 0
    p = payload()
    sid = p.get("session_id")
    infos = []
    for info in [artlib.repo_info(where(p))] + artlib.registered_repos(sid):
        if info and info[0] not in {r for r, _ in infos}:
            infos.append(info)
    if not infos:
        return 0
    root, gitdir = infos[0]   # the loop guard's count lives in the first repo's ledger
    cfg, led, res, bad = artlib.evaluate(root, gitdir, sid)
    for oroot, ogit in infos[1:]:   # repos this session worked in from outside them
        _c, _l, ores, obad = artlib.evaluate(oroot, ogit, sid)
        res += [("%s: %s" % (os.path.basename(oroot), m), st, pr) for m, st, pr in ores]
        bad += obad
    unmet = [(m, pr) for m, st, pr in res if st in ("fail", "forged")]
    forged = [m for m, st, _ in res if st == "forged"]
    waived = [m for m, st, _ in res if st == "waived"]
    notes = ["art-pipeline: " + pr[0] for m, st, pr in res if st == "timeout"]
    unapproved = [m for m, st, _ in res if st == "unapproved"]
    if unapproved:
        notes.append("art-pipeline: UNATTENDED run - made without a human-approved spec, for review in the "
                     "morning: " + ", ".join(unapproved))
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
    if n >= artlib.MAX_BLOCKS and not forged:
        notes.append("art-pipeline: stopping with UNREVIEWED or UNAPPROVED art: " + ", ".join(m for m, _ in unmet)
                     + " (blocked %d times with the same set; releasing the stop)" % (n - 1))
        emit({"systemMessage": " | ".join(notes)})
        return 0
    lines = ["art-pipeline: these files changed this session and are not approved or not reviewed:"]
    for m, pr in unmet:
        lines.append("- %s" % m)
        lines += ["    * " + x for x in pr]
    if bad:
        lines.append("Unreadable review records: " + "; ".join(bad))
    if any(artlib.is_model(m, cfg) for m, _ in unmet):
        lines.append("To review models: " + artlib.fix_hint(cfg))
    lines += notes
    emit({"decision": "block", "reason": "\n".join(lines)})
    return 0


def deny(reason):
    emit({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                 "permissionDecisionReason": "art-pipeline: " + reason}})
    return 0


SETTINGS = (".claude/settings.json", ".claude/settings.local.json")
# what a Bash command may not name unless it is a git command: the human's files and the ledger
BASH_GUARDED = r"\.art-pipeline\.json|\.claude/settings(\.local)?\.json|\.git/art-pipeline|git-dir\)?[\"']?/art-pipeline" \
    r"|\.claude/art-pipeline"


def _protected(cfg, rel):
    return rel == ".art-pipeline.json" or rel in SETTINGS or rel.startswith(".git/") or \
        artlib._under(rel, cfg["approval_dir"])


def _sheet_ok(root, cfg, sid):
    """The spec is complete and its sheet on disk is exactly what it renders to now."""
    spec, probs = artlib.validate_spec(root, cfg, sid)
    return not probs and sheet.is_current(root, cfg, sid, spec)


CD = re.compile(r"(?:^|[;&|(\s])(?:cd|pushd)\s+([\"']?)([^\s;&|)\"']+)\1")
GIT_C = re.compile(r"\bgit\s+-C\s+([\"']?)([^\s;&|)\"']+)\1")
ABS = re.compile(r"(?<![\w.:/])((?:[A-Za-z]:[\\/]|/)[^\s;&|)\"'<>]+)")   # /posix/path or C:/win/path
GITBASH_DRIVE = re.compile(r"^/([A-Za-z])(?=/|$)")


def _native(path):
    """Git Bash writes C:\\x as /c/x; on Windows that must be turned back into a drive path to be found."""
    return GITBASH_DRIVE.sub(lambda m: m.group(1).upper() + ":", path) if os.name == "nt" else path


def _repo_of(path):
    """The repo holding path, or the nearest existing folder above it. A path inside a .git folder
    belongs to the repo above it (git names no work tree from inside .git)."""
    parts = path.split(os.sep)
    d = os.sep.join(parts[:parts.index(".git")]) if ".git" in parts else path
    while d and not os.path.isdir(d):
        d = os.path.dirname(d)
    return artlib.repo_info(d) if d else None


def bash_repos(p):
    """Every git repo a command can act in: the session's working directory, every folder it cds,
    pushds or `git -C`s into, and the repo of every absolute path it names. Judged by the working
    directory alone, `cd other-repo && render movie` was checked against the wrong repo's rules."""
    cmd = (p.get("tool_input") or {}).get("command") or ""
    base = where(p)
    dirs = [base]
    dirs += [os.path.join(base, os.path.expanduser(_native(m.group(2)))) for rx in (CD, GIT_C) for m in rx.finditer(cmd)]
    dirs += [_native(m.group(1)) for m in ABS.finditer(cmd)]
    out, seen = [], set()
    for d in dirs:
        d = os.path.normpath(d)
        if d in seen:
            continue
        seen.add(d)
        info = _repo_of(d)
        if info and info[0] not in {r for r, _ in out}:
            out.append(info)
    return out


def event_pre():
    """PreToolUse. Refuses art made without a usable human approval, and any write to what only the
    human may change."""
    if off():
        return 0
    p = payload()
    tool, ti = p.get("tool_name", ""), p.get("tool_input") or {}
    if tool == "Bash":
        cmd = ti.get("command") or ""
        if re.search(r"approve\.py[\"']?\s+grant", cmd):
            return deny("approve.py grant is the human's terminal command; ask with AskUserQuestion instead.")
        if re.search(r"plugins?\s+(disable|uninstall|remove)\b", cmd):
            return deny("only the human turns plugins off.")
        home = artlib.repo_info(where(p))
        for root, gitdir in bash_repos(p):
            if not home or root != home[0]:
                artlib.register_repo(p.get("session_id"), root)   # the Stop gate checks it too
            why = bash_pre(root, gitdir, p, cmd)
            if why:
                return deny(why)
        return 0
    if tool == "AskUserQuestion" and artlib.unattended(where(p)):
        return deny("unattended run (ART_PIPELINE=unattended): nobody is there to answer. Pick the safest "
                    "option yourself, put the question and your choice in your final report, and carry on.")
    if tool == "AskUserQuestion":
        info = artlib.repo_info(where(p))
    else:
        fp = ti.get("file_path") or ti.get("notebook_path")
        if not isinstance(fp, str):
            return 0
        absf = os.path.normpath(os.path.join(p.get("cwd") or os.getcwd(), fp))
        reg = artlib.registry_dir()
        if absf == reg or absf.startswith(reg + os.sep):
            return deny("the session's repo list is kept by the plugin; it is not changed by hand.")
        info = _repo_of(absf)
        home = artlib.repo_info(where(p))
        if info and (not home or info[0] != home[0]):
            artlib.register_repo(p.get("session_id"), info[0])   # the Stop gate checks it too
    if not info:
        return 0
    root, gitdir = info
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
            if not _sheet_ok(root, cfg, sid):
                return deny("the review sheet for %s is missing or out of date; run approve.py check %s and show "
                            "the human the sheet before asking." % (sid, sid))
        return 0
    absf = os.path.normpath(os.path.join(p.get("cwd") or os.getcwd(), ti.get("file_path") or ti.get("notebook_path")))
    rel = os.path.relpath(absf, root).replace(os.sep, "/")
    if rel.startswith("../"):
        return 0
    if _protected(cfg, rel):
        return deny("%s is changed only by the human (approvals come from AskUserQuestion or approve.py grant)." % rel)
    if artlib.unattended(root) or not artlib.is_production(rel, cfg):
        return 0
    ok, why = artlib.ready(root, artlib.covering(rel, artlib.load_approvals(root, cfg, led)), led)
    if ok:
        return 0
    return deny("%s is an art asset and cannot be written yet: %s" % (rel, "; ".join(why) if why else
                "no human-approved item covers it. To make it: " + artlib.approval_hint(cfg)))


def bash_pre(root, gitdir, p, cmd):
    """The Bash checks for one repo the command can act in: None to allow, else the reason to refuse."""
    cfg = artlib.load_config(root)
    path = artlib.ledger_path(gitdir, p.get("session_id"))
    led = artlib.load_ledger(path)
    if not cmd.lstrip().startswith("git ") and (
            re.search(BASH_GUARDED, cmd) or cfg["approval_dir"].strip("/") in cmd):
        return ("%s, .art-pipeline.json, the plugin settings and the session ledger are changed only by "
                "a human grant or the human; read them with Read, commit them with git." % cfg["approval_dir"])
    if artlib.unattended(root):
        return None   # no approval to check, no build budget to charge
    use = p.get("tool_use_id")
    if use and use == led.get("pre_use"):
        return None  # a second copy of the plugin (user and project scope) already allowed this call
    led["t0"], led["counted"], led["pre_use"] = time.time(), False, use
    led["check_cmd"] = ""
    approvals = None
    runs = artlib.run_part(cmd)   # only the parts that run something: not git add, cat, a message
    if any(re.search(rx, runs) for rx in cfg.get("gated_commands") or []):
        approvals = artlib.load_approvals(root, cfg, led)
        stale = []
        for _sid, rec, _pr in approvals:
            for it in (rec or {}).get("items", []):
                if any(t.lower() in cmd.lower() for t in it["match"]):
                    ok, why = artlib.check_state(root, cfg, led, it, gated_cmd=cmd)
                    stale += why if not ok else artlib.clip_review_state(root, cfg, led, it, cmd)[1]
        stale = list(dict.fromkeys(stale))   # two approvals of one item give one reason
        if stale:
            artlib.save_ledger(path, led)
            return ("this command shows or exports art that has not passed its check: %s. A movie or "
                    "an export is made only from work a check has passed since its last edit." % "; ".join(stale))
    if any(re.search(rx, runs) for rx in cfg["producer_commands"]):
        approvals = approvals or artlib.load_approvals(root, cfg, led)
        ok, why = artlib.ready(root, artlib.named_in(cmd, approvals), led)
        if not ok:
            return "this command builds art and cannot run yet: %s. %s" % (
                "; ".join(why) if why else "it names no approved item (a word from an item's \"match\")",
                "" if why else "To make art: " + artlib.approval_hint(cfg))
        for rec, it in ok:
            artlib.charge(led, rec, it, "running `%s`" % cmd.strip()[:70])
        led["counted"] = True
    elif artlib.check_entries(runs, cfg):
        # a check is never a build. Its items are "pending" until `after` reads a pass from its
        # output: Claude Code runs no PostToolUse hook for a command that exits non-zero, so a
        # failing check never reaches `after`, and must not leave an older pass standing.
        led["check_cmd"] = cmd
        approvals = approvals or artlib.load_approvals(root, cfg, led)
        for _sid, rec, _pr in approvals:
            for it in (rec or {}).get("items", []):
                if any(t.lower() in cmd.lower() for t in it["match"]):
                    led["checks"][artlib.check_key(it)] = {"verdict": "pending", "fp": "", "t": artlib.now(),
                                                           "cmd": cmd.strip()[:120], "words": []}
    artlib.save_ledger(path, led)
    return None


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


def quarantine(root, gitdir, start, rel, stamp):
    """Copies rel aside, then puts it back as it was when the session started (or removes it)."""
    src = os.path.join(root, rel)
    dst = os.path.join(gitdir, "art-pipeline", "quarantine", stamp, rel)
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    shutil.copy2(src, dst)
    old = subprocess.run(["git", "show", "%s:%s" % (start, rel)], cwd=root, stdout=subprocess.PIPE,
                         stderr=subprocess.PIPE) if start else None
    if old is None or old.returncode != 0:  # new this session: nothing to put back
        os.remove(src)
    else:
        with open(src, "wb") as fh:
            fh.write(old.stdout)
    return dst


def event_after():
    """PostToolUse on Bash: whatever the command was, art it made without approval does not stay.
    Run for every repo the command could act in (bash_repos), as `pre` is."""
    if off():
        return 0
    p = payload()
    lines, notes = [], []
    for root, gitdir in bash_repos(p):
        ln, nt = after_repo(root, gitdir, p)
        lines += ln
        notes += nt
    if lines:
        emit({"decision": "block", "reason": "\n".join(lines + ["art-pipeline: " + n for n in notes])})
    elif notes:
        emit({"hookSpecificOutput": {"hookEventName": "PostToolUse",
                                     "additionalContext": "art-pipeline: " + " | ".join(notes)}})
    return 0


def after_repo(root, gitdir, p):
    """`after` for one repo: (block lines, notes)."""
    cfg = artlib.load_config(root)
    path = artlib.ledger_path(gitdir, p.get("session_id"))
    led = artlib.load_ledger(path)
    use = p.get("tool_use_id")
    if use and use == led.get("after_use"):
        return [], []  # a second copy of the plugin already checked this call
    led["after_use"] = use
    approvals = artlib.load_approvals(root, cfg, led)
    stamp = time.strftime("%Y%m%d-%H%M%S")
    undone = []
    d = os.path.join(root, cfg["approval_dir"])
    for f in sorted(os.listdir(d)) if os.path.isdir(d) else []:
        rel = "%s/%s" % (cfg["approval_dir"].strip("/"), f)
        if f.endswith(".json") and not artlib.human_granted(root, led, rel):
            undone.append((rel, quarantine(root, gitdir, led["start"], rel, stamp), "no human grant wrote it"))
    t0 = led.get("t0") or 0
    outputs = {}
    for rel, h in ({} if artlib.unattended(root) else artlib.changed_art(root, cfg)).items():
        if led["known"].get(rel) == h or os.path.getmtime(os.path.join(root, rel)) < t0 - 1:
            continue  # unchanged since accepted, or changed outside this call (the person's own edit)
        good = [(rec, it) for rec, it, pr in artlib.covering(rel, approvals) if not pr]
        if good:
            led["known"][rel] = h
            if not artlib.is_source(rel, cfg):   # editing the code an asset is made from is not a build
                for rec, it in good:
                    outputs.setdefault(artlib.budget_key(rec, it), (rec, it, rel))
        else:
            undone.append((rel, quarantine(root, gitdir, led["start"], rel, stamp), "no approved item covers it"))
    if outputs and not led.get("counted"):
        for rec, it, rel in outputs.values():  # a tool missing from producer_commands still spends the budget
            artlib.charge(led, rec, it, "a command that changed %s" % rel)
    led["counted"] = False
    cmd = led.get("check_cmd") or ""
    if cmd:
        led["check_cmd"] = ""
        res = p.get("tool_response")
        out = "\n".join(str(res.get(k) or "") for k in ("stdout", "stderr")) if isinstance(res, dict) else \
            (res if isinstance(res, str) else "")
        verdict = artlib.check_verdict(artlib.check_entries(cmd, cfg), out)
        named = list({artlib.check_key(it): it for _sid, rec, _pr in approvals if rec for it in rec["items"]
                      if any(t.lower() in cmd.lower() for t in it["match"])}.values())
        for it in named:
            led["checks"][artlib.check_key(it)] = {"verdict": verdict, "fp": artlib.fingerprint(root, cfg, it),
                                                   "t": artlib.now(), "cmd": cmd.strip()[:120],
                                                   "words": artlib.check_words(cmd, cfg)}
        if named:
            led["notes"].append("check recorded for %s: %s%s" % (", ".join(i["name"] for i in named), verdict.upper(),
                                "" if verdict != "unknown" else " (its output matched neither the pass nor the fail "
                                "pattern, or was not captured: a check run in the background is not seen)"))
    notes, led["notes"] = led.get("notes") or [], []
    artlib.save_ledger(path, led)
    lines = []
    if undone:
        lines = ["art-pipeline: this command changed files that may not change yet, so they were put back "
                 "as they were at the start of the session. A copy of each is kept:"]
        lines += ["- %s (%s): copy at %s" % (rel, why, os.path.relpath(dst, root)) for rel, dst, why in undone]
        lines.append("To make art: " + artlib.approval_hint(cfg))
    return lines, notes


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
            if not probs and not _sheet_ok(root, cfg, sid):
                probs = ["the review sheet is missing or out of date"]
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


EVENTS = {"start": event_start, "seen": event_seen, "gate": event_gate, "pre": event_pre,
          "after": event_after, "answered": event_answered}


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
        extra = {"start": "The gates may not be armed.", "seen": "A viewed image may not have been recorded.",
                 "answered": "A human approval may NOT have been recorded; ask again.",
                 "after": "Art this command made was NOT checked; the Stop gate will still see it.",
                 "gate": "The gate did NOT run; changed art is UNCHECKED (failing open)."}[event]
        emit({"systemMessage": "art-pipeline plugin: the %s hook hit an internal error (%s). %s" % (event, detail, extra)})
        return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
