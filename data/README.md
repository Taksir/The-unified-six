# Data

| Path | Committed | What |
|---|---|---|
| `sources.json` | yes | Pinned upstream commit and sha256 of every raw file |
| `raw/` | **no** | Upstream downloads. Recreate: `python -m u6 fetch` |
| `external/` | **no** | Third-party validation corpora (e.g. LK-Hadith-Corpus); not redistributable |
| `narrations/<book>.jsonl` | yes | One record per upstream entry, in source order |
| `books.json` | yes | Book metadata and chapter list (English chapter names from upstream) |
| `concordance.csv` | yes | Record ID ↔ numbering schemes ↔ sunnah.com URL |

## Narration record (schema v1)

| field | type | notes |
|---|---|---|
| `id` | str | `<book>:<n>`, e.g. `bukhari:1`, `tirmidhi:391.2` |
| `book` | str | `bukhari` `muslim` `abudawud` `tirmidhi` `nasai` `ibnmajah` |
| `seq` | int | position in the upstream file (source order) |
| `n` | str | standard number (see `books.json` → `numbering`); a decimal marks an upstream sub-entry |
| `n_fab` | str/null | Muslim only: Fuad Abd al-Baqi number as sunnah.com prints it (`8a`) |
| `chapter` | int | kitab number. From the entry's own upstream reference; entries upstream marks as `0` inherit the previous chapter unless they lie in a real introduction (Muslim 1–92, Ibn Majah 1–266) |
| `chapter_hadith` | int/null | position in the kitab (upstream in-book reference), null when upstream has none |
| `intro` | bool | Muslim's Muqaddima |
| `kind` | str | `full` · `ref` · `ref_variant` · `empty` (see `docs/methodology/isnad-matn-split.md`) |
| `text` | str | full Arabic with tashkeel, invisible marks removed |
| `split` | [int, int] | `u6.split.segments(text, split)` → `(isnad, matn, tail)` |
| `isnad_last` | str | heuristic last narrator, diacritic-free |
| `tirmidhi_grade` | obj/null | Tirmidhi only: `{"ar": "حسن صحيح", "en": "hasan sahih"}` |
| `split_flags` | list | which splitter rule fired, for auditing |

Third-party grades in the upstream data (al-Albani, Zubair Ali Zai, Arnaut …) are
deliberately **not** carried over. English upstream text is not used (copyrighted).

## Numbering

`n` is the standard printed numbering for every book except Muslim, where upstream's
sequential number (1–7563) is kept as `n` and the Fuad Abd al-Baqi number is `n_fab`.
The scheme names in `books.json` are the ones sunnah.com's numbers correspond to. The
7,277-entry Bukhari count seen in AhmedBaset/hadith-json is of unclear origin and is not
mapped in M0.

## Known upstream issues

- 75 records across the six books contain U+FFFD replacement characters (lost characters
  in the upstream scrape). They are kept as-is; any page that embeds the text escapes them.
