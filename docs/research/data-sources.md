# Data Sources Research: The Unified Six

Researched 2026-10-13. Standard: we must be legally able to REDISTRIBUTE (including derivatives) whatever we use. Confidence tags: **VERIFIED** (I read the primary text this session), **UNVERIFIED** (secondhand or from memory; must be checked before reliance).

Tooling limits during research: `sunnah.com`, `zenodo.org`, `data.mendeley.com` and `api.github.com` were blocked by the sandbox proxy (HTTP 403 / ENOTFOUND). `raw.githubusercontent.com` and web search worked. So sunnah.com terms and the Mendeley license field could not be read first-hand. Both are flagged below.

## 0. Headline findings

1. **No source found has a clean, verifiable license chain for the Arabic text AND the English.** Every GitHub dataset that covers all six books is, directly or by evident structure, a scrape of sunnah.com or Shamela. A permissive license on a scrape does not clear the underlying rights.
2. **The Arabic text of the six books is classical (authors died 256-303 AH) and is itself public domain.** The risk lies in the modern editorial layer: a specific edition's numbering, tashkeel, chapter titles, and editors' text. The English translations are all modern and copyrighted. No open or public-domain full English translation of any of the six was found.
3. **fawazahmed0/hadith-api is the best technical candidate for Arabic**, and its repo license is the Unlicense (public domain dedication, VERIFIED). Its provenance is undocumented but it evidently derives from sunnah.com. Treat as "license clean, provenance unproven".
4. **The English side is a blocker.** Default plan: machine translation (MT) of our own, or a negotiated permission from a translator or publisher.

## 1. Part A: Arabic sources

### Summary table

| Source | Stated license | Books complete (of 6) | Arabic / English | Tashkeel | Isnad/matn split | Numbering | Chapter titles | Format | Redistributable? |
|---|---|---|---|---|---|---|---|---|---|
| fawazahmed0/hadith-api | Unlicense (VERIFIED) | 6/6 | Both (English: 6 books, various translators) | Yes (`ara-X`); stripped variant `ara-X1` | No | sunnah.com in-book number (`hadithnumber`); `arabicnumber`; `reference{book,hadith}` | Yes, in `metadata.sections`, but section names are English only | JSON per edition | **Unclear.** The license is clean, the upstream is not documented. |
| AhmedBaset/hadith-json | None declared (VERIFIED: no LICENSE file, none in README) | 6/6 | Both | Yes | No | `idInBook` plus `bookId` and `chapterId`. Bukhari has 7,277 hadiths, so it is the Fuad Abd al-Baqi-style count, not the 7,563 sunnah.com count. | Yes, Arabic and English | JSON per book and per chapter | **No.** No license means all rights reserved, and it is a scrape of sunnah.com. |
| sunnah.com (site/API) | Proprietary. Terms unread (blocked). | 6/6 | Both | Yes | No | In-book number and reference | Yes | Web, API | **No** without written permission (see below). |
| Jammooly1/hadiths-json-files | MIT, "Copyright (c) 2022 Jammooly1" (VERIFIED) | 6 (UNVERIFIED) | Both | Yes | No (narrator field only) | `local_num`, title string "Sunan Abi Dawud 4031" | Yes | JSON per collection | **No/unclear.** MIT on a sunnah.com-style scrape. |
| mhashim6/Open-Hadith-Data | ODbL 1.0 on the DB, DbCL on contents (VERIFIED, LICENSE text) | 6/6 (README) | Arabic only | Yes, plus a no-tashkeel variant | No | UNVERIFIED | UNVERIFIED | CSV | **Unclear.** ODbL is share-alike on the database. Upstream not stated. |
| ShathaTm/LK-Hadith-Corpus (Leeds/King Saud) | **No LICENSE file** (404, VERIFIED); only a citation request | 6 books, 39,038 hadiths | Both (parallel) | UNVERIFIED | **Yes**, English and Arabic isnad/matn columns, plus chapter/section | Per-book hadith number | Yes (EN+AR, chapter and section) | CSV | **No.** Unlicensed academic corpus. English is almost certainly the sunnah.com translations. |
| Sanadset 650K (Mendeley, DOI 10.17632/5xth87zwb5) | Mendeley license field not readable here. An HF mirror (freococo/650k_sanadset) lists CC0 (UNVERIFIED, third-party). | Covers 926 books, includes the six (UNVERIFIED which editions) | Arabic only | Mixed (UNVERIFIED) | **Yes**: separate matn, plus narrator list | Source-book number, not in-book numbering | No | CSV | **Unclear.** Mixed Shamela-derived text, not 1:1 per book. |
| OpenITI / KITAB | Release repos have no LICENSE file (404 on RELEASE and 0275AH). The README states no license (VERIFIED by grep). Zenodo record license not read (blocked). | Likely all six via Shamela-derived files (UNVERIFIED, file names not located) | Arabic only | Mostly none; mARkdown | Structure markup, not isnad/matn | Shamela-based | Header markup | OpenITI mARkdown text | **Unclear.** Texts originate from Shamela / open digital libraries. |
| Shamela (al-Maktaba al-Shamela) | Not researched in depth. Free to read, not an open license. | All | Arabic | Varies | No | Per edition | Yes | Proprietary DB | **No** (assume). |
| Kaggle / HF "hadith" sets | Per upload, e.g. freococo/sunnah_dataset on HF is CC BY-NC-SA 4.0 (reported by search result, UNVERIFIED) | varies | varies | varies | varies | varies | varies | varies | **No.** Non-commercial. Derivative of sunnah.com. |

