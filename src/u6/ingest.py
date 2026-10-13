"""Build the common-schema narration files and the numbering concordance.

Outputs (all committed):
  data/narrations/<book>.jsonl   one record per upstream entry, source order;
                                 isnad/matn/tail = u6.split.segments(text, split)
  data/books.json                book metadata and chapter list
  data/concordance.csv           id <-> every numbering scheme <-> sunnah.com URL
  docs/reports/m0-ingest.md      per-book statistics
"""

import csv
import json
import statistics
from collections import Counter
from pathlib import Path

from .books import BOOKS
from .fetch import edition_name
from .grades import tirmidhi_grade
from .split import last_narrator, segments, split_narration
from .textnorm import clean

SCHEMA_VERSION = 1


def number_str(n) -> str:
    """402.2 -> "402.2", 7.0 -> "7"; upstream mixes ints and floats."""
    return str(int(n)) if float(n).is_integer() else str(n)


def muslim_fab(arabicnumber) -> str | None:
    """Fuad Abd al-Baqi label as sunnah.com prints it: "8.01" -> "8a", "9" -> "9"."""
    if arabicnumber in (None, ""):
        return None
    s = str(arabicnumber)
    if "." not in s:
        return s
    base, sub = s.split(".")
    sub = int(sub)
    if sub == 0:
        return base
    letters = ""
    while sub:  # 1->a ... 26->z, 27->aa
        sub, r = divmod(sub - 1, 26)
        letters = chr(ord("a") + r) + letters
    return base + letters


def sunnah_url(slug: str, n: str, fab: str | None) -> str:
    if slug == "muslim":
        return f"https://sunnah.com/muslim:{fab}" if fab else ""
    if "." in n:
        return ""  # sub-numbered entries have no stable public URL
    return f"https://sunnah.com/{slug}:{n}"


def _intro_range(raw: dict) -> tuple[float, float] | None:
    """Number range of a real introduction section (Muslim, Ibn Majah), if any."""
    d = raw["metadata"]["section_details"].get("0")
    if d and float(d["hadithnumber_last"]) > 0 and raw["metadata"]["sections"].get("0"):
        return float(d["hadithnumber_first"]), float(d["hadithnumber_last"])
    return None


def build_records(slug: str, raw: dict) -> list[dict]:
    records = []
    intro = _intro_range(raw)
    prev_chapter = None
    for seq, h in enumerate(raw["hadiths"]):
        n = number_str(h["hadithnumber"])
        text = clean(h["text"])
        sp = split_narration(text)
        fab = muslim_fab(h.get("arabicnumber")) if slug == "muslim" else None
        ref = h.get("reference") or {}
        # Chapter = the entry's own reference. Upstream marks entries without one as
        # book 0; outside a real introduction those inherit the previous chapter.
        # Empty placeholders can point into another book (muslim:384 -> 43): ignore.
        num = float(h["hadithnumber"])
        if text and ref.get("book"):
            chapter, in_chapter = ref["book"], ref.get("hadith")
        elif text and intro and intro[0] <= num <= intro[1]:
            chapter, in_chapter = 0, ref.get("hadith") or None
        else:
            chapter, in_chapter = prev_chapter if prev_chapter is not None else ref.get("book"), None
        prev_chapter = chapter
        rec = {
            "id": f"{slug}:{n}",
            "book": slug,
            "seq": seq,
            "n": n,
            "n_fab": fab,
            "chapter": chapter,
            "chapter_hadith": in_chapter,
            "intro": slug == "muslim" and chapter == 0,
            "kind": sp.kind,
            "text": text,
            "split": list(sp.bounds),
            "isnad_last": last_narrator(sp.isnad),
            "tirmidhi_grade": (tirmidhi_grade(sp.tail) or tirmidhi_grade(text)) if slug == "tirmidhi" else None,
            "split_flags": sp.flags,
        }
        records.append(rec)
    ids = Counter(r["id"] for r in records)
    dup = [i for i, c in ids.items() if c > 1]
    if dup:
        raise SystemExit(f"{slug}: duplicate ids {dup[:5]}")
    return records


def _book_meta(slug: str, raw: dict) -> dict:
    meta = raw["metadata"]
    b = next(b for b in BOOKS if b.slug == slug)
    return {
        "slug": slug, "letter": b.letter, "name_en": b.name_en, "name_ar": b.name_ar,
        "numbering": b.numbering,
        "chapters": [
            {"chapter": int(k), "title_en": v,
             "first": number_str(meta["section_details"][k]["hadithnumber_first"]),
             "last": number_str(meta["section_details"][k]["hadithnumber_last"])}
            for k, v in sorted(meta["sections"].items(), key=lambda kv: int(kv[0]))
        ],
    }


