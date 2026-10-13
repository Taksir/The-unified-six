# Status

*Pickup file for any session. Update at the end of every stage.*

**Last updated:** 2026-10-13 · **Current milestone:** M1 done → M2 next (not started) · **Branch:** `claude/nifty-faraday-ptd4qw`

## Budget

**≈ $50 of API credit left, no refill.** M1 spent $49.50 (≈ $22 of it a cancelled batch
that was billed anyway). Every step projected above $5 needs the owner's go-ahead.
Spend log: `data/m1/spend.jsonl`. Batch IDs: `data/batches.json`.

## Done

- **Design v1** — `docs/PROPOSAL.md`; **data-source research** — `docs/research/data-sources.md`
- **M0 Data foundation** — all six books in one schema (34,532 records), isnad/matn split
  (89.8 % agreement with LK Bukhari gold), numbering concordance. `docs/reports/m0-*.md`
- **M1 MVP: Bukhari + Muslim**
  - 14,937 narrations → **5,541 merged hadith** (`data/m1/hadith.jsonl`); 1,961 in both books
  - Candidates: char/word TF-IDF + rare n-grams + e5-large embeddings (filtered) → 74,215 pairs
  - Labels: 30,293 by calibrated lexical rules, 43,922 by Sonnet 5.5 (high effort, grouped, Batch API)
  - **Quality gate passed:** 100 % merge precision on gold (187/187, 95 % CI 98.0–100 %),
    recall 93.5 %. Gold = Opus 5.5 labels + Opus adjudication of disputes (no human check;
    the owner does not read Arabic). `docs/reports/m1-eval.md`
  - Ambiguity tags: 554 hadith "≈ grouping uncertain"; 2,729 with "see also" links
  - **Sample PDFs** (format review): `samples/m1/m1-sample-edition-A.pdf` (by attestation),
    `samples/m1/m1-sample-edition-B.pdf` (by topic) — 27 pages each, EN + AR, 46 hadith.
    English is draft machine translation; topics from a provisional list.

## Next

**M2 — add Abu Dawud and Tirmidhi.** Brief with a costed, cheaper method: `docs/handoff/M2.md`.

## Owner decisions on record

- Star rule: ★ per book with the full text, ⯪ per book with only a fragment (main text too).
- Muslim's Muqaddima (almost empty upstream) is out of v1.
- No human gold review; Opus adjudicates. Hard cases get an "ambiguous" tag, not more spend.

## How to rebuild

```bash
pip install -e '.[dev]' anthropic datasketch scikit-learn networkx fastembed typst
python -m u6 fetch && python -m u6 ingest
python -m u6 m1 pairs            # needs huggingface.co + *.hf.co for the e5 model (~34 min CPU)
python -m u6 m1 gold-sample && python -m u6 m1 gold-label && python -m u6 m1 gold-adjudicate
python -m u6 m1 calibrate && python -m u6 m1 label    # label = Batch API spend (~$23)
python -m u6 m1 cluster && python -m u6 m1 sample && python -m u6 m1 evaluate
python -m pytest -q
```
LLM stages need `ANTHROPIC_API_KEY` in the environment (never commit it).
