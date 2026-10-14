from u6.m4 import pack
from u6.m5 import classify_stub, commentary_from, volumes


def h(i, words, stars=1):
    return {"id": i, "stars": stars, "segments": [{"ar": " ".join(["كلمة"] * words), "core": True}]}


def test_pack_respects_word_limit_and_keeps_long_alone():
    packs = pack([h("a", 300), h("b", 300), h("c", 10), h("d", 900), h("e", 5)], max_words=600)
    assert [[x["id"] for x in p] for p in packs] == [["a", "b"], ["c"], ["d"], ["e"]]


def test_volumes_split_long_group_and_mark_continued():
    groups = [("★★", "", [h(f"x{k}", 10) for k in range(5)]), ("★", "", [h(f"y{k}", 10) for k in range(3)])]
    vols = volumes(groups, lambda x: 10, per_vol=30)
    assert [[(t, len(hs)) for t, _, hs in v] for v in vols] == [
        [("★★", 3)], [("★★ (continued)", 2), ("★", 1)], [("★ (continued)", 2)]]


def narr(text, split):
    return {"r:1": {"text": text, "split": split}}


def test_classify_stub_ref_and_extend():
    isnad = "حَدَّثَنَا فُلاَنٌ، عَنْ فُلاَنٍ، "
    ref = {"representative": "r:1"}
    assert classify_stub(ref, narr(isnad + "بِهَذَا.", (len(isnad), len(isnad) + 7)))[0] == "ref"
    long_tail = "جَلَسْتُ. وَحَدَّثَنِي إِسْحَاقُ قَالَ جَلَسْتُ إِلَى مَلإٍ مِنْ قُرَيْشٍ فَجَاءَ رَجُلٌ خَشِنُ الشَّعَرِ"
    kind, text = classify_stub(ref, narr(isnad + long_tail, (len(isnad), len(isnad) + 8)))
    assert kind == "extend" and text.startswith("جَلَسْتُ") and "قُرَيْشٍ" in text
    with_comment = "جَلَسْتُ مَعَ قَوْمٍ مِنْ أَهْلِ الْمَدِينَةِ فِي الْمَسْجِدِ. قَالَ أَبُو عِيسَى هَذَا حَدِيثٌ حَسَنٌ"
    _, text = classify_stub(ref, narr(isnad + with_comment, (len(isnad), len(isnad) + 8)))
    assert "عِيسَى" not in text


def test_commentary_from_only_at_segment_start_in_tirmidhi():
    segs = [{"ar": "قَالَ رَسُولُ اللَّهِ صلى الله عليه وسلم الْحَيَاءُ مِنَ الإِيمَانِ"},
            {"ar": "قَالَ هَذَا حَدِيثٌ حَسَنٌ صَحِيحٌ"}]
    assert commentary_from({"representative": "tirmidhi:1", "segments": segs}) == 1
    assert commentary_from({"representative": "bukhari:1", "segments": segs}) is None
    inside = [segs[0], {"ar": "وَالْبَذَاءُ مِنَ الْجَفَاءِ قَالَ هَذَا حَدِيثٌ حَسَنٌ"}]
    assert commentary_from({"representative": "tirmidhi:1", "segments": inside}) is None
