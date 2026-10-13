"""Sentence embeddings for the third candidate channel (paraphrased re-tellings).

Model: intfloat/multilingual-e5-large via fastembed (ONNX runtime, CPU). Vectors are
cached in data/cache/ (not committed) keyed by model + a hash of the input texts.
"""

import hashlib
from pathlib import Path

import numpy as np

from .corpus import DATA, Doc

MODEL = "intfloat/multilingual-e5-large"
MAX_WORDS = 120


def embed(docs: list[Doc], batch_size: int = 16) -> np.ndarray:
    # e5 wants a "query: " prefix for symmetric similarity. The first 120 words carry the
    # gist (90 % of matns are shorter than 84 words) and keep CPU encoding tractable.
    texts = ["query: " + " ".join(d.match.split()[:MAX_WORDS]) for d in docs]
    key = hashlib.sha1(("\n".join(texts) + MODEL).encode()).hexdigest()[:16]
    cache = DATA / "cache" / f"emb-{key}.npy"
    if cache.exists():
        return np.load(cache).astype(np.float32)
    from fastembed import TextEmbedding
    model = TextEmbedding(MODEL, cache_dir=str(DATA / "cache" / "models"))
    # Encode in length order so each batch pads to similar lengths, then restore order.
    order = sorted(range(len(texts)), key=lambda i: len(texts[i]))
    enc = list(model.embed([texts[i] for i in order], batch_size=batch_size))
    vecs = np.zeros((len(texts), len(enc[0])), dtype=np.float32)
    for k, i in enumerate(order):
        vecs[i] = enc[k]
    vecs /= np.linalg.norm(vecs, axis=1, keepdims=True)
    cache.parent.mkdir(parents=True, exist_ok=True)
    np.save(cache, vecs.astype(np.float16))
    return vecs


def embedding_knn(vecs: np.ndarray, k: int = 10, min_cos: float = 0.85) -> dict:
    """Exact cosine kNN (13k x 13k fits in memory in blocks)."""
    pairs = {}
    for s in range(0, len(vecs), 2048):
        sims = vecs[s:s + 2048] @ vecs.T
        for r in range(sims.shape[0]):
            i = s + r
            sims[r, i] = -1
            top = np.argpartition(-sims[r], k)[:k]
            for j in top:
                c = float(sims[r, j])
                if c >= min_cos:
                    key = (min(i, int(j)), max(i, int(j)))
                    pairs[key] = max(pairs.get(key, 0.0), c)
    return pairs
