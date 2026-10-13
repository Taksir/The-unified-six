"""Build the owner's gold-set review page (published as a claude.ai artifact with a
`verdicts` collection in its db). Output: out/gold-review.html."""

import json

from .corpus import DATA, ROOT, load_docs
from .m1 import M1, auto_label, is_merge, read_jsonl


def build() -> str:
    th = json.loads((M1 / "thresholds.json").read_text())["thresholds"]
    docs = {d.id: d for d in load_docs()}
    recs = {}
    for b in ("bukhari", "muslim"):
        for line in (DATA / "narrations" / f"{b}.jsonl").open(encoding="utf-8"):
            r = json.loads(line)
            recs[r["id"]] = r

    def ref(i):
        r = recs[i]
        return f"Bukhārī {r['n']}" if r["book"] == "bukhari" else f"Muslim {r['n_fab'] or r['n']}"

    out = []
    for k, g in enumerate(read_jsonl(M1 / "gold.jsonl")):
        a = auto_label(g, th)
        system = a or g.get("sonnet_grouped", g["sonnet"])["label"]
        om, sm = is_merge(g["opus"]["label"]), is_merge(g["sonnet"]["label"])
        sysm = system in ("same", "partial", "a_in_b", "b_in_a")
        out.append({"k": f"p{k:03d}", "pid": g["pid"], "a": ref(g["a"]), "b": ref(g["b"]),
                    "at": docs[g["a"]].matn or docs[g["a"]].text, "bt": docs[g["b"]].matn or docs[g["b"]].text,
                    "an": docs[g["a"]].isnad_last, "bn": docs[g["b"]].isnad_last,
                    "opus": g["opus"]["label"], "sonnet": g["sonnet"]["label"], "system": system,
                    "by": "rule" if a else "Sonnet", "flag": "conflict" if (om != sm or om != sysm) else "",
                    "stratum": g["stratum"]})
    out.sort(key=lambda x: (x["flag"] != "conflict", x["k"]))
    data = json.dumps(out, ensure_ascii=False).replace("</", "<\\/").replace("�", "\\ufffd")
    tpl = (ROOT / "docs" / "review" / "gold-review.template.html").read_text()
    html = tpl.replace("/*DATA*/[]", data)
    (ROOT / "out").mkdir(exist_ok=True)
    (ROOT / "out" / "gold-review.html").write_text(html)
    return html
