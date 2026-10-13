"""M2 + M3: add Abu Dawud, Tirmidhi, Nasa'i and Ibn Majah to the M1 result, incrementally.

M1's 74k Bukhari/Muslim pair decisions are reused as they are; only pairs that involve at
least one narration from a new book are generated and labelled. Cost controls (owner has a
fixed budget, see docs/handoff/M2.md):
  * middle-band pairs with lexical score < LOW_BAND get no LLM call: "see also, unconfirmed";
  * Haiku (medium) pre-filters the rest: confident no-merge (>= HAIKU_DROP) and very
    confident merge (>= HAIKU_MERGE) calls are final (both error-free on M1 gold);
  * Sonnet (high, grouped) decides what remains, after a one-chunk pilot projects the cost.
Outputs go to data/six/.
"""

import json
import random
import time
from collections import Counter

import numpy as np

from . import llm, m1
from .candidates import backref_edges, candidate_pairs, cosine_rows, exact_edges, matchable
from .corpus import DATA, ROOT, load_docs
from .features import pair_features, score, shingles

ALL = ("bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah")
OLD = ("bukhari", "muslim")
NEW = ("abudawud", "tirmidhi", "nasai", "ibnmajah")
D6 = DATA / "six"
LOW_BAND = 0.40          # middle-band pairs below this get no LLM call ("see also")
HAIKU_DROP = 0.7         # Haiku no-merge calls at or above this confidence are final
HAIKU_MERGE = 0.9        # Haiku merge calls at or above this confidence are final
SONNET_CAP_USD = 18.0  # stop and ask the owner if the Sonnet stage projects above this
SONNET_EFFORT = "medium"  # owner's choice after the gold re-test (see docs/reports/m23-eval.md)
PILOT2_CAP_USD = 19.0     # medium effort: projected cost of the rest must stay under this
WAVE = 2000               # requests per wave; spend is re-measured between waves


def _use_six() -> None:
    """Point the shared M1 helpers at the six-book run."""
    m1.M1 = D6
    m1.BOOKS = ALL


def is_new(doc_id: str) -> bool:
    return doc_id.split(":")[0] in NEW


# ---------------------------------------------------------------- pairs

def stage_pairs() -> None:
    from .embed import embed, embedding_knn
    _use_six()
    docs = load_docs(ALL)
    free = [e for e in backref_edges(docs) + exact_edges(docs) if is_new(e["a"]) or is_new(e["b"])]
    m1._write_jsonl(D6 / "edges_free.jsonl", free)
    M = matchable(docs)
    old = [d for d in M if d.book in OLD]
    new = [d for d in M if d.book in NEW]
    assert M == old + new, "matchable order must be old books then new books"
    cands, X = candidate_pairs(M)
    emb = np.vstack([embed(old), embed(new)])
    for key, c in embedding_knn(emb).items():
        cands.setdefault(key, {"knn_cos": None, "shared4": 0})["emb_knn"] = c
    keys = sorted(k for k in cands if M[k[0]].book in NEW or M[k[1]].book in NEW)
    cos_t = cosine_rows(X, keys)
    cos_e = np.einsum("ij,ij->i", emb[[k[0] for k in keys]], emb[[k[1] for k in keys]])
    sh = {}
    rows = []
    for (i, j), ct, ce in zip(keys, cos_t, cos_e):
        a, b = M[i], M[j]
        sa = sh.setdefault(i, shingles(a.match))
        sb = sh.setdefault(j, shingles(b.match))
        f = pair_features(a, b, sa, sb, ct, ce)
        ch = cands[(i, j)]
        via = "".join(c for c, on in (("t", ch.get("knn_cos")), ("w", ch.get("word_knn")),
                                       ("r", ch.get("shared4")), ("e", ch.get("emb_knn"))) if on)
        if via == "e" and f["cos_tfidf"] < m1.EMB_ONLY_MIN_TFIDF:
            continue
        rows.append({"pid": f"{a.id}|{b.id}", "a": a.id, "b": b.id, **f, "score": round(score(f), 4), "via": via})
    m1._write_jsonl(D6 / "pairs.jsonl", rows)
    th = json.loads((DATA / "m1" / "thresholds.json").read_text())["thresholds"]
    routes = Counter(route(r, th) for r in rows)
    print(f"pairs: {len(rows)} new pairs over {len(new)} new + {len(old)} old matchable docs; routes {routes}")


