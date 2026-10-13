"""Pair features used by the auto-decision rules and for gold-set stratification."""

import numpy as np

from .corpus import Doc


def shingles(text: str, n: int = 5) -> set[str]:
    t = f" {text} "
    return {t[i:i + n] for i in range(max(1, len(t) - n + 1))}


def pair_features(a: Doc, b: Doc, sa: set, sb: set, cos_tfidf: float, cos_emb: float | None) -> dict:
    inter = len(sa & sb)
    wa, wb = a.words, b.words
    return {
        "jac": round(inter / max(1, len(sa | sb)), 4),
        "cont": round(inter / max(1, min(len(sa), len(sb))), 4),   # containment of the shorter
        "len_ratio": round(min(wa, wb) / max(1, max(wa, wb)), 4),
        "cos_tfidf": round(float(cos_tfidf), 4),
        "cos_emb": None if cos_emb is None else round(float(cos_emb), 4),
        "same_book": a.book == b.book,
        "same_fab": bool(a.fab_base and a.fab_base == b.fab_base),
        "same_narrator": bool(a.isnad_last and a.isnad_last == b.isnad_last),
        "same_chapter": a.book == b.book and a.chapter == b.chapter,
    }


def score(f: dict) -> float:
    """One lexical number for stratifying and ranking: the strongest overlap signal.
    (e5 cosines sit in a narrow 0.85-1.0 band, so embeddings stay a separate feature.)"""
    return max(f["jac"], f["cont"] * (0.5 + 0.5 * f["len_ratio"]) if f["cont"] else 0.0,
               f["cos_tfidf"])


# Formula words that make short reports look alike ("نهى رسول الله ﷺ عن ...").
FORMULA = set("""قال قالت قالوا يقول سمعت سمع عن ان انه انها كان رسول الله النبي نبي صلي عليه وسلم
نهي امر ينهي يامر لا ما من في علي الي او و ثم قد لقد اذا اذ هذا ذلك هو هي يا فقال فقالت
رضي عنه عنها""".split())


def _stem(w: str) -> str:
    for p in ("وال", "فال", "بال", "لل", "ال"):
        if w.startswith(p) and len(w) > len(p) + 2:
            w = w[len(p):]
            break
    if len(w) > 3 and w[0] in "وفب":
        w = w[1:]
    return w[:5]


def content_words(match: str) -> set[str]:
    return {_stem(w) for w in match.split() if w not in FORMULA and len(w) > 1}


def content_ok(a: str, b: str, min_jac: float = 0.34, min_cont: float = 0.6) -> bool:
    """Do two match texts share their *content*, not just a formula? Used to veto
    lexical-rule and Haiku merges of short formulaic reports."""
    ca, cb = content_words(a), content_words(b)
    if not ca or not cb:
        return a == b
    inter = len(ca & cb)
    return inter / len(ca | cb) >= min_jac or inter / min(len(ca), len(cb)) >= min_cont