def _stats(slug: str, recs: list[dict]) -> dict:
    kinds = Counter(r["kind"] for r in recs)
    flags = Counter(f for r in recs for f in r["split_flags"])
    nonempty = [r for r in recs if r["kind"] != "empty"]
    segs = {r["id"]: segments(r["text"], r["split"]) for r in nonempty}
    matn_lens = [len(m.split()) for _, m, _ in segs.values() if m]
    st = {
        "records": len(recs),
        "empty": kinds["empty"],
        "full": kinds["full"],
        "ref": kinds["ref"],
        "ref_variant": kinds["ref_variant"],
        "no_isnad": flags["no_isnad"],
        "no_boundary": flags["no_boundary"],
        "empty_matn": sum(1 for _, m, _ in segs.values() if not m),
        "with_tail": sum(1 for _, _, t in segs.values() if t),
        "median_matn_words": int(statistics.median(matn_lens)) if matn_lens else 0,
        "with_isnad_last": sum(1 for r in nonempty if r["isnad_last"]),
    }
    if slug == "tirmidhi":
        st["tirmidhi_graded"] = sum(1 for r in recs if r["tirmidhi_grade"])
        st["tirmidhi_grades"] = Counter(r["tirmidhi_grade"]["en"] for r in recs if r["tirmidhi_grade"]).most_common(8)
    return st


def ingest(data_dir: Path, docs_dir: Path) -> dict:
    out_dir = data_dir / "narrations"
    out_dir.mkdir(parents=True, exist_ok=True)
    books_meta, all_stats, conc_rows = [], {}, []
    for b in BOOKS:
        raw = json.loads((data_dir / "raw" / f"{edition_name(b.slug)}.json").read_text())
        recs = build_records(b.slug, raw)
        with (out_dir / f"{b.slug}.jsonl").open("w", encoding="utf-8") as f:
            for r in recs:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
        books_meta.append(_book_meta(b.slug, raw))
        all_stats[b.slug] = _stats(b.slug, recs)
        for r in recs:
            conc_rows.append([r["id"], b.letter, r["n"], r["n_fab"] or "", r["chapter"],
                              r["chapter_hadith"], r["kind"], sunnah_url(b.slug, r["n"], r["n_fab"])])
        print(f"{b.slug}: {len(recs)} records")

    (data_dir / "books.json").write_text(json.dumps(
        {"schema_version": SCHEMA_VERSION, "books": books_meta}, ensure_ascii=False, indent=1) + "\n")
    with (data_dir / "concordance.csv").open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["id", "book", "n", "n_fab", "chapter", "chapter_hadith", "kind", "sunnah_url"])
        w.writerows(conc_rows)
    _write_report(docs_dir / "reports" / "m0-ingest.md", all_stats)
    return all_stats


def _write_report(path: Path, stats: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    cols = ["records", "empty", "full", "ref", "ref_variant", "no_isnad", "no_boundary",
            "empty_matn", "with_tail", "median_matn_words", "with_isnad_last"]
    lines = [
        "# M0 ingest report",
        "",
        "Generated by `python -m u6 ingest`. Do not edit by hand.",
        "",
        "| book | " + " | ".join(cols) + " |",
        "|---|" + "---:|" * len(cols),
    ]
    for slug, st in stats.items():
        lines.append(f"| {slug} | " + " | ".join(str(st[c]) for c in cols) + " |")
    tot = {c: sum(st[c] for st in stats.values()) for c in cols if c != "median_matn_words"}
    lines.append("| **total** | " + " | ".join(str(tot.get(c, "")) for c in cols) + " |")
    t = stats.get("tirmidhi", {})
    lines += [
        "",
        "Column meanings: `empty` = no Arabic text upstream; `ref` = back-reference to the "
        "previous narration with no own wording (\"بهذا الإسناد مثله\"); `ref_variant` = "
        "back-reference that adds or changes wording; `no_boundary` = splitter found no "
        "isnad/matn seam (whole text kept as isnad); `with_tail` = has further chains or "
        "compiler comments after the matn.",
        "",
        f"Tirmidhi's own grade extracted for {t.get('tirmidhi_graded', 0)} of "
        f"{t.get('records', 0)} entries. Most common: "
        + ", ".join(f"{g} ({c})" for g, c in t.get("tirmidhi_grades", [])) + ".",
        "",
    ]
    path.write_text("\n".join(lines))
