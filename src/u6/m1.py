"""M1 pipeline stages for Bukhari + Muslim. Each stage reads/writes data/m1/ and is rerunnable.

  pairs       candidate pairs + features              -> data/m1/pairs.jsonl, edges_free.jsonl
  gold-sample stratified gold pairs                   -> data/m1/gold.jsonl (unlabelled)
  gold-label  Sonnet labels (and Haiku labels, for the bake-off) on the gold pairs
  calibrate   choose auto-decision thresholds on gold -> data/m1/thresholds.json, report
  label       auto rules + Haiku batch + Sonnet escalation -> data/m1/labels.jsonl
"""

import json
import random
from collections import Counter
from pathlib import Path

import numpy as np

from . import llm
from .candidates import backref_edges, candidate_pairs, cosine_rows, exact_edges, matchable
from .corpus import DATA, ROOT, load_docs
from .features import pair_features, score, shingles

M1 = DATA / "m1"
BOOKS = ("bukhari", "muslim")
MERGE = {"same", "a_in_b", "b_in_a"}
EMB_ONLY_MIN_TFIDF = 0.15


def _write_jsonl(path: Path, rows) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_jsonl(path: Path) -> list[dict]:
    with path.open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


# ---------------------------------------------------------------- pairs

def stage_pairs(use_embeddings: bool = True) -> None:
    docs = load_docs(BOOKS)
    _write_jsonl(M1 / "edges_free.jsonl", backref_edges(docs) + exact_edges(docs))
    M = matchable(docs)
    cands, X = candidate_pairs(M)
    emb = None
    if use_embeddings:
        from .embed import embed, embedding_knn
        emb = embed(M)
        for key, c in embedding_knn(emb).items():
            cands.setdefault(key, {"knn_cos": None, "shared4": 0})["emb_knn"] = c
    keys = sorted(cands)
    cos_t = cosine_rows(X, keys)
    cos_e = (np.einsum("ij,ij->i", emb[[k[0] for k in keys]], emb[[k[1] for k in keys]])
             if emb is not None else [None] * len(keys))
    sh = [shingles(d.match) for d in M]
    rows = []
    for (i, j), ct, ce in zip(keys, cos_t, cos_e):
        a, b = M[i], M[j]
        f = pair_features(a, b, sh[i], sh[j], ct, ce)
        ch = cands[(i, j)]
        rows.append({"pid": f"{a.id}|{b.id}", "a": a.id, "b": b.id, **f, "score": round(score(f), 4),
                     "via": "".join(c for c, on in (("t", ch.get("knn_cos")), ("w", ch.get("word_knn")), ("r", ch.get("shared4")),
                                                    ("e", ch.get("emb_knn"))) if on)})
    # Embedding-only neighbours are mostly same-topic noise (449 of 72k were same-FAB in
    # the first run); keep those that also share some vocabulary.
    rows = [r for r in rows if r["via"] != "e" or r["cos_tfidf"] >= EMB_ONLY_MIN_TFIDF]
    _write_jsonl(M1 / "pairs.jsonl", rows)
    print(f"pairs: {len(rows)} candidate pairs over {len(M)} matchable docs; "
          f"via {Counter(r['via'] for r in rows).most_common()}")


# ---------------------------------------------------------------- gold

BANDS = [(0.0, 0.3), (0.3, 0.45), (0.45, 0.6), (0.6, 0.75), (0.75, 0.9), (0.9, 1.01)]


