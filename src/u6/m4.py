"""M4: English translation of every representative, and topic tagging.

Translation sends several hadith per request (≤ PACK_WORDS Arabic words) and asks for one
English segment per Arabic segment, so the italics of the Arabic line up in English.
Model choice comes from a bake-off (stage `bakeoff`): Opus 5.5 compares a candidate model's
translations blind against the M1 sample's Sonnet 5.5 (medium) translations.
Outputs go to data/m4/. Budget rules: docs/handoff/M4.md.
"""

import json
import random
import time
from concurrent.futures import ThreadPoolExecutor

from . import llm
from .corpus import DATA
from .sample import GLOSSARY, TRANSLATE_SYSTEM
from .textnorm import letters

M4 = DATA / "m4"
PACK_WORDS = 600   # Arabic words per translation request (one long hadith may exceed it alone)

PACK_NOTE = """Several hadith arrive in one message, each in its own <hadith id="..."> element. \
Translate each independently and return one result per hadith, with its id and exactly as \
many English segments as it has Arabic segments."""

PACK_SCHEMA = {
    "type": "object",
    "properties": {"hadith": {"type": "array", "items": {
        "type": "object",
        "properties": {"id": {"type": "string"},
                       "segments": {"type": "array", "items": {"type": "string"}}},
        "required": ["id", "segments"], "additionalProperties": False}}},
    "required": ["hadith"], "additionalProperties": False,
}


def words(h: dict) -> int:
    return sum(len(s["ar"].split()) for s in h["segments"])


def pack(hadith: list[dict], max_words: int = PACK_WORDS) -> list[list[dict]]:
    """Consecutive hadith into requests of at most max_words Arabic words."""
    packs, cur, n = [], [], 0
    for h in hadith:
        w = words(h)
        if cur and n + w > max_words:
            packs.append(cur)
            cur, n = [], 0
        cur.append(h)
        n += w
    return packs + ([cur] if cur else [])


def translate_params(model: str, effort: str, hs: list[dict]) -> dict:
    parts = []
    for h in hs:
        segs = "\n".join(f"[{i + 1}] {letters(s['ar'])}" for i, s in enumerate(h["segments"]))
        parts.append(f"<hadith id=\"{h['id']}\" segments=\"{len(h['segments'])}\">\n{segs}\n</hadith>")
    return {
        "model": model,
        "max_tokens": 8000 + 6 * sum(words(h) for h in hs),
        "system": [{"type": "text", "text": TRANSLATE_SYSTEM + "\n\n" + PACK_NOTE,
                    "cache_control": {"type": "ephemeral"}}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": PACK_SCHEMA}},
        "messages": [{"role": "user", "content": "\n".join(parts)}],
    }


def parse_pack(msg, hs: list[dict]) -> dict:
    """{hadith id: [English segments]} for the hadith whose segment count lines up."""
    if msg.stop_reason != "end_turn":
        return {}
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        got = {r["id"]: r["segments"] for r in json.loads(text)["hadith"]}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}
    return {h["id"]: got[h["id"]] for h in hs
            if len(got.get(h["id"], [])) == len(h["segments"]) and all(s.strip() for s in got[h["id"]])}


def translate_live(hs: list[dict], model: str, effort: str, stage: str, cap_usd: float,
                   workers: int = 8) -> dict:
    client = llm._client()
    total, out = 0.0, {}

    def run(p):
        return p, client.messages.create(**translate_params(model, effort, p))

    with ThreadPoolExecutor(workers) as ex:
        for p, msg in ex.map(run, pack(hs)):
            total += llm.cost(model, msg.usage, batch=False)
            out.update(parse_pack(msg, p))
            if llm.spent(stage) + total > cap_usd:
                llm.log_spend(stage, model, total, 0)
                raise SystemExit(f"{stage}: spend cap ${cap_usd} reached")
    llm.log_spend(stage, model, total, len(pack(hs)))
    return out


# ---------------------------------------------------------------- bake-off