def route(p: dict, th: dict) -> str:
    a = m1.auto_label(p, th)
    if a:
        return "auto"
    return "skip" if p["score"] < LOW_BAND else "llm"


# ---------------------------------------------------------------- gold

def stage_gold(per_band: int = 25, hard_negatives: int = 25, seed: int = 11, cap_usd: float = 3.0) -> None:
    """150 stratified new pairs + 25 hard negatives; Opus reference, Sonnet grouped (the
    production format), Haiku medium (the pre-filter); Opus xhigh adjudicates disputes."""
    _use_six()
    llm.require_key()
    path = D6 / "gold.jsonl"
    if not path.exists():
        rng = random.Random(seed)
        pairs = m1.read_jsonl(D6 / "pairs.jsonl")
        gold = []
        for lo, hi in m1.BANDS:
            band = [p for p in pairs if lo <= p["score"] < hi]
            gold += [{**p, "stratum": f"{lo:.2f}-{hi:.2f}"} for p in rng.sample(band, min(len(band), per_band))]
        docs = {d.id: d for d in matchable(load_docs(ALL))}
        have = {p["pid"] for p in pairs}
        by_ch = {}
        for d in docs.values():
            if d.book in NEW:
                by_ch.setdefault((d.book, d.chapter), []).append(d)
        pool = [g for g in by_ch.values() if len(g) > 5]
        while sum(1 for g in gold if g["stratum"] == "hard_negative") < hard_negatives:
            a, b = sorted(rng.sample(rng.choice(pool), 2), key=lambda d: d.seq)
            pid = f"{a.id}|{b.id}"
            f = pair_features(a, b, shingles(a.match), shingles(b.match), 0.0, None)
            if pid in have or f["jac"] < 0.12:
                continue
            gold.append({"pid": pid, "a": a.id, "b": b.id, **f, "score": round(score(f), 4), "via": "",
                         "stratum": "hard_negative"})
            have.add(pid)
        m1._write_jsonl(path, gold)
    gold = m1.read_jsonl(path)
    pp = m1._prompt_pairs(gold)
    for q, g in zip(pp, gold):
        q["a"], q["b"] = g["a"], g["b"]
    if any("opus" not in g for g in gold):
        got = llm.classify_live([q for q, g in zip(pp, gold) if "opus" not in g], llm.OPUS, "high",
                                stage="six-gold-opus", cap_usd=cap_usd, per_request=5)
        for g in gold:
            g.setdefault("opus", got.get(g["pid"]))
    for field, model, effort in (("sonnet_grouped", llm.SONNET, "high"), ("haiku_grouped", llm.HAIKU, "medium")):
        todo = [q for q, g in zip(pp, gold) if field not in g]
        if todo:
            got = llm.classify_groups_live(llm.group_pairs(todo), model, effort, stage=f"six-gold-{field}",
                                           cap_usd=cap_usd)
            for g in gold:
                if g["pid"] in got:
                    g[field] = got[g["pid"]]
    m1._write_jsonl(path, gold)
    # Adjudicate where Opus, Sonnet and the six-book decision path disagree.
    th = json.loads((DATA / "m1" / "thresholds.json").read_text())["thresholds"]
    disputed = [g for g in gold if g.get("opus") and len({m1.is_merge(g["opus"]["label"]),
                                                          m1.is_merge(g.get("sonnet_grouped", {}).get("label")),
                                                          m1.is_merge(decision(g, th))}) > 1]
    todo = [g for g in disputed if "adjudicated" not in g]
    if todo:
        got = llm.classify_live(m1._prompt_pairs(todo), llm.OPUS, "xhigh", stage="six-gold-adjudicate",
                                cap_usd=cap_usd, per_request=1)
        for g in gold:
            if g["pid"] in got:
                g["adjudicated"] = got[g["pid"]]
    for g in gold:
        if not g.get("opus"):
            continue
        if g in disputed and "adjudicated" in g:
            a = g["adjudicated"]
            g["truth"] = "ambiguous" if a["confidence"] < m1.AMBIGUOUS_BELOW else a["label"]
        elif g not in disputed:
            g["truth"] = g["opus"]["label"]
    m1._write_jsonl(path, gold)
    print(f"gold: {len(gold)} pairs, {len(disputed)} disputed; truth {Counter(g.get('truth') for g in gold)}; "
          f"spend ${llm.spent():.2f}")


