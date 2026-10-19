"""IL IDFPR adapter via the Illinois open-data portal (Socrata).

Verified (keyless):
  dataset pzzh-kp68 "Professional Licensing" - 4.37M rows, all IDFPR licenses:
    License Type, Description, License Number, License Status, Business flag,
    Title/First/Last, Business Name/DBA, Issue/Effective/Expiration dates,
    City/State/Zip/County, Specialty/Qualifier, discipline fields.
  Refreshed daily by IDFPR (rowsUpdatedAt moves with the register).

Trades included: ROOFING CONTRACTOR (34k), HOME INSPECTOR, plus city/county
geography on every row.
"""
from __future__ import annotations

import sys
import time
from typing import Iterator

import curl_cffi.requests as cr

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

RESOURCE = "pzzh-kp68"
SODA = f"https://data.illinois.gov/resource/{RESOURCE}.json"
PAGE_LIMIT = 50000
POLITE_DELAY = 0.45


def normalize_status(raw: str) -> str:
    up = (raw or "").strip().upper()
    if up in ("ACTIVE", "RENEWED", "ISSUED"):
        return "Active"
    if "NOT RENEWED" in up or "EXPIRED" in up:
        return "Expired"
    if "SUSPEND" in up:
        return "Suspended"
    if "REVOK" in up:
        return "Revoked"
    if "INACTIVE" in up:
        return "Inactive"
    return raw.title() if raw else ""


def count(where: str = "") -> int:
    http = cr.Session(impersonate="chrome")
    params = {"$select": "count(*)"}
    if where:
        params["$where"] = where
    r = http.get(SODA, params=params, timeout=120)
    r.raise_for_status()
    return int(r.json()[0]["count"])


def soda_where(prefix: str = "", class_filter: str = "", status: str = "") -> str:
    """Translate CLI flags into one SODA WHERE clause (server-side filtering)."""
    conds = []
    if prefix and prefix.strip() and prefix.strip().lower() not in ("all", "*", "%"):
        frag = prefix.replace("%", "%%").replace("'", "''").strip().upper()
        conds.append(f"upper(license_type) like '%{frag}%'")
    if class_filter:
        frag2 = class_filter.replace("%", "%%").replace("'", "''").strip().upper()
        conds.append(f"upper(description) like '%{frag2}%'")
    if status and status.lower() not in ("all", "any"):
        st = status.replace("'", "''").strip()
        conds.append(f"upper(license_status) = '{st.upper()}'")
    return " AND ".join(conds)


def all_rows(where: str = "", **kw) -> Iterator[dict]:
    """Stream the dataset (optionally filtered). status/body filters applied locally."""
    http = cr.Session(impersonate="chrome")
    offset = 0
    while True:
        params = {"$limit": PAGE_LIMIT, "$offset": offset}
        if where:
            params["$where"] = where
        r = http.get(SODA, params=params, timeout=180)
        r.raise_for_status()
        rows = r.json()
        if not rows:
            return
        for row in rows:
            yield {
                "license_number": row.get("license_number", ""),
                "name": " ".join(x for x in (row.get("first_name", ""), row.get("middle", ""), row.get("last_name", "")) if x) or row.get("business_name", ""),
                "business_name": row.get("business_name", ""),
                "board": row.get("license_type", ""),
                "classes": row.get("description", ""),
                "city": (row.get("city") or "").title(),
                "state": row.get("state", "IL"),
                "zip": row.get("zip", ""),
                "county": (row.get("county") or "").title(),
                "issue_date": row.get("effective_date", ""),
                "expire_date": row.get("expiration_date", ""),
                "status": normalize_status(row.get("license_status", "")),
                "business_flag": row.get("business", ""),
                "email": "",
                "phone": "",
            }
        offset += PAGE_LIMIT
        time.sleep(POLITE_DELAY)