JUDGE_SYSTEM = f"""You are an expert translator of classical Arabic hadith into English. For \
each hadith you get the Arabic and two English translations, X and Y, made by different \
systems for a general readership. Judge each against the Arabic:
- accuracy (1-5): 5 = every statement faithful, nothing added or lost; 3 = a minor \
inaccuracy; 1 = a mistranslation that changes a ruling or meaning.
- fluency (1-5): natural, readable modern English.
- major_errors: short notes on any error that changes meaning (empty if none).
Then pick the better translation overall (accuracy first), or "tie" if they are equally good.
The house glossary both were asked to follow: {GLOSSARY}"""

JUDGE_SCHEMA = {
    "type": "object",
    "properties": {"results": {"type": "array", "items": {
        "type": "object",
        "properties": {
            "id": {"type": "string"},
            "accuracy_x": {"type": "integer"}, "accuracy_y": {"type": "integer"},
            "fluency_x": {"type": "integer"}, "fluency_y": {"type": "integer"},
            "major_errors_x": {"type": "array", "items": {"type": "string"}},
            "major_errors_y": {"type": "array", "items": {"type": "string"}},
            "better": {"type": "string", "enum": ["X", "Y", "tie"]}},
        "required": ["id", "accuracy_x", "accuracy_y", "fluency_x", "fluency_y",
                     "major_errors_x", "major_errors_y", "better"],
        "additionalProperties": False}}},
    "required": ["results"], "additionalProperties": False,
}


def judge(items: list[dict], stage: str, cap_usd: float, per_request: int = 5) -> dict:
    """items: [{"id", "ar", "x", "y"}] -> {id: verdict}"""
    client = llm._client()
    chunks = [items[i:i + per_request] for i in range(0, len(items), per_request)]
    total, out = 0.0, {}

    def run(c):
        body = "\n".join(f"<hadith id=\"{it['id']}\">\n<arabic>{it['ar']}</arabic>\n<X>{it['x']}</X>\n"
                         f"<Y>{it['y']}</Y>\n</hadith>" for it in c)
        return client.messages.create(
            model=llm.OPUS, max_tokens=16000,
            system=[{"type": "text", "text": JUDGE_SYSTEM, "cache_control": {"type": "ephemeral"}}],
            output_config={"effort": "high", "format": {"type": "json_schema", "schema": JUDGE_SCHEMA}},
            messages=[{"role": "user", "content": body}])

    with ThreadPoolExecutor(6) as ex:
        for msg in ex.map(run, chunks):
            total += llm.cost(llm.OPUS, msg.usage, batch=False)
            if msg.stop_reason == "end_turn":
                text = next((b.text for b in msg.content if b.type == "text"), "{}")
                out.update({r["id"]: r for r in json.loads(text)["results"]})
            if llm.spent(stage) + total > cap_usd:
                llm.log_spend(stage, llm.OPUS, total, 0)
                raise SystemExit(f"{stage}: spend cap ${cap_usd} reached")
    llm.log_spend(stage, llm.OPUS, total, len(chunks))
    return out


