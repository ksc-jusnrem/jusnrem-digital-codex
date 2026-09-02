#!/usr/bin/env python3
"""
Build a clean public reading edition from a Code, Law and Capital editorial Reader.

Reads only the READ pane of a Reader file. Discards the editorial apparatus
(stage panes, history, tab bar, per-paragraph marking controls, export bar,
build stamps, all-stage search index) and re-renders the prose in the
v0.20 "Designed" visual identity with web reading mechanics.

The source Reader is never modified. Output is a new file.

Usage:
    python build_clean_edition.py <reader.html> <output.html>
"""

import html
import re
import sys
from pathlib import Path

# ---------------------------------------------------------------- v0.20 tokens
GREEN = "#233B2C"
GOLD = "#A8813C"
INK = "#241E13"
INK_HEAD = "#17150F"
INK_SOFT = "#3A3226"
INK_MUTE = "#6A6152"
CREAM = "#F4EFDE"
BACKDROP = "#E9E4D6"
RULE = "#DCD3BC"
RULE_FAINT = "#E2DACA"
OXBLOOD = "#7A2E22"


def read_pane(src: str) -> str:
    """Isolate the READ pane; everything else in the Reader is apparatus."""
    start = src.index('<div class="pane on" id="read">')
    end = src.find('<div class="pane"', start)
    return src[start : end if end > 0 else len(src)]


def strip_controls(fragment: str) -> str:
    """Remove marking buttons and per-paragraph tooling, keeping prose intact."""
    fragment = re.sub(r'<span class="secmarks">.*?</span>', "", fragment, flags=re.S)
    fragment = re.sub(r'<div class="marks">.*?</div>', "", fragment, flags=re.S)
    fragment = re.sub(r'<div class="ptools">.*?</div>', "", fragment, flags=re.S)
    return fragment


