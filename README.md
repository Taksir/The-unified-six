# The Unified Six

A complete, deduplicated compilation of the **Kutub al-Sittah** — Sahih al-Bukhari, Sahih Muslim, Sunan Abi Dawud, Jami' al-Tirmidhi, Sunan al-Nasa'i, and Sunan Ibn Majah. Each distinct hadith is listed once, with references to every book where it appears.

- **Design and plan:** [`docs/PROPOSAL.md`](docs/PROPOSAL.md)
- **Data-source research:** [`docs/research/data-sources.md`](docs/research/data-sources.md)
- **Where we are:** [`docs/STATUS.md`](docs/STATUS.md) · next milestone brief: [`docs/handoff/M1.md`](docs/handoff/M1.md)
- **Data:** [`data/README.md`](data/README.md)

```bash
pip install -e '.[dev]'
python -m u6 fetch && python -m u6 ingest && python -m pytest -q
```

**v1.1:** 34,150 narrations → 13,003 entries, machine-translated into English (re-checked against the Arabic in v1.1), in two PDF editions (by attestation, by topic; English and English + Arabic) and an open dataset (`data/release/`). Build: `docs/STATUS.md`; release notes: `CHANGELOG.md`. Text and data CC BY 4.0, code MIT.

Planned outputs: free PDFs (English, and English + Arabic) in two arrangements (by attestation ★6→★1, and by topic), an open CC-licensed dataset, and later an interactive website.
