import re
import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import license_finder.ncbeec as ncbeec
import license_finder.nyc_dob as nyc_dob

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_nc_rows():
    html = (FIX / "nc_results.html").read_text(encoding="utf-8")
    rows = ncbeec.parse_rows(html)
    assert len(rows) >= 4, len(rows)
    for row in rows:
        assert re.fullmatch(r"[A-Z]\.\d{3,6}", row["account"]), row["account"]
        assert row["owner"], "owner missing"
    # Arrow Electric of Landis appears in the fixture
    assert any("lectric" in r["owner"] or "ector" in r["owner"] for r in rows), rows[:2]


def test_nc_status():
    assert ncbeec.normalize_status("License Not Active") == "Inactive"
    assert ncbeec.normalize_status("Active") == "Active"


def test_nyc_status():
    assert nyc_dob.normalize_status("ACTIVE") == "Active"
    assert nyc_dob.normalize_status("EXPIRED") == "Expired"
