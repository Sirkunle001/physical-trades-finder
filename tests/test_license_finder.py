import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import pytest

import license_finder.cslb as cslb_mod
from license_finder.cslb import LicenseRow, normalize_status, parse_detail
from license_finder.export import dedupe, write_csv

FIX = pathlib.Path(__file__).parent / "fixtures"
ROW_ID = "MainContent_dlMain"


@pytest.fixture(scope="module")
def results_html():
    return (FIX / "results_ab.html").read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def detail_html():
    return (FIX / "license_detail.html").read_text(encoding="utf-8")


def _parse_rows_from_fixture(html: str):
    import re

    pat = re.compile(rf'id="{ROW_ID}_(lblName|lblType|lblLicenseStatus|lblCity)_(\d+)"[^>]*>([^<]*)<')
    licpat = re.compile(rf'id="{ROW_ID}_hlLicense_(\d+)"\s+href="[^"]*LicNum=(\d+)"')
    vals: dict[int, dict] = {}
    for fid, idx, val in pat.findall(html):
        vals.setdefault(int(idx), {})[fid] = val.strip()
    out = []
    for idx, lic in licpat.findall(html):
        d = vals.get(int(idx), {})
        out.append(LicenseRow(license_number=lic, name=d.get("lblName", ""),
                              name_type=d.get("lblType", ""),
                              city=cslb_mod.normal_city(d.get("lblCity", "")),
                              status=normalize_status(d.get("lblLicenseStatus", ""))))
    return out


def test_rows_parsed(results_html):
    rows = _parse_rows_from_fixture(results_html)
    assert 30 <= len(rows) <= 60, f"got {len(rows)}"
    assert rows[0].name and rows[0].license_number.isdigit()
    assert any(r.status == "Active" for r in rows)


def test_status_normalization():
    cases = {
        "Active": "Active",
        "Expired": "Expired",
        "Cancelled": "Cancelled",
        "Inactive-Verifiable Lic": "Inactive",
    }
    for raw, expected in cases.items():
        assert normalize_status(raw) == expected, raw


def test_detail_parse(detail_html):
    d = parse_detail(detail_html)
    assert d["business"]["city"], d
    assert d["business"]["state"] == "CA"
    assert d["business"]["zip"].isdigit() and len(d["business"]["zip"]) == 5
    assert d["business"]["phone"].startswith("(")
    assert d["entity"], d
    assert d["classes"], d
    # the fixture license is expired
    assert "expired" in d["status"].lower() or not d["status"]


def test_dedupe():
    a = LicenseRow(license_number="1", name="A")
    b = LicenseRow(license_number="1", name="A")
    c = LicenseRow(license_number="2", name="C")
    assert len(dedupe([a, b, c])) == 2


def test_csv_roundtrip(tmp_path):
    rows = [LicenseRow(license_number="9", name="X", city="Lodi", status="Active")]
    out = tmp_path / "o.csv"
    write_csv(dedupe(rows), str(out))
    txt = out.read_text(encoding="utf-8")
    assert "license_number,name" in txt
    assert "9,X" in txt
