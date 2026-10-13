"""Registry of the six books, in canonical priority order (B, M, D, T, N, J)."""

from dataclasses import dataclass


@dataclass(frozen=True)
class Book:
    slug: str           # fawazahmed0 edition suffix and our ID prefix
    letter: str         # one-letter code used in the printed editions
    name_en: str
    name_ar: str
    numbering: str      # the standard numbering scheme that `n` follows
    author_kunya: str   # how the compiler is named in his own comments ("qala Abu ...")


BOOKS = (
    Book("bukhari", "B", "Sahih al-Bukhari", "صحيح البخاري",
         "Fath al-Bari / Fuad Abd al-Baqi (7563)", "أبو عبد الله"),
    Book("muslim", "M", "Sahih Muslim", "صحيح مسلم",
         "sunnah.com sequential (7563); FAB number in `n_fab`", "أبو الحسين"),
    Book("abudawud", "D", "Sunan Abi Dawud", "سنن أبي داود",
         "Muhyi al-Din Abd al-Hamid (5274)", "أبو داود"),
    Book("tirmidhi", "T", "Jami' al-Tirmidhi", "جامع الترمذي",
         "Ahmad Shakir (3956)", "أبو عيسى"),
    Book("nasai", "N", "Sunan al-Nasa'i", "سنن النسائي",
         "Abu Ghudda (5758)", "أبو عبد الرحمن"),
    Book("ibnmajah", "J", "Sunan Ibn Majah", "سنن ابن ماجه",
         "Fuad Abd al-Baqi (4341)", "أبو عبد الله"),
)

BY_SLUG = {b.slug: b for b in BOOKS}
