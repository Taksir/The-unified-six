"""M6: static website for GitHub Pages (plain HTML/CSS + a few lines of JS; search by Pagefind).

    python -m u6 m6 build          -> site/   (then: python -m pagefind --site site)

Input: data/release/hadith.jsonl (run `m5 clean && m5 dataset` first), data/narrations,
data/books.json, data/release/concordance.csv. Every link is relative, so the site works at
https://taksir.github.io/The-unified-six/ and from a local folder alike.
"""

import csv
import html
import json
import re
import shutil
from collections import defaultdict

from . import m4
from .corpus import DATA, ROOT
from .m5 import BOOKS, LETTER, VERSION, load_narrations
from .split import segments as split_segments
from .textnorm import DIACRITICS, letters

SITE = ROOT / "site"
REPO = "https://github.com/Taksir/The-unified-six"
PER_PAGE = 150
STAR_NOTE = {6: "in all six books", 5: "in five books", 4: "in four books", 3: "in three books",
             2: "in two books", 1: "in one book"}
esc = html.escape


def slug(s: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


CSS = """
:root{--bg:#fbfaf7;--fg:#1d1c1a;--muted:#6b665e;--line:#e3dfd6;--card:#fff;--accent:#1f5fa8;
--green:#2e8540;--blue:#1f5fa8;--hl:#fff1b8;--it:#5a554d}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#141412;--fg:#ebe8e1;--muted:#a39d92;
--line:#2f2d29;--card:#1c1b19;--accent:#8db8ef;--green:#5cbf73;--blue:#8db8ef;--hl:#4a4020;--it:#c9c3b8}}
@font-face{font-family:Amiri;src:url(%(root)sfonts/Amiri-Regular.ttf);font-display:swap}
@font-face{font-family:Amiri;font-weight:700;src:url(%(root)sfonts/Amiri-Bold.ttf);font-display:swap}
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%%}
body{margin:0;background:var(--bg);color:var(--fg);font:17px/1.6 Georgia,"Times New Roman",serif}
a{color:var(--accent)}header,main,footer{max-width:860px;margin:0 auto;padding:0 16px}
header{display:flex;flex-wrap:wrap;gap:.4em 1.2em;align-items:baseline;padding-top:14px;padding-bottom:10px;border-bottom:1px solid var(--line)}
header .brand{font-size:1.25em;font-weight:700;text-decoration:none;color:var(--fg)}
header nav a{margin-right:.9em;white-space:nowrap;font-family:system-ui,sans-serif;font-size:.9em}
footer{color:var(--muted);font:13px/1.5 system-ui,sans-serif;padding-top:24px;padding-bottom:40px;border-top:1px solid var(--line);margin-top:40px}
h1{font-size:1.6em;line-height:1.25;margin:.8em 0 .3em}h2{font-size:1.2em;margin:1.6em 0 .5em}
.sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}.muted{color:var(--muted)}.small{font:14px/1.5 system-ui,sans-serif}
.en .add{font-style:italic;color:var(--it)}.ar{font-family:Amiri,serif;font-size:1.35em;line-height:2;direction:rtl;text-align:right}
.ar .add{color:var(--it)}.seg{border-radius:3px;transition:background .15s}.seg.on{background:var(--hl)}
.bracket{font:14px/1.6 system-ui,sans-serif;color:var(--muted);margin:.6em 0 1.2em}
.dot{display:inline-block;width:.7em;height:.7em;border-radius:50%%;vertical-align:-.05em}.muttafaq{background:var(--green)}.sahih_one{background:var(--blue)}
details{border:1px solid var(--line);border-radius:6px;background:var(--card);margin:.7em 0;padding:.4em .9em}
summary{cursor:pointer;font:600 15px/1.8 system-ui,sans-serif}
table{border-collapse:collapse;width:100%%;font:14px/1.5 system-ui,sans-serif}td,th{border-bottom:1px solid var(--line);padding:.35em .4em;text-align:left;vertical-align:top}
tr.on td{background:var(--hl)}.chain{font-family:Amiri,serif;font-size:1.15em;direction:rtl;text-align:right;line-height:1.9}
ol.list{padding-left:0;list-style:none}ol.list li{padding:.7em 0;border-bottom:1px solid var(--line)}
ol.list .n{font-weight:700;margin-right:.3em}.pager{font:15px system-ui,sans-serif;margin:1.2em 0}.pager a,.pager span{margin-right:.6em}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:.3em 1.2em;font:15px/1.6 system-ui,sans-serif}
.note{background:var(--card);border-left:3px solid var(--accent);padding:.6em .9em;font:14px/1.55 system-ui,sans-serif}
@media (min-width:900px){.pair{display:grid;grid-template-columns:1fr 1fr;gap:28px}}
"""

JS = """
document.querySelectorAll('.seg[data-in]').forEach(function(s){
  function set(on){var ids=s.dataset.in.split(' ');
    document.querySelectorAll('.seg[data-i="'+s.dataset.i+'"]').forEach(function(x){x.classList.toggle('on',on)});
    document.querySelectorAll('tr[data-id]').forEach(function(r){r.classList.toggle('on',on&&ids.indexOf(r.dataset.id)>=0)});}
  s.addEventListener('mouseenter',function(){set(true)});s.addEventListener('mouseleave',function(){set(false)});
  s.addEventListener('click',function(){var o=!s.classList.contains('on');set(o);if(o){var d=document.getElementById('sources');if(d)d.open=true}});
});
"""


def page(title: str, body: str, root: str, desc: str = "", search: bool = False) -> str:
    extra = (f'<link rel="stylesheet" href="{root}pagefind/pagefind-ui.css">'
             f'<script src="{root}pagefind/pagefind-ui.js"></script>') if search else ""
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{esc(title)}</title><meta name="description" content="{esc(desc or 'The six canonical hadith books, each distinct hadith once.')}">
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns=%22http://www.w3.org/2000/svg%22 viewBox=%220 0 16 16%22%3E%3Ctext y=%2213%22 font-size=%2213%22%3E6%3C/text%3E%3C/svg%3E"><link rel="stylesheet" href="{root}style.css">{extra}</head><body>
<header><a class="brand" href="{root}index.html">The Unified Six</a>
<nav><a href="{root}topics/index.html">Topics</a><a href="{root}stars/index.html">By attestation</a><a href="{root}books/index.html">By book</a><a href="{root}search/index.html">Search</a><a href="{root}about/index.html">About</a></nav></header>
<main>{body}</main>
<footer>The Unified Six v{VERSION} · machine-assisted compilation, machine translation — please
<a href="{REPO}/issues">report mistakes</a>. Text and data CC BY 4.0, code MIT ·
<a href="{REPO}">source</a> · <a href="{REPO}/releases">PDFs and dataset</a></footer>
<script>{JS}</script></body></html>"""


def write(path: str, content: str) -> None:
    p = SITE / path
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def depth_root(path: str) -> str:
    return "../" * path.count("/")


class Data:
    def __init__(self):
        self.hadith = [json.loads(l) for l in (DATA / "release" / "hadith.jsonl").open(encoding="utf-8")]
        self.n_narr = sum(len(h["members"]) for h in self.hadith)   # all 34,150, text-less entries included
        self.hadith = [h for h in self.hadith if not h.get("no_text")]
        self.narr = load_narrations()
        books = json.loads((DATA / "books.json").read_text())["books"]
        self.books = {b["slug"]: b for b in books}
        self.ch_title = {(b["slug"], c["chapter"]): c["title_en"] for b in books for c in b["chapters"]}
        self.url = {r["narration"]: r["sunnah_url"] for r in
                    csv.DictReader((DATA / "release" / "concordance.csv").open(encoding="utf-8"))}
        self.by_id = {h["id"]: h for h in self.hadith}
        self.of = {m["id"]: h["id"] for h in self.hadith for m in h["members"]}

    def number(self, nid: str) -> str:
        r = self.narr[nid]
        return (r["n_fab"] or r["n"]) if r["book"] == "muslim" else r["n"]


def letters_of(h: dict) -> str:
    return " ".join(LETTER[b] for b in BOOKS if b in h["books_full"] + h["books_partial"])


def bracket(h: dict) -> str:
    grades = sorted({g["en"] for g in h.get("tirmidhi_grades") or []})
    badge = f' <span class="dot {h["badge"]}" title="{"muttafaq ʿalayh" if h["badge"] == "muttafaq" else "in al-Bukhārī or Muslim"}"></span>' if h["badge"] else ""
    parts = [f'{h["stars_display"]}{badge}', letters_of(h)]
    if grades:
        parts.append("T: " + "; ".join(grades))
    if h.get("uncertain"):
        parts.append('<span title="grouping rests on an uncertain machine judgement">≈ uncertain grouping</span>')
    parts.append(f'A{h["edition_a"]} · B{h["edition_b"]}')
    return '<div class="bracket">' + " · ".join(parts) + "</div>"


def shown(h: dict):
    k = h.get("commentary_from")
    return h["segments"][:k] if k is not None else h["segments"]


def text_html(h: dict, lang: str, link_ids: bool) -> str:
    out = []
    for i, s in enumerate(shown(h)):
        cls = "seg" + ("" if s["core"] or h.get("italics_dropped") else " add")
        attrs = f' data-i="{i}" data-in="{esc(" ".join(s["in"]))}"' if link_ids and not s["core"] else f' data-i="{i}"'
        out.append(f'<span class="{cls}"{attrs}>{esc(s[lang])}</span>')
    return " ".join(out)


def snippet(h: dict, n: int = 260) -> str:
    t = " ".join(s["en"] for s in shown(h))
    return esc(t if len(t) <= n else t[:n].rsplit(" ", 1)[0] + " …")


def hadith_page(d: Data, h: dict) -> str:
    path = f"h/{h['id']}/index.html"
    root = depth_root(path)
    members = sorted(h["members"], key=lambda m: (BOOKS.index(m["book"]), d.narr[m["id"]]["seq"]))
    grade = {g["id"]: g["en"] for g in h.get("tirmidhi_grades") or []}
    rows, chains = [], []
    for m in members:
        r = d.narr[m["id"]]
        b = d.books[m["book"]]
        kind = {"ref": "chain only (“with this isnād, likewise”)", "ref_variant": "variant chain"}.get(m["kind"], "")
        role = "★ full" if m["role"] == "full" else "⯪ fragment"
        rep = " <strong>— text shown</strong>" if m["id"] == h["representative"] else ""
        link = f' · <a href="{esc(d.url.get(m["id"], ""))}" rel="noopener">sunnah.com</a>' if d.url.get(m["id"]) else ""
        g = f"<br>Tirmidhī: {esc(grade[m['id']])}" if m["id"] in grade else ""
        rows.append(f'<tr data-id="{esc(m["id"])}"><td>{LETTER[m["book"]]} {esc(d.number(m["id"]))}</td>'
                    f'<td>{esc(b["name_en"])}, {esc(d.ch_title.get((m["book"], r["chapter"]), ""))}<br>'
                    f'{role}{" · " + kind if kind else ""}{rep}{g}</td>'
                    f'<td class="chain" lang="ar">{esc(r.get("isnad_last") or "")}</td><td>{link}</td></tr>')
        if r["kind"] != "empty" and r["text"]:
            isnad, matn, tail = split_segments(r["text"], r["split"])
            chains.append(f'<details><summary>{LETTER[m["book"]]} {esc(d.number(m["id"]))} — full text with chain</summary>'
                          f'<p class="chain" lang="ar">{esc(isnad)} <strong>{esc(matn)}</strong> {esc(tail)}</p></details>')
    see = [f'<a href="{root}h/{x}/index.html">{x}</a>' for x in h.get("see_also") or [] if x in d.by_id]
    topics = [h["topic"]] + list(h.get("topics_secondary") or [])
    topic_links = ", ".join(f'<a href="{root}topics/{slug(t)}/index.html">{esc(t)}</a>' for t in topics)
    notes = []
    if h.get("review_fix"):
        notes.append(f"Translation corrected in v1.1 (machine review): {esc(h['review_fix'])}")
    if h.get("extended_from_stub"):
        notes.append("Text repaired: the source split cut it short; shown in full after the first chain.")
    if h.get("commentary_from") is not None:
        notes.append("Al-Tirmidhī's own commentary after the hadith is not shown here (see the full text below).")
    issue = f"{REPO}/issues/new?title={h['id']}%3A%20&body=Hadith%20{h['id']}%20%28site%20v{VERSION}%29"
    # search sees every narration's wording (not only the version shown), without diacritics,
    # with and without hamza forms, so any book's phrasing finds the entry
    texts = [" ".join(s["ar"] for s in shown(h))]
    for m in members:
        r = d.narr[m["id"]]
        if r["kind"] != "empty" and r["text"]:
            texts.append(split_segments(r["text"], r["split"])[1])
    seen, parts = set(), []
    for t in texts:
        for v in (DIACRITICS.sub("", t), letters(t)):
            if v and v not in seen:
                seen.add(v)
                parts.append(v)
    hidden_ar = esc(" | ".join(parts))
    body = f"""
<article data-pagefind-body>
<h1>{h['id']} <span class="muted small">{esc(h['topic'])}</span></h1>
<div data-pagefind-filter="topic" hidden>{esc(h['topic'])}</div>
<div data-pagefind-filter="books" hidden>{esc(letters_of(h))}</div>
<div data-pagefind-filter="stars" hidden>{h['stars']}</div>
<div class="pair"><p class="en">{text_html(h, 'en', True)}</p>
<p class="ar" lang="ar" dir="rtl">{text_html(h, 'ar', True)}</p></div>
<div class="sr" lang="ar">{hidden_ar}</div>
</article>
{bracket(h)}
<p class="small muted">Upright text appears in every full version; <em>italic</em> text only in some —
tap or hover it to see which narrations carry it. ★ = full in that book, ⯪ = fragment only.
Stars count books, not authenticity. English: machine translation.</p>
{''.join(f'<p class="note">{n}</p>' for n in notes)}
<details id="sources" open><summary>Sources — {len(members)} narration{'s' if len(members) > 1 else ''}</summary>
<table><tr><th>No.</th><th>Book, chapter</th><th>Narrator</th><th></th></tr>{''.join(rows)}</table></details>
<details><summary>Full Arabic texts with chains</summary>{''.join(chains)}</details>
<p class="small">Topics: {topic_links}</p>
{f'<p class="small">See also (possible duplicates, unconfirmed): {", ".join(see)}</p>' if see else ''}
<p class="small"><a href="{issue}" rel="noopener">Report an issue with this hadith</a></p>
"""
    return page(f"{h['id']} · The Unified Six", body, root, desc=snippet(h, 150))


def entry_li(h: dict, root: str) -> str:
    return (f'<li><a class="n" href="{root}h/{h["id"]}/index.html">{h["id"]}</a> {snippet(h)}'
            f'<div class="bracket">{h["stars_display"]} · {letters_of(h)}</div></li>')


def listing(prefix: str, title: str, intro: str, hs: list[dict]) -> None:
    pages = max(1, -(-len(hs) // PER_PAGE))
    for k in range(pages):
        path = f"{prefix}/index.html" if k == 0 else f"{prefix}/{k + 1}/index.html"
        root = depth_root(path)
        here = "" if k == 0 else "../"
        nav = " ".join(f'<span>{i + 1}</span>' if i == k else
                       f'<a href="{here}{"" if i == 0 else f"{i + 1}/"}index.html">{i + 1}</a>' for i in range(pages))
        chunk = hs[k * PER_PAGE:(k + 1) * PER_PAGE]
        body = (f"<h1>{esc(title)}</h1><p class='muted'>{intro} · {len(hs):,} hadith</p>"
                + (f'<div class="pager">{nav}</div>' if pages > 1 else "")
                + "<ol class='list'>" + "".join(entry_li(h, root) for h in chunk) + "</ol>"
                + (f'<div class="pager">{nav}</div>' if pages > 1 else ""))
        write(path, page(f"{title} · The Unified Six", body, root))


def order(hs, edition):
    t = {x: i for i, x in enumerate(m4.TOPICS)}
    key = (lambda h: h["edition_a"]) if edition == "A" else (lambda h: h["edition_b"])
    return sorted(hs, key=key)


def build() -> None:
    d = Data()
    if SITE.exists():
        shutil.rmtree(SITE)
    SITE.mkdir()
    (SITE / "fonts").mkdir()
    for f in ("Amiri-Regular.ttf", "Amiri-Bold.ttf", "OFL-Amiri.txt"):
        shutil.copy(ROOT / "typeset" / "fonts" / f, SITE / "fonts" / f)
    (SITE / "style.css").write_text(CSS.replace("%(root)s", "").replace("%%", "%"), encoding="utf-8")
    (SITE / ".nojekyll").write_text("")

    for h in d.hadith:
        write(f"h/{h['id']}/index.html", hadith_page(d, h))

    by_b = order(d.hadith, "B")
    topics = defaultdict(list)
    for h in by_b:
        topics[h["topic"]].append(h)
    for t in m4.TOPICS:
        listing(f"topics/{slug(t)}", t, "Ordered ★6 → ★1", topics[t])
    write("topics/index.html", page("Topics · The Unified Six",
          "<h1>Topics</h1><p class='muted'>33 subjects, after the arrangement of Ibn al-Athīr's <em>Jāmiʿ al-Uṣūl</em>.</p><div class='grid'>"
          + "".join(f'<a href="{slug(t)}/index.html">{esc(t)}</a> <span class="muted">{len(topics[t]):,}</span>' for t in m4.TOPICS)
          + "</div>", "../"))

    by_a = order(d.hadith, "A")
    stars = defaultdict(list)
    for h in by_a:
        stars[h["stars"]].append(h)
    for n in range(6, 0, -1):
        listing(f"stars/{n}", "★" * n, STAR_NOTE[n].capitalize() + " (★ full, ⯪ fragment) — by topic within", stars[n])
    write("stars/index.html", page("By attestation · The Unified Six",
          "<h1>By attestation</h1><p class='muted'>How many of the six books carry each hadith. Stars count books; they say nothing about authenticity.</p><ol class='list'>"
          + "".join(f'<li><a href="{n}/index.html">{"★" * n}</a> {STAR_NOTE[n]} — {len(stars[n]):,} hadith</li>' for n in range(6, 0, -1))
          + "</ol>", "../"))

    # by book: an index page per book, and /books/<book>/<n>/ redirects to the hadith page
    per_book = defaultdict(list)
    for nid, hid in d.of.items():
        r = d.narr[nid]
        per_book[r["book"]].append((r["seq"], d.number(nid), hid))
    for b in BOOKS:
        rows = sorted(per_book[b])
        for _, num, hid in rows:
            path = f"books/{b}/{num}/index.html"
            target = f"{depth_root(path)}h/{hid}/index.html"
            write(path, f'<!doctype html><meta charset="utf-8"><link rel="icon" href="data:,"><meta http-equiv="refresh" content="0; url={target}">'
                        f'<link rel="canonical" href="{target}"><a href="{target}">{hid}</a>')
        lines = "".join(f'<a href="{num}/index.html">{LETTER[b]} {esc(num)}</a> → {hid}<br>' for _, num, hid in rows)
        write(f"books/{b}/index.html", page(f"{d.books[b]['name_en']} · The Unified Six",
              f"<h1>{esc(d.books[b]['name_en'])}</h1><p class='muted'>Numbering: {esc(d.books[b]['numbering'])}. "
              f"Each number leads to the entry that contains it. Tip: open <code>books/{b}/NUMBER/</code> directly.</p>"
              f"<p class='small'>{lines}</p>", "../../"))
    write("books/index.html", page("By book · The Unified Six",
          "<h1>By book</h1><p class='muted'>Find a hadith by its number in one of the six books.</p><ol class='list'>"
          + "".join(f'<li><a href="{b}/index.html">{esc(d.books[b]["name_en"])}</a> ({LETTER[b]}) — {len(per_book[b]):,} narrations</li>' for b in BOOKS)
          + "</ol>", "../"))

    write("search/index.html", page("Search · The Unified Six",
          "<h1>Search</h1><p class='muted small'>English or Arabic (with or without diacritics). Filter by topic, books or stars.</p>"
          "<div id='search'></div><script>window.addEventListener('DOMContentLoaded',function(){new PagefindUI({element:'#search',showSubResults:false,resetStyles:false})});</script>",
          "../", search=True))

    n_narr = d.n_narr
    write("index.html", page("The Unified Six", f"""
<h1>The Unified Six</h1>
<p>The six canonical hadith books — Ṣaḥīḥ al-Bukhārī, Ṣaḥīḥ Muslim, Sunan Abī Dāwūd, Jāmiʿ al-Tirmidhī,
Sunan al-Nasāʾī and Sunan Ibn Mājah — hold {n_narr:,} narrations. Here every distinct hadith appears
<strong>once</strong>: {len(d.hadith):,} entries, each with a pointer to every book that carries it.</p>
<div class="pair"><div><h2>Browse</h2><ul>
<li><a href="topics/index.html">By topic</a> — 33 subjects</li>
<li><a href="stars/index.html">By attestation</a> — ★6 (all six books) to ★1</li>
<li><a href="books/index.html">By book number</a> — e.g. <a href="books/bukhari/1/index.html">al-Bukhārī 1</a></li>
<li><a href="search/index.html">Search</a> English and Arabic</li></ul></div>
<div><h2>Download</h2><ul><li><a href="{REPO}/releases/latest">PDF editions</a> (by attestation, by topic; English and English + Arabic)</li>
<li><a href="{REPO}/releases/latest">Open dataset</a> (JSON Lines + CSV, CC BY 4.0)</li></ul></div></div>
<p class="note">Read with care: the grouping was made by software and checked on samples; the English is a
machine translation, re-checked by a second machine pass but not by a scholar. Rely on the Arabic and
the source books, and please <a href="{REPO}/issues">report mistakes</a> — every hadith page has a link.</p>
""", "", desc="Each distinct hadith of the six canonical books once, with references to every book."))

    write("about/index.html", page("About · The Unified Six", f"""
<h1>About</h1>
<h2>What a hadith page shows</h2>
<p>The fullest version as the main text. Upright text is found in every full version; <em>italic</em> text only
in some — tap it to see which. ★ one per book with the full hadith, ⯪ per book with only a fragment;
<span class="dot muttafaq"></span> in both al-Bukhārī and Muslim (muttafaq ʿalayh), <span class="dot sahih_one"></span> in one of them;
T: al-Tirmidhī's own grading; ≈ the grouping rests on an uncertain machine judgement. A/B numbers are the
entry numbers in PDF editions A (by attestation) and B (by topic).</p>
<h2>How it was made</h2>
<p>All {n_narr:,} narrations were compared with text-similarity methods and language models (Claude), merged where
they report the same statement or event, and checked on evaluation samples (about 96–100 % of merges correct).
The English is a machine translation (Claude Sonnet), re-checked against the Arabic in v1.1. No modern grader is
used. Arabic text from the editions published on sunnah.com. Full method and reports:
<a href="{REPO}/tree/main/docs">docs</a>; changes: <a href="{REPO}/blob/main/CHANGELOG.md">changelog</a>.</p>
<h2>License</h2><p>Text and data CC BY 4.0 — share and adapt with attribution
(“The Unified Six, github.com/Taksir/The-unified-six”). Code MIT. Amiri font: SIL Open Font License.</p>
""", "../"))
    print(f"site: {len(d.hadith):,} hadith pages, {sum(1 for _ in SITE.rglob('*.html')):,} html files")
