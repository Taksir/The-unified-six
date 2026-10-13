"""Load narrations and derive the matching table used by every M1+ stage."""

import json
import re
from dataclasses import dataclass
from pathlib import Path

from .split import segments, strip_prophet_formula
from .textnorm import normalize

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT / "data"


@dataclass
class Doc:
    id: str
    book: str
    seq: int
    chapter: int | None
    kind: str
    n_fab: str | None
    isnad_last: str
    text: str          # cleaned Arabic, tashkeel kept
    isnad: str
    matn: str
    tail: str
    match: str         # normalized matn without the leading Prophet formula

    @property
    def fab_base(self) -> str | None:
        return re.match(r"\d+", self.n_fab).group() if self.n_fab else None

    @property
    def words(self) -> int:
        return len(self.match.split())


def load_records(book: str) -> list[dict]:
    with (DATA / "narrations" / f"{book}.jsonl").open(encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def load_docs(books=("bukhari", "muslim"), include_intro: bool = False) -> list[Doc]:
    """Non-empty narrations of `books`, in canonical book order then source order."""
    docs = []
    for b in books:
        for r in load_records(b):
            if r["kind"] == "empty" or (r["intro"] and not include_intro):
                continue
            isnad, matn, tail = segments(r["text"], r["split"])
            m = strip_prophet_formula(normalize(matn)) if matn else ""
            if not m and r["kind"] == "full":
                m = normalize(r["text"])  # no seam found: match on everything
            docs.append(Doc(r["id"], b, r["seq"], r["chapter"], r["kind"], r["n_fab"],
                            r["isnad_last"], r["text"], isnad, matn, tail, m))
    return docs
