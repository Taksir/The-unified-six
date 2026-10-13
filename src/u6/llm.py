"""LLM pair classification: live calls (small jobs) and the Message Batches API (bulk).

Every call's token usage is priced and appended to data/m1/spend.jsonl; a stage stops
before submitting work that would push its spend past its cap. Batch IDs are recorded in
data/batches.json so a later session can collect results if this one dies.
"""

import json
import os
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from .corpus import DATA
from .textnorm import letters

HAIKU = "claude-haiku-5-5"
SONNET = "claude-sonnet-5-5"
OPUS = "claude-opus-5-5"   # gold-set reference annotator only
PRICES = {HAIKU: (0.10, 0.50), SONNET: (2.00, 10.00), OPUS: (4.00, 20.00)}  # $ per MTok in/out
SPEND_LOG = DATA / "m1" / "spend.jsonl"
BATCHES = DATA / "batches.json"
MAX_WORDS = 150  # M1 ran with 400; M2/M3 cut it for cost (re-validated on gold)

LABELS = ["same", "a_in_b", "b_in_a", "related", "different"]

SYSTEM = """You are a hadith scholar's assistant. You compare pairs of Arabic hadith texts \
(the matn only; chains of narrators have been removed, but a few chain words may remain at \
the start, and "قال رسول الله ﷺ"-type openings may be missing). The goal is to merge \
duplicates across and within the six canonical books without ever merging two distinct hadith.

For each pair (A, B) choose exactly one label:
- same: both report the same Prophetic statement, action, or event. Differences in wording, \
word order, framing, the Companion who narrates it, or a small extra phrase are fine.
- a_in_b: everything A reports is also in B, and B adds substantial further content (another \
sentence of the statement, another part of the story) that A lacks. A is a fragment of B.
- b_in_a: the reverse: B is a fragment of A.
- related: same topic or same occasion, but the core content differs materially: a different \
ruling or statement, a different incident, a statement with a different meaning, or a \
Companion's own opinion versus a Prophetic statement. Related texts must NOT be merged.
- different: unrelated content.

Rules:
- A wrong merge hides a hadith from readers; a missed merge only leaves a duplicate. When torn \
between same/a_in_b/b_in_a and related, choose related.
- Two texts that share a common clause but each add a different main statement are related, \
not fragments.
- Judge the meaning, not surface overlap. Formulaic phrases (oaths, "يا رسول الله") do not make \
texts the same.
- confidence is your probability (0 to 1) that the label is correct."""

SCHEMA = {
    "type": "object",
    "properties": {
        "results": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "pair": {"type": "string"},
                    "label": {"type": "string", "enum": LABELS},
                    "confidence": {"type": "number"},
                },
                "required": ["pair", "label", "confidence"],
                "additionalProperties": False,
            },
        }
    },
    "required": ["results"],
    "additionalProperties": False,
}


def _client():
    import anthropic
    return anthropic.Anthropic(max_retries=6)


def show(matn: str) -> str:
    """Diacritic-free text for the prompt (tashkeel roughly doubles the token count)."""
    w = letters(matn).split()
    return " ".join(w[:MAX_WORDS]) + (" …[مقطوع]" if len(w) > MAX_WORDS else "")


def build_prompt(pairs: list[dict]) -> str:
    """pairs: [{"pid", "a_text", "b_text"}]"""
    parts = ["Classify each pair. Return one result per pair, using its pair id.\n"]
    for p in pairs:
        parts.append(f"<pair id=\"{p['pid']}\">\n<A>{show(p['a_text'])}</A>\n<B>{show(p['b_text'])}</B>\n</pair>")
    return "\n".join(parts)


def request_params(model: str, pairs: list[dict], effort: str) -> dict:
    return {
        "model": model,
        "max_tokens": 4000 + 120 * len(pairs),
        "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
        "messages": [{"role": "user", "content": build_prompt(pairs)}],
    }


def cost(model: str, usage, batch: bool) -> float:
    pin, pout = PRICES[model]
    tin = (usage.input_tokens + (usage.cache_creation_input_tokens or 0) * 1.25
           + (usage.cache_read_input_tokens or 0) * 0.1)
    c = (tin * pin + usage.output_tokens * pout) / 1e6
    return c * (0.5 if batch else 1.0)


def log_spend(stage: str, model: str, usd: float, n_requests: int) -> None:
    SPEND_LOG.parent.mkdir(parents=True, exist_ok=True)
    with SPEND_LOG.open("a") as f:
        f.write(json.dumps({"t": time.strftime("%Y-%m-%dT%H:%M:%S"), "stage": stage, "model": model,
                            "usd": round(usd, 5), "requests": n_requests}) + "\n")


def spent(stage: str | None = None) -> float:
    if not SPEND_LOG.exists():
        return 0.0
    rows = [json.loads(l) for l in SPEND_LOG.open()]
    return sum(r["usd"] for r in rows if stage is None or r["stage"] == stage)


