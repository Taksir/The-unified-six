"""M5: release v1.0 — stub cleanup, the open dataset, and the PDF editions.

Stage `clean` repairs representatives of <= STUB_WORDS Arabic words (isnad/matn split
leftovers found in M4) and writes the release dataset to data/release/:
  * "ref" stubs (the matn is only "بهذا", "مثله", "نحوه" ...): the narration joins the hadith
    of the narration just before it in the same book, as a chain-only member;
  * "extend" stubs (the split cut the text before a second chain that carries the real
    hadith): the representative text becomes everything after the first chain, translated
    again (Sonnet, live, cents); stubs whose extended texts are identical are merged;
  * other short texts are real short reports ("هذه طابة") and stay as they are.
"""

import json
import re
from collections import defaultdict

from . import llm, m4
from .corpus import DATA, ROOT
from .split import segments
from .textnorm import letters

REL = DATA / "release"
STUB_WORDS = 5
REF_WORDS = ("بهذا", "مثله", "نحوه", "بمثله", "بنحوه", "بمعناه", "مثل ذلك", "نحو")
BOOKS = ("bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah")


def load_narrations() -> dict:
    out = {}
    for b in BOOKS:
        for l in (DATA / "narrations" / f"{b}.jsonl").open(encoding="utf-8"):
            r = json.loads(l)
            out[r["id"]] = r
    return out


_COMMENT = re.compile(r"(قال ابو عيسي|هذا حديث (حسن|صحيح|غريب)|وفي الباب عن)")


def commentary_from(h: dict) -> int | None:
    """Index of the first segment of al-Tirmidhi's own commentary (grading, "wa fi al-bab"),
    when it starts at a segment boundary; the PDFs print the segments before it."""
    if not h["representative"].startswith("tirmidhi"):
        return None
    for i, s in enumerate(h["segments"]):
        m = _COMMENT.search(letters(s["ar"]))
        if m:
            return i if i > 0 and len(letters(s["ar"])[:m.start()].split()) <= 1 else None
    return None


def classify_stub(h: dict, narr: dict) -> tuple[str, str]:
    """-> (kind, extended Arabic text) for a short representative."""
    r = narr[h["representative"]]
    _, matn, tail = segments(r["text"], r["split"])
    if any(w in letters(matn) for w in REF_WORDS):
        return "ref", ""
    rest = (matn + " " + tail).strip()
    cut = rest.find("قَالَ أَبُو عِيسَى")  # Tirmidhi's own comment is not part of the hadith
    rest = rest[:cut].strip() if cut > 0 else rest
    return ("extend", rest) if len(letters(rest).split()) >= 8 else ("short", "")


def _absorb(keep: dict, gone: dict) -> None:
    """Carry a removed entry's Tirmidhi grades and see-also links over to its new home."""
    if gone.get("tirmidhi_grades"):
        keep["tirmidhi_grades"] = keep.get("tirmidhi_grades", []) + gone["tirmidhi_grades"]
    keep["see_also"] = keep.get("see_also", []) + gone.get("see_also", [])


