import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import license_finder.export as export
import license_finder.mi_accela as mi
import license_finder.tdlr as tdlr


def test_expiry_status_derivation():
    for fn in (tdlr.status_from_expiry, mi.status_from_expiry):
        assert fn("01/11/2026") == "Expired"
        assert fn("12/31/2099") == "Active"
        assert fn("") == ""
        assert fn("garbage") == ""


def test_dedupe_rows_keeps_blank_license_records_apart():
    a = {"license_number": "", "board": "X", "name": "JOHN SMITH", "city": "A", "zip": "1", "expire_date": "01/01/2030"}
    b = {"license_number": "", "board": "X", "name": "JOHN SMITH", "city": "B", "zip": "2", "expire_date": "01/01/2030"}
    c = dict(a)
    assert len(export.dedupe_rows([a, b, c])) == 2


def test_dedupe_rows_license_key():
    rows = [{"license_number": "1", "name": "A"}, {"license_number": "1", "name": "A2"}, {"license_number": "2", "name": "B"}]
    assert len(export.dedupe_rows(rows)) == 2
