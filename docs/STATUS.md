# Status

*Pickup file for any session. Update at the end of every stage.*

**Last updated:** 2026-10-13 · **Current milestone:** M0 done → M1 next · **Branch:** `claude/nifty-faraday-ptd4qw`

## Done

- **Design v1** — `docs/PROPOSAL.md`
- **Data-source research** — `docs/research/data-sources.md`
- **M0 Data foundation** (exit criteria met)
  - Source pinned: fawazahmed0/hadith-api @ `df57907`, checksums in `data/sources.json`
  - All six books ingested to one schema: 34,532 records (32,230 full, 880 ref, 1,043 ref_variant, 379 empty) — `data/narrations/*.jsonl`, schema in `data/README.md`
  - Rule-based isnad/matn/tail split: 89.8 % start agreement with the LK Bukhari gold set — `docs/reports/m0-split-eval.md`, method in `docs/methodology/isnad-matn-split.md`
  - Numbering concordance (incl. Muslim FAB numbers and sunnah.com links) — `data/concordance.csv`
  - Tirmidhi's own grade extracted for 3,081 of 3,924 non-empty entries
  - Per-book report — `docs/reports/m0-ingest.md`

## Next

**M1 — MVP: Bukhari + Muslim.** Brief: `docs/handoff/M1.md`.

## Blockers / owner actions

| # | Item | Blocks |
|---|---|---|
| 1 | Add `ANTHROPIC_API_KEY` as an environment secret (rotate the one pasted in chat first). Not set in this environment as of 2026-10-13. | M1 LLM labelling, gold-set annotation |
| 2 | `huggingface.co` is blocked by the environment's network policy. Either allow it (to download a local Arabic embedding model) or accept the no-download plan in the M1 brief (MinHash + TF-IDF char n-grams). | Optional; M1 has a fallback |
| 3 | Confirm star rule (§7.2 of the proposal) and dataset licence (§7.3) | M1 PDF sample |
| 4 | Before public release: ask fawazahmed0 about provenance; contact sunnah.com | M5 |

## How to rebuild

```bash
pip install -e '.[dev]'
python -m u6 fetch        # downloads to data/raw/, verifies checksums
python -m u6 ingest       # writes data/narrations, data/concordance.csv, docs/reports/m0-ingest.md
python -m pytest -q
# optional, needs a local clone of ShathaTm/LK-Hadith-Corpus at data/external/LK-Hadith-Corpus:
python -m u6 eval-split
```