def stage_clean() -> None:
    narr = load_narrations()
    hadith = [json.loads(l) for l in (DATA / "six" / "hadith.jsonl").open(encoding="utf-8")]
    tr = m4.load_translations()
    topics = {r["id"]: r for r in map(json.loads, m4.TOPICS_FILE.open(encoding="utf-8"))}
    by_id = {h["id"]: h for h in hadith}
    of_narr = {m["id"]: h["id"] for h in hadith for m in h["members"]}
    seq = {(r["book"], r["seq"]): i for i, r in narr.items()}
    log = []

    stubs = [h for h in hadith if h.get("segments") and m4.words(h) <= STUB_WORDS]
    kinds = {h["id"]: classify_stub(h, narr) for h in stubs}

    # ref stubs -> the previous narration's hadith in the same book
    for h in stubs:
        if kinds[h["id"]][0] != "ref":
            continue
        r = narr[h["representative"]]
        prev = seq.get((r["book"], r["seq"] - 1))
        target = of_narr.get(prev)
        if not target or target == h["id"] or target not in by_id or not by_id[target].get("segments"):
            log.append({"id": h["id"], "action": "ref-kept", "why": "no usable previous narration"})
            continue
        for m in h["members"]:
            by_id[target]["members"].append({**m, "kind": "ref", "role": "full"})
            of_narr[m["id"]] = target
        _absorb(by_id[target], h)
        log.append({"id": h["id"], "action": "ref-merged", "into": target,
                    "narrations": [m["id"] for m in h["members"]]})
        del by_id[h["id"]]

    # extend stubs -> full text after the first chain; identical texts merge
    seen = {}
    retranslate = []
    for h in stubs:
        kind, text = kinds[h["id"]]
        if kind != "extend" or h["id"] not in by_id:
            continue
        key = letters(text)
        if key in seen:
            keep = by_id[seen[key]]
            keep["members"] += h["members"]
            _absorb(keep, h)
            log.append({"id": h["id"], "action": "extend-merged", "into": keep["id"]})
            del by_id[h["id"]]
            continue
        seen[key] = h["id"]
        h["segments"] = [{"ar": text, "core": True, "in": [h["representative"]]}]
        h["extended_from_stub"] = True
        retranslate.append(h)
        log.append({"id": h["id"], "action": "extended", "words": len(key.split())})

    fixes = REL / "stub-translations.json"
    REL.mkdir(parents=True, exist_ok=True)
    done = json.loads(fixes.read_text()) if fixes.exists() else {}
    todo = [h for h in retranslate if h["id"] not in done]
    if todo:
        llm.require_key()
        done.update(m4.translate_live(todo, m4.TRANSLATE_MODEL, m4.TRANSLATE_EFFORT,
                                      "m5-stub-translate", cap_usd=1.0))
        fixes.write_text(json.dumps(done, ensure_ascii=False, indent=1) + "\n")
    for h in retranslate:
        tr[h["id"]] = {"id": h["id"], "segments_en": done[h["id"]], "model": m4.TRANSLATE_MODEL,
                       "label": "machine translation"}

    # see-also links to removed entries point at the entry that absorbed them
    moved = {r["id"]: r["into"] for r in log if "into" in r}
    for h in by_id.values():
        h["see_also"] = sorted({moved.get(x, x) for x in h.get("see_also", [])} - {h["id"]})

    # recount stars and books for hadith that gained members
    for h in by_id.values():
        full = sorted({m["book"] for m in h["members"] if m["role"] == "full"}, key=BOOKS.index)
        part = sorted({m["book"] for m in h["members"] if m["role"] == "partial"} - set(full), key=BOOKS.index)
        h["books_full"], h["books_partial"] = full, part
        h["stars"] = len(full) + len(part)
        h["stars_display"] = "★" * len(full) + "⯪" * len(part)
        h["badge"] = ("muttafaq" if {"bukhari", "muslim"} <= set(full + part)
                      else "sahih_one" if {"bukhari", "muslim"} & set(full + part) else None)

    out = []
    for h in by_id.values():
        if not h.get("segments"):  # 18 upstream entries with no text: kept in the dataset only
            h.update(segments=[], segments_en=[], no_text=True, topic=None, topics_secondary=[])
            out.append(h)
            continue
        t = tr[h["id"]]
        h["segments_en"] = t["segments_en"]
        h["italics_dropped"] = bool(t.get("italics_dropped"))
        h["topic"] = topics[h["id"]]["topic"] if h["id"] in topics else "Manners and good character"
        h["topics_secondary"] = topics.get(h["id"], {}).get("secondary", [])
        cut = commentary_from(h)
        if cut is not None:
            h["commentary_from"] = cut
        out.append(h)
    with (REL / "hadith.work.jsonl").open("w", encoding="utf-8") as f:
        for h in out:
            f.write(json.dumps(h, ensure_ascii=False) + "\n")
    (REL / "clean-log.json").write_text(json.dumps(log, ensure_ascii=False, indent=1) + "\n")
    acts = defaultdict(int)
    for r in log:
        acts[r["action"]] += 1
    covered = {m["id"] for h in out for m in h["members"]}
    print(f"clean: {dict(acts)}; hadith {len(out)}; narrations covered {len(covered)}")


# ---------------------------------------------------------------- PDF editions

VERSION = "1.0"
TYPESET = ROOT / "typeset"
OUT = ROOT / "out" / "release"
LETTER = dict(zip(BOOKS, "BMDTNJ"))
STAR_NOTE = {6: "in all six books", 5: "in five books", 4: "in four books", 3: "in three books",
             2: "in two books", 1: "in one book"}


def load_release() -> list[dict]:
    return [json.loads(l) for l in (REL / "hadith.work.jsonl").open(encoding="utf-8")]