def haiku_final(h: dict) -> bool:
    return h["confidence"] >= (HAIKU_MERGE if m1.is_merge(h["label"]) else HAIKU_DROP)


def decision(g: dict, th: dict) -> str:
    """What the six-book pipeline decides for a pair (gold rows carry the model labels)."""
    a = m1.auto_label(g, th)
    if a:
        return {"partial": "a_in_b"}.get(a, a)
    if g["score"] < LOW_BAND:
        return "skipped"
    h = g.get("haiku_grouped")
    if h and haiku_final(h):
        return h["label"]
    return (g.get("sonnet_grouped") or {}).get("label", "unlabelled")


# ---------------------------------------------------------------- label

def _pending(stage: str) -> list[str]:
    rows = json.loads(llm.BATCHES.read_text()) if llm.BATCHES.exists() else []
    return [r["id"] for r in rows if r["stage"] == stage and not r["collected"]]


def _run_batches(groups: list[dict], model: str, effort: str, stage: str) -> dict:
    """Submit in <=500-request chunks (never cancelled), collect as they finish."""
    pending = _pending(stage)
    if not pending:
        for k in range(0, len(groups), m1.BATCH_CHUNK):
            pending.append(llm.submit_group_batch(groups[k:k + m1.BATCH_CHUNK], model, effort, stage=stage))
        print(f"{stage}: {len(groups)} requests in {len(pending)} batches", flush=True)
    client = llm._client()
    got = {}
    while pending:
        ended = [b for b in pending if client.messages.batches.retrieve(b).processing_status == "ended"]
        if not ended:
            time.sleep(60)
            continue
        for b in ended:
            pending.remove(b)
            g, _ = llm.collect_group_batch(b)
            got.update(g)
            print(f"  {stage} {b}: {len(g)} labelled; spend ${llm.spent():.2f}", flush=True)
    return got