def text_of(fragment: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", fragment))).strip()


def parse(pane: str) -> dict:
    doc = {"title": "", "subtitle": "", "blocks": [], "notes": []}

    m = re.search(r'<h1 class="chtitle">(.*?)</h1>', pane, re.S)
    doc["title"] = m.group(1).strip() if m else "Chapter"
    m = re.search(r'<div class="subtitle">(.*?)</div>', pane, re.S)
    doc["subtitle"] = m.group(1).strip() if m else ""

    # Footnote definitions live in a trailing .notes block.
    m = re.search(r'<div class="notes">.*?<ol>(.*?)</ol>', pane, re.S)
    if m:
        for li in re.finditer(r'<li id="(fn\d+)">(.*?)</li>', m.group(1), re.S):
            body = re.sub(r'<a class="backref".*?</a>\s*', "", li.group(2), flags=re.S)
            doc["notes"].append((li.group(1), body.strip()))
        pane = pane[: pane.index('<div class="notes">')]

    # Walk headings and paragraphs in document order.
    STOP = r'(?=<div class="para"|<(?:h[2-4]) id=|<figure|<div class="(?:caption|figurenote)"|$)'
    pattern = re.compile(
        # Two Reader generations exist: newer builds write class="hsec sec",
        # older builds write a bare <h2 id="s2-1">. Inner markup is identical,
        # so the class is optional here.
        r'<(h[2-4]) id="(s[\w-]*|sx\d+)"(?:\s+class="hsec sec")?[^>]*>(.*?)</\1>'
        r'|<div class="para" id="(p\d+)" data-pid="\4">(.*?)' + STOP +
        r'|<figure([^>]*)>\s*<img([^>]*)>\s*</figure>'
        r'|<div class="caption">(.*?)</div>'
        r'|<div class="figurenote">(.*?)</div>',
        re.S,
    )
    for m in pattern.finditer(pane):
        if m.group(1):
            inner = strip_controls(m.group(3))
            num = re.search(r'<span class="num">(.*?)</span>', inner)
            label = num.group(1).strip() if num else ""
            title = text_of(re.sub(r'<span class="num">.*?</span>', "", inner, flags=re.S))
            doc["blocks"].append(
                {"kind": "heading", "level": int(m.group(1)[1]), "id": m.group(2),
                 "num": label, "title": title}
            )
        elif m.group(4):
            body = strip_controls(m.group(5))
            t = re.search(r'<div class="ptext"[^>]*>(.*?)</div>\s*</div>\s*$', body, re.S)
            if not t:
                t = re.search(r'<div class="ptext"[^>]*>(.*?)</div>', body, re.S)
            doc["blocks"].append(
                {"kind": "para", "id": m.group(4), "num": m.group(4)[1:],
                 "html": (t.group(1) if t else body).strip()}
            )
        elif m.group(7) is not None:
            doc["blocks"].append({"kind": "figure",
                                  "figattrs": (m.group(6) or "").strip(),
                                  "attrs": m.group(7).strip()})
        elif m.group(8) is not None:
            doc["blocks"].append({"kind": "caption", "html": m.group(8).strip()})
        else:
            doc["blocks"].append({"kind": "fignote", "html": m.group(9).strip()})
    return doc


def render(doc: dict, note_map: dict) -> str:
    contents, body = [], []
    blocks = doc["blocks"]
    for i, b in enumerate(blocks):
        if b["kind"] in ("caption", "fignote"):
            continue  # emitted with the figure they belong to
        if b["kind"] == "figure":
            # The caption and the accessible description follow the image.
            cap = next((x["html"] for x in blocks[i + 1 : i + 3] if x["kind"] == "caption"), "")
            note = next((x["html"] for x in blocks[i + 1 : i + 3] if x["kind"] == "fignote"), "")
            attrs = re.sub(r'\salt="[^"]*"', "", b["attrs"])
            decorative = (
                "aria-hidden" in b.get("figattrs", "")
                or (not cap and not note and 'alt=""' in b["attrs"])
            )
            if decorative:
                # An ornament carries no information: keep it, but keep it silent
                # for assistive technology rather than inventing a description.
                body.append(
                    f'<figure class="ornament" aria-hidden="true">'
                    f'<img {attrs} alt=""></figure>'
                )
            else:
                alt = html.escape(text_of(note or cap), quote=True)
                body.append(
                    f'<figure><img {attrs} alt="{alt}">'
                    + (f'<figcaption>{cap}</figcaption>' if cap else "")
                    + (f'<p class="fignote">{note}</p>' if note else "")
                    + "</figure>"
                )
            continue
        if b["kind"] == "heading":
            lvl = b["level"]
            label = f'<span class="num">{b["num"]}</span> ' if b["num"] else ""
            body.append(
                f'<h{lvl} id="{b["id"]}" class="sec lvl{lvl}">{label}{html.escape(b["title"])}</h{lvl}>'
            )
            contents.append(
                f'<li class="toc-l{lvl}"><a href="#{b["id"]}">'
                f'{html.escape((b["num"] + " " + b["title"]).strip())}</a></li>'
            )
        else:
            body.append(
                f'<div class="para" id="{b["id"]}">'
                f'<a class="pnum" href="#{b["id"]}" aria-label="Paragraph {b["num"]}">{b["num"]}</a>'
                f'<div class="ptext">{b["html"]}</div></div>'
            )

    notes_html = "".join(
        f'<li id="{fid}"><a class="backref" href="#{fid.replace("fn", "fnref")}" '
        f'aria-label="Back to text">&#8593;</a> {txt}</li>'
        for fid, txt in doc["notes"]
    )

    return TEMPLATE.format(
        title=doc["title"],
        title_text=html.escape(text_of(doc["title"])),
        subtitle=doc["subtitle"],
        contents="".join(contents),
        body="".join(body),
        notes=notes_html,
        note_data=note_map,
        **TOKENS,
    )


TOKENS = dict(
    green=GREEN, gold=GOLD, ink=INK, ink_head=INK_HEAD, ink_soft=INK_SOFT,
    ink_mute=INK_MUTE, cream=CREAM, backdrop=BACKDROP, rule=RULE,
    rule_faint=RULE_FAINT, oxblood=OXBLOOD,
)

TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_text} &mdash; Code, Law and Capital</title>
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Archivo:wght@400;500;600;700&family=Cormorant+Garamond:ital,wght@0,500;0,600;1,500&family=Spectral:ital,wght@0,400;0,600;1,400&display=swap" rel="stylesheet">
<style>
:root{{
  --green:{green}; --gold:{gold}; --ink:{ink}; --ink-head:{ink_head};
  --ink-soft:{ink_soft}; --ink-mute:{ink_mute}; --cream:{cream};
  --backdrop:{backdrop}; --rule:{rule}; --rule-faint:{rule_faint}; --oxblood:{oxblood};
  --sans:Archivo,"Helvetica Neue",Arial,sans-serif;
  --serif:Spectral,Georgia,"Times New Roman",serif;
  --display:"Cormorant Garamond",Georgia,serif;
}}
*{{box-sizing:border-box}}
html{{scroll-behavior:smooth;scroll-padding-top:5rem}}
body{{margin:0;background:var(--backdrop);color:var(--ink);font:400 1.0625rem/1.65 var(--serif)}}

