"""Group narrations into merged hadith and build each hadith's record.

Clustering = connected components over merge edges (back-references, exact duplicates,
same / fragment labels), followed by an anti-chaining guard: if one narration is the only
bridge between two groups whose texts are not similar to each other (typically a
narration that strings two hadith together), the groups are split apart and the case is
written to the review queue.
"""

import re
from collections import defaultdict

import networkx as nx

from .corpus import Doc
from .features import shingles
from .textnorm import normalize

BOOK_ORDER = ["bukhari", "muslim", "abudawud", "tirmidhi", "nasai", "ibnmajah"]
LETTER = {"bukhari": "B", "muslim": "M", "abudawud": "D", "tirmidhi": "T", "nasai": "N", "ibnmajah": "J"}
MERGE = {"same", "a_in_b", "b_in_a", "variant"}
UNCERTAIN_BELOW = 0.7
COMMUNITY_MIN = 8          # clusters above this size are checked for chaining
COMMUNITY_DENSITY = 0.5    # ... and split into communities when sparser than this  # LLM confidence under which a merge decision counts as uncertain


def _sim(a: Doc, b: Doc) -> float:
    sa, sb = shingles(a.match), shingles(b.match)
    if not sa or not sb:
        return 0.0
    return len(sa & sb) / min(len(sa), len(sb))


def build_graph(docs: dict[str, Doc], edges: list[dict]) -> nx.Graph:
    g = nx.Graph()
    g.add_nodes_from(docs)
    for e in edges:
        if e["label"] in MERGE and e["a"] in docs and e["b"] in docs:
            w = 1.0 if e.get("source") in ("backref", "exact") else max(0.05, float(e.get("score") or 0.5))
            g.add_edge(e["a"], e["b"], label=e["label"], source=e.get("source", ""),
                       confidence=e.get("confidence"), weight=w)
    return g


def guard(g: nx.Graph, docs: dict[str, Doc], bridge_sim: float = 0.35) -> tuple[list[set], list[dict]]:
    """Split chained components at articulation points that join dissimilar groups."""
    clusters, review = [], []
    stack = [set(c) for c in nx.connected_components(g)]
    while stack:
        comp = stack.pop()
        if len(comp) < 4:
            clusters.append(comp)
            continue
        sub = g.subgraph(comp)
        split_done = False
        for x in nx.articulation_points(sub):
            if docs[x].kind != "full":
                continue  # back-reference hubs are the compiler's own grouping
            rest = sub.copy()
            rest.remove_node(x)
            parts = [set(p) for p in nx.connected_components(rest)]
            big = [p for p in parts if len(p) >= 2]
            if len(big) < 2:
                continue
            # Are the parts about the same thing? Compare their best cross-pair.
            def best(p, q):
                ps = [d for d in p if docs[d].match][:30]
                qs = [d for d in q if docs[d].match][:30]
                return max((_sim(docs[a], docs[b]) for a in ps for b in qs), default=0.0)
            big.sort(key=len, reverse=True)
            if all(best(big[0], q) >= bridge_sim for q in big[1:]):
                continue
            # Keep x with the part it is most similar to; the others become separate.
            home = max(parts, key=lambda p: max((_sim(docs[x], docs[d]) for d in list(p)[:30]), default=0))
            review.append({"bridge": x, "parts": [sorted(p) for p in parts], "kept_with": sorted(home)[:3]})
            for p in parts:
                stack.append(p | {x} if p is home else p)
            split_done = True
            break
        if not split_done:
            clusters.append(comp)
    # Second pass: large clusters held together by many weak links (compound narrations
    # that bundle several hadith) are split into weighted communities. Dense families of
    # near-identical narrations keep high modularity and stay whole.
    out = []
    for comp in clusters:
        if len(comp) <= COMMUNITY_MIN:
            out.append(comp)
            continue
        sub = g.subgraph(comp)
        n = len(comp)
        density = sub.number_of_edges() / (n * (n - 1) / 2)
        if density >= COMMUNITY_DENSITY:
            out.append(comp)
            continue
        comms = nx.community.louvain_communities(sub, weight="weight", resolution=1.0, seed=1)
        if len(comms) == 1:
            out.append(comp)
            continue
        review.append({"community_split": sorted(comp)[:5], "size": n, "parts": [len(c) for c in comms]})
        out.extend(set(c) for c in comms)
    return out, review


def _clauses(matn: str) -> list[str]:
    """Split a matn (with tashkeel) into clauses at punctuation and quote marks, merging
    pieces shorter than 3 words into their neighbour."""
    raw = [c.strip() for c in re.split(r'(?<=[،,.؟?!:;؛"])\s+', matn) if c.strip()]
    out = []
    for c in raw:
        if out and len(normalize(c).split()) < 3:
            out[-1] += " " + c
        else:
            out.append(c)
    return out


def _present(clause_norm: str, member_norm: str, thresh: float = 0.5) -> bool:
    cs = shingles(clause_norm, 4)
    if not cs:
        return True
    return len(cs & shingles(member_norm, 4)) / len(cs) >= thresh


