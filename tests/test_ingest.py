import json
from pathlib import Path

import pytest

from u6.books import BOOKS
from u6.grades import tirmidhi_grade
from u6.ingest import muslim_fab, number_str, sunnah_url

DATA = Path(__file__).resolve().parents[1] / "data"


def test_number_str():
    assert number_str(7) == "7" and number_str(7.0) == "7" and number_str(402.2) == "402.2"


def test_muslim_fab():
    assert muslim_fab("8.01") == "8a"
    assert muslim_fab("8.26") == "8z"
    assert muslim_fab("8.27") == "8aa"
    assert muslim_fab("9") == "9"
    assert muslim_fab(None) is None


def test_sunnah_url():
    assert sunnah_url("bukhari", "1", None) == "https://sunnah.com/bukhari:1"
    assert sunnah_url("bukhari", "402.2", None) == ""
    assert sunnah_url("muslim", "93", "8a") == "https://sunnah.com/muslim:8a"


def test_tirmidhi_grade():
    assert tirmidhi_grade("قال أبو عيسى هذا حديث حسن صحيح.")["en"] == "hasan sahih"
    assert tirmidhi_grade("قال أبو عيسى حديث ابن عباس حديث حسن غريب.")["en"] == "hasan gharib"
    assert tirmidhi_grade("قال أبو عيسى هذا حديث لا نعرفه إلا من هذا الوجه.") is None


@pytest.mark.skipif(not (DATA / "narrations" / "bukhari.jsonl").exists(), reason="run `python -m u6 ingest` first")
def test_built_data_integrity():
    expected = {"bukhari": 7589, "muslim": 7563, "abudawud": 5274,
                "tirmidhi": 3998, "nasai": 5765, "ibnmajah": 4343}
    seen = set()
    for b in BOOKS:
        recs = [json.loads(l) for l in (DATA / "narrations" / f"{b.slug}.jsonl").open(encoding="utf-8")]
        assert len(recs) == expected[b.slug]
        for r in recs:
            assert r["id"] not in seen
            seen.add(r["id"])
            a, z = r["split"]
            assert 0 <= a <= z <= len(r["text"])
            assert (r["kind"] == "empty") == (r["text"] == "")
    assert len(seen) == sum(expected.values())