/* ---- masthead ---- */
.masthead{{position:sticky;top:0;z-index:40;background:var(--green);color:var(--cream);
  border-bottom:2px solid var(--gold);display:flex;align-items:center;gap:1rem;
  padding:.6rem 1.1rem;font-family:var(--sans)}}
.masthead .work{{font:600 .72rem/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;
  color:var(--cream);text-decoration:none;white-space:nowrap}}
.masthead .work span{{color:var(--gold)}}
.masthead form{{margin-left:auto;display:flex;align-items:center}}
#q{{font:400 .82rem var(--sans);padding:.32rem .6rem;width:14rem;max-width:38vw;
  border:1px solid rgba(244,239,222,.35);background:rgba(244,239,222,.08);
  color:var(--cream);border-radius:2px}}
#q::placeholder{{color:rgba(244,239,222,.55)}}
#q:focus{{outline:2px solid var(--gold);outline-offset:1px}}
#navtoggle{{display:none;font:600 .72rem var(--sans);letter-spacing:.12em;text-transform:uppercase;
  background:none;border:1px solid rgba(244,239,222,.4);color:var(--cream);
  padding:.3rem .55rem;border-radius:2px;cursor:pointer}}

/* ---- shell ---- */
.shell{{display:grid;grid-template-columns:17rem minmax(0,1fr);gap:0;
  max-width:76rem;margin:0 auto;align-items:start}}

/* ---- sidebar ---- */
.sidebar{{position:sticky;top:3.1rem;max-height:calc(100vh - 3.1rem);overflow-y:auto;
  padding:1.6rem 1rem 3rem 1.2rem;font-family:var(--sans);
  border-right:1px solid var(--rule)}}
.sidebar h2{{font:600 .68rem/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;
  color:var(--ink-mute);margin:0 0 .9rem}}
.sidebar ol{{list-style:none;margin:0;padding:0}}
.sidebar a{{display:block;padding:.24rem .45rem;font-size:.79rem;line-height:1.35;
  color:var(--ink-soft);text-decoration:none;border-left:2px solid transparent;border-radius:2px}}
.sidebar a:hover{{color:var(--green);background:rgba(168,129,60,.09)}}
.sidebar a.here{{color:var(--green);font-weight:600;border-left-color:var(--gold);
  background:rgba(168,129,60,.13)}}
.toc-l3 a{{padding-left:1.15rem;font-size:.75rem;color:var(--ink-mute)}}
.toc-l4 a{{padding-left:1.9rem;font-size:.73rem;color:var(--ink-mute)}}

/* ---- sheet ---- */
.sheet{{background:#fff;border-left:1px solid var(--rule);border-right:1px solid var(--rule);
  padding:3rem 3.4rem 5rem;min-height:100vh}}
