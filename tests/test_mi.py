import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import license_finder.mi_accela as mi

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_mi_rows():
    text = (FIX / "mi_export.csv").read_text(encoding="utf-8")
    rows = mi.parse_csv_rows(text, "Electrical Contractor")
    assert len(rows) >= 10, len(rows)
    row = rows[0]
    assert row["license_number"].startswith("610")
    assert row["board"] == "Electrical Contractor"
    assert row["state"] == "MI"
    assert row["city"], row
