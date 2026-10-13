"""CLI: python -m u6 {fetch,ingest,eval-split}"""

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
    a = p.parse_args()

    if a.cmd == "fetch":
        from .fetch import fetch
        fetch(a.data, record=a.record)
    elif a.cmd == "ingest":
        from .ingest import ingest
        ingest(a.data, ROOT / "docs")
    elif a.cmd == "eval-split":
        from .evalsplit import evaluate, write_report
        r = evaluate(a.lk, a.data / "raw" / "ara-bukhari.json", a.misses)
        write_report(ROOT / "docs" / "reports" / "m0-split-eval.md", r)
        print(json.dumps(r["stats"], indent=1))


if __name__ == "__main__":
    main()
