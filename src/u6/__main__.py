"""CLI: python -m u6 {fetch,ingest,eval-split,m1 <stage>}"""

import argparse
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def main() -> None:
    p = argparse.ArgumentParser(prog="u6")
    p.add_argument("--data", type=Path, default=ROOT / "data")
    sub = p.add_subparsers(dest="cmd", required=True)
    f = sub.add_parser("fetch", help="download pinned upstream editions into data/raw")
    f.add_argument("--record", action="store_true", help="(re)write checksums in data/sources.json")
    sub.add_parser("ingest", help="build data/narrations, data/concordance.csv, report")
    e = sub.add_parser("eval-split", help="score the isnad/matn splitter against LK Bukhari")
    e.add_argument("--lk", type=Path, default=ROOT / "data" / "external" / "LK-Hadith-Corpus")
    e.add_argument("--misses", type=int, default=40)
    m = sub.add_parser("m1", help="M1 pipeline stage (Bukhari + Muslim)")
    m.add_argument("stage", choices=["pairs", "gold-sample", "gold-label", "calibrate", "label",
                                     "cluster", "assemble", "sample", "gold-adjudicate", "evaluate"])
    m.add_argument("--no-embeddings", action="store_true")
    x = sub.add_parser("six", help="M2+M3 stage (all six books, incremental on M1)")
    x.add_argument("stage", choices=["pairs", "gold", "label", "cluster", "evaluate"])
    q = sub.add_parser("m4", help="M4 stage (translation and topics)")
    q.add_argument("stage", choices=["bakeoff", "translate", "topics", "check"])
    q.add_argument("--pilot", type=int, default=100)
    q.add_argument("--singles", action="store_true")
    a = p.parse_args()

    if a.cmd == "fetch":
        from .fetch import fetch
        fetch(a.data, record=a.record)
    elif a.cmd == "ingest":
        from .ingest import ingest
        ingest(a.data, ROOT / "docs")
    elif a.cmd == "m1":
        from . import m1
        if a.stage == "pairs":
            m1.stage_pairs(use_embeddings=not a.no_embeddings)
        else:
            getattr(m1, "stage_" + a.stage.replace("-", "_"))()
    elif a.cmd == "six":
        from . import six
        getattr(six, "stage_" + a.stage)()
    elif a.cmd == "m4":
        from . import m4
        if a.stage == "translate":
            m4.stage_translate(pilot=a.pilot, singles=a.singles)
        else:
            getattr(m4, "stage_" + a.stage)()
    elif a.cmd == "eval-split":
        from .evalsplit import evaluate, write_report
        r = evaluate(a.lk, a.data / "raw" / "ara-bukhari.json", a.misses)
        write_report(ROOT / "docs" / "reports" / "m0-split-eval.md", r)
        print(json.dumps(r["stats"], indent=1))


if __name__ == "__main__":
    main()
