# Changelog

## v1.1 — 2026-10-14

- Translation review: every entry's English re-checked against the Arabic (with diacritics) by a
  second model pass (Claude Sonnet 5.5, high effort) that corrects meaning errors only —
  omissions, additions, wrong subject/object, reversed sense. 246 translations corrected;
  each carries `review_fix` in hadith.jsonl. Style was not touched.
- `translation` in hadith.jsonl gains `machine_reviewed` and `corrected_in_review`.
- No change to grouping, numbering, topics or the Arabic.

## v1.0 — 2026-10-14

- All six books merged: 34,150 narrations → 13,003 entries with text.
- English machine translation of every entry (Claude Sonnet 5.5), clause-aligned for italics.
- 33-topic arrangement; editions A (by attestation) and B (by topic), English and English + Arabic.
- M5 cleanup: 16 chain-only stubs attached to their hadith; 44 truncated texts repaired and
  re-translated (2 merged as duplicates); al-Tirmidhī's commentary kept out of the main text
  where it starts at a clause boundary (296).
- Known limits: ~6 % of translations with a meaning-changing error (sample of 50; reduced in
  v1.1); merge
  precision 96.3 % on the four Sunan (gold sample); 159 entries of ≤ 5 Arabic words are
  real short reports or fragments and are printed as they are.
