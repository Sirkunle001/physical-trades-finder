"""NYC DOB construction-trades licenses adapter.

Verified dataset: SODA (keyless), dataset id t8hj-ruu2, 103,276 rows.
Fields: license_sl_no, license_type, license_number, last_name, first_name, license_status
"""
from __future__ import annotations

import re
import sys
import time
from typing import Iterator

import curl_cffi.requests as cr

RESOURCE = "t8hj-ruu2"
SODA = f"https://data.cityofnewyork.us/resource/{RESOURCE}.json"
COUNT_URI = f"{SODA}?$select=count(*)"
POLITE_DELAY = 0.3
PAGE_LIMIT = 50000

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


def normalize_status(raw: str) -> str:
    up = (raw or "").strip().upper()
    if up.startswith("ACT"):
        return "Active"
    if up.startswith("EXP"):
        return "Expired"
    if up.startswith("SUS"):
        return "Suspended"
    return raw.title() if raw else ""


def count() -> int:
    http = cr.Session(impersonate="chrome124")
    r = http.get(COUNT_URI, timeout=30)
    r.raise_for_status()
    return int(r.json()[0]["count"])


def all_rows(**kw) -> Iterator[dict]:
    """Stream every row of the dataset (status/type filters optional)."""
    http = cr.Session(impersonate="chrome124")
    offset = 0
    while True:
        params = {"$limit": PAGE_LIMIT, "$offset": offset}
        if kw.get("license_type"):
            params["license_type"] = kw["license_type"]
        if kw.get("status"):
            params["license_status"] = kw["status"]
        r = http.get(SODA, params=params, timeout=90)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return
        for row in rows:
            yield {
                "license_number": row.get("license_number", ""),
                "name": f"{row.get('first_name','').strip()} {row.get('last_name','').strip()}".strip(),
                "license_type": row.get("license_type", ""),
                "status": normalize_status(row.get("license_status", "")),
                "sl_no": row.get("license_sl_no", ""),
            }
        offset += PAGE_LIMIT
        time.sleep(POLITE_DELAY)
