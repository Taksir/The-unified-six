from u6.site import depth_root, shown, slug, text_html


def hadith(**kw):
    h = {"segments": [{"ar": "قال", "en": "He said", "core": True, "in": ["a:1", "b:2"]},
                      {"ar": "زيادة", "en": "an addition", "core": False, "in": ["a:1"]},
                      {"ar": "قال أبو عيسى", "en": "Abu Isa said", "core": True, "in": ["a:1"]}]}
    h.update(kw)
    return h


def test_relative_roots_and_slugs():
    assert depth_root("index.html") == ""
    assert depth_root("h/U6-00001/index.html") == "../../"
    assert slug("Food, drink and hunting") == "food-drink-and-hunting"
    assert slug("Qur'anic commentary (tafsir)") == "qur-anic-commentary-tafsir"


def test_commentary_cut_and_italics():
    h = hadith(commentary_from=2)
    assert len(shown(h)) == 2
    out = text_html(h, "en", True)
    assert "Abu Isa" not in out
    assert 'class="seg add" data-i="1" data-in="a:1"' in out     # addition: italic, linked to its narrations
    assert 'class="seg" data-i="0"' in out                       # core text: upright


def test_italics_dropped_prints_upright():
    out = text_html(hadith(italics_dropped=True), "en", False)
    assert "seg add" not in out
