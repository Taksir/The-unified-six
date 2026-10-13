"""Extract al-Tirmidhi's own grading statement ("قال أبو عيسى: هذا حديث حسن صحيح").

Only the standard ḥasan/ṣaḥīḥ/gharīb vocabulary is captured. Other verdicts
("مرسل", "لا يصح", "إسناده ليس بمتصل") and entries he leaves ungraded yield None;
refining those is M2 work.
"""

import re

from .textnorm import normalize

_TERMS = {"حسن": "hasan", "صحيح": "sahih", "غريب": "gharib"}
_G = r"((?:حسن|صحيح|غريب)(?: (?:حسن|صحيح|غريب)){0,2})\b"
_AFTER_ABU_ISA = re.compile(r"قال ابو عيسي(?: \S+){0,6}? حديث(?: \S+){0,4}? " + _G)
_HADHA = re.compile(r"\bهذا حديث " + _G)


def tirmidhi_grade(text: str) -> dict | None:
    """First grade phrase in `text` (pass the tail, or the full text as a fallback)."""
    t = normalize(text)
    g = _AFTER_ABU_ISA.search(t) or _HADHA.search(t)
    if not g:
        return None
    words = g.group(1).split()
    return {"ar": g.group(1), "en": " ".join(_TERMS[w] for w in words)}