def stage_gold_sample(per_band: int = 50, hard_negatives: int = 50, seed: int = 7) -> None:
    rng = random.Random(seed)
    pairs = read_jsonl(M1 / "pairs.jsonl")
    gold = []
    for lo, hi in BANDS:
        band = [p for p in pairs if lo <= p["score"] < hi]
        # half cross-book, half within-book where possible
        cross = [p for p in band if not p["same_book"]]
        within = [p for p in band if p["same_book"]]
        pick = rng.sample(cross, min(len(cross), per_band // 2))
        pick += rng.sample(within, min(len(within), per_band - len(pick)))
        gold += [{**p, "stratum": f"{lo:.2f}-{hi:.2f}"} for p in pick]
    # Hard negatives: same chapter, not a candidate pair, moderately similar vocabulary.
    docs = {d.id: d for d in matchable(load_docs(BOOKS))}
    have = {p["pid"] for p in pairs}
    by_ch = {}
    for d in docs.values():
        by_ch.setdefault((d.book, d.chapter), []).append(d)
    pool = [g for g in by_ch.values() if len(g) > 5]
    hn = 0
    while hn < hard_negatives:
        g = rng.choice(pool)
        a, b = rng.sample(g, 2)
        a, b = sorted((a, b), key=lambda d: (d.book != "bukhari", d.seq))
        pid = f"{a.id}|{b.id}"
        if pid in have:
            continue
        f = pair_features(a, b, shingles(a.match), shingles(b.match), 0.0, None)
        if f["jac"] < 0.12:
            continue
        gold.append({"pid": pid, "a": a.id, "b": b.id, **f, "score": round(score(f), 4),
                     "via": "", "stratum": "hard_negative"})
        have.add(pid)
        hn += 1
    _write_jsonl(M1 / "gold.jsonl", gold)
    print(f"gold: {len(gold)} pairs; {Counter(g['stratum'] for g in gold)}")


def _prompt_pairs(rows: list[dict]) -> list[dict]:
    docs = {d.id: d for d in load_docs(BOOKS)}
    return [{"pid": r["pid"], "a_text": docs[r["a"]].matn or docs[r["a"]].text,
             "b_text": docs[r["b"]].matn or docs[r["b"]].text} for r in rows]


def stage_gold_label(cap_usd: float = 6.0) -> None:
    llm.require_key()
    gold = read_jsonl(M1 / "gold.jsonl")
    pp = _prompt_pairs(gold)
    for field, model, effort, per in (("sonnet", llm.SONNET, "high", 5),
                                      ("haiku", llm.HAIKU, "low", 25),
                                      ("haiku_med", llm.HAIKU, "medium", 25)):
        todo = [p for p, g in zip(pp, gold) if field not in g]
        if not todo:
            continue
        got = llm.classify_live(todo, model, effort, stage=f"gold-{field}", cap_usd=cap_usd, per_request=per)
        for g in gold:
            if g["pid"] in got:
                g[field] = got[g["pid"]]
        _write_jsonl(M1 / "gold.jsonl", gold)
        print(f"gold-label {field}: {len(got)}/{len(todo)} labelled, spend so far ${llm.spent():.3f}")


# ---------------------------------------------------------------- calibrate

def is_merge(label: str | None) -> bool:
    return label in MERGE


def auto_label(p: dict, th: dict) -> str | None:
    """Confident lexical decisions; None = send to the LLM."""
    if p["jac"] >= th["same_jac"] and p["len_ratio"] >= th["same_len"]:
        return "same"
    if p["cont"] >= th["part_cont"] and p["len_ratio"] < th["same_len"]:
        return "partial"
    if p["score"] < th["diff_score"]:
        return "different"
    return None


def _wilson(k: int, n: int, z: float = 1.96) -> tuple[float, float]:
    if n == 0:
        return (0.0, 1.0)
    ph = k / n
    d = 1 + z * z / n
    c = ph + z * z / (2 * n)
    r = z * ((ph * (1 - ph) + z * z / (4 * n)) / n) ** 0.5
    return ((c - r) / d, (c + r) / d)


def stage_calibrate() -> None:
    gold = [g for g in read_jsonl(M1 / "gold.jsonl") if "sonnet" in g]
    truth = {g["pid"]: is_merge(g["sonnet"]["label"]) for g in gold}
    best = None
    # Smallest auto-merge thresholds whose auto-merges are all correct on gold, and the
    # largest auto-different threshold that drops at most 1 gold merge.
    for sj in np.arange(0.40, 0.95, 0.025):
        for pc in np.arange(0.60, 0.99, 0.025):
            for sl in (0.5, 0.6, 0.7):
                th = {"same_jac": round(float(sj), 3), "part_cont": round(float(pc), 3),
                      "same_len": sl, "diff_score": 0.0}
                auto_m = [g for g in gold if auto_label(g, th) in ("same", "partial")]
                if any(not truth[g["pid"]] for g in auto_m):
                    continue
                if best is None or len(auto_m) > best[0]:
                    best = (len(auto_m), th)
    th = best[1]
    for ds in np.arange(0.05, 0.6, 0.01):
        lost = [g for g in gold if g["score"] < ds and truth[g["pid"]]]
        if len(lost) > 1:
            break
        th["diff_score"] = round(float(ds), 3)
    # Pick the Haiku setting and the escalation cut-off on the middle band.
    mid = [g for g in gold if auto_label(g, th) is None]
    report = {"thresholds": th, "gold": len(gold), "middle": len(mid), "haiku": {}}
    for field in ("haiku", "haiku_med"):
        rows = [g for g in mid if field in g]
        for cmin in (0.0, 0.6, 0.7, 0.8, 0.9):
            kept = [g for g in rows if g[field]["confidence"] >= cmin]
            esc = len(rows) - len(kept)
            pred_m = [g for g in kept if is_merge(g[field]["label"])]
            tp = sum(truth[g["pid"]] for g in pred_m)
            pos = sum(truth[g["pid"]] for g in kept)
            agree = sum(is_merge(g[field]["label"]) == truth[g["pid"]] for g in kept)
            report["haiku"][f"{field}@{cmin}"] = {
                "kept": len(kept), "escalated": esc, "merge_precision": round(tp / max(1, len(pred_m)), 4),
                "merge_recall": round(tp / max(1, pos), 4), "agreement": round(agree / max(1, len(kept)), 4)}
    # Choice: the cheapest Haiku setting whose kept answers reach the merge-precision
    # target with the fewest escalations; Sonnet answers the escalated rest.
    ok = [(v["escalated"], k) for k, v in report["haiku"].items()
          if v["merge_precision"] >= 0.97 and v["merge_recall"] >= 0.85]
    if ok:
        k = min(ok)[1]
        field, c = k.split("@")
        report["choice"] = {"haiku_effort": "low" if field == "haiku" else "medium",
                            "escalate_below": float(c), "basis": k}
    else:
        report["choice"] = {"haiku_effort": "medium", "escalate_below": 1.01,
                            "basis": "no Haiku setting met the target: escalate everything"}
    (M1 / "thresholds.json").write_text(json.dumps(report, indent=1) + "\n")
    print(json.dumps(report, indent=1))


# ---------------------------------------------------------------- label

def stage_label(cap_usd: float = 15.0) -> None:
    """Auto-decide confident pairs; Sonnet (high effort, anchor-grouped, Batch API) for the
    middle band. Haiku was measured on gold and not used (merge precision 0.89 vs the
    Opus reference; see docs/reports/m1-eval.md). Resumable via labels.jsonl + batches.json."""
    llm.require_key()
    th = json.loads((M1 / "thresholds.json").read_text())["thresholds"]
    pairs = read_jsonl(M1 / "pairs.jsonl")
    out_path = M1 / "labels.jsonl"
    done = {r["pid"]: r for r in read_jsonl(out_path)} if out_path.exists() else {}
    words = {d.id: d.words for d in load_docs(BOOKS)}

    for p in pairs:
        if p["pid"] in done:
            continue
        lab = auto_label(p, th)
        if lab == "partial":
            lab = "a_in_b" if words[p["a"]] <= words[p["b"]] else "b_in_a"
        if lab:
            done[p["pid"]] = {"pid": p["pid"], "a": p["a"], "b": p["b"], "label": lab,
                              "source": "auto", "confidence": None}
    _write_jsonl(out_path, done.values())

    mid = [p for p in pairs if p["pid"] not in done]
    print(f"label: {len(done)} auto, {len(mid)} to Sonnet")
    if mid:
        pending = [r for r in (json.loads(llm.BATCHES.read_text()) if llm.BATCHES.exists() else [])
                   if r["stage"] == "label-sonnet" and not r["collected"]]
        if pending:
            bid = pending[-1]["id"]
            print(f"resuming batch {bid}")
        else:
            if llm.spent() > cap_usd:
                raise SystemExit("spend cap reached")
            pp = _prompt_pairs(mid)
            for q, p in zip(pp, mid):
                q["a"], q["b"] = p["a"], p["b"]
            groups = llm.group_pairs(pp)
            bid = llm.submit_group_batch(groups, llm.SONNET, "high", stage="label-sonnet")
            print(f"submitted {len(groups)} requests as batch {bid}; waiting")
        got, failed = llm.collect_group_batch(bid)
        for p in mid:
            if p["pid"] in got:
                g = got[p["pid"]]
                done[p["pid"]] = {"pid": p["pid"], "a": p["a"], "b": p["b"], "label": g["label"],
                                  "source": "sonnet", "confidence": g["confidence"]}
        _write_jsonl(out_path, done.values())
        print(f"Sonnet: {len(got)} labelled, {len(failed)} failed requests")
    missing = [p for p in pairs if p["pid"] not in done]
    if missing:
        print(f"{len(missing)} pairs unanswered; rerun to retry them live")
        if len(missing) <= 600:
            pp = _prompt_pairs(missing)
            for q, p in zip(pp, missing):
                q["a"], q["b"] = p["a"], p["b"]
            got = llm.classify_groups_live(llm.group_pairs(pp), llm.SONNET, "high",
                                           stage="label-sonnet-retry", cap_usd=cap_usd)
            for p in missing:
                if p["pid"] in got:
                    done[p["pid"]] = {"pid": p["pid"], "a": p["a"], "b": p["b"], **got[p["pid"]],
                                      "source": "sonnet"}
            _write_jsonl(out_path, done.values())
    print(f"labels: {Counter((r['source'], r['label']) for r in done.values()).most_common()}; "
          f"total spend ${llm.spent():.2f}")


# ---------------------------------------------------------------- cluster + assemble

def stage_cluster() -> None:
    from .cluster import BOOK_ORDER, assemble, build_graph, guard

    docs = {d.id: d for d in load_docs(BOOKS)}
    edges = read_jsonl(M1 / "edges_free.jsonl")
    for r in read_jsonl(M1 / "labels.jsonl"):
        if r["label"] in MERGE:
            edges.append({**r, "source": r["source"]})
    g = build_graph(docs, edges)
    clusters, review = guard(g, docs)
    order = {b: k for k, b in enumerate(BOOK_ORDER)}
    hadith = [assemble(c, docs, g) for c in clusters]
    # Provisional IDs: by stars (desc), then first appearance in canonical book order.
    def first(h):
        m = h["members"][0]
        return (order[m["book"]], docs[m["id"]].seq)
    hadith.sort(key=lambda h: (-h["stars"], -len(h["books_full"]), first(h)))
    for k, h in enumerate(hadith, 1):
        h["id"] = f"U6-{k:05d}"
    # "See also": low-confidence no-merge calls between different hadith (possible duplicates
    # a researcher may want to check), shown in the appendix.
    where = {m["id"]: h["id"] for h in hadith for m in h["members"]}
    see = {}
    for r in read_jsonl(M1 / "labels.jsonl"):
        if r["source"] == "sonnet" and r["label"] in ("related", "different") \
                and (r["confidence"] or 0) < 0.7 and r["a"] in where and r["b"] in where:
            ha, hb = where[r["a"]], where[r["b"]]
            if ha != hb:
                see.setdefault(ha, set()).add(hb)
                see.setdefault(hb, set()).add(ha)
    for h in hadith:
        h["see_also"] = sorted(see.get(h["id"], ()))
    _write_jsonl(M1 / "hadith.jsonl", ({"id": h.pop("id"), **h} for h in hadith))
    _write_jsonl(M1 / "review_chaining.jsonl", review)

    seen = Counter(m["id"] for h in hadith for m in h["members"])
    assert all(v == 1 for v in seen.values()) and len(seen) == len(docs), "narration in 0 or 2+ hadith"
    per_book = {b: sum(1 for h in hadith if any(m["book"] == b for m in h["members"])) for b in BOOKS}
    stats = {
        "narrations": len(docs), "hadith": len(hadith),
        "unique_per_book": per_book,
        "in_both": sum(1 for h in hadith if h["badge"] == "muttafaq"),
        "stars": Counter(h["stars_display"] for h in hadith).most_common(),
        "chaining_splits": len(review),
        "uncertain_grouping": sum(1 for h in hadith if h["uncertain"]),
        "with_see_also": sum(1 for h in hadith if h["see_also"]),
        "largest_cluster": max(len(h["members"]) for h in hadith),
    }
    (M1 / "cluster_stats.json").write_text(json.dumps(stats, indent=1, ensure_ascii=False) + "\n")
    print(json.dumps(stats, indent=1, ensure_ascii=False))


# ---------------------------------------------------------------- gold adjudication

AMBIGUOUS_BELOW = 0.7


def system_label(g: dict, th: dict) -> str:
    return auto_label(g, th) or g.get("sonnet_grouped", g["sonnet"])["label"]


def stage_gold_adjudicate(cap_usd: float = 3.0) -> None:
    """The owner cannot read Arabic, so disputed gold pairs (Opus vs Sonnet vs pipeline
    disagree on merge/no-merge) are re-judged by Opus at xhigh effort, one pair per
    request. Final truth: consensus where all agree; otherwise the adjudication, or
    "ambiguous" when the adjudicator's confidence is below AMBIGUOUS_BELOW."""
    llm.require_key()
    th = json.loads((M1 / "thresholds.json").read_text())["thresholds"]
    gold = read_jsonl(M1 / "gold.jsonl")
    disputed = [g for g in gold if len({is_merge(g["opus"]["label"]), is_merge(g["sonnet"]["label"]),
                                        is_merge(system_label(g, th))}) > 1]
    todo = [g for g in disputed if "adjudicated" not in g]
    if todo:
        got = llm.classify_live(_prompt_pairs(todo), llm.OPUS, "xhigh", stage="gold-adjudicate",
                                cap_usd=cap_usd, per_request=1)
        for g in gold:
            if g["pid"] in got:
                g["adjudicated"] = got[g["pid"]]
    for g in gold:
        if g in disputed and "adjudicated" in g:
            a = g["adjudicated"]
            g["truth"] = "ambiguous" if a["confidence"] < AMBIGUOUS_BELOW else a["label"]
        elif g not in disputed:
            g["truth"] = g["opus"]["label"]
    _write_jsonl(M1 / "gold.jsonl", gold)
    print(f"disputed {len(disputed)}; truth: {Counter(g.get('truth') for g in disputed)}; spend ${llm.spent():.2f}")


# ---------------------------------------------------------------- evaluation report

def _ev(rows: list[dict], pred) -> dict:
    pm = [g for g in rows if is_merge(pred(g))]
    tp = sum(is_merge(g["truth"]) for g in pm)
    pos = sum(is_merge(g["truth"]) for g in rows)
    lo, hi = _wilson(tp, len(pm))
    return {"tp": tp, "pred": len(pm), "pos": pos, "p": tp / max(1, len(pm)), "r": tp / max(1, pos),
            "lo": lo, "hi": hi}


def stage_evaluate() -> None:
    th = json.loads((M1 / "thresholds.json").read_text())["thresholds"]
    gold = read_jsonl(M1 / "gold.jsonl")
    clear = [g for g in gold if g.get("truth") and g["truth"] != "ambiguous"]
    mid = [g for g in clear if not auto_label(g, th)]
    norm = lambda l: "a_in_b" if l == "partial" else l
    rows = [("Full pipeline (rules + Sonnet high, grouped)", _ev(clear, lambda g: norm(system_label(g, th)))),
            ("Confident lexical rules only", _ev([g for g in clear if auto_label(g, th)],
                                                 lambda g: norm(auto_label(g, th)) if auto_label(g, th) != "different" else "different"))]
    for f, name in (("sonnet_grouped", "Sonnet high, grouped (production format)"), ("sonnet", "Sonnet high, pairwise"),
                    ("sonnet_medium", "Sonnet medium"), ("sonnet_low", "Sonnet low"),
                    ("haiku_med", "Haiku medium"), ("haiku", "Haiku low")):
        rows.append((f"Middle band: {name}", _ev([g for g in mid if f in g], lambda g, f=f: g[f]["label"])))
    spend = Counter()
    for r in read_jsonl(llm.SPEND_LOG):
        spend[r["stage"]] += r["usd"]
    stats = json.loads((M1 / "cluster_stats.json").read_text()) if (M1 / "cluster_stats.json").exists() else None
    L = ["# M1 evaluation: Bukhari + Muslim", "",
         "Generated by `python -m u6 m1 evaluate`.", "",
         "## Gold set", "",
         f"{len(gold)} pairs: 50 per lexical-score band (six bands, half cross-book) plus 50 same-chapter "
         "hard negatives. Labelled by Opus 5.5 (high effort, reference), Sonnet 5.5 and Haiku 5.5 at several "
         "efforts. Where Opus, Sonnet and the pipeline disagreed on merge vs no-merge "
         f"({sum(1 for g in gold if 'adjudicated' in g)} pairs), Opus re-judged the pair alone at xhigh effort; "
         f"adjudications below {AMBIGUOUS_BELOW} confidence count as **ambiguous** "
         f"({len(gold) - len(clear)} pairs) and are left out of the scores below. "
         "The owner does not read Arabic, so no human verified these labels: they are model consensus "
         "plus model adjudication, and agreement-based gold can share the models' blind spots.", "",
         "## Merge precision and recall (unit: pair)", "",
         "| decision path | precision | 95% CI | recall |", "|---|---:|---:|---:|"]
    for name, e in rows:
        L.append(f"| {name} | {e['p']:.1%} ({e['tp']}/{e['pred']}) | {e['lo']:.1%}–{e['hi']:.1%} | {e['r']:.1%} ({e['tp']}/{e['pos']}) |")
    L += ["", f"**Quality gate (≥ 97 % precision on merges): "
          f"{'PASSED' if rows[0][1]['p'] >= 0.97 else 'NOT PASSED'}** on the full pipeline.", "",
          "Lexical thresholds (calibrated on gold): " + ", ".join(f"`{k}={v}`" for k, v in th.items()) + ".", "",
          "Haiku was dropped from pair labelling: its merge precision is below the gate at every effort. "
          "Sonnet below high effort also falls under the gate.", ""]
    if stats:
        L += ["## Clusters", "", "```json", json.dumps(stats, indent=1, ensure_ascii=False), "```", ""]
    L += ["## Spend (USD)", "", "| stage | $ |", "|---|---:|"]
    L += [f"| {k} | {v:.2f} |" for k, v in sorted(spend.items())] + [f"| **total** | **{sum(spend.values()):.2f}** |", ""]
    (ROOT / "docs" / "reports" / "m1-eval.md").write_text("\n".join(L))
    print("\n".join(L))