def _parse(msg) -> dict:
    if msg.stop_reason == "refusal":
        return {}
    text = next((b.text for b in msg.content if b.type == "text"), "")
    try:
        return {r["pair"]: r for r in json.loads(text)["results"]}
    except (json.JSONDecodeError, KeyError, TypeError):
        return {}


def classify_live(pairs: list[dict], model: str, effort: str, stage: str, cap_usd: float,
                  per_request: int = 10, workers: int = 8) -> dict:
    """Synchronous concurrent calls. Returns {pid: {"label", "confidence"}}."""
    client = _client()
    chunks = [pairs[i:i + per_request] for i in range(0, len(pairs), per_request)]
    out, total = {}, 0.0

    def run(chunk):
        msg = client.messages.create(**request_params(model, chunk, effort))
        return chunk, msg

    with ThreadPoolExecutor(workers) as ex:
        for chunk, msg in ex.map(run, chunks):
            usd = cost(model, msg.usage, batch=False)
            total += usd
            got = _parse(msg)
            for p in chunk:
                if p["pid"] in got:
                    out[p["pid"]] = {"label": got[p["pid"]]["label"], "confidence": got[p["pid"]]["confidence"]}
            if spent(stage) + total > cap_usd:
                log_spend(stage, model, total, len(chunks))
                raise SystemExit(f"{stage}: spend cap ${cap_usd} reached")
    log_spend(stage, model, total, len(chunks))
    return out


def _record_batch(batch_id: str, stage: str, model: str, n: int) -> None:
    rows = json.loads(BATCHES.read_text()) if BATCHES.exists() else []
    rows.append({"id": batch_id, "stage": stage, "model": model, "requests": n,
                 "created": time.strftime("%Y-%m-%dT%H:%M:%S"), "collected": False})
    BATCHES.write_text(json.dumps(rows, indent=1) + "\n")


def submit_batch(pairs: list[dict], model: str, effort: str, stage: str, per_request: int = 25) -> str:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    chunks = [pairs[i:i + per_request] for i in range(0, len(pairs), per_request)]
    reqs = [Request(custom_id=f"{stage}-{k}", params=MessageCreateParamsNonStreaming(
        **request_params(model, c, effort))) for k, c in enumerate(chunks)]
    batch = _client().messages.batches.create(requests=reqs)
    _record_batch(batch.id, stage, model, len(reqs))
    manifest = DATA / "m1" / f"batch-{batch.id}.json"
    manifest.write_text(json.dumps({f"{stage}-{k}": [p["pid"] for p in c] for k, c in enumerate(chunks)}))
    return batch.id


def collect_batch(batch_id: str, poll: int = 30) -> tuple[dict, list[str]]:
    """Wait for a batch, price it, and return ({pid: label}, [failed custom_ids])."""
    client = _client()
    while (b := client.messages.batches.retrieve(batch_id)).processing_status != "ended":
        time.sleep(poll)
    rows = json.loads(BATCHES.read_text())
    meta = next(r for r in rows if r["id"] == batch_id)
    manifest = json.loads((DATA / "m1" / f"batch-{batch_id}.json").read_text())
    out, failed, usd = {}, [], 0.0
    for res in client.messages.batches.results(batch_id):
        if res.result.type != "succeeded":
            failed.append(res.custom_id)
            continue
        msg = res.result.message
        usd += cost(meta["model"], msg.usage, batch=True)
        got = _parse(msg)
        for pid in manifest[res.custom_id]:
            if pid in got:
                out[pid] = {"label": got[pid]["label"], "confidence": got[pid]["confidence"]}
    if not meta["collected"]:
        log_spend(meta["stage"], meta["model"], usd, meta["requests"])
        meta["collected"] = True
        BATCHES.write_text(json.dumps(rows, indent=1) + "\n")
    return out, failed


def require_key() -> None:
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise SystemExit("ANTHROPIC_API_KEY is not set")


# ---------------------------------------------------------------- anchor-grouped requests
# One anchor text compared with several candidates sends each text once per request
# instead of once per pair (~45 % fewer input tokens on the M1 middle band).

GROUP_NOTE = """Each <group> has one anchor text A and several candidates. Compare A with \
each candidate separately and label the pair (A, candidate) as above: a_in_b means A is a \
fragment of the candidate, b_in_a means the candidate is a fragment of A."""