def order(hadith: list[dict], edition: str, narr: dict) -> list[dict]:
    """Edition A: ★6 → ★1, then topic, then canonical book order. Edition B: topic first."""
    t = {x: i for i, x in enumerate(m4.TOPICS)}

    def canon(h):
        r = narr[h["representative"]]
        return BOOKS.index(r["book"]), r["seq"]
    if edition == "A":
        key = lambda h: (-h["stars"], -len(h["books_full"]), t[h["topic"]], canon(h))
    else:
        key = lambda h: (t[h["topic"]], -h["stars"], -len(h["books_full"]), canon(h))
    return sorted((h for h in hadith if not h.get("no_text")), key=key)


def _number(r: dict) -> str:
    return (r["n_fab"] or r["n"]) if r["book"] == "muslim" else r["n"]


def entry_json(h: dict, n: int, lang: str) -> dict:
    grades = sorted({g["en"] for g in h.get("tirmidhi_grades", [])})
    return {"n": n, "uid": h["id"], "st": h["stars_display"], "bd": h["badge"] or "",
            "lt": " ".join(LETTER[b] for b in BOOKS if b in h["books_full"] + h["books_partial"]),
            "tg": "; ".join(grades), "un": bool(h.get("uncertain")),
            "s": [[s["ar"] if lang == "enar" else "", e, bool(s["core"] or h.get("italics_dropped"))]
                  for s, e in list(zip(h["segments"], h["segments_en"]))[:h.get("commentary_from")]]}


def app_json(h: dict, n: int, num: dict, narr: dict, urls: dict, lang: str) -> dict:
    grade = {g["id"]: g["en"] for g in h.get("tirmidhi_grades", [])}
    mem = []
    for m in sorted(h["members"], key=lambda m: (BOOKS.index(m["book"]), narr[m["id"]]["seq"])):
        r = narr[m["id"]]
        mem.append([LETTER[m["book"]], _number(r), m["role"], m["kind"],
                    r.get("isnad_last", "") if lang == "enar" else "", urls.get(m["id"], ""),
                    m["id"] == h["representative"], grade.get(m["id"], "")])
    return {"n": n, "uid": h["id"], "st": h["stars_display"], "bd": h["badge"] or "",
            "topic": h["topic"], "sec": h.get("topics_secondary", []), "mem": mem,
            "var": sum(1 for m in h["members"] if m["kind"] != "ref") - 1, "un": bool(h.get("uncertain")),
            "idrop": bool(h.get("italics_dropped")), "ext": bool(h.get("extended_from_stub")),
            "see": sorted(num[x] for x in h.get("see_also", []) if x in num)}


def groups_for(ordered: list[dict], edition: str) -> list[tuple[str, str, list[dict]]]:
    out = []
    for h in ordered:
        if edition == "A":
            title, note = "★" * h["stars"], STAR_NOTE[h["stars"]]
        else:
            title, note = h["topic"], ""
        if not out or out[-1][0] != title:
            out.append((title, note, []))
        out[-1][2].append(h)
    return out


def volumes(groups, weight, per_vol: float) -> list[list[tuple[str, str, list[dict]]]]:
    """Split groups into volumes of about per_vol weight; a long group continues across volumes."""
    vols, cur, w = [], [], 0.0
    for title, note, hs in groups:
        chunk = []
        for h in hs:
            if w + weight(h) > per_vol and (chunk or cur):
                if chunk:
                    cur.append((title, note, chunk))
                vols.append(cur)
                cur, chunk, w = [], [], 0.0
                title = title if title.endswith("(continued)") else f"{title} (continued)"
            chunk.append(h)
            w += weight(h)
        if chunk:
            cur.append((title, note, chunk))
    vols += [cur] if cur else []
    if len(vols) > 1 and sum(weight(h) for _, _, hs in vols[-1] for h in hs) < 0.15 * per_vol:
        tail = vols.pop()   # a few overshooting entries: fold them into the previous volume
        t, n, hs = tail[0]
        if t.endswith("(continued)") and vols[-1][-1][0].removesuffix(" (continued)") == t.removesuffix(" (continued)"):
            pt, pn, phs = vols[-1][-1]
            vols[-1][-1] = (pt, pn, phs + hs)
            tail = tail[1:]
        vols[-1] += tail
    return vols


def _urls() -> dict:
    out = {}
    for l in (DATA / "concordance.csv").open(encoding="utf-8"):
        p = l.rstrip("\n").split(",")
        out[p[0]] = p[-1]
    return out


