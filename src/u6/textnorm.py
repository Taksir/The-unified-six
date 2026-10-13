"""Arabic text cleaning (for storage/display) and normalization (for matching).

`clean` is lossless for the reader: it keeps tashkeel and only removes invisible
bidi marks and spacing noise from the upstream scrape.
`normalize` is lossy and used only for matching: no tashkeel, unified letter forms,
no punctuation, no honorific formulae.
"""

import re

_INVISIBLE = re.compile("[​-‏‪-‮⁦-⁩﻿]")
_WS = re.compile(r"\s+")
_SPACE_BEFORE_PUNCT = re.compile(r"\s+([،,:;؛.?؟!])")
_DOT_RUN = re.compile(r"(?:\s*\.){2,}")

# Harakat, Quranic annotation marks, superscript alef, tatweel.
DIACRITICS = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ]")
# One-to-one letter unification (keeps string length, so offsets survive).
_LETTER_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي"})
_TA_MARBUTA = str.maketrans({"ة": "ه"})

_HONORIFICS = re.compile(
    r"ﷺ|صلي الله عليه وسلم|صلي الله عليه وعلي اله وسلم"
    r"|رضي الله (?:عنهما|عنهم|عنهن|عنها|عنه)"
    r"|(?:عليهما|عليهم|عليها|عليه) السلام"
    r"|عز وجل|جل وعز|تبارك وتعالي|سبحانه وتعالي|جل جلاله"
)
_NON_LETTER = re.compile(r"[^ء-ي\s]")


def clean(text: str) -> str:
    """Remove invisible marks and spacing noise; keep everything a reader sees."""
    t = _INVISIBLE.sub("", text or "")
    t = _WS.sub(" ", t)
    t = _DOT_RUN.sub(".", t)
    t = _SPACE_BEFORE_PUNCT.sub(r"\1", t)
    return t.strip()


def letters(text: str) -> str:
    """Strip diacritics and unify alef/ya forms. Not length-preserving (diacritics go)."""
    return DIACRITICS.sub("", text).translate(_LETTER_MAP)


def normalize(text: str) -> str:
    """Matching form: bare letters, ة→ه, no honorifics, no punctuation, single spaces."""
    t = letters(clean(text)).translate(_TA_MARBUTA)
    t = _NON_LETTER.sub(" ", t)
    t = _WS.sub(" ", t)
    # Honorific patterns are written with ة→ه/ى→ي already applied.
    t = _HONORIFICS.sub(" ", t)
    return _WS.sub(" ", t).strip()


def skeleton(text: str) -> tuple[str, list[int]]:
    """Diacritic-free, letter-unified copy of `text` plus a map from each skeleton
    index to its index in `text`, so spans found on the skeleton map back exactly."""
    out, idx = [], []
    for i, ch in enumerate(text):
        if DIACRITICS.match(ch):
            continue
        out.append(ch)
        idx.append(i)
    idx.append(len(text))
    return "".join(out).translate(_LETTER_MAP), idx
