# The Unified Six — Project Proposal & Design

*A complete, deduplicated compilation of the Kutub al-Sittah.*
Status: **Design v1 · M0 + M1 complete** (see `docs/STATUS.md`) · Lead: Claude (under project owner) · Last updated: 2026-10-13

---

## 1. Vision

The six canonical Sunni hadith books — **Sahih al-Bukhari, Sahih Muslim, Sunan Abi Dawud, Jami' al-Tirmidhi, Sunan al-Nasa'i, Sunan Ibn Majah** — contain ~35,000 narrations. Once within-book repetitions and cross-book overlaps are merged, scholars estimate roughly ~10,000 distinct hadith remain.

No existing work is a complete deduplicated merge of the modern canonical six:

| Precedent | Shortfall |
|---|---|
| Ibn al-Athir, *Jami' al-Usul* | Uses the Muwatta instead of Ibn Majah; trims chains |
| al-Tabrizi, *Mishkat al-Masabih* | A ~6,000-hadith selection, not complete |
| al-Suyuti, *al-Jami' al-Kabir* | Unfinished |

**Goal:** every narration in the six books is represented **at least once**, each distinct hadith is printed **once**, and every printed hadith carries a compact pointer to every book where it appears.

### Guiding principles

1. **Reader first.** The main text is hadith, not apparatus. Sources, variants, and chains live in the appendix.
2. **Count ≠ quality.** The star rating counts how many books carry a hadith. Authenticity is shown separately and never inferred from stars.
3. **Nothing lost.** Every original narration (with its isnad) is traceable from the merged entry.
4. **Open and reproducible.** Open data, open code, every pipeline stage re-runnable.

---

## 2. Two groupings (two separate outputs)

### Edition A — *By Attestation*
Ordered **★6 → ★1**. Within each star level, hadith are ordered by topic (see Edition B taxonomy), then by canonical book order.

### Edition B — *By Topic*
Grouped by a unified topic taxonomy (adapted from Ibn al-Athir's *Jami' al-Usul* arrangement, which was itself designed for merging the six). Within each topic, ordered **★6 → ★1**.

### Stars and badges

| Element | Meaning |
|---|---|
| **★ / ⯪ (main text)** | One ★ per book that carries the full hadith, one ⯪ per book that carries only a fragment (owner decision, M1). |
| **★ / ⯪ (appendix)** | Per narration: ★ = full version, ⯪ = fragment. |
| **≈** | Grouping rests on a low-confidence machine judgement; possible duplicates are listed as "see also". |
| 🟢 **Muttafaq ʿalayh** | In both Bukhari and Muslim |
| 🔵 **Sahih (one)** | In Bukhari *or* Muslim |
| **T: grade** | Tirmidhi's own grading, where he gives one (ḥasan, ṣaḥīḥ, gharīb …) |

No modern grader (e.g. al-Albani) is used — avoids importing a contested authority.

### Entry format (main text)

Kept to one short bracket so the reader's attention stays on the hadith:

```
1234. Actions are but by intentions, and every person shall have only what he
intended. *Whoever emigrated for the sake of Allah and His Messenger…*
[★★★★★★ 🟢 · B M D T N J · →A1234]
```

- Book letters: **B** Bukhari, **M** Muslim, **D** Abu Dawud, **T** Tirmidhi, **N** Nasa'i, **J** Ibn Majah.
- `→A1234` points to the appendix entry with full references, variants, Companions, and chains.

### Italics for partial overlap

When versions differ in length, the main text shows the **fullest version**:
- **Roman (upright)** = the core text found in every version.
- ***Italic*** = additional text found only in some versions.

The appendix says exactly which book carries which addition.

*Caveat:* versions rarely match word-for-word, so alignment is done at the **clause level** with fuzzy matching, not word by word. Borderline alignments go to review.

---

## 3. Outputs

### 3.1 PDFs (first deliverable, free)

Generated from one data source by **Typst** (free, good Arabic RTL support, fast; one command per book).