/* ---- chapter cover band, after the v0.20 cover ---- */
.cover{{position:relative;margin:-3rem -3.4rem 2.4rem;padding:2.6rem 3.4rem 2.4rem;
  background:var(--green);color:var(--cream);overflow:hidden}}
.cover .plate{{position:absolute;inset:0;background:url("assets/clc-cover.jpg") center/cover no-repeat;
  opacity:.20;filter:grayscale(.25)}}
.cover .frame{{position:absolute;inset:.7rem;border:2px solid rgba(168,129,60,.45);
  pointer-events:none}}
.cover > *:not(.plate):not(.frame){{position:relative}}
.cover .eyebrow{{font:600 .68rem/1 var(--sans);letter-spacing:.24em;text-transform:uppercase;
  color:var(--gold);margin-bottom:1rem}}
.cover .rule{{display:flex;align-items:center;gap:.6rem;margin:.9rem 0 0;width:60%}}
.cover .rule i{{display:block;width:5px;height:5px;background:var(--gold);transform:rotate(45deg)}}
.cover .rule b{{flex:1;height:1px;background:rgba(168,129,60,.6)}}
h1{{margin:0;font:600 2.5rem/1.12 var(--display);color:var(--cream);text-wrap:balance}}
.cover .subtitle{{margin-top:.7rem;font:500 1.12rem/1.35 var(--display);font-style:italic;
  color:var(--gold)}}
.cover .byline{{margin-top:1.1rem;font:500 .72rem/1 var(--sans);letter-spacing:.28em;
  text-transform:uppercase;color:rgba(244,239,222,.85)}}

h2.sec{{margin:2.6rem 0 .9rem;padding-bottom:.4rem;border-bottom:1px solid var(--rule);
  font:600 1.08rem/1.3 var(--sans);letter-spacing:.02em;color:var(--ink-head);text-wrap:balance}}
h3.sec{{margin:2rem 0 .6rem;font:600 1.16rem/1.35 var(--display);color:var(--oxblood);text-wrap:balance}}
h4.sec{{margin:1.5rem 0 .5rem;font:600 .95rem/1.35 var(--sans);color:var(--ink-soft)}}
.sec .num{{color:var(--gold);font-variant-numeric:tabular-nums}}

/* ---- paragraphs ---- */
.para{{position:relative;margin:0 0 1.05rem;padding-left:2.6rem;scroll-margin-top:5rem}}
.pnum{{position:absolute;left:0;top:.28rem;width:2rem;text-align:right;
  font:500 .68rem/1 var(--sans);color:#B9B09C;text-decoration:none;
  font-variant-numeric:tabular-nums;transition:color .12s}}
.para:hover .pnum,.pnum:focus{{color:var(--gold)}}
.para:target .ptext{{background:rgba(168,129,60,.1);box-shadow:-.5rem 0 0 rgba(168,129,60,.1),.5rem 0 0 rgba(168,129,60,.1)}}
.ptext{{text-align:left;text-wrap:pretty}}
.ptext em{{font-style:italic}}
.ptext ul.condlist{{margin:.6rem 0 .6rem 1.15rem;padding:0;list-style:disc}}
.ptext ul.condlist li{{margin:.42rem 0}}
.ptext ul.condlist strong{{font-weight:600;color:var(--ink-head)}}

/* ---- figures ---- */
figure{{margin:2.2rem 0}}
img{{max-width:100%;height:auto;display:block;border:1px solid var(--rule-faint)}}
figcaption{{margin-top:.7rem;font:600 1.02rem/1.35 var(--display);color:var(--oxblood)}}
.fignote{{margin:.5rem 0 0;font:italic 400 .82rem/1.5 var(--serif);color:var(--ink-mute)}}
figure.ornament{{margin:2rem auto;max-width:16rem;opacity:.55}}
figure.ornament img{{border:0}}

