from u6.textnorm import clean, normalize, skeleton


def test_clean_removes_bidi_marks_and_spacing():
    raw = "قَالَ ، حَدَّثَنَا ‏\"‏ إِنَّمَا ‏\"‏‏.‏"
    assert clean(raw) == 'قَالَ، حَدَّثَنَا " إِنَّمَا ".'


def test_normalize_strips_tashkeel_letters_and_honorifics():
    s = "عَنْ عَائِشَةَ رضى الله عنها قَالَتْ قَالَ رَسُولُ اللَّهِ صلى الله عليه وسلم إِنَّ الصَّلاَةَ"
    assert normalize(s) == "عن عائشه قالت قال رسول الله ان الصلاه"


def test_normalize_prefers_longest_honorific():
    # "عنهما" must not be cut down to "عنه" + leftover "ما"
    assert normalize("عن ابن عمر رضي الله عنهما قال") == "عن ابن عمر قال"


def test_skeleton_offsets_map_back():
    text = "حَدَّثَنَا مُسَدَّدٌ"
    sk, idx = skeleton(text)
    assert sk == "حدثنا مسدد"
    j = sk.index("مسدد")
    assert text[idx[j]:].startswith("مُ")
