"""Download the pinned upstream Arabic editions into data/raw/ and verify checksums.

The source is fawazahmed0/hadith-api (Unlicense), pinned to one commit so that every
rebuild sees identical input. `data/sources.json` records the commit and the sha256 of
each file; a first run with `--record` writes the checksums, later runs verify them.
"""

import hashlib
import json
import urllib.request
from pathlib import Path

from .books import BOOKS

REPO = "fawazahmed0/hadith-api"
COMMIT = "df57907be35291c91ad6a6691180e22ca9920784"
URL = "https://raw.githubusercontent.com/{repo}/{commit}/editions/{edition}.json"


def edition_name(slug: str) -> str:
    return f"ara-{slug}"


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def fetch(data_dir: Path, record: bool = False) -> dict:
    raw = data_dir / "raw"
    raw.mkdir(parents=True, exist_ok=True)
    manifest_path = data_dir / "sources.json"
    manifest = json.loads(manifest_path.read_text()) if manifest_path.exists() else {}
    if manifest and manifest.get("commit") != COMMIT and not record:
        raise SystemExit(f"sources.json pins {manifest.get('commit')}, code pins {COMMIT}; rerun with --record")

    files = {}
    for book in BOOKS:
        ed = edition_name(book.slug)
        dest = raw / f"{ed}.json"
        expected = manifest.get("files", {}).get(ed, {}).get("sha256")
        if not (dest.exists() and expected and sha256(dest) == expected):
            url = URL.format(repo=REPO, commit=COMMIT, edition=ed)
            print(f"fetch {url}")
            with urllib.request.urlopen(url, timeout=120) as r:
                dest.write_bytes(r.read())
        digest = sha256(dest)
        if expected and digest != expected and not record:
            raise SystemExit(f"checksum mismatch for {ed}: {digest} != {expected}")
        files[ed] = {"sha256": digest, "bytes": dest.stat().st_size}

    if record or not manifest:
        manifest = {
            "source": REPO,
            "license": "Unlicense (repository); upstream provenance undocumented, see docs/research/data-sources.md",
            "commit": COMMIT,
            "url_template": URL.replace("{repo}", REPO).replace("{commit}", COMMIT),
            "files": files,
        }
        manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n")
    return manifest
