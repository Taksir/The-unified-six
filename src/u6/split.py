"""Rule-based isnad / matn / tail segmentation of one narration.

Input is `clean()`ed Arabic (tashkeel kept). Matching runs on a diacritic-free skeleton
whose offsets map back to the input, so the returned segments keep their tashkeel.

Conventions (see docs/methodology/isnad-matn-split.md):
- isnad: the transmission chain, including the last narrator's speech verb
  ("... عن أبي هريرة، قال") and a Prophet link ("سمعت رسول الله ﷺ يقول").
- matn: the reported content, up to the first tail sentence.
- tail: everything after the main matn that is not part of it: further chains
  ("حدثنا ... بهذا الإسناد مثله"), the compiler's comments ("قال أبو عيسى ..."),
  "وفي الباب" lists, and Bukhari's mutaba'at ("تابعه ...").
- kind: "full", "ref" (points back to the previous narration: "بهذا الإسناد مثله"
  with no own text), "ref_variant" (points back but adds/changes wording), "empty".
"""

import re
from dataclasses import dataclass, field

from .textnorm import skeleton

_V = "(?:و|ف)?"  # optional conjunction prefix

TRANSMIT = re.compile(
    rf"^{_V}(?:(?:حدث|اخبر|انبا)(?:ت|تا|وا|ا)?(?:نا|ني|ه|ها|هم|هما|كم|ناه|نيه|ناها|وه|اه)?"
    r"|ثنا"
    r"|سمعت|سمع|سمعا|سمعوا|سمعنا|سمعته|سمعه|سمعها|سمعاه"
    r"|عن|يحدث|تحدث|يحدثه|يحدثان|يحدثون|يخبر|تخبر|يرفعه|رفعه)$"
)
SAY = re.compile(rf"^{_V}(?:قال|قالت|قالا|قالوا|يقول|تقول|يقولان|يقولون|قلت|قلنا)$")
CONNECT = re.compile(rf"^{_V}(?:انه|انها|انهما|انهم|انهن)$")
AN = re.compile(rf"^{_V}ان$")
NAME_START = re.compile(r"^و?(?:او|ابو|ابي|ابا|ابن|بن|عبد|ام|بنت|اخيه|ابيه|جده|عمه|خاله|امه|مولي)$")
PROPHET = re.compile(r"^(?:رسول|النبي|نبي)$")
INDEFINITE = {"رجلا", "امراة", "اعرابيا", "ناسا", "قوما", "رجالا", "نفرا", "يهوديا", "غلاما", "جارية"}

TAIL_CHAIN = re.compile(
    rf"^{_V}(?:حدثنا|حدثني|حدثناه|حدثنيه|اخبرنا|اخبرني|اخبرناه|انبانا|تابعه|وتابعه|رواه|ورواه)$"
)
# Compilers' (and their transmitters') kunyas: Bukhari, Muslim's transmitter Ibrahim
# ibn Sufyan, Abu Dawud, Tirmidhi, Nasa'i, Ibn Majah's transmitter al-Qattan.
TAIL_COMMENT = re.compile(
    r"^(?:و|ثم )?قال (?:ابو (?:عبد الله|اسحاق|داود|عيسي|عبد الرحمن|الحسن|الحسين)|مسلم|البخاري)\b"
    r"|^(?:و|قال و)في الباب\b"
)
REF = re.compile(r"بهذا الاسناد|بهذا الحديث|باسناده|باسنادهما|بمثله|مثله|بنحوه|نحوه|بمعناه|بمثل حديث|نحو حديث|بمعني حديث")
REF_WORDS = {"نحوه", "مثله", "بمثله", "بنحوه", "بمعناه"}
_TOKEN = re.compile(r"[ء-ي]+|[\".،,\-{}]")


@dataclass
class Split:
    isnad: str
    matn: str
    tail: str
    kind: str
    flags: list[str] = field(default_factory=list)
    bounds: tuple[int, int] = (0, 0)  # text[:a] isnad, text[a:b] matn, text[b:] tail