def stage_bakeoff(model: str = llm.HAIKU, effort: str = "high", seed: int = 5) -> None:
    """Candidate model vs the M1 sample's Sonnet (medium) translations, judged blind by Opus."""
    llm.require_key()
    M4.mkdir(exist_ok=True)
    tag = f"{model.split('-')[1]}-{effort}"
    sample = json.loads((DATA / "m1" / "sample.json").read_text())
    sample = [h for h in sample if h.get("segments_en") and not h.get("italics_dropped")]
    cache = M4 / f"bakeoff-{tag}.json"
    cand = json.loads(cache.read_text()) if cache.exists() else {}
    todo = [h for h in sample if h["id"] not in cand]
    if todo:
        cand.update(translate_live(todo, model, effort, f"m4-bakeoff-{tag}", cap_usd=1.0))
        cache.write_text(json.dumps(cand, ensure_ascii=False, indent=1) + "\n")
    rng = random.Random(seed)
    items, flip = [], {}
    for h in sample:
        if h["id"] not in cand:
            continue
        a, b = " ".join(cand[h["id"]]), " ".join(h["segments_en"])
        flip[h["id"]] = rng.random() < 0.5   # True: candidate is Y
        x, y = (b, a) if flip[h["id"]] else (a, b)
        items.append({"id": h["id"], "ar": " ".join(letters(s["ar"]) for s in h["segments"]), "x": x, "y": y})
    vcache = M4 / f"bakeoff-{tag}-verdicts.json"
    verdicts = json.loads(vcache.read_text()) if vcache.exists() else {}
    rest = [it for it in items if it["id"] not in verdicts]
    if rest:
        verdicts.update(judge(rest, f"m4-bakeoff-judge", cap_usd=2.0))
        vcache.write_text(json.dumps(verdicts, ensure_ascii=False, indent=1) + "\n")

    def side(v, h_id, who):  # who: "cand" or "sonnet" -> "x"/"y"
        return ("y" if flip[h_id] else "x") if who == "cand" else ("x" if flip[h_id] else "y")

    rows = []
    for h_id, v in verdicts.items():
        c, s = side(v, h_id, "cand"), side(v, h_id, "sonnet")
        better = {"tie": "tie", c.upper(): "cand", s.upper(): "sonnet"}[v["better"]]
        rows.append({"id": h_id, "acc_c": v[f"accuracy_{c}"], "acc_s": v[f"accuracy_{s}"],
                     "flu_c": v[f"fluency_{c}"], "flu_s": v[f"fluency_{s}"],
                     "err_c": v[f"major_errors_{c}"], "err_s": v[f"major_errors_{s}"], "better": better})
    n = len(rows)
    mean = lambda k: sum(r[k] for r in rows) / n
    summary = {
        "candidate": f"{model} ({effort})", "reference": f"{llm.SONNET} (medium), M1 sample",
        "judged": n, "missing_translations": len(sample) - len(cand),
        "accuracy": {"candidate": round(mean("acc_c"), 2), "sonnet": round(mean("acc_s"), 2)},
        "fluency": {"candidate": round(mean("flu_c"), 2), "sonnet": round(mean("flu_s"), 2)},
        "hadith_with_major_errors": {"candidate": sum(bool(r["err_c"]) for r in rows),
                                     "sonnet": sum(bool(r["err_s"]) for r in rows)},
        "better": {k: sum(r["better"] == k for r in rows) for k in ("cand", "sonnet", "tie")},
        "spend_usd": {"translate": round(llm.spent(f"m4-bakeoff-{tag}"), 4),
                      "judge": round(llm.spent("m4-bakeoff-judge"), 4)},
    }
    (M4 / f"bakeoff-{tag}-summary.json").write_text(json.dumps({"summary": summary, "rows": rows},
                                                               ensure_ascii=False, indent=1) + "\n")
    print(json.dumps(summary, indent=1))


# ---------------------------------------------------------------- full translation (Batch API)

TRANSLATIONS = M4 / "translations.jsonl"
TRANSLATE_MODEL, TRANSLATE_EFFORT = llm.SONNET, "medium"   # bake-off: docs/reports/m4-bakeoff.md
TRANSLATE_CAP_USD = 20.0   # whole stage; waves stop when measured spend + projection exceeds it
WAVE = 500                 # requests per batch (handoff rule: ≤ 500, in waves)


def representatives() -> list[dict]:
    rows = [json.loads(l) for l in (DATA / "six" / "hadith.jsonl").open(encoding="utf-8")]
    return [h for h in rows if h.get("segments")]


def load_translations() -> dict:
    if not TRANSLATIONS.exists():
        return {}
    return {r["id"]: r for r in map(json.loads, TRANSLATIONS.open(encoding="utf-8"))}