| | English | English + Arabic |
|---|---|---|
| **Edition A** (by attestation) | Hadiths · Appendix · Combined | Hadiths · Appendix · Combined |
| **Edition B** (by topic) | Hadiths · Appendix · Combined | Hadiths · Appendix · Combined |

That is 12 PDF builds, split into volumes where needed (estimated 3,000–5,000 pages for full English+Arabic). Every volume is a separate PDF; merging is a single `pdfunite`/`qpdf` command.

**Simple vs. extended:** v1 prints only the representative text in the main body. A later **extended edition** prints the variants inline.

### 3.2 Open dataset

- `narrations.jsonl` — every original narration: book, number(s) in each numbering scheme, chapter, full Arabic, isnad, matn, Companion, Tirmidhi grade, English.
- `hadith.jsonl` — merged entries: ID (`U6-xxxx`), member narrations with role (`full` / `partial`), representative, stars, badges, topic, aligned core/addition segments, English.
- `concordance.csv` — narration ↔ merged hadith ↔ all numbering schemes.
- License: **CC BY 4.0** by default, or **CC BY-SA 4.0** if an upstream source requires share-alike (decided by the data-source research, `docs/research/data-sources.md`).

### 3.3 GitHub repo
All code, under MIT. Every hadith in the PDFs and on the website gets a "Report an issue" link that opens a pre-filled GitHub issue.

### 3.4 Website (later phase)
A free static site on **GitHub Pages** with client-side search (Pagefind). It is interactive: clicking a hadith reveals its sources, chains, variants, and Companions. It is built from the same dataset after the PDFs ship.

---

## 4. Methodology

### 4.1 Unit of deduplication

> Two narrations are the **same hadith** if their **matn** reports the same Prophetic statement or event, regardless of isnad or Companion.

