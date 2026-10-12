"""CSLB (California contractors board) adapter: search, parse, detail.

Verified flow (keyless):
  1. GET  /OnlineServices/CheckLicenseII/CheckLicense.aspx  (session + aspx state)
  2. POST same URL with the "business name" postback: rows for a name prefix
     (first 50 in HTML; when the board caps at 50 we subdivide the prefix)
  3. GET  /OnlineServices/CheckLicenseII/LicenseDetail.aspx?LicNum=...  (full record)
"""
from __future__ import annotations

import re
import time
import sys
from dataclasses import dataclass, field
from typing import Iterable, Iterator

import curl_cffi.requests as cr

BASE = "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII"
CHECK_URL = f"{BASE}/CheckLicense.aspx"
DETAIL_URL = f"{BASE}/LicenseDetail.aspx?LicNum={0}"  # LicNum filled per row
POLITE_DELAY = 0.45

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROW_ID = "MainContent_dlMain"


@dataclass
class LicenseRow:
    license_number: str = ""
    name: str = ""
    name_type: str = ""
    city: str = ""
    status: str = ""
    street: str = ""
    state: str = ""
    zip: str = ""
    phone: str = ""
    entity: str = ""
    classes: str = ""
    issue_date: str = ""
    expire_date: str = ""
    extra: dict = field(default_factory=dict)


STATUS_MAP = {
    "ACTIVE": "Active",
    "EXPIRED": "Expired",
    "CANCELLED": "Cancelled",
    "SUSPENDED": "Suspended",
    "REVOKE": "Revoked",
    "REVOKED": "Revoked",
    "INACTIVE": "Inactive",
    "PENDING": "Pending",
}


def normalize_status(raw: str) -> str:
    raw = (raw or "").strip()
    up = raw.upper()
    for key, val in sorted(STATUS_MAP.items(), key=lambda kv: -len(kv[0])):
        if key in up:
            return val
    return raw.title() if raw else ""


class CslbSession:
    """One persistent session (cookies kept tight like the capture guideline)."""

    def __init__(self, impersonate: str = "chrome", delay: float = POLITE_DELAY):
        self.http = cr.Session(impersonate=impersonate)
        self.delay = delay
        self._form: dict | None = None

    # -- internal ---------------------------------------------------------
    def _load_form(self) -> None:
        r = self.http.get(CHECK_URL, timeout=40)
        r.raise_for_status()
        t = r.text

        def grab(hid: str) -> str:
            m = re.search(rf'id="__{hid}"[^>]*value="([^"]*)"', t)
            return m.group(1) if m else ""

        self._form = {
            "__VIEWSTATE": grab("VIEWSTATE"),
            "__VIEWSTATEGENERATOR": grab("VIEWSTATEGENERATOR"),
            "__EVENTVALIDATION": grab("EVENTVALIDATION"),
        }

    def _post_search(self, prefix: str) -> str:
        if self._form is None:
            self._load_form()
        data = dict(self._form)
        data["ctl00$MainContent$NextName"] = prefix
        data["ctl00$MainContent$Contractor_Business_Name_Button"] = " "
        r = self.http.post(CHECK_URL, data=data, timeout=60)
        r.raise_for_status()
        time.sleep(self.delay)
        return r.text

    # -- public -----------------------------------------------------------
    def search_rows(self, prefix: str) -> list[LicenseRow]:
        """Rows (max 50 visible) whose business name starts with prefix."""
        html = self._post_search(prefix)
        out: list[LicenseRow] = []
        pat = re.compile(
            rf'id="{ROW_ID}_(lblName|lblType|lblLicenseStatus|lblCity)_(\d+)"[^>]*>([^<]*)<'
        )
        licpat = re.compile(rf'id="{ROW_ID}_hlLicense_(\d+)"\s+href="[^"]*LicNum=(\d+)"')
        vals: dict[int, dict[str, str]] = {}
        for fid, idx, val in pat.findall(html):
            vals.setdefault(int(idx), {})[fid] = val.strip()
        for idx, lic in licpat.findall(html):
            d = vals.get(int(idx))
            if not d:
                continue
            out.append(
                LicenseRow(
                    license_number=lic,
                    name=d.get("lblName", ""),
                    name_type=d.get("lblType", ""),
                    city=normal_city(d.get("lblCity", "")),
                    status=normalize_status(d.get("lblLicenseStatus", "")),
                )
            )
        return out

    def sweep(
        self,
        prefixes: Iterable[str],
        min_len: int = 2,
        max_len: int = 4,
        details: bool = True,
        status: str | None = "Active",
    ) -> Iterator[LicenseRow]:
        """Recursively sweep prefixes; subdivides when the board caps at 50."""
        seen: set[str] = set()
        for root in prefixes:
            root = root.strip().upper()
            stack = [root]
            while stack:
                qx = stack.pop()
                rows = self.search_rows(qx)
                if len(rows) >= 50 and len(qx) < max_len:
                    stack.extend(qx + chr(c) for c in range(ord("A"), ord("Z") + 1))
                    continue
                for row in rows:
                    if row.license_number in seen:
                        continue
                    seen.add(row.license_number)
                    if status and row.status != status:
                        continue
                    if details:
                        self.enrich(row)
                        if status and row.status != status:
                            continue
                    yield row

    def enrich(self, row: LicenseRow) -> None:
        det = self.license_detail(row.license_number)
        b = det.get("business", {})
        row.street = b.get("street", "")
        row.city = b.get("city", "") or row.city
        row.state = b.get("state", "")
        row.zip = b.get("zip", "")
        row.phone = b.get("phone", "")
        row.entity = det.get("entity", "")
        row.classes = det.get("classes", "")
        row.issue_date = det.get("issue_date", "")
        row.expire_date = det.get("expire_date", "")
        if det.get("status"):
            row.status = normalize_status(det["status"])

    def license_detail(self, lic_num: str) -> dict:
        url = f"{BASE}/LicenseDetail.aspx?LicNum={lic_num}"
        r = self.http.get(url, timeout=40, headers={"Referer": CHECK_URL})
        r.raise_for_status()
        time.sleep(self.delay)
        return parse_detail(r.text)