def _append(rows: list[dict]) -> None:
    M4.mkdir(exist_ok=True)
    with TRANSLATIONS.open("a", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def _submit(packs: list[list[dict]], stage: str) -> str:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request
    reqs = [Request(custom_id=f"{stage}-{k}", params=MessageCreateParamsNonStreaming(
        **translate_params(TRANSLATE_MODEL, TRANSLATE_EFFORT, p))) for k, p in enumerate(packs)]
    batch = llm._client().messages.batches.create(requests=reqs)
    llm._record_batch(batch.id, stage, TRANSLATE_MODEL, len(reqs))
    (M4 / f"batch-{batch.id}.json").write_text(json.dumps(
        {f"{stage}-{k}": [h["id"] for h in p] for k, p in enumerate(packs)}))
    return batch.id


def _collect(batch_id: str, by_id: dict, poll: int = 60) -> tuple[float, int]:
    """Wait for a batch, append aligned translations, log its spend. -> (usd, Arabic words done)."""
    client = llm._client()
    while client.messages.batches.retrieve(batch_id).processing_status != "ended":
        time.sleep(poll)
    rows = json.loads(llm.BATCHES.read_text())
    meta = next(r for r in rows if r["id"] == batch_id)
    manifest = json.loads((M4 / f"batch-{batch_id}.json").read_text())
    have = load_translations()
    usd, done, out = 0.0, 0, []
    for res in client.messages.batches.results(batch_id):
        if res.result.type != "succeeded":
            continue
        msg = res.result.message
        usd += llm.cost(meta["model"], msg.usage, batch=True)
        hs = [by_id[i] for i in manifest[res.custom_id]]
        for h_id, en in parse_pack(msg, hs).items():
            if h_id not in have:
                out.append({"id": h_id, "segments_en": en, "model": meta["model"],
                            "effort": TRANSLATE_EFFORT, "label": "machine translation"})
                done += words(by_id[h_id])
    if not meta["collected"]:
        _append(out)
        llm.log_spend(meta["stage"], meta["model"], usd, meta["requests"])
        meta["collected"] = True
        llm.BATCHES.write_text(json.dumps(rows, indent=1) + "\n")
    return usd, done


def stage_translate(pilot: int = 100, cap_usd: float = TRANSLATE_CAP_USD, singles: bool = False) -> None:
    """Pilot batch, then waves of WAVE requests, re-projecting the cost after each.
    Resumable: uncollected batches in data/batches.json are collected first. `singles`
    re-sends leftovers (failed or misaligned) one hadith per request."""
    llm.require_key()
    M4.mkdir(exist_ok=True)
    reps = representatives()
    by_id = {h["id"]: h for h in reps}
    for r in json.loads(llm.BATCHES.read_text()):
        if r["stage"].startswith("m4-tr") and not r["collected"]:
            print("collecting", r["id"], _collect(r["id"], by_id))
    stage_spend = lambda: sum(llm.spent(s) for s in {r["stage"] for r in json.loads(llm.BATCHES.read_text())
                                                     if r["stage"].startswith("m4-tr")})
    have = load_translations()
    todo = [h for h in reps if h["id"] not in have]
    packs = [[h] for h in todo] if singles else pack(todo)
    random.Random(4).shuffle(packs)   # waves are unbiased samples of request size
    wave_no = len([r for r in json.loads(llm.BATCHES.read_text()) if r["stage"].startswith("m4-tr")])
    first = pilot if not have and not singles else WAVE
    while packs:
        wave, packs = packs[:first], packs[first:]
        first = WAVE
        stage = f"m4-tr{'-single' if singles else ''}-w{wave_no}"
        bid = _submit(wave, stage)
        print(f"{stage}: {len(wave)} requests, batch {bid}", flush=True)
        usd, done = _collect(bid, by_id)
        wave_no += 1
        have = load_translations()
        left_words = sum(words(h) for h in reps if h["id"] not in have)
        all_done = sum(words(h) for h in reps if h["id"] in have)
        per_word = stage_spend() / max(all_done, 1)
        projected = stage_spend() + per_word * left_words
        print(f"  wave ${usd:.2f}; stage ${stage_spend():.2f}; translated {len(have)}/{len(reps)}; "
              f"${per_word * 1e6:.1f}/M words; projected total ${projected:.2f}", flush=True)
        if packs and projected > cap_usd:
            raise SystemExit(f"projected ${projected:.2f} exceeds the ${cap_usd} cap: ask the owner")
    have = load_translations()
    print(f"done: {len(have)}/{len(reps)} translated; leftovers {len(reps) - len(have)} "
          f"(re-run with singles=True); stage spend ${stage_spend():.2f}")
