# Status

*Pickup file for any session. Update at the end of every stage.*

**Last updated:** 2026-10-14 · **Current milestone:** M6 website built → owner enables Pages → done · **Branch:** `main` (= `claude/blissful-franklin-z0z0m6`)

## Budget

**API credit used up (≈ $98 of $100 spent, no refill). Nothing left in the plan needs the API.**
M1 $50.05 (≈ $22 of it a cancelled batch that was billed anyway), M2 + M3 $18.63, M4 $15.89,
M5 $0.12, v1.1 review $13.45. The key used so far is to be rotated by the owner.
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

- **M4: translation and topics** (`docs/reports/m4.md`, bake-off `docs/reports/m4-bakeoff.md`)
  - All 13,021 representatives translated by Sonnet 5.5 (medium, packed, Batch API), $14.40;
    segments aligned except 9 long texts (italics dropped); every record labelled machine translation.
    `data/m4/translations.jsonl`
  - Bake-off: Haiku 5.5 high rejected (meaning errors in 16/45 vs 1/45 for Sonnet)
  - 33-topic taxonomy; every hadith tagged by Haiku 5.5 ($0.39). `data/m4/topics.jsonl`
  - Opus spot-check of 50: accuracy 4.78/5, 3 meaning-changing errors, topics 49/50 right
  - Found: 98 representatives of ≤ 3 words (split leftovers such as بِهَذَا) → M5 cleanup

- **M5: release v1.0, built** (`docs/reports/m5.md`)
  - Cleanup: 16 chain-only stubs attached, 44 truncated texts repaired (2 merged), al-Tirmidhī's
    commentary kept out of 296 main texts; every narration in exactly one entry
  - Dataset: `hadith.jsonl`, `narrations.jsonl`, `concordance.csv` (+ README, CC BY 4.0)
  - 12 PDF builds (A/B × EN/EN+AR × hadith/appendix/combined), ~17,500 pages in 38 volumes
  - `.github/workflows/release.yml`: a `v*` tag rebuilds everything and publishes a GitHub Release

- **v1.0 published** 2026-10-14: GitHub Release `v1.0` (43 files), Zenodo record made by the owner.
- **v1.1 built** (`docs/reports/v1.1-review.md`): every translation re-checked against the Arabic
  (Sonnet, high effort); 246 meaning errors corrected (`review_fix`), $13.45.

- **M6 website built** (`docs/reports/m6.md`): static site, 13,003 hadith pages, topic / attestation /
  book-number browsing, Pagefind search (English + Arabic, every member's wording indexed),
  `.github/workflows/pages.yml` deploys on every push to `main`.

## Security incident (2026-10-14) — read this

The owner's Windows PC was infected (malicious VS Code project; a hidden `folderOpen` task in
`.vscode/tasks.json` runs obfuscated JavaScript disguised as a font, `*/public/fonts/fa-*.eot`).
With the stolen Git credentials it rewrote the last commit of 8 repositories, this one included,
and removed `.env` from `.gitignore`. All 8 were restored with history rewritten (same files
minus the malware); the v1.0 release was built before the attack and is clean. Owner revoked
tokens/sessions, changed passwords, enabled 2FA and reinstalled Windows.
**If you ever see `.vscode/tasks.json`, `fa-solid-900.eot` or `config.bat`/`node_modules`
appended to `.gitignore` in this repo: stop and tell the owner.**

## Next

1. **Publish v1.1:** Actions → release → Run workflow, branch `main`, tag `v1.1` (owner).
2. **Turn on the website:** Settings → Pages → Source: GitHub Actions; then Actions → pages → Run workflow (owner).
3. Later (no budget needed): better isnad/matn split for representatives (see m6 report, known limits);
   the extended edition and the 71-book programme (PROPOSAL §5.6).

## Owner decisions on record

- Star rule: ★ per book with the full text, ⯪ per book with only a fragment (main text too).
- Muslim's Muqaddima (almost empty upstream) is out of v1.
- No human gold review; Opus adjudicates. Hard cases get an "ambiguous" tag, not more spend.
- M2 + M3 Sonnet labelling at medium effort to save cost, accepting 96.3 % vs the 97 % gate (small sample).
- Translation with Sonnet, if it fits the budget (it did: $14.40). Haiku high was tried and rejected on quality.
- Topic taxonomy: 33 top-level topics (`m4.TOPICS`).
- Arabic source: keep the current edition for the public release; no permission request (owner: the Sunnah belongs to the whole ummah).
- Dataset license: **CC BY 4.0** (improvements by others welcome). Code: MIT.
- API key: owner rotates it now that the API work is finished.
- v1.1: spend the remaining credit on a translation review pass (done).

## How to rebuild

```bash
pip install -e '.[dev]' anthropic datasketch scikit-learn networkx fastembed typst pypdf
python -m u6 fetch && python -m u6 ingest
python -m u6 m1 pairs            # needs huggingface.co + *.hf.co for the e5 model (~34 min CPU)
python -m u6 m1 gold-sample && python -m u6 m1 gold-label && python -m u6 m1 gold-adjudicate
python -m u6 m1 calibrate && python -m u6 m1 label    # label = Batch API spend (~$23)
python -m u6 m1 cluster && python -m u6 m1 sample && python -m u6 m1 evaluate
python -m u6 six pairs && python -m u6 six gold && python -m u6 six label   # label ≈ $15 Batch API
python -m u6 six cluster && python -m u6 six evaluate
python -m u6 m4 bakeoff && python -m u6 m4 translate && python -m u6 m4 translate --singles
python -c "from u6 import m4; m4.stage_fallback('<singles batch id>')"   # italics-dropped fallback, no spend
python -m u6 m4 topics && python -m u6 m4 check     # M4 ≈ $16 in all
python -c "from u6 import m4; m4.stage_review()"   # v1.1 review pass, ≈ $13 Batch API
python -m u6 m5 clean && python -m u6 m5 dataset && python -m u6 m5 pdf   # PDFs in out/release/
python -m u6 m6 build && python -m pagefind --site site                    # website in site/
python -m pytest -q
```
LLM stages need `ANTHROPIC_API_KEY` in the environment (never commit it).
