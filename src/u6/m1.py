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