def stage_label() -> None:
    _use_six()
    llm.require_key()
    th = json.loads((DATA / "m1" / "thresholds.json").read_text())["thresholds"]
    pairs = m1.read_jsonl(D6 / "pairs.jsonl")
    out = D6 / "labels.jsonl"
    done = {r["pid"]: r for r in m1.read_jsonl(out)} if out.exists() else {}
    words = {d.id: d.words for d in load_docs(ALL)}

    def put(p, label, source, conf=None, **extra):
        done[p["pid"]] = {"pid": p["pid"], "a": p["a"], "b": p["b"], "label": label, "source": source,
                          "confidence": conf, **extra}

    for p in pairs:
        if p["pid"] in done:
            continue
        r = route(p, th)
        if r == "auto":
            lab = m1.auto_label(p, th)
            if lab == "partial":
                lab = "a_in_b" if words[p["a"]] <= words[p["b"]] else "b_in_a"
            put(p, lab, "auto")
        elif r == "skip":
            put(p, "unresolved", "skipped")
    m1._write_jsonl(out, done.values())

    def groups_for(rows):
        pp = m1._prompt_pairs(rows)
        for q, p in zip(pp, rows):
            q["a"], q["b"] = p["a"], p["b"]
        return llm.group_pairs(pp)

    llm_rows = [p for p in pairs if p["pid"] not in done or done[p["pid"]]["source"] == "haiku-keep"]
    todo_h = [p for p in llm_rows if p["pid"] not in done]
    if todo_h:
        got = _run_batches(groups_for(todo_h), llm.HAIKU, "medium", "six-haiku")
        for p in todo_h:
            h = got.get(p["pid"])
            if h and haiku_final(h):
                put(p, h["label"], "haiku", h["confidence"])
            else:
                put(p, "pending", "haiku-keep", None, haiku=h)
        m1._write_jsonl(out, done.values())
    todo_s = [p for p in pairs if done[p["pid"]]["source"] == "haiku-keep"]
    print(f"label: {Counter(r['source'] for r in done.values())}; {len(todo_s)} pairs for Sonnet", flush=True)
    if not todo_s:
        return
    groups = groups_for(todo_s)
    # Pilot: the first chunk measures the real cost per request before the rest is sent.
    if not _pending("six-sonnet") and not (D6 / "pilot.json").exists():
        before = llm.spent()
        got = _run_batches(groups[:m1.BATCH_CHUNK], llm.SONNET, "high", "six-sonnet-pilot")
        per_req = (llm.spent() - before) / max(1, min(len(groups), m1.BATCH_CHUNK))
        projected = per_req * len(groups)
        (D6 / "pilot.json").write_text(json.dumps({"per_request_usd": per_req, "requests": len(groups),
                                                    "projected_usd": projected}, indent=1))
        for p in todo_s:
            if p["pid"] in got:
                g = got[p["pid"]]
                put(p, g["label"], "sonnet", g["confidence"])
        m1._write_jsonl(out, done.values())
        print(f"pilot: ${per_req:.4f}/request, projected Sonnet stage ${projected:.2f}", flush=True)
        if projected > SONNET_CAP_USD:
            raise SystemExit(f"projected ${projected:.2f} exceeds the ${SONNET_CAP_USD} cap: ask the owner")
    todo_s = [p for p in pairs if done[p["pid"]]["source"] == "haiku-keep"]
    if todo_s and not _pending("six-sonnet") and not (D6 / "pilot2.json").exists():
        # Second pilot at the chosen effort with the repacked, shorter requests.
        groups = groups_for(todo_s)
        before = llm.spent()
        first = groups[:m1.BATCH_CHUNK]
        got = _run_batches(first, llm.SONNET, SONNET_EFFORT, "six-sonnet-pilot2")
        per_req = (llm.spent() - before) / max(1, len(first))
        projected = per_req * (len(groups) - len(first))
        (D6 / "pilot2.json").write_text(json.dumps({"effort": SONNET_EFFORT, "per_request_usd": per_req,
                                                     "remaining_requests": len(groups) - len(first),
                                                     "projected_rest_usd": projected}, indent=1))
        for p in todo_s:
            if p["pid"] in got:
                g = got[p["pid"]]
                put(p, g["label"], "sonnet", g["confidence"], effort=SONNET_EFFORT)
        m1._write_jsonl(out, done.values())
        print(f"pilot2: ${per_req:.4f}/request (front-loaded groups; waves re-measure)", flush=True)
    # The rest goes out in waves; after each wave the measured spend re-projects the
    # remainder, and the run stops if it would exceed the cap. (Greedy packing puts the
    # largest groups first, so a per-request projection from the first chunk overstates.)
    todo_s = [p for p in pairs if done[p["pid"]]["source"] == "haiku-keep"]
    if todo_s:
        groups = groups_for(todo_s)
        rest_start = llm.spent()
        cost_model = json.loads((D6 / "pilot2.json").read_text())
        for w in range(0, len(groups), WAVE):
            wave = groups[w:w + WAVE]
            stage = f"six-sonnet-w{w // WAVE}"
            before = llm.spent()
            got = _run_batches(wave, llm.SONNET, SONNET_EFFORT, stage)
            for p in todo_s:
                if p["pid"] in got:
                    g = got[p["pid"]]
                    put(p, g["label"], "sonnet", g["confidence"], effort=SONNET_EFFORT)
            m1._write_jsonl(out, done.values())
            used = llm.spent() - rest_start
            per_req = (llm.spent() - before) / max(1, len(wave))
            left = len(groups) - (w + len(wave))
            projected = used + per_req * left
            print(f"wave {w // WAVE}: ${llm.spent() - before:.2f} for {len(wave)} requests; rest so far ${used:.2f}, "
                  f"projected rest ${projected:.2f}", flush=True)
            if left and projected > PILOT2_CAP_USD:
                raise SystemExit(f"projected ${projected:.2f} exceeds ${PILOT2_CAP_USD}: ask the owner")
    print(f"labels: {Counter((r['source'], r['label']) for r in done.values()).most_common(12)}; "
          f"spend ${llm.spent():.2f}")


# ---------------------------------------------------------------- cluster + evaluate

def stage_cluster() -> None:
    _use_six()
    m1.stage_cluster([DATA / "m1", D6])


