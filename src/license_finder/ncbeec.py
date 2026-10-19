"""NC NCBEEC (electrical contractors) adapter.

Verified flow (keyless):
  POST https://arls-public.ncbeec.org/Public/_Search/
  with the public form fields. Returns the Search Results fragment.
  POST /Public/Search renders the form; POST /Public/_Search/ returns rows.
"""
from __future__ import annotations

import re
import sys
import time
from html import unescape
from typing import Iterator

import curl_cffi.requests as cr

BASE = "https://arls-public.ncbeec.org/Public"
SEARCH_URI = f"{BASE}/_Search/"
POLITE_DELAY = 0.4

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CLASSIFICATION_UNKNOWN = ""


def _pipe_text(html: str) -> str:
    txt = re.sub(r"<script[\s\S]*?</script>", "|", html, flags=re.I)
    txt = re.sub(r"<[^>]+>", "|", txt)
    txt = re.sub(r"&nbsp;", " ", txt)
    return re.sub(r"\s+", " ", re.sub(r"\|{2,}", "|", txt))


_ROWSPLIT_RE = re.compile(r"\|\s*(?=[A-Z]\.\d{2,6}\s*\|)")


def _row_cells(seg: str) -> list[str]:
    """One pipe-splitted segment -> [account, status_note, classification, owner]."""
    if "|" not in seg:
        return []
    acc = seg.split("|", 1)[0].strip()
    body = seg.split("|", 1)[1]
    parts = [p.strip() for p in _ROWFILERPRS.findall(body)]
    return [acc] + parts if parts else []


_ROWFILERPRS = re.compile(r"[^|]+")


def parse_rows(html: str) -> list[dict]:
    txt = _pipe_text(html)
    out: list[dict] = []
    for seg in _ROWSPLIT_RE.split(txt)[1:]:
        cells = [p.strip() for p in seg.split("|") if p.strip()]
        if not cells:
            continue
        row = {"account": cells[0], "owner": "", "classification": "", "status": "Unknown"}
        rest = cells[1:]
        if rest and not rest[0].lower().startswith("license"):
            # odd pieces then classification; classification always contains 'Classification License'
            cl_idx = None
            for i, piece in enumerate(rest):
                if "classification license" in piece.lower():
                    cl_idx = i
                    break
            if cl_idx is None:
                continue
            note = " ".join(rest[: cl_idx])
            if "not active" in note.lower():
                row["status"] = "Inactive"
            elif "name" in note.lower() or len(note) < 4 or "view" in note.lower():
                row["status"] = "Active"
            row["classification"] = unescape(rest[cl_idx])
            owner_parts = rest[cl_idx + 1:]
            if owner_parts:
                row["owner"] = unescape(owner_parts[0])
                # AKA business alias
                if len(owner_parts) >= 3 and owner_parts[1].lower().startswith("aka:"):
                    row["aka"] = unescape(owner_parts[2])
            out.append(row)
    return out


STATUS_MAP = {"INACTIVE": "Inactive", "NOT ACTIVE": "Inactive", "NONE": "Unknown"}


def normalize_status(raw: str) -> str:
    up = (raw or "").strip().upper()
    if "NOT ACTIVE" in up or "INACTIVE" in up:
        return "Inactive"
    if "ACTIVE" in up:
        return "Active"
    return raw.title() if raw else ""


class NcSession:
    def __init__(self, impersonate: str = "chrome", delay: float = POLITE_DELAY):
        self.http = cr.Session(impersonate=impersonate)
        self.delay = delay

    def search(self, first_name: str = "", last_name: str = "", company_name: str = "",
               classification: str = "", city: str = "") -> list[dict]:
        data = {
            "AccountSearch": "Y",
            "AccountDefinitionIdnt": classification or "",
            "CompanyName": company_name or "",
            "FirstName": first_name or "",
            "LastName": last_name or "",
            "City": city or "",
            "AccountTypeID": "",
            "AccountNumber": "",
            "PhoneNumber": "",
            "Email": "",
        }
        r = self.http.post(SEARCH_URI, data=data, timeout=60)
        r.raise_for_status()
        time.sleep(self.delay)
        return parse_rows(r.text)


def sweep(session: NcSession, branches: str, **kw) -> Iterator[dict]:
    seen: set[str] = set()
    for letter in branches:
        for row in session.search(company_name=letter, **kw):
            key = row.get("account", "")
            if key and key not in seen:
                seen.add(key)
                yield row
