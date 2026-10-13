"""M1 format sample: a ~30-page PDF per edition (A by attestation, B by topic), EN + AR.

The sample is for reviewing the *format*. Its English is a draft machine translation and
its topics come from a provisional taxonomy (the real taxonomy and translation are M4).
"""

import json
import random
from collections import Counter

from . import llm
from .corpus import DATA, ROOT, load_docs
from .textnorm import letters

M1 = DATA / "m1"
OUT = ROOT / "out"
TYPESET = ROOT / "typeset"

# Provisional top-level topics, after the kitab arrangement of Ibn al-Athir's Jami' al-Usul
# (regrouped and shortened). Replaced by the M4 taxonomy.
TOPICS = [
    "Faith and belief", "Knowledge and the Sunnah", "The Qur'an and its recitation",
    "Purification", "Prayer", "Funerals", "Zakat and charity", "Fasting", "Hajj and Umrah",
    "Trade and transactions", "Marriage and divorce", "Inheritance and bequests",
    "Food, drink and hunting", "Dress and adornment", "Manners and good character",
    "Supplication and remembrance", "Medicine and dreams", "Oaths, vows and expiation",
    "Crimes and punishments", "Judgments and testimony", "Government and leadership",
    "Jihad and expeditions", "Virtues of the Prophet and Companions", "Prophets and creation",
    "Signs of the Hour and tribulations", "Resurrection, Paradise and Hell", "Softening of hearts",
]

GLOSSARY = """Glossary (use exactly): صلى الله عليه وسلم -> ﷺ; الصلاة -> prayer (ṣalāh when \
technical); الزكاة -> zakāh; الصدقة -> charity (ṣadaqah); الصوم/الصيام -> fasting; الحج -> Hajj; \
العمرة -> ʿUmrah; الجنة -> Paradise; النار -> the Fire; رسول الله -> the Messenger of Allah; \
النبي -> the Prophet; الله -> Allah; أمير المؤمنين -> the Commander of the Faithful; \
Companion names transliterated (ʿĀʾishah, Abū Hurayrah, ʿUmar, Ibn ʿAbbās, Anas ibn Mālik ...)."""

TRANSLATE_SYSTEM = f"""You translate hadith from Arabic into clear, faithful modern English for \
a general readership. Keep the meaning exact; do not add commentary or explanatory brackets \
except minimal [ ] insertions needed for grammar. Keep "ﷺ" after mentions of the Prophet.
{GLOSSARY}
The Arabic arrives split into numbered segments; return one English segment per Arabic \
segment, in order, so that the segments can be typeset separately. Segments may begin or \
end mid-sentence; translate each so that the concatenation reads naturally."""

TRANSLATE_SCHEMA = {
    "type": "object",
    "properties": {"segments": {"type": "array", "items": {"type": "string"}}},
    "required": ["segments"], "additionalProperties": False,
}

TOPIC_SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"}, "topic": {"type": "string", "enum": TOPICS}},
        "required": ["id", "topic"], "additionalProperties": False}}},
    "required": ["results"], "additionalProperties": False,
}


