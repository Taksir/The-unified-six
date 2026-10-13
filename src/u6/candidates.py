"""Free edges (back-references, exact duplicates) and candidate pairs for matching.

Three lexical channels, all cheap and download-free:
  * TF-IDF over char 3-5-grams, cosine kNN  -> near-verbatim matches
  * TF-IDF over (prefix-stemmed) words, kNN -> paraphrased re-tellings
  * shared rare word 4-grams                -> fragments contained in longer texts
An optional embedding channel is added in `embed.py` if recall needs it.
"""

import hashlib
from collections import defaultdict

import numpy as np

from .corpus import Doc

MIN_WORDS = 4  # texts shorter than this carry too little to match on


def backref_edges(docs: list[Doc]) -> list[dict]:
    """`ref`/`ref_variant` -> the nearest preceding non-ref narration, same book+chapter."""
    edges, last_anchor = [], {}
    for d in docs:  # docs are in source order per book
        key = (d.book, d.chapter)
        if d.kind in ("ref", "ref_variant"):
            prev = last_anchor.get(key)
            if prev:
                edges.append({"a": prev, "b": d.id, "label": "same" if d.kind == "ref" else "variant",
                              "source": "backref"})
        else:
            last_anchor[key] = d.id
    return edges


def exact_edges(docs: list[Doc]) -> list[dict]:
    groups = defaultdict(list)
    for d in docs:
        if d.kind == "full" and d.words >= MIN_WORDS:
            groups[hashlib.sha1(d.match.encode()).hexdigest()].append(d.id)
    edges = []
    for ids in groups.values():
        for other in ids[1:]:
            edges.append({"a": ids[0], "b": other, "label": "same", "source": "exact"})
    return edges


def matchable(docs: list[Doc]) -> list[Doc]:
    """Docs that take part in similarity matching (back-references join via backref only)."""
    return [d for d in docs if d.kind == "full" and d.words >= MIN_WORDS]


def tfidf_knn(docs: list[Doc], k: int = 10, min_cos: float = 0.25, analyzer: str = "char_wb"):
    """analyzer "char_wb": char 3-5-grams (near-verbatim); "word": word 1-2-grams with
    5-char prefix stemming (paraphrased re-tellings sharing content words)."""
    from sklearn.feature_extraction.text import TfidfVectorizer
    from sklearn.neighbors import NearestNeighbors

    if analyzer == "word":
        vec = TfidfVectorizer(analyzer="word", ngram_range=(1, 2), min_df=2, max_df=0.05,
                              sublinear_tf=True, preprocessor=lambda t: " ".join(w[:5] for w in t.split()))
    else:
        vec = TfidfVectorizer(analyzer="char_wb", ngram_range=(3, 5), min_df=2, sublinear_tf=True)
    X = vec.fit_transform([d.match for d in docs])
    nn = NearestNeighbors(n_neighbors=min(k + 1, len(docs)), metric="cosine").fit(X)
    dist, idx = nn.kneighbors(X)
    pairs = {}
    for i in range(len(docs)):
        for dd, j in zip(dist[i], idx[i]):
            if j == i or 1 - dd < min_cos:
                continue
            key = (min(i, j), max(i, j))
            pairs[key] = max(pairs.get(key, 0.0), 1 - float(dd))
    return pairs, X


def rare_ngram_pairs(docs: list[Doc], n: int = 4, max_df: int = 25, min_shared: int = 2):
    """Pairs sharing >= min_shared word n-grams that occur in at most max_df docs."""
    post = defaultdict(set)
    for i, d in enumerate(docs):
        w = d.match.split()
        for g in {" ".join(w[p:p + n]) for p in range(len(w) - n + 1)}:
            post[g].add(i)
    shared = defaultdict(int)
    for ids in post.values():
        if 1 < len(ids) <= max_df:
            ids = sorted(ids)
            for x in range(len(ids)):
                for y in range(x + 1, len(ids)):
                    shared[(ids[x], ids[y])] += 1
    return {k: v for k, v in shared.items() if v >= min_shared}


def candidate_pairs(docs: list[Doc], k: int = 10):
    """Union of both channels -> {(i, j): {"cos": float|None, "shared4": int}}, plus the TF-IDF matrix."""
    knn, X = tfidf_knn(docs, k)
    wknn, _ = tfidf_knn(docs, 15, min_cos=0.2, analyzer="word")
    rare = rare_ngram_pairs(docs)
    out = {}
    for key in set(knn) | set(rare) | set(wknn):
        out[key] = {"knn_cos": knn.get(key), "shared4": rare.get(key, 0), "word_knn": wknn.get(key)}
    return out, X


def cosine_rows(X, pairs) -> np.ndarray:
    """Exact TF-IDF cosine for each (i, j) (rows of X are L2-normalized)."""
    i = np.fromiter((p[0] for p in pairs), dtype=np.int64)
    j = np.fromiter((p[1] for p in pairs), dtype=np.int64)
    return np.asarray(X[i].multiply(X[j]).sum(axis=1)).ravel()