def assemble(cluster: set, docs: dict[str, Doc], g: nx.Graph) -> dict:
    members = [docs[i] for i in cluster]
    order = {b: k for k, b in enumerate(BOOK_ORDER)}
    texted = ([d for d in members if d.kind == "full" and d.match]
              or [d for d in members if d.kind != "ref" and d.match])
    # Representative: the fullest version; ties go to the earlier book (B before M).
    rep = max(texted or members, key=lambda d: (d.words, -order[d.book], -d.seq))
    rep_sh = shingles(rep.match)
    roles = {}
    for d in members:
        if d.id == rep.id:
            roles[d.id] = "full"
        elif d.kind == "ref":
            roles[d.id] = None  # inherits from its anchor below
        else:
            ms = shingles(d.match)
            cont_in_rep = len(ms & rep_sh) / max(1, len(ms))
            roles[d.id] = "partial" if d.words < 0.5 * rep.words and cont_in_rep >= 0.5 else "full"
    for d in members:
        if roles[d.id] is None:
            anchors = [n for n in g.neighbors(d.id) if n in roles and roles[n]] if d.id in g else []
            roles[d.id] = roles[anchors[0]] if anchors else "full"

    books = defaultdict(set)
    for d in members:
        books[d.book].add(roles[d.id])
    attest = {b: ("full" if "full" in r else "partial") for b, r in books.items()}
    full_books = [b for b in BOOK_ORDER if attest.get(b) == "full"]
    part_books = [b for b in BOOK_ORDER if attest.get(b) == "partial"]

    # Clause alignment against the other full versions (not fragments, not back-references).
    others = [d for d in members if d.id != rep.id and roles[d.id] == "full" and d.kind != "ref" and d.match]
    segs = []
    clauses = _clauses(rep.matn) if rep.matn else []
    if others and clauses:
        onorm = [(d.id, d.match) for d in others]
        for c in clauses:
            cn = normalize(c)
            inside = [i for i, m in onorm if _present(cn, m)]
            segs.append({"ar": c, "core": len(inside) == len(onorm), "in": [rep.id] + inside})
    elif clauses:
        segs = [{"ar": c, "core": True, "in": [rep.id]} for c in clauses]
    # Paraphrased versions share few clauses; italicising most of the text would mislead,
    # so alignment that finds under half the clauses shared falls back to no italics.
    if segs and sum(s["core"] for s in segs) < 0.5 * len(segs):
        for s in segs:
            s["core"] = True

    # Uncertain grouping: the cluster falls apart without its low-confidence merge edges.
    sub = g.subgraph(cluster)
    sure = nx.Graph()
    sure.add_nodes_from(cluster)
    sure.add_edges_from((u, v) for u, v, a in sub.edges(data=True)
                        if a.get("confidence") is None or a["confidence"] >= UNCERTAIN_BELOW)
    uncertain = len(cluster) > 1 and nx.number_connected_components(sure) > 1

    return {
        "uncertain": uncertain,
        "members": sorted(({"id": d.id, "book": d.book, "kind": d.kind, "role": roles[d.id]}
                           for d in members), key=lambda m: (order[m["book"]], docs[m["id"]].seq)),
        "representative": rep.id,
        "books_full": full_books,
        "books_partial": part_books,
        "stars": len(full_books) + len(part_books),
        "stars_display": "★" * len(full_books) + "⯪" * len(part_books),
        "badge": ("muttafaq" if {"bukhari", "muslim"} <= attest.keys()
                  else "sahih_one" if attest.keys() & {"bukhari", "muslim"} else None),
        "segments": segs,
        "isnad_last": sorted({d.isnad_last for d in members if d.isnad_last}),
        "chapter": {"book": rep.book, "chapter": rep.chapter},
    }


def containment_edges(docs: dict[str, Doc], edges: list[dict]) -> tuple[list[dict], list[dict]]:
    """Keep "same"-type edges; turn fragment edges into a forest so that a compound
    narration (one report bundling several hadith) never chains its parts together.

    Returns (edges to cluster on, compound notes). A fragment component attaches to
    exactly one container component: the most specific one (fewest words). A container
    that would receive two or more fragment components with no merge edge between them
    is a compound: it absorbs none of them."""
    same = [e for e in edges if e["label"] in ("same", "variant") and e["a"] in docs and e["b"] in docs]
    part = [e for e in edges if e["label"] in ("a_in_b", "b_in_a") and e["a"] in docs and e["b"] in docs]
    g = nx.Graph()
    g.add_nodes_from(docs)
    g.add_edges_from((e["a"], e["b"]) for e in same)
    comp_of = {}
    for k, c in enumerate(nx.connected_components(g)):
        for n in c:
            comp_of[n] = k
    size = defaultdict(int)
    for n, k in comp_of.items():
        size[k] = max(size[k], docs[n].words)
    best = {}  # child comp -> (container words, edge)
    for e in part:
        child, parent = (e["a"], e["b"]) if e["label"] == "a_in_b" else (e["b"], e["a"])
        cc, pc = comp_of[child], comp_of[parent]
        if cc == pc:
            continue
        key = (docs[parent].words, -(e.get("confidence") or 0))
        if cc not in best or key < best[cc][0]:
            best[cc] = (key, e, pc)
    children = defaultdict(list)
    for cc, (_, e, pc) in best.items():
        children[pc].append((cc, e))
    linked = {(comp_of[e["a"]], comp_of[e["b"]]) for e in part} | {(comp_of[e["b"]], comp_of[e["a"]]) for e in part}
    keep, notes = list(same), []
    for pc, kids in children.items():
        if len(kids) >= 2:
            ks = [k for k, _ in kids]
            related = all((x, y) in linked for i, x in enumerate(ks) for y in ks[i + 1:])
            if not related:
                notes.append({"compound_component": pc, "fragments": len(kids),
                              "pairs": [(e["a"], e["b"]) for _, e in kids]})
                continue
        keep.extend(e for _, e in kids)
    return keep, notes