def select(hadith: list[dict], n: int = 60, seed: int = 3) -> list[dict]:
    """A spread over attestation patterns, favouring entries that show the apparatus
    (italics, partial stars) and keeping long texts rare so ~30 pages suffice."""
    rng = random.Random(seed)
    by = {}
    for h in hadith:
        words = sum(len(s["ar"].split()) for s in h["segments"])
        if not h["segments"] or words > 160:
            continue
        by.setdefault(h["stars_display"], []).append(h)
    quotas = {"★★": 18, "★⯪": 10, "⯪★": 0, "⯪⯪": 4, "★": 18, "⯪": 0}
    pick = []
    for disp, q in quotas.items():
        pool = by.get(disp, [])
        with_italics = [h for h in pool if any(not s["core"] for s in h["segments"])]
        k = min(len(with_italics), q // 2)
        chosen = rng.sample(with_italics, k)
        rest = [h for h in pool if h not in chosen]
        chosen += rng.sample(rest, min(len(rest), q - k))
        pick += chosen
    return pick[:n]


def translate(sample: list[dict]) -> None:
    client = llm._client()
    total = 0.0
    for h in sample:
        if h.get("segments_en"):
            continue
        segs = [letters(s["ar"]) for s in h["segments"]]
        prompt = "\n".join(f"[{i + 1}] {s}" for i, s in enumerate(segs))
        msg = client.messages.create(
            model=llm.SONNET, max_tokens=8000,
            system=TRANSLATE_SYSTEM,
            output_config={"effort": "medium", "format": {"type": "json_schema", "schema": TRANSLATE_SCHEMA}},
            messages=[{"role": "user", "content": prompt}])
        total += llm.cost(llm.SONNET, msg.usage, batch=False)
        text = next((b.text for b in msg.content if b.type == "text"), "{}")
        en = json.loads(text).get("segments", [])
        if len(en) != len(segs):  # misaligned: keep the text, drop per-segment italics
            en = [" ".join(en)] + [""] * (len(segs) - 1)
            h["italics_dropped"] = True
        h["segments_en"] = en
    llm.log_spend("sample-translate", llm.SONNET, total, len(sample))


def tag_topics(sample: list[dict]) -> None:
    items = "\n".join(f"<h id=\"{h['id']}\">{' '.join(letters(s['ar']) for s in h['segments'])[:1500]}</h>"
                      for h in sample)
    msg = llm._client().messages.create(
        model=llm.HAIKU, max_tokens=8000,
        system="Assign each hadith exactly one primary topic from the allowed list.",
        output_config={"effort": "low", "format": {"type": "json_schema", "schema": TOPIC_SCHEMA}},
        messages=[{"role": "user", "content": items}])
    llm.log_spend("sample-topics", llm.HAIKU, llm.cost(llm.HAIKU, msg.usage, batch=False), 1)
    got = {r["id"]: r["topic"] for r in json.loads(next(b.text for b in msg.content if b.type == "text"))["results"]}
    for h in sample:
        h["topic"] = got.get(h["id"], "Manners and good character")


def build_data(sample: list[dict]) -> dict:
    docs = {d.id: d for d in load_docs(("bukhari", "muslim"))}
    recs = {}
    for b in ("bukhari", "muslim"):
        for line in (DATA / "narrations" / f"{b}.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            recs[r["id"]] = r
    conc = {}
    for line in (DATA / "concordance.csv").open(encoding="utf-8"):
        p = line.rstrip("\n").split(",")
        conc[p[0]] = p[-1]
    entries = []
    for k, h in enumerate(sample, 1):
        members = []
        for m in h["members"]:
            r = recs[m["id"]]
            label = r["n"] if m["book"] == "bukhari" else (r["n_fab"] or r["n"])
            members.append({"letter": "B" if m["book"] == "bukhari" else "M", "number": label,
                            "role": m["role"], "kind": m["kind"], "narrator": docs[m["id"]].isnad_last,
                            "url": conc.get(m["id"], ""), "is_rep": m["id"] == h["representative"]})
        entries.append({
            "uid": h["id"], "stars": h["stars_display"], "badge": h["badge"] or "",
            "letters": [x for x in ("B", "M") if any(mm["letter"] == x for mm in members)],
            "topic": h["topic"],
            "segments": [{"ar": s["ar"], "en": e, "core": s["core"] or h.get("italics_dropped", False)}
                         for s, e in zip(h["segments"], h["segments_en"])],
            "members": members,
            "narrators": sorted({m["narrator"] for m in members if m["narrator"]}),
            "variants": sum(1 for m in members if m["kind"] != "ref") - 1,
        })
    return {"entries": entries, "topics": TOPICS}


def stage_sample() -> None:
    llm.require_key()
    hadith = [json.loads(l) for l in (M1 / "hadith.jsonl").open(encoding="utf-8")]
    cache = M1 / "sample.json"
    sample = json.loads(cache.read_text()) if cache.exists() else select(hadith)
    if not all(h.get("topic") for h in sample):
        tag_topics(sample)
    translate(sample)
    cache.write_text(json.dumps(sample, ensure_ascii=False, indent=1) + "\n")
    data = build_data(sample)
    build = TYPESET / "build"
    build.mkdir(parents=True, exist_ok=True)
    (build / "sample-data.json").write_text(json.dumps(data, ensure_ascii=False))
    import typst
    OUT.mkdir(exist_ok=True)
    for ed in ("A", "B"):
        pdf = typst.compile(str(TYPESET / "sample.typ"), root=str(ROOT),
                            font_paths=[str(TYPESET / "fonts")], sys_inputs={"edition": ed})
        (OUT / f"m1-sample-edition-{ed}.pdf").write_bytes(pdf)
    print(f"sample: {len(sample)} hadith; {Counter(h['stars_display'] for h in sample)}; "
          f"spend ${llm.spent():.2f}; PDFs in out/")