# Volume sizes, calibrated on 500 entries (A5, 9.5 pt): EN+AR ≈ 165 Arabic words per page,
# English only ≈ 295, appendix ≈ 8.8 entries per page. Target ≈ 500 pages per volume.
# Appendix weight = 2 + members per entry (≈ 22k per 500 pages). Volumes are then evened out.
PER_VOL = {("enar", "hadith"): 82_000, ("en", "hadith"): 147_000,
           ("enar", "appendix"): 22_000, ("en", "appendix"): 22_000}


def _compile(data: dict, name: str, edition: str, lang: str, part: str) -> bytes:
    import typst
    build = TYPESET / "build"
    build.mkdir(parents=True, exist_ok=True)
    (build / f"{name}.json").write_text(json.dumps(data, ensure_ascii=False))
    return typst.compile(str(TYPESET / "release.typ"), root=str(ROOT), font_paths=[str(TYPESET / "fonts")],
                         sys_inputs={"data": f"build/{name}.json", "edition": edition, "lang": lang, "part": part})


def stage_pdf(editions=("A", "B"), langs=("enar", "en")) -> None:
    from io import BytesIO
    from pypdf import PdfReader, PdfWriter
    narr, urls, hadith = load_narrations(), _urls(), load_release()
    OUT.mkdir(parents=True, exist_ok=True)
    total = sum(1 for h in hadith if not h.get("no_text"))
    mpath = REL / "pdf-manifest.json"
    manifest = [r for r in (json.loads(mpath.read_text()) if mpath.exists() else [])
                if not (r["edition"] in editions and r["lang"] in langs)]
    for ed in editions:
        ordered = order(hadith, ed, narr)
        num = {h["id"]: i + 1 for i, h in enumerate(ordered)}
        for lang in langs:
            files = {}
            for part in ("hadith", "appendix"):
                weight = (lambda h: m4.words(h)) if part == "hadith" else (lambda h: 2 + len(h["members"]))
                tw = sum(weight(h) for h in ordered)
                per_vol = tw / -(-tw // PER_VOL[(lang, part)]) * 1.001
                vols = volumes(groups_for(ordered, ed), weight, per_vol)
                files[part] = []
                for v, groups in enumerate(vols, 1):
                    first, last = num[groups[0][2][0]["id"]], num[groups[-1][2][-1]["id"]]
                    make = (lambda h: entry_json(h, num[h["id"]], lang)) if part == "hadith" else \
                           (lambda h: app_json(h, num[h["id"]], num, narr, urls, lang))
                    data = {"vol": v, "nvols": len(vols), "range": f"Nos. {first}–{last}", "version": VERSION,
                            "narrations": f"{sum(len(h['members']) for h in hadith):,}", "total": f"{total:,}",
                            "groups": [{"title": t, "note": note, "entries": [make(h) for h in hs]}
                                       for t, note, hs in groups]}
                    name = f"the-unified-six-v{VERSION}-{ed}-{lang}-{part}-vol{v}"
                    pdf = _compile(data, name, ed, lang, part)
                    (OUT / f"{name}.pdf").write_bytes(pdf)
                    pages = len(PdfReader(BytesIO(pdf)).pages)
                    files[part].append(name)
                    manifest.append({"file": f"{name}.pdf", "edition": ed, "lang": lang, "part": part,
                                     "volume": v, "range": data["range"], "pages": pages,
                                     "mb": round(len(pdf) / 1e6, 1)})
                    print(f"{name}: {pages} pages, {len(pdf) / 1e6:.1f} MB", flush=True)
            w = PdfWriter()
            for part in ("hadith", "appendix"):
                for name in files[part]:
                    w.append(str(OUT / f"{name}.pdf"))
            name = f"the-unified-six-v{VERSION}-{ed}-{lang}-combined"
            with (OUT / f"{name}.pdf").open("wb") as f:
                w.write(f)
            pages = sum(r["pages"] for r in manifest if r["edition"] == ed and r["lang"] == lang)
            manifest.append({"file": f"{name}.pdf", "edition": ed, "lang": lang, "part": "combined",
                             "volume": None, "range": "all", "pages": pages,
                             "mb": round((OUT / f"{name}.pdf").stat().st_size / 1e6, 1)})
            print(f"{name}: {pages} pages", flush=True)
    manifest.sort(key=lambda r: (r["edition"], r["lang"] != "enar", r["part"], r["volume"] or 0))
    mpath.write_text(json.dumps(manifest, indent=1) + "\n")


# ---------------------------------------------------------------- dataset

DATASET_README = """# The Unified Six — dataset v{version}

The six canonical Sunni hadith books merged so that each distinct hadith appears once.
Text and data: **CC BY 4.0** (attribution: "The Unified Six, github.com/Taksir/The-unified-six").
Code: MIT. Corrections: open an issue on GitHub (every PDF entry links to one).

| file | rows | what |
|---|---:|---|
| `hadith.jsonl` | {n_hadith:,} | merged entries ({n_text:,} with text; {n_empty} upstream entries have no text) |
| `narrations.jsonl` | {n_narr:,} | every original narration, with the entry it belongs to |
| `concordance.csv` | {n_narr:,} | narration ↔ entry ↔ book numbering ↔ edition A/B numbers ↔ sunnah.com |

## hadith.jsonl

`id` (U6-xxxxx, stable across editions) · `members` [{{`id`, `book`, `kind`, `role`}}]: `role`
`full` or `partial` (fragment); `kind` `full`, `ref` (chain only, "with this isnād, likewise"),
`ref_variant` · `representative`: narration whose text is shown · `books_full`, `books_partial`
· `stars` (books carrying it in any form) · `badge`: `muttafaq` (Bukhārī and Muslim), `sahih_one`
(one of them) or null · `segments` [{{`ar`, `en`, `core`, `in`}}]: the representative text in
clauses; `core` = found in every full version (roman), else an addition (italic), `in` = the
narrations carrying that clause · `en`: whole English text · `topic`, `topics_secondary`
(33-topic list) · `tirmidhi_grades` [{{`id`, `ar`, `en`}}]: al-Tirmidhī's own grading ·
`uncertain`: grouping rests on a low-confidence machine judgement · `see_also`: possible
duplicates, unconfirmed · `edition_a`, `edition_b`: entry numbers in the PDFs · flags:
`italics_dropped`, `extended_from_stub` (split repaired in M5), `commentary_from` (index of the
first segment that is al-Tirmidhī's commentary, not printed in the main text), `no_text`.

**English is machine translation** (Claude Sonnet 5.5), not reviewed by a scholar; a sample
check found a meaning-changing error in about 6 % of hadith. **Grouping** is machine-assisted
(merge precision 96–100 % on evaluation samples). Stars count books, not authenticity.

## narrations.jsonl

`id` (`book:number`) · `book` · `n` (standard number) · `n_fab` (Muslim: Fuʾād ʿAbd al-Bāqī)
· `chapter`, `chapter_title` · `kind` · `text` (full Arabic with tashkeel) · `isnad`, `matn`,
`tail` (machine split) · `narrator` (last narrator in the chain, heuristic) ·
`tirmidhi_grade` · `hadith` (U6 id) · `role` · `representative` (bool) · `sunnah_url`.

Arabic text: the editions published on sunnah.com (via the fawazahmed0/hadith-api dataset).
Numbering per book: see `books.json`. Third-party gradings in the upstream data are not included.
"""

CHANGELOG = """# Changelog

## v1.0 — {date}

- All six books merged: {n_narr:,} narrations → {n_text:,} entries with text.
- English machine translation of every entry (Claude Sonnet 5.5), clause-aligned for italics.
- 33-topic arrangement; editions A (by attestation) and B (by topic), English and English + Arabic.
- M5 cleanup: 16 chain-only stubs attached to their hadith; 44 truncated texts repaired and
  re-translated (2 merged as duplicates); al-Tirmidhī's commentary kept out of the main text
  where it starts at a clause boundary ({n_comment}).
- Known limits: ~6 % of translations with a meaning-changing error (sample of 50); merge
  precision 96.3 % on the four Sunan (gold sample); {n_short} entries of ≤ 5 Arabic words are
  real short reports or fragments and are printed as they are.
"""


def stage_dataset() -> None:
    import csv
    import shutil
    import time
    narr, urls, hadith = load_narrations(), _urls(), load_release()
    books = {b["slug"]: b for b in json.loads((DATA / "books.json").read_text())["books"]}
    ch_title = {(s, c["chapter"]): c["title_en"] for s, b in books.items() for c in b["chapters"]}
    nums = {ed: {h["id"]: i + 1 for i, h in enumerate(order(hadith, ed, narr))} for ed in ("A", "B")}
    ds = OUT / f"the-unified-six-v{VERSION}-dataset"
    ds.mkdir(parents=True, exist_ok=True)

    final, of = [], {}
    for h in hadith:
        rec = {k: h.get(k) for k in ("id", "members", "representative", "books_full", "books_partial",
                                     "stars", "stars_display", "badge", "uncertain", "topic",
                                     "topics_secondary", "tirmidhi_grades", "see_also")}
        rec["tirmidhi_grades"] = rec["tirmidhi_grades"] or []
        rec["segments"] = [{"ar": s["ar"], "en": e, "core": s["core"], "in": s.get("in", [])}
                           for s, e in zip(h["segments"], h["segments_en"])]
        rec["en"] = " ".join(h["segments_en"][:h.get("commentary_from")])
        rec["edition_a"], rec["edition_b"] = nums["A"].get(h["id"]), nums["B"].get(h["id"])
        for k in ("italics_dropped", "extended_from_stub", "commentary_from", "no_text"):
            if h.get(k) not in (None, False):
                rec[k] = h[k]
        rec["translation"] = None if h.get("no_text") else {"model": m4.TRANSLATE_MODEL, "label": "machine translation"}
        final.append(rec)
        for m in h["members"]:
            assert m["id"] not in of, f"{m['id']} in two entries"
            of[m["id"]] = (h["id"], m["role"], m["id"] == h["representative"])
    assert set(of) <= set(narr)

    with (ds / "hadith.jsonl").open("w", encoding="utf-8") as f:
        for r in final:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    shutil.copy(ds / "hadith.jsonl", REL / "hadith.jsonl")
    grade = {g["id"]: g for h in hadith for g in h.get("tirmidhi_grades", [])}
    rows = []
    with (ds / "narrations.jsonl").open("w", encoding="utf-8") as f:
        for nid, r in narr.items():
            if nid not in of:
                continue
            isnad, matn, tail = segments(r["text"], r["split"])
            hid, role, rep = of[nid]
            g = grade.get(nid) or r.get("tirmidhi_grade")
            f.write(json.dumps({"id": nid, "book": r["book"], "n": r["n"], "n_fab": r["n_fab"],
                                "chapter": r["chapter"], "chapter_title": ch_title.get((r["book"], r["chapter"]), ""),
                                "kind": r["kind"], "text": r["text"], "isnad": isnad, "matn": matn, "tail": tail,
                                "narrator": r.get("isnad_last", ""),
                                "tirmidhi_grade": {"ar": g["ar"], "en": g["en"]} if g else None,
                                "hadith": hid, "role": role, "representative": rep,
                                "sunnah_url": urls.get(nid, "")}, ensure_ascii=False) + "\n")
            rows.append([nid, r["book"], r["n"], r["n_fab"] or "", r["chapter"], hid, role, r["kind"],
                         nums["A"].get(hid, ""), nums["B"].get(hid, ""), urls.get(nid, "")])
    for path in (ds / "concordance.csv", REL / "concordance.csv"):
        with path.open("w", encoding="utf-8", newline="") as f:
            w = csv.writer(f)
            w.writerow(["narration", "book", "n", "n_fab", "chapter", "hadith", "role", "kind",
                        "edition_a", "edition_b", "sunnah_url"])
            w.writerows(rows)
    stats = {"version": VERSION, "n_hadith": len(final), "n_text": sum(1 for r in final if not r.get("no_text")),
             "n_empty": sum(1 for r in final if r.get("no_text")), "n_narr": len(rows),
             "n_comment": sum(1 for r in final if "commentary_from" in r),
             "n_short": sum(1 for h in hadith if h["segments"] and m4.words(h) <= STUB_WORDS),
             "date": time.strftime("%Y-%m-%d")}
    (ds / "README.md").write_text(DATASET_README.format(**stats), encoding="utf-8")
    for path in (ROOT / "CHANGELOG.md", ds / "CHANGELOG.md"):
        path.write_text(CHANGELOG.format(**stats), encoding="utf-8")
    shutil.copy(DATA / "books.json", ds / "books.json")
    shutil.copy(ROOT / "LICENSE-DATA", ds / "LICENSE")
    shutil.make_archive(str(ds), "zip", ds.parent, ds.name)
    (REL / "stats.json").write_text(json.dumps(stats, indent=1) + "\n")
    print(json.dumps(stats))
