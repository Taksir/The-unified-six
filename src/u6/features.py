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
    """One number for stratifying and ranking: the strongest similarity signal."""
    return max(f["jac"], f["cont"] * (0.5 + 0.5 * f["len_ratio"]) if f["cont"] else 0.0,
               f["cos_tfidf"], (f["cos_emb"] or 0.0) - 0.15)
