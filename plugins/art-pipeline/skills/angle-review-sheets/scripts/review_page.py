#!/usr/bin/env python3
"""Build the page where the owner reviews every character's angle sheet: Approved or Revise, plus what to revise.

    python review_page.py <folder of <Character>.json files>

Reads <folder>/<Character>.json (written by angle_sheets.py, with each clip's video and
sheet strips) and writes
<folder>/review.html. Answers are kept in the browser (localStorage) and can be copied
as text from the page.
"""

import glob
import html
import json
import os
import sys

if len(sys.argv) < 2:
    sys.exit("usage: python review_page.py <folder of <Character>.json files>")
SHEETS = os.path.abspath(sys.argv[1])


CSS = """
:root{--bg:#15130f;--card:#1f1b16;--ink:#ece5d8;--muted:#a69c8c;--line:#3a332c;--ok:#4caf7a;--bad:#e0894a;--accent:#d9b25a}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,sans-serif}
header.top{position:sticky;top:0;z-index:5;background:#0f0d0a;border-bottom:1px solid var(--line);padding:10px 16px;display:flex;flex-wrap:wrap;gap:10px;align-items:center}
header.top h1{font-size:1.1rem;margin:0 12px 0 0}
main{max-width:1400px;margin:0 auto;padding:16px}
button{font:inherit;border-radius:8px;border:1px solid var(--line);background:#2a251e;color:var(--ink);padding:8px 14px;cursor:pointer}
button:hover{border-color:var(--accent)}
button.approve.on{background:var(--ok);color:#06150d;border-color:var(--ok);font-weight:700}
button.revise.on{background:var(--bad);color:#1c0e03;border-color:var(--bad);font-weight:700}
details.card{background:var(--card);border:1px solid var(--line);border-radius:12px;margin:12px 0}
details.card>summary{cursor:pointer;padding:12px 16px;font-size:1.1rem;display:flex;gap:12px;align-items:center;flex-wrap:wrap;list-style:none}
details.card>summary::-webkit-details-marker{display:none}
.badge{font-size:.8rem;padding:2px 10px;border-radius:99px;border:1px solid var(--line);color:var(--muted)}
.badge.approved{background:var(--ok);color:#06150d;border-color:var(--ok)}
.badge.revise{background:var(--bad);color:#1c0e03;border-color:var(--bad)}
.muted{color:var(--muted);font-size:.9rem}
.bar{position:sticky;top:52px;z-index:4;background:var(--card);border-top:1px solid var(--line);border-bottom:1px solid var(--line);padding:10px 16px;display:flex;flex-wrap:wrap;gap:10px;align-items:flex-start}
.bar textarea{flex:1 1 320px;min-height:56px;background:#14110d;color:var(--ink);border:1px solid var(--line);border-radius:8px;padding:8px;font:inherit}
.clips{padding:8px 16px;display:flex;flex-wrap:wrap;gap:6px}
.clips a{color:var(--accent);font-size:.85rem;text-decoration:none;border:1px solid var(--line);border-radius:6px;padding:1px 8px}
.clip{padding:0 16px 8px}
.clip h3{margin:14px 0 4px;font-size:1rem;color:var(--accent)}
.clip video{width:min(100%,560px);height:auto;display:block;background:#000;border:1px solid var(--line);margin:4px 0 8px}
.clip img{width:100%;height:auto;display:block;border:1px solid var(--line);background:#000}
.legend{color:var(--muted);font-size:.9rem;margin:4px 0 12px}
@media (max-width:700px){header.top h1{width:100%}}
"""