### Detail: fawazahmed0/hadith-api (primary candidate)

- License: `LICENSE` at https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/LICENSE (branch `1`). Quote: "This is free and unencumbered software released into the public domain. ... Anyone is free to copy, modify, publish, use, compile, sell, or distribute this software, either in source code form or as a compiled binary, for any purpose, commercial or non-commercial..." (The Unlicense, https://unlicense.org.) VERIFIED.
- Provenance: the README (https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/README.md) has no source or license-of-data statement. `editions.json` lists the author as "Unknown" for almost all editions. The data layout (sunnah.com-style English section names, `reference` book/hadith, Muhsin Khan listed for Bukhari and Siddiqui for Muslim) matches sunnah.com. Inference only, not proven.
- Editions: `ara-{bukhari,muslim,abudawud,tirmidhi,nasai,ibnmajah}` with diacritics, and `ara-X1` with diacritics stripped. Many other languages.
- Grades: Abu Dawud, Tirmidhi, Nasa'i and Ibn Majah carry grades from Al-Albani, Zubair Ali Zai, Shuaib Arnaut and Fuad Abd al-Baqi. Those are third-party scholarly judgements. Do not redistribute grades without separate clearance.
- Access note: fetch raw files from `https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/editions/<edition>.json`. jsDelivr is the documented route.

### Detail: AhmedBaset/hadith-json

- README (https://raw.githubusercontent.com/AhmedBaset/hadith-json/main/README.md): "scraped from Sunnah.com", 50,884 hadiths, 17 books. No LICENSE (raw `LICENSE`, `LICENSE.md`, `license` all 404; repo page lists none). VERIFIED.
- Useful as a cross-check only, for its Arabic chapter titles.

### Detail: sunnah.com terms

- Site and API: https://sunnah.com/about, API https://github.com/sunnah-com/api. I could not fetch the live terms. Search snippets of the About page (https://sunnah.com/about, https://beta.sunnah.com/about) report a "Reproduction, Copying, Scraping" section saying the site does not permit "the scraping of our data, nor mass reproduction of entire books or collections on other websites", while describing itself as an "open platform" for software and data. This is a search-result paraphrase. UNVERIFIED. **Someone must read the current About page and write to the maintainers.** Their English translations belong to third-party publishers.

### Detail: others

- LK-Hadith-Corpus: https://github.com/ShathaTm/LK-Hadith-Corpus (README read). Citation: Altammami, Atwell, Alsalka, "The Arabic-English Parallel Corpus of Authentic Hadith", IJASAT / IMAN 2019. No license file. Its isnad/matn split is the only one found for the six in both languages, so it is valuable as a reference for evaluating our own splitting, even if not redistributable.
- Open-Hadith-Data license text: https://raw.githubusercontent.com/mhashim6/Open-Hadith-Data/master/LICENSE. "made available under the Open Database License ... Any rights in individual contents ... under the Database Contents License". Its README says the diacritic text contains special RTL marker characters around "important words or narrator's names".
- Sanadset: https://data.mendeley.com/datasets/5xth87zwb5 and paper https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9440281/. Authors: Mghari, Bouras, El Hibaoui (Data in Brief, 2022). Good for narrator-chain and matn research, but it is not a faithful per-book edition.
- OpenITI: https://github.com/OpenITI/RELEASE, Zenodo DOI 10.5281/zenodo.3082463, metadata http://kitab-corpus-metadata.azurewebsites.net/. The README says texts were assembled within the OpenArabic project. I could not locate specific file URIs for the six books (my guessed paths returned 404), so coverage and license are UNVERIFIED.

## 2. Part B: English translations

| Book | Widely available English translation | Translator / publisher / year | Copyright status | Open or PD? |
|---|---|---|---|---|
| Sahih al-Bukhari | "The Translation of the Meanings of Sahih al-Bukhari" | Muhammad Muhsin Khan, Darussalam, 1997 (printing seen) | An archived 1997 Darussalam copy carries an "ALL RIGHTS RESERVED ... without written permission of the publisher or the translator" notice (per search result, https://archive.org/download/EnglishislamicBooks_MAE/406SahihBukhari1.pdf; UNVERIFIED first-hand) | **No** |
| Sahih Muslim | Abdul Hamid Siddiqui | Kitab Bhavan / Ashraf, 1970s (UNVERIFIED) | Presumed in copyright. fawaz `editions.json` credits Siddiqui for `eng-muslim`. | **No** (unverified) |
| Sunan Abi Dawud | Ahmad Hasan (Kitab Bhavan), and the newer Darussalam set | Darussalam volumes credit Nasiruddin al-Khattab and Yasir Qadhi (listing, UNVERIFIED) | Copyrighted (presumed) | **No** (unverified) |
| Jami' at-Tirmidhi | Darussalam | translator credit not confirmed here | Copyrighted (presumed) | **No** (unverified) |
| Sunan an-Nasa'i | Darussalam, 2007 listing (https://libcat.egst.edu.et//bib/20030) | Nasiruddin al-Khattab (UNVERIFIED) | Copyrighted (presumed) | **No** (unverified) |
| Sunan Ibn Majah | Darussalam | Nasiruddin al-Khattab, reviewed by Abu Khaliyl; edited by Zubair Ali Za'i (search result https://darussalam.pk/collections/vendors/products/sunan-ibn-majah-5-vol-set-english) | Copyrighted | **No** |

Dataset English terms:
- fawaz hadith-api: `eng-bukhari` (Muhsin Khan), `eng-muslim` (Siddiqui), `eng-abudawud`, `eng-nasai`, `eng-tirmidhi`, `eng-ibnmajah` (author "Unknown"). The Unlicense covers the repo, it cannot grant rights the repo owner does not hold in the translations. **Not usable for redistribution.**
- AhmedBaset, Jammooly1, LK corpus: English from sunnah.com, same problem.
- I found **no** openly licensed or public-domain full English translation of any of the six. Older pre-1923 partial translations (for example of Mishkat or Bukhari excerpts) exist but are not complete and were not evaluated. UNVERIFIED that none exists; I only searched shallowly.

## 3. Part C: Validation resources

- **Tuhfat al-Ashraf (al-Mizzi, d. 742 AH).** The only web hit for a digital copy is Shamela (https://shamela.ws/book/12570, UNVERIFIED that this is the Tuhfa). No OpenITI file located (searches for "0742Mizzi" found nothing; guessed URIs 404). 15-volume print edition (Dar al-Kitab al-Arabi / Dar al-Gharb) exists. **No machine-readable open version confirmed.**
- **Jami' al-Usul (Ibn al-Athir) and Misbah al-Zujajah (al-Busiri):** not located in a machine-readable open form. UNVERIFIED; not searched deeply.
- **Existing concordance between the six:** none found as a ready dataset. Closest: the per-hadith `grades` and `reference` fields in fawaz data (reference only points to sunnah.com's own numbering). The dedup pipeline will have to build its own matn-similarity clustering. Use the LK corpus and Sanadset as test material for isnad/matn splitting, not as shipped data.

## 4. Part D: Sample analysis

Samples are in `/tmp/claude-0/-home-user-The-unified-six/5e4a1dc5-12ba-5f06-aea5-9146f990194f/scratchpad/data_samples/` (`fawaz/`, `baset/`). Parsed with `python3 -I`; nothing executed.

### fawazahmed0 Arabic editions (branch `1`)

| Book | Records | Non-empty text | With tashkeel | Graded | Fractional numbers | Section count | Number range |
|---|---|---|---|---|---|---|---|
| Bukhari | 7,589 | 7,580 | 7,580 | 0 | 26 | 98 | 1-7563 |
| Muslim | 7,563 | **7,360** (203 empty) | 7,360 | 0 | 0 | 57 | 1-7563 |
| Abu Dawud | 5,274 | 5,272 | 5,272 | 5,274 | 0 | 44 | 1-5274 |
| Tirmidhi | 3,998 | 3,924 | 3,924 | 3,954 | 42 | 50 | 1-3956 |
| Nasa'i | 5,765 | 5,679 | 5,679 | 5,758 | 7 | 52 | 1-5758 |
| Ibn Majah | 4,343 | 4,338 | 4,338 | 4,341 | 2 | 38 | 1-4341 |

Sample (truncated), Bukhari #1:
`{"hadithnumber":1,"arabicnumber":1,"text":"حَدَّثَنَا الْحُمَيْدِيُّ عَبْدُ اللَّهِ بْنُ الزُّبَيْرِ ، قَالَ : حَدَّثَنَا سُفْيَانُ ... \" إِنَّمَا الْأَعْمَالُ بِالنِّيَّاتِ ...","grades":[],"reference":{"book":1,"hadith":1}}`

Quality issues:
1. Empty text: Muslim has 203 records with empty Arabic (for example #1, 2, 5-14), Nasa'i 86, Tirmidhi 74, Bukhari 9. These are mostly sub-numbered or cross-referenced entries that sunnah.com leaves blank. English may fill some.
2. Fractional `hadithnumber` values (Bukhari 26, Tirmidhi 42, Nasa'i 7, Ibn Majah 2) denote sub-hadiths (like 3.1), which breaks naive integer keys.
3. Numbering is sunnah.com's, not Fuad Abd al-Baqi for Muslim and Ibn Majah. Bukhari top number 7563 is the sunnah.com count; fawaz has 7,589 records.
4. Isnad and matn are fused in one `text` string; no split.
5. Section names in `metadata.sections` are English, with no Arabic kitab titles. Section 0 is an empty or introduction pseudo-chapter in several books (for example "0": "" in Bukhari, Muslim section 0 "Introduction").
6. Bukhari text contains double spaces before commas and embedded `\n` before quotes. Ibn Majah (and other sunnah.com-sourced) text contains U+200F-style marks (RLM/`‏`) around quotes and the sentence-final `‏.‏`. Normalization needed.
7. Grading data is absent in Bukhari and Muslim, as expected.

### AhmedBaset/hadith-json (`db/by_book/the_9_books/bukhari.json`)

- 7,277 hadiths, 97 chapters, Arabic and English chapter titles ("كتاب بدء الوحى" / "Revelation"). Fields: `id, idInBook, chapterId, bookId, arabic, english{narrator,text}`.
- Its Bukhari count (7,277) differs from fawaz (7,589 records / 7,563 numbers), so the two use different counting. Reconcile before relying on either as "the" numbering.
- Not licensed (see above).

## 5. Recommendation

**Primary Arabic source:** fawazahmed0/hadith-api (`ara-*` editions, with diacritics). Reasons: only candidate with a verified, explicit public-domain-style license; all six books; tashkeel; sunnah.com in-book numbering; Arabic chapter coverage via sections. **Conditions before shipping:**
1. Ask the maintainer (issue on the repo) to state the upstream source and whether he holds permission. Record the answer.
2. Contact sunnah.com about reuse of the Arabic and chapter data.
3. Cross-check a sample against an independent edition (Shamela/OpenITI) so we can attest the text matches the public-domain classical text, and consider rebuilding from OpenITI/Shamela if provenance stays murky.
4. Do not ship the `grades` field (Al-Albani, Zubair Ali Zai, Arnaut are copyrighted opinions).

**Isnad/matn splitting:** do it ourselves on the Arabic (rule-based with the standard "qala / sami'tu / annahu" markers), and validate against LK-Hadith-Corpus and Sanadset samples without redistributing them.

**English per book:** *none open* for all six (Bukhari, Muslim, Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah). Fall back to either (a) original machine translation by us, clearly labelled, released CC-licensed, or (b) a written permission request to the translators or Darussalam. The English+Arabic PDF cannot reuse Muhsin Khan, Siddiqui, or Darussalam text under the facts found.

**Validation:** no machine-readable Tuhfat al-Ashraf, Jami' al-Usul, or Misbah al-Zujajah confirmed. Use internal consistency checks: per-book counts (Bukhari 7,563 / Muslim 7,563 / Abu Dawud 5,274 / Tirmidhi 3,956 / Nasa'i 5,758 / Ibn Majah 4,341 by sunnah.com numbering), plus the Tuhfa as a manual spot-check source (print / Shamela) and a self-built matn-similarity concordance.

## 6. Blockers and open items

1. English: no open translation. Decide on MT or permissions.
2. sunnah.com terms unread (proxy blocked); must be read by a human and confirmed in writing.
3. Provenance of fawaz data undocumented.
4. OpenITI/Zenodo license and the existence of a Tuhfa file unconfirmed (proxy blocked zenodo.org).
5. Mendeley license for Sanadset unconfirmed.
6. Numbering conflict: sunnah.com vs Fuad Abd al-Baqi (Muslim, Ibn Majah) vs counts in other scrapes; pick one scheme and document a crosswalk.

## Source URLs

- https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/LICENSE
- https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/README.md
- https://raw.githubusercontent.com/fawazahmed0/hadith-api/1/editions.json
- https://raw.githubusercontent.com/AhmedBaset/hadith-json/main/README.md
- https://raw.githubusercontent.com/mhashim6/Open-Hadith-Data/master/LICENSE
- https://raw.githubusercontent.com/Jammooly1/hadiths-json-files/main/LICENSE
- https://github.com/ShathaTm/LK-Hadith-Corpus
- https://raw.githubusercontent.com/OpenITI/RELEASE/master/README.md
- https://data.mendeley.com/datasets/5xth87zwb5 ; https://www.ncbi.nlm.nih.gov/pmc/articles/PMC9440281/
- https://sunnah.com/about ; https://github.com/sunnah-com/api