| Relation | Treatment |
|---|---|
| Same matn, different chain/Companion | **Merged**; Companions listed in the appendix |
| One is a fragment of the other | **Merged**; the fragment is a `partial` member (⯪); the extra text is italicized |
| Same topic, materially different content | **Separate hadith**, cross-linked as "related" in the appendix |
| Repetition within the same book | **Merged** (e.g. Bukhari's ~7,000 narrations collapse to ~2,600) |

### 4.2 Pipeline (efficient by construction)

Code does most of the work. The LLM sees only what code cannot decide. We never compare all pairs (35k² ≈ 600M); candidate generation narrows each narration to its ~10 nearest neighbours.

```
 ingest ─▶ normalize ─▶ split isnad/matn ─▶ exact-hash merge
                                               │
                    ┌──────────────────────────┴─────────────┐
                    ▼                                        ▼
         MinHash-LSH (char 5-grams)               embedding kNN (local model)
                    └──────────── candidate pairs ───────────┘
                                     │
                     features: Jaccard, containment, length ratio, cosine
                                     │
            ┌──────── confident ─────┼───── middle band ─────┐
            ▼                        ▼                       ▼
     auto same/partial/diff   Haiku batch classify ──▶ low-confidence ──▶ Sonnet
                                     │                                     │
                                     └──────────▶ human review queue ◀─────┘
                                     │
                     graph clustering (with anti-chaining guard)
                                     │
            representative · clause alignment · stars/badges · topic · translation
                                     │
                              dataset ─▶ Typst ─▶ PDFs
```

| Stage | Method | Cost |
|---|---|---|
| **Normalize** | Strip tashkeel and tatweel; unify alef forms (أإآ→ا), ى→ي, ة→ه; drop punctuation and honorific formulas (ﷺ, صلى الله عليه وسلم) | free |
| **Isnad/matn split** | Use the source's split if it has one. Otherwise rules on transmission formulae (حدثنا، أخبرنا، عن … قال رسول الله / عن النبي ﷺ), with Haiku for leftovers | ~free |
| **Exact merge** | Hash of the normalized matn | free |
| **Candidates** | MinHash-LSH plus kNN over a local open-source Arabic sentence-embedding model (CPU, FAISS) | free |
| **Auto-decide** | Thresholds on Jaccard / containment / cosine, **calibrated on the gold set** | free |
| **Middle band** | Haiku, batched (~25–50 pairs per request), labels: `same` · `partial(A⊂B)` · `related` · `different` + confidence | cheap |
| **Escalation** | Low-confidence results, or Haiku disagreeing with lexical signals → Sonnet (medium effort) | moderate |
| **Clustering** | Connected components on `same`/`partial` edges, plus a guard that splits clusters whose members drift apart (A≈B≈C but A≠C) | free |
| **Human review** | Only Sonnet low-confidence items. Target ≤ 300 items, presented side by side | owner time |

### 4.3 Representative, alignment, and ordering
- **Representative text:** the fullest version, tie-broken by book priority **B → M → D → T → N → J** (classical practice).
- **Clause alignment:** split each matn into clauses, then fuzzy-match each clause to every member. Clauses present in all members are core (roman); the rest are additions (italic).
- **Topic tagging:** Haiku assigns each merged hadith one primary topic (plus optional secondary topics) from the fixed taxonomy.

### 4.4 Translation
Research (`docs/research/data-sources.md`) found **no openly licensed English translation for any of the six books**: the standard translations (Darussalam, Siddiqui) are copyrighted, and the English in every dataset is those same translations. So we use the agreed fallback:

**LLM translation**, clearly labelled as machine translation, with community correction via GitHub issues. (Requesting permission from the copyright holders remains an optional parallel track.)

For LLM translation, we translate only the ~10k representatives, not all 35k narrations. Segment markers are kept through translation so the English italics match the Arabic. A fixed glossary (ṣalāh, zakāh, ﷺ → "ﷺ", Companion names) keeps terms consistent.

**Model choice is measured, not assumed:** 100 gold hadith are translated by Haiku and by Sonnet and compared side by side. Haiku is used if it is close enough. Even all-Sonnet translation fits the budget (see §5.3).

---

## 5. Execution plan

### 5.1 Who does what

| Role | Who | Why |
|---|---|---|
| Lead: design, integration, final review | Claude (lead session) | Holds the plan; reviews every merge into `main` |
| Code modules (ingest, matcher, typesetting) | Sonnet subagents | Each gets one module with a clear interface and tests |
| Bulk LLM labelling, tagging, translation | **Message Batches API** called by pipeline scripts (Haiku → Sonnet) | 50% cheaper than live calls, reproducible, survives session death |
| Spot-checks and sample reading | Haiku subagents, each ≤ 100k tokens | Cheap reading of sample outputs, flagging anomalies |
| Research | Sonnet subagent | Licensing needs judgment |
| Human review, final say on scholarly calls | Project owner | — |

**Why bulk work goes through the API rather than subagents:** a subagent re-reads its prompt and context on every step, while a batch request processes each item once at half price. Subagents are used where reasoning over code or files is needed.

### 5.2 Models

| Task | Model | Effort |
|---|---|---|
| Pair classification (middle band), topic tagging, isnad split leftovers | `claude-haiku-5-5` | low |
| Escalated ambiguous pairs, clause-alignment disputes | `claude-sonnet-5-5` | medium |
| Translation | Haiku or Sonnet — decided by the §4.4 bake-off | medium |

### 5.3 API cost estimate (Batch API, 50% off list price)

List prices: Haiku 5.5 $0.10 / $0.50 per MTok input/output; Sonnet 5.5 $2 / $10. Arabic tokenizes heavily, so the estimates below are conservative.

| Work | Volume | Model | Est. cost |
|---|---|---|---|
| Middle-band pair classification | ~25k pairs | Haiku | ~$2 |
| Escalations | ~3k pairs | Sonnet | ~$10 |
| Topic tagging | ~10k hadith | Haiku | ~$1 |
| Translation (representatives) | ~10k hadith | Haiku / Sonnet | ~$2 / ~$30 |
| Evaluation runs, re-runs, slack | — | mixed | ~$15 |
| **Total** | | | **~$30 (Haiku translation) – ~$60 (Sonnet translation)** |

This fits within the $100 credit. Each stage has a hard spend cap in config and logs its actual cost.

### 5.4 Evaluation (gold set)

- **Gold set:** ~300 candidate pairs stratified across score bands, plus ~50 known-different "hard negatives" on the same topic. Annotated by Sonnet, then verified by the owner.
- **External ground truth:** research found no machine-readable *Tuhfat al-Ashraf*, *Jami' al-Usul* or *Misbah al-Zujajah*. Instead: per-book unique-count checks against scholarly figures, and owner spot-checks of samples against a printed edition or Shamela. If a digital Tuhfa turns up later, it gets plugged in.
- **Metrics:** precision and recall for `same` and `partial`; cluster purity.
- **Quality gate:** **≥ 97% precision on `same`** before scaling past the MVP. A false merge hides a hadith, which is worse than leaving a duplicate.
- **Sanity checks:** every narration ID appears in exactly one merged hadith; per-book unique counts are compared with scholarly estimates (e.g. Bukhari ≈ 2,600 unique).

### 5.5 Session resilience

The cloud session can end at any time, so:
- Every stage writes outputs to `data/` and is **committed and pushed** at the end of the stage.
- Stages are idempotent and keyed by input hash, so a rerun skips finished work.
- Batch job IDs are recorded in `data/batches.json`, so results can be fetched by a later session.
- `docs/STATUS.md` records where we are, for pickup.

### 5.6 Milestones

| # | Milestone | Exit criteria |
|---|---|---|
| **M0** ✅ | Data foundation | Source: `fawazahmed0/hadith-api` Arabic with tashkeel (Unlicense; provenance to be confirmed, see §6); rule-based isnad/matn split; all six books ingested to a common schema; numbering concordance built |
| **M1** ✅ | **MVP: Bukhari + Muslim** | Within- and cross-book merge; gold set and evaluation pass the quality gate; 30-page sample PDF (both editions, EN+AR) for owner review of format |
| **M2** | + Abu Dawud, Tirmidhi | Merged; Tirmidhi grades attached; gate re-checked |
| **M3** | + Nasa'i, Ibn Majah | All six merged; zawāʾid validation; human review queue cleared |
| **M4** | Translation + topics | Bake-off decided; all representatives translated; taxonomy tagged |
| **M5** | **Release v1.0** | 12 PDF builds, dataset on GitHub (Releases + Zenodo DOI, free), changelog |
| **M6** | Website | GitHub Pages interactive site |
| *later* | Extended edition; the 71-book programme | — |

---

## 6. Risks

| Risk | Mitigation |
|---|---|
| No openly licensed English translation (**confirmed**) | Labelled LLM translation (agreed fallback) |
| Arabic source provenance: the Unlicense dataset is likely a sunnah.com scrape | The classical text itself is public domain, but modern editorial layers (tashkeel, numbering) may not be. Develop on it now; before the **public** v1.0 release, seek written permission from sunnah.com or switch to an independently sourced edition |
| No source splits isnad from matn | Rule-based split, validated against LK-Hadith-Corpus and Sanadset (used for validation only, not shipped) |
| Numbering schemes disagree (e.g. Bukhari 7,563 vs 7,277 numbers) | Numbering crosswalk built in M0 |
| False merges hide distinct hadith | Precision-first threshold; anti-chaining guard; review queue; public issue reporting |
| Isnad/matn split errors corrupt matching | Prefer sources with a native split; measure split accuracy on the gold set |
| Clause alignment noisy for italics | Clause-level (not word-level) alignment; uncertain cases fall back to no italics, with variants in the appendix |
| Numbering-scheme confusion | Concordance table; every reference states its scheme |
| Religious sensitivity of errors | Clear "machine-assisted compilation" disclaimer; corrections welcomed and versioned |

---

## 7. Open items for the owner

1. **API key:** the key pasted in chat should be rotated, since it now sits in the conversation log. Store the new key as an environment secret named `ANTHROPIC_API_KEY`, never in the repo. Its `sk-ant-usr-` prefix also differs from standard Console API keys (`sk-ant-api…`), so it will be verified with a one-cent test call before use.
2. **Star rule:** confirm that the main-text ★ count includes books that carry only a fragment, with the full/partial split (★/⯪) shown in the appendix.
3. **Dataset license:** CC BY 4.0, unless upstream sources force BY-SA.
