"""PA PALS (BPOA statewide license verification) adapter.

Verified flow (keyless):
  POST https://www.pals.pa.gov/api/Search/SearchForPersonOrFacilty   (JSON body)
  -> WCF XML rows (ArrayOfPersonOrFacilitySearchModel), 50 per page.

Body shape:
  {"OptPersonFacility": "Person" | "Facility", "LastName"/"FacilityName": ...,
   "State": "", "Country": "ALL", "County": null, "IsFacility": 0|1,
   "PersonId": null, "PageNo": 1}
No captcha/token required for the search post (the portal's robot checkbox is
client-side; skipped entirely by direct API calls).
"""
from __future__ import annotations

import sys
import time
import xml.etree.ElementTree as ET
from typing import Iterator

import curl_cffi.requests as cr

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

BASE = "https://www.pals.pa.gov"
SEARCH_URI = f"{BASE}/api/Search/SearchForPersonOrFacilty"
NS = "{http://schemas.datacontract.org/2004/07/BPOA.ExternalApp.srvExternalSearchService}"
POLITE_DELAY = 0.45
PAGE_SIZE = 50

_DROP = {"PropertyChanged", "complaintFromDateField", "complaintCloseDateField",
         "complaintToDateField", "complaintNumberField", "isFacilityField",
         "isPersonFacilityField", " disciplinaryActionTypeIdField",
         "disciplinaryActionTypeIdField"}

_SKIP = "0001-01-01T00:00:00"


def _row_from_element(el) -> dict:
    out: dict = {}
    for child in el:
        tag = child.tag.replace(NS, "")
        if tag in _DROP:
            continue
        val = (child.text or "").strip()
        if not val or val == _SKIP:
            continue
        key = tag[:-5] if tag.endswith("Field") else tag
        out[key] = val
    return out


def normalize_status(raw: str) -> str:
    up = (raw or "").strip().upper()
    if up.startswith("ACT"):
        return "Active"
    if up.startswith("EXPIRED") or up.startswith("INACTIVE"):
        return "Expired"
    if up.startswith("SUS"):
        return "Suspended"
    if up.startswith("REVOK"):
        return "Revoked"
    return raw.title() if raw else ""


def parse_rows(xml_text: str, page: int = 1) -> list[dict]:
    root = ET.fromstring(xml_text)
    models = root.findall(f"{NS}PersonOrFacilitySearchModel")
    out = []
    for el in models:
        row = _row_from_element(el)
        if not row:
            continue
        out.append({
            "license_number": row.get("licenseNumber", ""),
            "name": row.get("fullName", ""),
            "board": row.get("boardName", ""),
            "classes": row.get("licenceType", ""),
            "city": row.get("city", ""),
            "state": row.get("state", row.get("country", "")),
            "county": row.get("county", ""),
            "zip": row.get("zipcode", ""),
            "phone": row.get("phoneNo1", ""),
            "email": row.get("emailid1", ""),
            "status": normalize_status(row.get("status", "")),
            "total_records": row.get("totalRecords", ""),
            "page": page,
        })
    return out


class PalsSession:
    def __init__(self, impersonate: str = "chrome", delay: float = POLITE_DELAY):
        self.http = cr.Session(impersonate=impersonate)
        self.delay = delay

    def _post(self, body: dict) -> str:
        r = self.http.post(SEARCH_URI, json=body, timeout=90)
        r.raise_for_status()
        time.sleep(self.delay)
        return r.text

    def search(self, name: str = "", facility: bool = False, page: int = 1) -> list[dict]:
        if facility:
            body = {"OptPersonFacility": "Facility", "FacilityName": name, "State": "",
                    "Country": "ALL", "County": None, "IsFacility": 1, "PersonId": None,
                    "PageNo": page}
        else:
            body = {"OptPersonFacility": "Person", "LastName": name, "State": "",
                    "Country": "ALL", "County": None, "IsFacility": 0, "PersonId": None,
                    "PageNo": page}
        return parse_rows(self._post(body), page)

    def sweep(self, prefixes: str, facility: bool = False, **kw) -> Iterator[dict]:
        seen: set[str] = set()
        for letter in prefixes:
            page = 1
            while True:
                rows = self.search(name=letter, facility=facility, page=page)
                fresh = 0
                for row in rows:
                    key = row.get("license_number") or row.get("name", "") + str(page)
                    if key and key not in seen:
                        seen.add(key)
                        fresh += 1
                        yield row
                if rows and fresh == len(rows) and page < 100:
                    page += 1
                else:
                    break
