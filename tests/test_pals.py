import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import license_finder.pals as pals_mod

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_pals_rows():
    xml = (FIX / "pa_pals_results.xml").read_text(encoding="utf-8")
    rows = pals_mod.parse_rows(xml, page=1)
    assert len(rows) == 50, len(rows)
    first = rows[0]
    assert first["license_number"].startswith("AA")
    assert "SMITH" in first["name"].upper()
    assert first["status"] == "Active", first
    assert first["board"], first
    assert first["city"], first


def test_pals_status_norm():
    assert pals_mod.normalize_status("Active") == "Active"
    assert pals_mod.normalize_status("ExPIRED") == "Expired"
