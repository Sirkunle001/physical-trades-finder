import sys, pathlib

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parents[1] / "src"))

import license_finder.il_soda as il

import pytest


def test_il_status_norm():
    assert il.normalize_status("Active") == "Active"
    assert il.normalize_status("NOT RENEWED") == "Expired"
    assert il.normalize_status("Cancelled") == "Cancelled"


def test_il_count_mock():
    # the register is 4.37M rows; a filtered query must stay under the SODA cap
    assert il.PAGE_LIMIT == 50000