def segments(text: str, bounds) -> tuple[str, str, str]:
    """(isnad, matn, tail) of a stored record from its text and `split` offsets."""
    a, b = bounds
    return _strip(text[:a]), _strip(text[a:b]), _strip(text[b:])


def _tokens(skel: str):
    return [(m.group(), m.start(), m.end()) for m in _TOKEN.finditer(skel)]


def _dash_masked(toks) -> set[int]:
    """Token indices inside " - gloss - " asides (e.g. "- يعني ابن إسحاق -")."""
    masked, open_at = set(), None
    for i, (t, _, _) in enumerate(toks):
        if t == "-":
            if open_at is None:
                open_at = i
            else:
                masked.update(range(open_at, i + 1))
                open_at = None
        elif t == '"' and open_at is not None:
            break  # never mask across the start of quoted speech
    return masked


HONORIFIC_WORDS = {"صلي", "عليه", "وسلم", "رضي", "عنه", "عنها", "عنهما", "عنهم", "السلام"}


def _words_ahead(toks, i, masked, n, stop='".'):
    """Up to n word tokens after i (honorific words skipped), stopping at `stop`."""
    out = []
    for j in range(i + 1, len(toks)):
        t = toks[j][0]
        if t in stop:
            break
        if j in masked or t in "،,-{}" or t in HONORIFIC_WORDS:
            continue
        out.append((j, t))
        if len(out) == n:
            break
    return out


def _next_token(toks, i) -> int:
    """Index of the first word or quote after i (skipping commas and colons)."""
    for j in range(i + 1, len(toks)):
        if toks[j][0] not in "،,-":
            return j
    return len(toks)


def _is_chain_verb(t: str) -> bool:
    return bool(TRANSMIT.match(t)) and t not in ("عن", "وعن")


def _chunk_is_chain(toks, i, masked) -> bool:
    """Does the comma-chunk starting at i read as a chain link (name + verb)?"""
    words = [(i, toks[i][0])] + _words_ahead(toks, i, masked, 6)
    for pos, (_, w) in enumerate(words):
        if _is_chain_verb(w) and pos <= 5:
            return True
        if w in ("عن", "وعن") and pos <= 2:
            return True
    return False