JS = """
const KEY='angle-sheet-review-v1';
const chars=[...document.querySelectorAll('details.card')].map(d=>d.dataset.char);
function store(){try{localStorage.setItem(KEY,JSON.stringify(state));}catch(e){}}
let state={};try{state=JSON.parse(localStorage.getItem(KEY)||'{}');}catch(e){}
function save(){store();render();}
function get(c){return state[c]||{verdict:'',note:''};}
function setVerdict(c,v){state[c]={...get(c),verdict:get(c).verdict===v?'':v};save();}
function setNote(c,t){state[c]={...get(c),note:t};store();countOnly();}
function countOnly(){const a=chars.filter(c=>get(c).verdict==='approved').length,r=chars.filter(c=>get(c).verdict==='revise').length;
 document.getElementById('count').textContent=`${a} approved, ${r} to revise, ${chars.length-a-r} not yet reviewed`;}
function render(){
 for(const c of chars){const s=get(c);
  document.querySelectorAll(`[data-char="${c}"] .approve`).forEach(b=>b.classList.toggle('on',s.verdict==='approved'));
  document.querySelectorAll(`[data-char="${c}"] .revise`).forEach(b=>b.classList.toggle('on',s.verdict==='revise'));
  const badge=document.querySelector(`[data-char="${c}"] .badge`);
  badge.className='badge '+s.verdict; badge.textContent=s.verdict==='approved'?'Approved':s.verdict==='revise'?'Revise':'Not reviewed';
  document.querySelectorAll(`[data-char="${c}"] textarea`).forEach(t=>{if(t!==document.activeElement)t.value=s.note||'';});}
 countOnly();}
function report(){return chars.map(c=>{const s=get(c);return `${c}: ${s.verdict==='approved'?'APPROVED':s.verdict==='revise'?'REVISE':'NOT REVIEWED'}`+(s.note?`\\n  ${s.note.replace(/\\n/g,'\\n  ')}`:'');}).join('\\n');}
document.querySelectorAll('.approve').forEach(b=>b.onclick=()=>setVerdict(b.closest('[data-char]').dataset.char,'approved'));
document.querySelectorAll('.revise').forEach(b=>b.onclick=()=>setVerdict(b.closest('[data-char]').dataset.char,'revise'));
document.querySelectorAll('textarea').forEach(t=>t.oninput=()=>{setNote(t.closest('[data-char]').dataset.char,t.value);
 document.querySelectorAll(`[data-char="${t.closest('[data-char]').dataset.char}"] textarea`).forEach(o=>{if(o!==t)o.value=t.value;});});
document.getElementById('copy').onclick=async()=>{await navigator.clipboard.writeText(report());document.getElementById('copy').textContent='Copied';setTimeout(()=>document.getElementById('copy').textContent='Copy results',1500);};
let armed=false;document.getElementById('reset').onclick=e=>{if(!armed){armed=true;e.target.textContent='Click again to clear all';setTimeout(()=>{armed=false;e.target.textContent='Clear all';},3000);return;}armed=false;e.target.textContent='Clear all';state={};save();};
render();
"""


def main():
    cards, names = [], sorted(os.path.basename(p)[:-5] for p in glob.glob(os.path.join(SHEETS, "*.json")))
    if not names:
        sys.exit("no <Character>.json indexes; run angle_sheets.py first")
    for character in names:
        data = json.load(open(os.path.join(SHEETS, character + ".json"), encoding="utf-8"))
        clips = data["clips"]
        frames = sum(c["frames"] for c in clips)
        links = "".join(f'<a href="#{character}-{i}">{html.escape(c["clip"])} ({c["frames"]})</a>' for i, c in enumerate(clips))
        body = "".join(
            f'<div class="clip" id="{character}-{i}"><h3>{html.escape(c["clip"])} <span class="muted">{c["frames"]} frames at {c["fps"]} per second</span></h3>'
            f'<video src="{c["video"]}" controls loop muted autoplay playsinline preload="none"></video>'
            + "".join(f'<a href="{p}" target="_blank" title="Open full size"><img loading="lazy" src="{p}" alt="{html.escape(character)} {html.escape(c["clip"])}"></a>' for p in c["strips"]) + "</div>"
            for i, c in enumerate(clips))
        controls = ('<button class="approve">Approved</button> <button class="revise">Revise</button>'
                    '<textarea placeholder="What to revise (clip name and what is wrong)"></textarea>')
        cards.append(
            f'<details class="card" data-char="{character}"><summary><b>{character}</b>'
            f'<span class="muted">{len(clips)} clips, {frames} frames</span><span class="badge">Not reviewed</span></summary>'
            f'<div class="bar">{controls}</div><div class="clips">{links}</div>{body}'
            f'<div class="bar" style="position:static">{controls}</div></details>')
        print(f"{character}: {len(clips)} clips, {frames} frames", flush=True)
    page = (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<title>Animation angle sheets: review</title><style>{CSS}</style></head><body>'
            f'<header class="top"><h1>Animation angle sheets</h1><span id="count"></span>'
            f'<button id="copy">Copy results</button><button id="reset">Clear all</button></header>'
            f'<main><p class="legend">One card per character. Open a card, look through its clips, then press Approved or Revise and type what to change. '
            f'Above each clip is a looping video of the four views. Below it the frames: each frame is four pictures side by side (front, three-quarter, side, top-down) with its number in the corner. Read each column from top to bottom, then move to the column on its right. Click any strip to open it at full size. '
            f'Answers are saved in this browser as you go; press Copy results to paste them back.</p>{"".join(cards)}</main><script>{JS}</script></body></html>')
    with open(os.path.join(SHEETS, "review.html"), "w", encoding="utf-8") as fh:
        fh.write(page)
    print("RESULT wrote", os.path.join(SHEETS, "review.html"), len(names), "characters")


if __name__ == "__main__":
    main()