/* ---- footnotes: inline popover, print endnotes ---- */
sup.fnref{{line-height:0}}
sup.fnref a,button.fnbtn{{font:600 .62rem/1 var(--sans);color:#fff;background:var(--green);
  border:0;border-radius:2px;padding:.12rem .3rem;margin:0 .1rem;cursor:pointer;
  text-decoration:none;vertical-align:super;font-variant-numeric:tabular-nums}}
button.fnbtn:hover,button.fnbtn[aria-expanded=true]{{background:var(--gold)}}
.fnpop{{position:absolute;z-index:60;max-width:min(30rem,88vw);background:#fff;
  border:1px solid var(--gold);border-top:3px solid var(--gold);
  box-shadow:0 6px 24px rgba(36,30,19,.22);padding:.8rem .95rem;
  font:400 .84rem/1.5 var(--serif);color:var(--ink-soft);border-radius:2px}}
.fnpop .close{{float:right;margin:-.3rem -.3rem 0 .5rem;border:0;background:none;
  font:600 .95rem/1 var(--sans);color:var(--ink-mute);cursor:pointer}}
.notes{{margin-top:3.5rem;border-top:1px solid var(--rule);padding-top:1.4rem}}
.notes h2{{font:600 .72rem/1 var(--sans);letter-spacing:.2em;text-transform:uppercase;
  color:var(--ink-mute);margin:0 0 1rem}}
.notes ol{{margin:0;padding-left:1.4rem}}
.notes li{{margin:.45rem 0;font-size:.85rem;line-height:1.5;color:var(--ink-soft);
  scroll-margin-top:5rem}}
.notes li:target{{background:rgba(168,129,60,.12)}}
.backref{{color:var(--gold);text-decoration:none;margin-right:.25rem}}
a{{color:var(--green)}}
a:hover{{color:var(--gold)}}

/* ---- search ---- */
mark{{background:rgba(168,129,60,.34);color:inherit;padding:0 .08em}}
.nohit{{display:none}}
#searchnote{{font:500 .76rem var(--sans);color:var(--ink-mute);margin:1rem 0 0}}

