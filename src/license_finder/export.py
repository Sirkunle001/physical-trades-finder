"""Normalized CSV export + dedupe + funnel counts (the clean-output contract)."""
from __future__ import annotations

import csv
import dataclasses
from collections import Counter
from typing import Iterable

from .cslb import LicenseRow

FIELDS = [
    "license_number",
    "name",
    "name_type",
    "classes",
    "city",
    "state",
    "zip",
    "street",
    "phone",
    "entity",
    "status",
    "issue_date",
    "expire_date",
]


def dedupe(rows: Iterable[LicenseRow]) -> list[LicenseRow]:
    seen: dict[str, LicenseRow] = {}
    for row in rows:
        key = row.license_number
        if key and key not in seen:
            seen[key] = row
    return list(seen.values())


def funnel(counts: dict) -> str:
    line = " -> ".join(f"{k}:{v}" for k, v in counts.items())
    return f"funnel: {line}"


def write_csv(rows: list[LicenseRow], out_path: str, source_col: str = "") -> Counter:
    cols = list(FIELDS) + (["source"] if source_col else [])
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for r in rows:
            d = dataclasses.asdict(r)
            vals = [d[c] for c in FIELDS]
            if source_col:
                vals.append(source_col)
            w.writerow(vals)
    return Counter()  # callers track counts


def dedupe_rows(rows: list[dict]) -> list[dict]:
    """Dedupe dict rows. License/account number is the primary key; when a row has
    none, a composite key keeps distinct records apart (name alone collapses people)."""
    seen: set[str] = set()
    out: list[dict] = []
    for row in rows:
        key = str(row.get("license_number") or row.get("account") or "")
        if not key:
            key = "|".join(str(row.get(k, "")) for k in ("board", "name", "city", "zip", "expire_date"))
        if not key.strip("|"):
            continue
        if key in seen:
            continue
        seen.add(key)
        out.append(row)
    return out


def write_csv_rows(dict_rows: list[dict], out_path: str) -> None:
    """Write arbitrary-board dict rows with a normalized column order."""
    cols: list[str] = []
    for row in dict_rows:
        for key in row:
            if key not in cols:
                cols.append(key)
    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(cols)
        for row in dict_rows:
            w.writerow([row.get(c, "") for c in cols])
