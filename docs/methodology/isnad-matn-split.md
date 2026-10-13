# Isnad / matn / tail segmentation (M0)

Code: `src/u6/split.py`. Tests: `tests/test_split.py`. Score: `docs/reports/m0-split-eval.md`.

## Why rules first

No source with a redistributable licence separates the chain from the text (see
`docs/research/data-sources.md`). Transmission language is formulaic, so rules get most
of the way for free; the remaining errors are tolerable for deduplication because M1
matches on **containment and similarity**, not on exact boundaries.

## Segments

| Segment | Contents |
|---|---|
| **isnad** | The chain up to and including the last narrator's speech verb (`… عن أبي هريرة، قال`). A Prophet link with a speech verb (`سمعت رسول الله ﷺ يقول`) stays in the isnad. |
| **matn** | The reported content, up to the first tail sentence. |
| **tail** | Everything after the main matn: further chains (`حدثنا … بهذا الإسناد مثله`), compiler comments (`قال أبو عيسى …`, `قال أبو داود …`), `وفي الباب` lists, Bukhari's `تابعه …`. |

Records store the cleaned `text` and `split: [a, b]`; `segments(text, split)` returns
`(isnad, matn, tail)` = `text[:a]`, `text[a:b]`, `text[b:]` with separators trimmed.

## Kinds

| kind | meaning | M1 treatment |
|---|---|---|
| `full` | normal narration | normal matching |
| `ref` | back-reference with no own wording (`بهذا الإسناد مثله`, `نحوه`) | attach to the preceding non-ref narration in the same book |
| `ref_variant` | back-reference that adds or changes wording (`… بهذا الإسناد وزاد …`) | attach to the preceding narration **and** match its own fragment |
| `empty` | upstream has no Arabic text | keep the ID for the concordance; never printed |

A back-reference counts only at the seam between chain and text (6 tokens before to 12
after the boundary). `نحوه` in the middle of an isnad annotates a parallel chain, not
a reference to an earlier entry.

## Rules (in order, on the diacritic-free skeleton)

1. A chain must have started (any transmission term: `حدثنا/أخبرنا/أنبأنا` in all
   person/object forms, `سمعت`, `عن`, `ح` tahwil, `كتب إلي`).
2. Glosses between dashes (`- يعني ابن إسحاق -`) are skipped.
3. A **speech verb** (`قال/قالت/يقول/قلت…`) opens the matn unless a chain verb follows
   within 3 words (`قالا حدثنا`), or a name then `عن` follows (`قال الزهري عن`), or a
   name then a chain verb follows within 8 words.
4. `أنه/أنها` followed by a speech or chain verb is chain; otherwise it opens the matn.
5. `أن` + Prophet opens the matn. `أن` + name + chain verb (`أن أبا هريرة حدثه`) or
   name + speech verb (`أن عائشة قالت`) stays chain. Any other `أن` opens the matn.
6. Transmission verb + Prophet with no speech verb (`سمعت النبي ﷺ قرأ …`) opens the matn
   at the transmission verb.
7. A comma-chunk that begins with neither a name nor a chain link opens the matn.
8. A sentence stop opens the matn unless the chain resumes right after it.
9. A quote mark opens the matn.

Tail starts at the first sentence (outside quotes) after the matn that opens with a
chain verb, `تابعه/رواه`, `قال X حدثنا`, a compiler's kunya (`قال أبو عيسى`, etc.), or
`وفي الباب`.

## Measured accuracy

Against LK-Hadith-Corpus Bukhari (hand-checked by its authors): **89.8 %** of matn
start points agree within a few words; 86.3 % of matns are ≥ 0.90 similar. LK's own
segmentation tool reports 92 % on its automatically annotated books. Known weak spots:
`أن + Companion + verb` (we keep the Companion's name in the matn, LK puts it in the
isnad: harmless for matching), multi-hadith entries, and unusual chains (`أشهد على …`).

## Known limitations

- `isnad_last` (last narrator) is a heuristic string, not a resolved person.
- Tirmidhi grades: only the ḥasan/ṣaḥīḥ/gharīb vocabulary is captured (3,081 of 3,924
  non-empty entries). Other verdicts and entries graded under a sibling entry are M2 work.
