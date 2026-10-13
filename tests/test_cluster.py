from u6.cluster import _clauses, assemble, build_graph, guard
from u6.corpus import Doc
from u6.textnorm import normalize


def doc(i, book, seq, matn, kind="full"):
    m = normalize(matn)
    return Doc(i, book, seq, 1, kind, None, "", matn, "", matn, "", m)


def test_clauses_merge_short_pieces():
    cs = _clauses("إنما الأعمال بالنيات، وإنما لكل امرئ ما نوى، فمن كانت هجرته إلى الله ورسوله فهجرته إلى الله ورسوله.")
    assert len(cs) == 3


def test_assemble_roles_stars_and_italics():
    full = "إنما الأعمال بالنيات، وإنما لكل امرئ ما نوى، فمن كانت هجرته إلى دنيا يصيبها فهجرته إلى ما هاجر إليه"
    shorter = "إنما الأعمال بالنيات، وإنما لكل امرئ ما نوى، فمن كانت هجرته إلى امرأة ينكحها فهجرته إلى ما هاجر"
    frag = "إنما الأعمال بالنيات"
    docs = {d.id: d for d in (doc("bukhari:1", "bukhari", 0, full), doc("muslim:1", "muslim", 0, shorter),
                              doc("muslim:2", "muslim", 1, frag), doc("muslim:3", "muslim", 2, "", kind="ref"))}
    edges = [{"a": "bukhari:1", "b": "muslim:1", "label": "same"},
             {"a": "bukhari:1", "b": "muslim:2", "label": "b_in_a"},
             {"a": "muslim:2", "b": "muslim:3", "label": "same"}]
    g = build_graph(docs, edges)
    clusters, review = guard(g, docs)
    assert len(clusters) == 1 and not review
    h = assemble(clusters[0], docs, g)
    assert h["representative"] == "bukhari:1"
    roles = {m["id"]: m["role"] for m in h["members"]}
    assert roles["muslim:2"] == "partial" and roles["muslim:3"] == "partial"
    assert h["stars_display"] == "★★" and h["badge"] == "muttafaq"
    assert h["segments"][0]["core"] is True


def test_guard_splits_a_bridge_between_unrelated_groups():
    a = "من صام رمضان إيمانا واحتسابا غفر له ما تقدم من ذنبه"
    b = "لا يؤمن أحدكم حتى يحب لأخيه ما يحب لنفسه من الخير"
    compound = a + " " + b
    docs = {d.id: d for d in (doc("b:1", "bukhari", 0, a), doc("b:2", "bukhari", 1, a + " كله"),
                              doc("b:3", "bukhari", 2, compound),
                              doc("m:1", "muslim", 0, b), doc("m:2", "muslim", 1, b + " كله"))}
    edges = [{"a": "b:1", "b": "b:2", "label": "same"}, {"a": "b:1", "b": "b:3", "label": "a_in_b"},
             {"a": "b:3", "b": "m:1", "label": "b_in_a"}, {"a": "m:1", "b": "m:2", "label": "same"}]
    g = build_graph(docs, edges)
    clusters, review = guard(g, docs)
    assert len(clusters) == 2 and review[0]["bridge"] == "b:3"
