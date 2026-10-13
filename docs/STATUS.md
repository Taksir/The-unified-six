# Status

*Pickup file for any session. Update at the end of every stage.*

**Last updated:** 2026-10-13 · **Current milestone:** M2 + M3 done → M4 next (not started) · **Branch:** `claude/nifty-faraday-ptd4qw`

## Budget

**≈ $31 of API credit left, no refill.** Spent $68.68: M1 $50.05 (≈ $22 of it a cancelled
batch that was billed anyway), M2 + M3 $18.63. Every step projected above $5 needs the
owner's go-ahead.
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

- **M2 + M3: all six books** (run together, incremental on M1)
  - 34,150 narrations → **13,039 merged hadith** (`data/six/hadith.jsonl`); 65 in all six books
  - 183k new candidate pairs: 64.9k by rules, 63.6k skipped as "see also" (low band),
    21k final by Haiku, 33.8k by Sonnet (medium effort, owner's choice for budget)
  - Formulaic-merge veto: short "the Prophet forbade X" reports no longer merge on the formula
  - Tirmidhi's grade on 2,843 hadith; Ibn Majah *zawāʾid* 1,357 (classical 1,339–1,552)
  - Quality: 96.3 % merge precision on new-book gold (79/82), just under the 97 % gate,
    accepted by the owner for budget. `docs/reports/m23-eval.md`

## Next

**M4 — translation (Sonnet, ≈ $20, fits) and topics.** Brief: `docs/handoff/M4.md`.

## Owner decisions on record

- Star rule: ★ per book with the full text, ⯪ per book with only a fragment (main text too).
- Muslim's Muqaddima (almost empty upstream) is out of v1.
- No human gold review; Opus adjudicates. Hard cases get an "ambiguous" tag, not more spend.
- M2 + M3 Sonnet labelling at medium effort (cost over the 97 % gate on a small sample).
- Translation with Sonnet, if it fits the budget (measured ≈ $20: it fits).

## How to rebuild

```bash
pip install -e '.[dev]' anthropic datasketch scikit-learn networkx fastembed typst
python -m u6 fetch && python -m u6 ingest
python -m u6 m1 pairs            # needs huggingface.co + *.hf.co for the e5 model (~34 min CPU)
python -m u6 m1 gold-sample && python -m u6 m1 gold-label && python -m u6 m1 gold-adjudicate
python -m u6 m1 calibrate && python -m u6 m1 label    # label = Batch API spend (~$23)
python -m u6 m1 cluster && python -m u6 m1 sample && python -m u6 m1 evaluate
python -m u6 six pairs && python -m u6 six gold && python -m u6 six label   # label ≈ $15 Batch API
python -m u6 six cluster && python -m u6 six evaluate
python -m pytest -q
```
LLM stages need `ANTHROPIC_API_KEY` in the environment (never commit it).
