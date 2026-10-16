import re
import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import license_finder.arl as arl

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_nc_plumbing_rows():
    html = (FIX / "nc_plumbing_results.html").read_text(encoding="utf-8")
    rows = arl.parse_rows(html, board="nc-plumbing", label=arl.NC_PLUMBING.label)
    assert len(rows) >= 3, len(rows)
    assert any("lumb" in (r["owner"] or "").lower() or "lumb" in (r["classification"] or "").lower()
               for r in rows), rows[:3]
    for row in rows:
        assert row["board"] == "nc-plumbing"
        assert row["status"] in ("Active", "Inactive", "Unknown")


def test_nc_general_rows():
    html = (FIX / "nc_general_results.html").read_text(encoding="utf-8")
    rows = arl.parse_rows(html, board="nc-general", label=arl.NC_GENERAL.label)
    assert len(rows) >= 5, len(rows)
    assert any(o.lower() for o in [r["owner"] for r in rows])
    statuses = {r["status"] for r in rows}
    assert statuses <= {"Active", "Inactive", "Unknown"}


def test_nc_electrical_rows():
    html = (FIX / "nc_electrical_results.html").read_text(encoding="utf-8")
    rows = arl.parse_rows(html, board="nc-electrical", label=arl.NC_ELECTRICAL.label)
    assert len(rows) >= 3, len(rows)


def test_arl_family_registered():
    bases = [b.base for b in arl.NC_FAMILY]
    assert len(set(bases)) == 3
    assert all(b.label for b in arl.NC_FAMILY)