def group_pairs(pairs: list[dict], max_per_group: int = 16) -> list[dict]:
    """pairs: [{"pid", "a", "b", "a_text", "b_text"}] -> groups
    [{"anchor", "anchor_text", "items": [{"pid", "other", "text", "swapped"}]}].
    Greedy cover: the narration with the most unassigned pairs becomes the next anchor,
    so each request carries as many pairs as possible (fewer requests, less overhead)."""
    import heapq
    from collections import defaultdict
    adj = defaultdict(dict)  # doc -> {other doc: pair}
    text = {}
    for p in pairs:
        adj[p["a"]][p["b"]] = p
        adj[p["b"]][p["a"]] = p
        text[p["a"]], text[p["b"]] = p["a_text"], p["b_text"]
    heap = [(-len(v), k) for k, v in adj.items()]
    heapq.heapify(heap)
    groups = []
    while heap:
        d, anchor = heapq.heappop(heap)
        if -d != len(adj[anchor]):
            if adj[anchor]:
                heapq.heappush(heap, (-len(adj[anchor]), anchor))
            continue
        if not adj[anchor]:
            continue
        items = []
        for other, p in sorted(adj[anchor].items()):
            items.append({"pid": p["pid"], "text": text[other], "swapped": p["a"] != anchor})
            del adj[other][anchor]
        adj[anchor] = {}
        for k in range(0, len(items), max_per_group):
            groups.append({"anchor": anchor, "anchor_text": text[anchor], "items": items[k:k + max_per_group]})
    return groups


def build_group_prompt(groups: list[dict]) -> str:
    parts = [GROUP_NOTE, "Return one result per candidate, using its pair id.\n"]
    for g in groups:
        parts.append(f"<group>\n<A>{show(g['anchor_text'])}</A>")
        for it in g["items"]:
            parts.append(f"<candidate pair=\"{it['pid']}\">{show(it['text'])}</candidate>")
        parts.append("</group>")
    return "\n".join(parts)


def group_request_params(model: str, groups: list[dict], effort: str) -> dict:
    n = sum(len(g["items"]) for g in groups)
    return {
        "model": model,
        "max_tokens": 6000 + 120 * n,
        "system": [{"type": "text", "text": SYSTEM, "cache_control": {"type": "ephemeral"}}],
        "output_config": {"effort": effort, "format": {"type": "json_schema", "schema": SCHEMA}},
        "messages": [{"role": "user", "content": build_group_prompt(groups)}],
    }


_FLIP = {"a_in_b": "b_in_a", "b_in_a": "a_in_b"}


def _orient(groups: list[dict], got: dict) -> dict:
    """Map anchor-relative labels back to each pair's own (a, b) orientation."""
    out = {}
    for g in groups:
        for it in g["items"]:
            r = got.get(it["pid"])
            if r:
                lab = _FLIP.get(r["label"], r["label"]) if it["swapped"] else r["label"]
                out[it["pid"]] = {"label": lab, "confidence": r["confidence"]}
    return out


def classify_groups_live(groups: list[dict], model: str, effort: str, stage: str, cap_usd: float,
                         workers: int = 8) -> dict:
    client = _client()
    total, merged = 0.0, {}

    def run(g):
        return g, client.messages.create(**group_request_params(model, [g], effort))

    with ThreadPoolExecutor(workers) as ex:
        for g, msg in ex.map(run, groups):
            total += cost(model, msg.usage, batch=False)
            merged.update(_orient([g], _parse(msg)))
            if spent(stage) + total > cap_usd:
                log_spend(stage, model, total, len(groups))
                raise SystemExit(f"{stage}: spend cap ${cap_usd} reached")
    log_spend(stage, model, total, len(groups))
    return merged


def submit_group_batch(groups: list[dict], model: str, effort: str, stage: str) -> str:
    from anthropic.types.message_create_params import MessageCreateParamsNonStreaming
    from anthropic.types.messages.batch_create_params import Request

    reqs = [Request(custom_id=f"{stage}-{k}", params=MessageCreateParamsNonStreaming(
        **group_request_params(model, [g], effort))) for k, g in enumerate(groups)]
    batch = _client().messages.batches.create(requests=reqs)
    _record_batch(batch.id, stage, model, len(reqs))
    # Manifest for resuming: ids and orientation only (texts are reproducible from data/).
    (DATA / "m1" / f"batch-{batch.id}.json").write_text(json.dumps(
        {f"{stage}-{k}": {"anchor": g["anchor"], "items": [{"pid": i["pid"], "swapped": i["swapped"]}
                                                          for i in g["items"]]}
         for k, g in enumerate(groups)}))
    return batch.id


def collect_group_batch(batch_id: str, poll: int = 60) -> tuple[dict, list[str]]:
    client = _client()
    while (b := client.messages.batches.retrieve(batch_id)).processing_status != "ended":
        time.sleep(poll)
    rows = json.loads(BATCHES.read_text())
    meta = next(r for r in rows if r["id"] == batch_id)
    manifest = json.loads((DATA / "m1" / f"batch-{batch_id}.json").read_text())
    out, failed, usd = {}, [], 0.0
    for res in client.messages.batches.results(batch_id):
        if res.result.type != "succeeded":
            failed.append(res.custom_id)
            continue
        msg = res.result.message
        usd += cost(meta["model"], msg.usage, batch=True)
        out.update(_orient([manifest[res.custom_id]], _parse(msg)))
    if not meta["collected"]:
        log_spend(meta["stage"], meta["model"], usd, meta["requests"])
        meta["collected"] = True
        BATCHES.write_text(json.dumps(rows, indent=1) + "\n")
    return out, failed
