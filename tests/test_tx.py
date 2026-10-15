import re
import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import license_finder.tdlr as tdlr_mod

FIX = pathlib.Path(__file__).parent / "fixtures"


def test_tx_rows():
    html = (FIX / "tx_results.html").read_text(encoding="utf-8")
    rows = tdlr_mod._pipe_text(html)
    assert len(rows) >= 1, "no tx rows parsed"
    row = rows[0]
    assert re.search(r"^[A-Z]{2,6}[A-Z0-9]{0,10}$", row["license_number"])
    assert row["expire_date"], row


import re