def stage_evaluate() -> None:
    _use_six()
    th = json.loads((DATA / "m1" / "thresholds.json").read_text())["thresholds"]
    gold = [g for g in m1.read_jsonl(D6 / "gold.jsonl") if g.get("truth")]
    clear = [g for g in gold if g["truth"] != "ambiguous"]
    rows = [("Six-book pipeline (rules, low-band skip, Haiku pre-filter, Sonnet)", m1._ev(clear, lambda g: decision(g, th)))]
    mid = [g for g in clear if not m1.auto_label(g, th)]
    rows.append(("Middle band: Sonnet high, grouped", m1._ev([g for g in mid if "sonnet_grouped" in g],
                                                             lambda g: g["sonnet_grouped"]["label"])))
    rows.append(("Middle band: Haiku medium, grouped", m1._ev([g for g in mid if "haiku_grouped" in g],
                                                              lambda g: g["haiku_grouped"]["label"])))
    llm_band = [g for g in mid if g["score"] >= LOW_BAND and "haiku_grouped" in g]
    dropped = [g for g in llm_band if not m1.is_merge(g["haiku_grouped"]["label"]) and haiku_final(g["haiku_grouped"])]
    accepted = [g for g in llm_band if m1.is_merge(g["haiku_grouped"]["label"]) and haiku_final(g["haiku_grouped"])]
    skipped = [g for g in mid if g["score"] < LOW_BAND]
    stats = json.loads((D6 / "cluster_stats.json").read_text()) if (D6 / "cluster_stats.json").exists() else None
    spend = Counter()
    for r in m1.read_jsonl(llm.SPEND_LOG):
        spend[r["stage"]] += r["usd"]
    pilot = json.loads((D6 / "pilot.json").read_text()) if (D6 / "pilot.json").exists() else None
    L = ["# M2 + M3 evaluation: all six books", "", "Generated by `python -m u6 six evaluate`.", "",
         "## Gold set (new books)", "",
         f"{len(gold)} pairs that involve Abu Dawud, Tirmidhi, Nasa'i or Ibn Majah: 25 per lexical-score band "
         "plus 25 same-chapter hard negatives. Opus 5.5 (high) is the reference; disputes between Opus, Sonnet "
         "and the pipeline's decision were re-judged by Opus at xhigh, and adjudications under "
         f"{m1.AMBIGUOUS_BELOW} confidence count as ambiguous ({len(gold) - len(clear)} pairs, excluded). "
         "No human review (owner does not read Arabic).", "",
         "| decision path | precision | 95% CI | recall |", "|---|---:|---:|---:|"]
    for name, e in rows:
        L.append(f"| {name} | {e['p']:.1%} ({e['tp']}/{e['pred']}) | {e['lo']:.1%}–{e['hi']:.1%} | {e['r']:.1%} ({e['tp']}/{e['pos']}) |")
    L += ["", f"**Quality gate (≥ 97 % merge precision): {'PASSED' if rows[0][1]['p'] >= 0.97 else 'NOT PASSED'}.**", "",
          "Cost levers on gold:",
          f"- Low band (score < {LOW_BAND}, no LLM): {len(skipped)} middle-band gold pairs, "
          f"{sum(m1.is_merge(g['truth']) for g in skipped)} true merges among them (kept as see-also links).",
          f"- Haiku pre-filter (no-merge, confidence ≥ {HAIKU_DROP}): dropped {len(dropped)} of {len(llm_band)}, "
          f"true merges lost {sum(m1.is_merge(g['truth']) for g in dropped)}.",
          f"- Haiku merges accepted (confidence ≥ {HAIKU_MERGE}): {len(accepted)}, "
          f"correct {sum(m1.is_merge(g['truth']) for g in accepted)}.", ""]
    if pilot:
        L += [f"Sonnet pilot: ${pilot['per_request_usd']:.4f} per request, {pilot['requests']} requests, "
              f"projected ${pilot['projected_usd']:.2f}.", ""]
    if stats:
        L += ["## Clusters (all six books)", "", "```json", json.dumps(stats, indent=1, ensure_ascii=False), "```", ""]
    L += ["## Spend (USD, whole project)", "", "| stage | $ |", "|---|---:|"]
    L += [f"| {k} | {v:.2f} |" for k, v in sorted(spend.items())] + [f"| **total** | **{sum(spend.values()):.2f}** |", ""]
    (ROOT / "docs" / "reports" / "m23-eval.md").write_text("\n".join(L))
    print("\n".join(L))