def _find_matn_start(toks) -> tuple[int | None, list[str]]:
    masked = _dash_masked(toks)
    seen = False
    prev = ""
    chunk_start = True  # are we at the first word after a comma?
    for i, (t, _, _) in enumerate(toks):
        if i in masked:
            continue
        if t in "،,":
            chunk_start = True
            continue
        if t == '"':
            if seen:
                return i, []
            continue
        if t in ".-{}":
            if t == "." and seen:
                ahead = _words_ahead(toks, i, masked, 4)
                if ahead and (TRANSMIT.match(ahead[0][1]) or ahead[0][1] == "ح"
                              or any(_is_chain_verb(w) or w in ("عن", "وعن") for _, w in ahead[1:3])):
                    continue  # the chain resumes after the stop ("... نحوه. قال أخبرني ...")
                return i + 1, ["boundary_at_stop"]
            continue
        at_chunk = chunk_start
        chunk_start = False
        last, prev = prev, t
        if TRANSMIT.match(t) or t in ("ح", "كتب"):
            seen = True
            continue
        if not seen:
            continue
        ahead = _words_ahead(toks, i, masked, 4)
        nxt = ahead[0][1] if ahead else ""
        if PROPHET.match(t) and TRANSMIT.match(last):
            # "سمعت رسول الله ﷺ يقول" -> the speech verb decides; with no verb the
            # Prophet link opens the matn ("سمعت النبي ﷺ قرأ ...").
            rest = [w for _, w in _words_ahead(toks, i, masked, 7)
                    if w not in ("الله", "صلي", "عليه", "وسلم")]
            if rest and (SAY.match(rest[0]) or _is_chain_verb(rest[0])):
                continue
            return i - 1, ["prophet_link"]
        if SAY.match(t):
            if any(_is_chain_verb(w) or w == "كتب" for _, w in ahead[:3]) \
                    or (len(ahead) > 1 and ahead[1][1] in ("عن", "وعن")) \
                    or (len(ahead) > 2 and ahead[2][1] in ("عن", "وعن") and NAME_START.match(ahead[0][1])):
                continue  # "قالا حدثنا", "قال عبيد الله حدثنا", "قال الزهري عن"
            far = _words_ahead(toks, i, masked, 8, stop='".،,')
            if far and (NAME_START.match(far[0][1]) or (len(far) > 1 and far[1][1] in ("بن", "ابن"))) \
                    and any(_is_chain_verb(w) for _, w in far[:8]):
                continue  # "قال عبد الله بن أبي بكر أنه سمع ..."
            return _next_token(toks, i), []
        if CONNECT.match(t):
            if nxt and (SAY.match(nxt) or TRANSMIT.match(nxt)):
                continue  # "أنها قالت", "أنه سمع"
            return i, []
        if AN.match(t):
            if PROPHET.match(nxt):
                return i, []
            words = [w for _, w in _words_ahead(toks, i, masked, 12)]
            reach = 11 if (NAME_START.match(nxt) or (len(words) > 1 and words[1] in ("بن", "ابن"))) else 7
            if any(_is_chain_verb(w) for w in words[:reach]):
                continue  # "أن أبا هريرة حدثه"
            if nxt and nxt not in INDEFINITE and (
                NAME_START.match(nxt) or (len(words) > 1 and words[1] in ("بن", "ابن"))
                or (len(words) > 1 and SAY.match(words[1]))
            ) and any(SAY.match(w) for w in words[:7]):
                continue  # "أن أبا هريرة قال", "أن عائشة قالت"
            return i, []
        if t in REF_WORDS and any(_is_chain_verb(w) for _, w in _words_ahead(toks, i, masked, 3, stop='"')):
            continue  # "... عن الزهري، نحوه. قال أخبرني ..." — a parallel chain, then the chain resumes
        if at_chunk and not NAME_START.match(t) and nxt not in ("بن", "ابن") \
                and not _chunk_is_chain(toks, i, masked):
            # A comma-chunk that opens with neither a transmission term nor a name.
            return i, ["boundary_at_chunk"]
    return None, ["no_boundary"]


def _sentence_starts(toks, start):
    """Indices of tokens that begin a sentence (after a '.' outside quotes)."""
    in_quote = False
    quotes = sum(1 for t, _, _ in toks[start:] if t == '"')
    use_parity = quotes % 2 == 0
    out = []
    for i in range(start, len(toks)):
        t = toks[i][0]
        if t == '"':
            in_quote = not in_quote
        elif t == "." and (not in_quote or not use_parity) and i + 1 < len(toks):
            out.append(i + 1)
    return out


def _find_tail_start(skel, toks, matn_start) -> int | None:
    for s in _sentence_starts(toks, matn_start):
        if s <= matn_start:
            continue
        words = [t for t, _, _ in toks[s:s + 8] if t not in "،,\"-{}."]
        if not words:
            continue
        head = " ".join(words)
        if TAIL_CHAIN.match(words[0]) or TAIL_COMMENT.match(head):
            return s
        # Bukhari ta'liq: "وقال معاذ حدثنا شعبة ..."
        if SAY.match(words[0]) and any(TRANSMIT.match(w) and w not in ("عن", "وعن") for w in words[1:4]):
            return s
    return None


def _strip(s: str) -> str:
    return s.strip(" ،,:-.")


