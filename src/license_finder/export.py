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