def normal_city(city: str) -> str:
    return city.strip().title().replace("`", "'")


def _pipe_text(html: str) -> str:
    txt = re.sub(r"<script[\s\S]*?</script>", "|", html, flags=re.I)
    txt = re.sub(r"<[^>]+>", "|", txt)
    txt = re.sub(r"&nbsp;", " ", txt)
    return re.sub(r"\s+", " ", re.sub(r"\|{2,}", "|", txt))


def _piped(txt: str, start: str, stop: str, limit: int = 1200) -> list[str]:
    i = txt.find(start)
    if i < 0:
        return []
    j = txt.find(stop, i + len(start))
    if j < 0:
        j = i + limit
    seg = txt[i + len(start): j]
    return [p.strip() for p in seg.split("|") if p.strip()]


_ADDR_RE = re.compile(r"^(?P<city>[A-Za-z '.]+),\s*(?P<st>[A-Z]{2})\s*(?P<zip>\d{5}(?:-\d{4})?)$")
_PHONE_RE = re.compile(r"\((\d{3})\)\s*(\d{3}-\d{4})")


def parse_detail(html: str) -> dict:
    txt = _pipe_text(html)
    out: dict = {"business": {"name": "", "street": "", "city": "", "state": "",
                              "zip": "", "phone": ""},
                 "entity": "", "classes": "", "issue_date": "",
                 "expire_date": "", "status": ""}
    seg = _piped(txt, "Business Information", "Entity")
    vals = [s for s in seg if s]
    if vals:
        out["business"]["name"] = vals[0]
        if len(vals) >= 2 and re.search(r"\d", vals[1]):
            out["business"]["street"] = vals[1]
        for s in vals[2:]:
            m = _ADDR_RE.match(s)
            if m:
                out["business"]["city"] = m.group("city")
                out["business"]["state"] = m.group("st")
                out["business"]["zip"] = m.group("zip")
            pm = _PHONE_RE.search(s)
            if pm:
                out["business"]["phone"] = pm.group(0)
    m = re.search(r"\|\s*Entity\s*\|\s*([^|]+)\|", txt)
    if m:
        out["entity"] = m.group(1).strip()
    for key, name in (("issue_date", "Issue Date"), ("reissue_date", "Reissue Date"),
                      ("expire_date", "Expire Date")):
        m = re.search(rf"\|\s*{name}\s*\|\s*([^|]+)\|", txt)
        if m:
            out[key] = m.group(1).strip()
    m = re.search(r"License Status\|*\s*([^|]{10,120})\|", txt)
    if m:
        out["status"] = m.group(1).strip()
    cls = _piped(txt, "Classifications", "Bonding Information", limit=400)
    classes = [s for s in cls if re.match(r"^[A-Z]-?\d?\b|\b[A-C]\d", s) or re.match(r"^[A-Z]\d", s)]
    out["classes"] = "; ".join(dict.fromkeys(classes))
    return out
