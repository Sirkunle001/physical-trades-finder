import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import license_finder.fl_cilb as fl

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_fl_rows():
    text = (FIX / "fl_CONSTRUCTIONLICENSE_1.csv.slice").read_text(encoding="utf-8")
    rows = []
    for line in text.splitlines()[:4]:
        import csv, io

        for cells in csv.reader(io.StringIO(line)):
            row = fl.parse_row(cells)
            if row:
                rows.append(row)
    assert len(rows) >= 2, len(rows)
    row = rows[0]
    assert row["license_number"].startswith("CBC")
    assert row["state"] == "FL"
    assert row["city"], row
    assert row["expire_date"], row