def split_narration(text: str) -> Split:
    if not text.strip():
        return Split("", "", "", "empty", [], (0, 0))
    skel, idx = skeleton(text)
    toks = _tokens(skel)
    if not toks:
        return Split("", text, "", "full", ["no_tokens"], (0, len(text)))

    flags: list[str] = []
    ms, f = _find_matn_start(toks)
    flags += f
    if ms is None:
        # No boundary: treat everything as matn only if no chain was seen at all.
        if any(TRANSMIT.match(t) for t, _, _ in toks):
            ms = len(toks)
        else:
            ms = 0
            flags.append("no_isnad")
    ts = _find_tail_start(skel, toks, ms) if ms < len(toks) else None

    def off(tok_i):  # token index -> offset in `text`
        return len(text) if tok_i >= len(toks) else idx[toks[tok_i][1]]

    a, b = off(ms), off(ts) if ts is not None else len(text)
    isnad, matn, tail = segments(text, (a, b))

    # A back-reference ("بهذا الإسناد مثله") counts only at the seam between chain
    # and text; elsewhere "نحوه" just annotates a parallel chain inside the isnad.
    seam = " ".join(t for t, _, _ in toks[max(0, ms - 6): ms + 12] if t not in "\".،,-{}")
    kind = "full"
    if REF.search(seam) or (not matn.strip() and REF.search(skel)):
        own = _TOKEN.findall(REF.sub(" ", skeleton(matn)[0]))
        own = [w for w in own if w not in "\".،,-{}"]
        kind = "ref" if len(own) < 8 else "ref_variant"
    if not matn:
        flags.append("empty_matn")
    return Split(isnad, matn, tail, kind, flags, (a, b))


_PROPHET_FORMULA = re.compile(
    r"^(?:(?:و|ف)?(?:قال|قالت|سمعت|سمع|عن|ان|انه|انها|انهم)\s+)*"
    r"(?:(?:رسول الله|النبي|نبي الله)\s+(?:صلي الله عليه وسلم\s+)?)"
    r"(?:(?:انه\s+)?(?:قال|يقول|كان يقول|قال لنا|قال لي)\s+)?"
)


def strip_prophet_formula(normalized_matn: str) -> str:
    """Drop a leading "قال رسول الله ﷺ" / "سمعت النبي ﷺ يقول" from a normalize()d matn."""
    return _PROPHET_FORMULA.sub("", normalized_matn, count=1)


_LINK = re.compile(
    r"\b(?:و|ف)?(?:(?:حدث|اخبر|انبا)(?:ت|تا|وا|ا)?(?:نا|ني|ه|ها|هم|هما|كم|ناه|نيه|وه|اه)?"
    r"|سمعت|سمع|سمعا|سمعوا|عن|ح)\b"
)
_TRAILING = re.compile(
    r"(?:\s+(?:(?:و|ف)?(?:قال|قالت|قالا|قالوا|يقول|تقول|انه|انها|انهما|انهم|ان)"
    r"|يحدث|يحدثه|يرفعه|علي المنبر))+$"
)
_HONORIFIC = re.compile(r"\s*(?:رضي الله (?:عنهما|عنهم|عنها|عنه)|صلي الله عليه وسلم|عليه السلام)")
_PROPHET_END = re.compile(r"(?:رسول الله|النبي|نبي الله)(?:\s+صلي الله عليه وسلم)?$")


def last_narrator(isnad: str) -> str:
    """Heuristic name of the last transmitter before the matn (usually the Companion).

    Works on the diacritic-free form; returns "" when no chain is present."""
    s = re.sub(r"[^\u0621-\u064a ]", " ", skeleton(isnad)[0])
    s = re.sub(r"\s+", " ", _HONORIFIC.sub(" ", " " + s)).strip()
    s = _TRAILING.sub("", " " + s).strip()
    if _PROPHET_END.search(s):  # chain ends "... سمعت رسول الله ﷺ": drop that link
        s = _TRAILING.sub("", " " + _PROPHET_END.sub("", s).strip()).strip()
        s = re.sub(r"(?:^|\s)\S+$", "", s) if _LINK.fullmatch(s.split()[-1] if s else "") else s
    parts = [p.strip() for p in _LINK.split(s) if p.strip()]
    if not parts:
        return ""
    name = _TRAILING.sub("", " " + parts[-1]).strip()
    return " ".join(name.split()[:6])