/* ---- responsive ---- */
@media (max-width:960px){{
  .shell{{grid-template-columns:1fr}}
  .sidebar{{position:static;max-height:none;border-right:0;border-bottom:1px solid var(--rule);
    display:none;background:#fff}}
  .sidebar.open{{display:block}}
  #navtoggle{{display:inline-block}}
  .sheet{{padding:1.8rem 1.25rem 3.5rem;border:0}}
  .cover{{margin:-1.8rem -1.25rem 1.8rem;padding:2rem 1.25rem 1.8rem}}
  .cover .rule{{width:100%}}
  h1{{font-size:1.95rem}}
  .masthead{{gap:.6rem;padding:.55rem .8rem}}
  .masthead .work{{font-size:.62rem;overflow:hidden;text-overflow:ellipsis}}
  .masthead form{{flex:1;min-width:0}}
  #q{{width:100%;max-width:none}}
  .para{{padding-left:0}}
  .pnum{{position:static;display:inline-block;width:auto;margin-right:.5rem;
    text-align:left;color:var(--gold)}}
}}

@media (max-width:560px){{
  .masthead .work{{display:none}}
}}

/* ---- print: return to the v0.20 page design ---- */
@media print{{
  @page{{size:Letter;margin:.85in}}
  body{{background:#fff;font:400 10.4pt/1.62 var(--serif)}}
  .masthead,.sidebar,#searchnote,.fnpop,button.fnbtn{{display:none!important}}
  .shell{{display:block;max-width:none}}
  .sheet{{border:0;padding:0;min-height:0}}
  .ptext{{text-align:justify;hyphens:auto}}
  .para{{padding-left:2.2rem}}
  .pnum{{color:#8A8272}}
  h1,h2,h3,h4{{break-after:avoid}}
  p,.para{{orphans:2;widows:2}}
  sup.fnref a{{background:none;color:var(--ink);padding:0;font-size:.7em}}
  .notes{{break-before:page}}
  a{{color:var(--ink);text-decoration:none}}
}}
</style>
</head>
<body>
<header class="masthead">
  <button id="navtoggle" aria-expanded="false" aria-controls="sidebar">Contents</button>
  <a class="work" href="index.html">Code, Law <span>&amp;</span> Capital</a>
  <form role="search" onsubmit="return false">
    <label class="sr-only" for="q" hidden>Search this chapter</label>
    <input id="q" type="search" placeholder="Search this chapter&hellip;" autocomplete="off">
  </form>
</header>

<div class="shell">
  <nav class="sidebar" id="sidebar" aria-label="Chapter contents">
    <h2>On this page</h2>
    <ol>{contents}</ol>
    <p id="searchnote" hidden></p>
  </nav>

  <main class="sheet">
    <div class="cover">
      <div class="plate" role="presentation"></div>
      <div class="frame" role="presentation"></div>
      <div class="eyebrow">Chapter One &middot; Part A</div>
      <h1>{title}</h1>
      <div class="subtitle">{subtitle}</div>
      <div class="rule"><i></i><b></b></div>
      <div class="byline">Khurram Chughtai</div>
    </div>
    {body}
    <section class="notes" aria-label="Footnotes">
      <h2>Footnotes</h2>
      <ol>{notes}</ol>
    </section>
  </main>
</div>

<script>
const NOTES = {note_data};

/* Footnotes as inline popovers, with the anchor link preserved underneath. */
function upgradeFootnotes(root) {{
  root.querySelectorAll('sup.fnref > a').forEach(a => {{
    const id = (a.getAttribute('href') || '').slice(1);
    if (!NOTES[id]) return;
    const btn = document.createElement('button');
    btn.className = 'fnbtn';
    btn.type = 'button';
    btn.textContent = a.textContent;
    btn.setAttribute('aria-expanded', 'false');
    btn.setAttribute('aria-label', 'Footnote ' + a.textContent);
    btn.dataset.fn = id;
    a.parentNode.replaceChild(btn, a);
  }});
}}
upgradeFootnotes(document);

let openPop = null;
function closePop() {{
  if (!openPop) return;
  openPop.btn.setAttribute('aria-expanded', 'false');
  openPop.el.remove();
  openPop = null;
}}
document.addEventListener('click', e => {{
  const btn = e.target.closest('button.fnbtn');
  if (!btn) {{ if (!e.target.closest('.fnpop')) closePop(); return; }}
  const wasOpen = openPop && openPop.btn === btn;
  closePop();
  if (wasOpen) return;
  const pop = document.createElement('div');
  pop.className = 'fnpop';
  pop.innerHTML = '<button class="close" aria-label="Close">&times;</button>' + NOTES[btn.dataset.fn];
  document.body.appendChild(pop);
  const r = btn.getBoundingClientRect();
  const top = r.bottom + window.scrollY + 6;
  let left = r.left + window.scrollX - 20;
  left = Math.max(10, Math.min(left, window.scrollX + document.documentElement.clientWidth - pop.offsetWidth - 10));
  pop.style.top = top + 'px';
  pop.style.left = left + 'px';
  btn.setAttribute('aria-expanded', 'true');
  openPop = {{ btn, el: pop }};
  pop.querySelector('.close').addEventListener('click', closePop);
}});
document.addEventListener('keydown', e => {{ if (e.key === 'Escape') closePop(); }});
window.addEventListener('resize', closePop);

/* Sidebar: current-section highlight. */
const links = [...document.querySelectorAll('.sidebar a')];
const targets = links.map(a => document.getElementById(a.getAttribute('href').slice(1))).filter(Boolean);
const spy = new IntersectionObserver(entries => {{
  entries.forEach(en => {{
    if (!en.isIntersecting) return;
    links.forEach(l => l.classList.remove('here'));
    const hit = links.find(l => l.getAttribute('href') === '#' + en.target.id);
    if (hit) hit.classList.add('here');
  }});
}}, {{ rootMargin: '-64px 0px -75% 0px' }});  /* px or % only; rem throws */
targets.forEach(t => spy.observe(t));

/* Mobile contents toggle. */
const toggle = document.getElementById('navtoggle');
toggle.addEventListener('click', () => {{
  const open = document.getElementById('sidebar').classList.toggle('open');
  toggle.setAttribute('aria-expanded', String(open));
}});

/* Search, scoped to this chapter only. */
const paras = [...document.querySelectorAll('.para')];
const originals = paras.map(p => p.querySelector('.ptext').innerHTML);
const note = document.getElementById('searchnote');
const q = document.getElementById('q');
let timer;
q.addEventListener('input', () => {{ clearTimeout(timer); timer = setTimeout(run, 140); }});

/* Wrap matches in the text nodes only, so tags and footnote buttons survive. */
function highlight(el, term) {{
  const rx = new RegExp('(' + term.replace(/[.*+?^${{}}()|[\\]\\\\]/g, '\\\\$&') + ')', 'gi');
  const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
  const nodes = [];
  for (let n = walker.nextNode(); n; n = walker.nextNode()) nodes.push(n);
  let found = 0;
  nodes.forEach(n => {{
    rx.lastIndex = 0;
    if (!rx.test(n.nodeValue)) return;
    rx.lastIndex = 0;
    found++;
    const frag = document.createDocumentFragment();
    let last = 0, m;
    while ((m = rx.exec(n.nodeValue)) !== null) {{
      frag.appendChild(document.createTextNode(n.nodeValue.slice(last, m.index)));
      const mk = document.createElement('mark');
      mk.textContent = m[0];
      frag.appendChild(mk);
      last = m.index + m[0].length;
      if (m[0] === '') rx.lastIndex++;
    }}
    frag.appendChild(document.createTextNode(n.nodeValue.slice(last)));
    n.parentNode.replaceChild(frag, n);
  }});
  return found > 0;
}}

function run() {{
  const term = q.value.trim();
  closePop();
  paras.forEach((p, i) => {{
    const el = p.querySelector('.ptext');
    el.innerHTML = originals[i];   // discards the upgraded footnote buttons,
    upgradeFootnotes(el);          // so rebuild them on the restored markup
    p.classList.remove('nohit');
  }});
  if (term.length < 2) {{ note.hidden = true; return; }}
  let hits = 0;
  paras.forEach(p => {{
    if (highlight(p.querySelector('.ptext'), term)) hits++;
    else p.classList.add('nohit');
  }});
  note.hidden = false;
  note.textContent = hits
    ? hits + ' paragraph' + (hits === 1 ? '' : 's') + ' matching \\u201c' + term + '\\u201d'
    : 'No match in this chapter.';
}}
</script>
</body>
</html>
"""


def main() -> None:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    src_path, out_path = Path(sys.argv[1]), Path(sys.argv[2])
    src = src_path.read_text(encoding="utf-8")

    doc = parse(read_pane(src))
    note_map = "{" + ",".join(
        '"%s":%s' % (fid, _js(txt)) for fid, txt in doc["notes"]
    ) + "}"

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.write_text(render(doc, note_map), encoding="utf-8")

    print(f"{src_path.name}: {len(src):,} bytes")
    print(f"{out_path.name}: {out_path.stat().st_size:,} bytes")
    print(f"  paragraphs {sum(1 for b in doc['blocks'] if b['kind'] == 'para')}"
          f"  headings {sum(1 for b in doc['blocks'] if b['kind'] == 'heading')}"
          f"  footnotes {len(doc['notes'])}")


def _js(s: str) -> str:
    """Embed HTML safely inside a JS string literal."""
    return (
        '"' + s.replace("\\", "\\\\").replace('"', '\\"')
        .replace("\n", " ").replace("</", "<\\/") + '"'
    )


if __name__ == "__main__":
    main()
