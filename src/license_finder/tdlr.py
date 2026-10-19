"""TX TDLR (TDLR license search) adapter.

Verified flow (keyless):
  1. GET  https://www.tdlr.texas.gov/LicenseSearch/            (session + referer)
  2. POST https://www.tdlr.texas.gov/LicenseSearch/SearchResultsListBrowse.asp?from=search
     fields: pht_lic, pht_expdt, pht_oth_name, phy_zip, tdlr_status, phy_city, phy_cnty, B1
  3. results HTML: license#, exp date, name, city, zip, county, phone
     pagination: SearchResultsListBrowse.asp?pageNo=N&pageDir=N&k=..&j=..
"""
from __future__ import annotations

import re
import sys
import time
from typing import Iterator

import curl_cffi.requests as cr

BASE = "https://www.tdlr.texas.gov/LicenseSearch/"
POST_URI = f"{BASE}SearchResultsListBrowse.asp?from=search"
REFERER = BASE
POLITE_DELAY = 0.45

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_TDLR_ROW_RE = re.compile(
    r"([A-Z]{2,6}[A-Z0-9]{0,10})[\s|]*(\d{2}/\d{2}/\d{4})[\s|]*([A-Z][^|]{3,120})[\s|]*[|\s]*([A-Za-z][A-Za-z ]+)")
def status_from_expiry(exp: str) -> str:
    """TDLR's results grid carries no status column, so liveness is the expiry date."""
    m = re.match(r"^(\d{2})/(\d{2})/(\d{4})$", (exp or "").strip())
    if not m:
        return ""
    mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    today = time.localtime()
    if (yy, mm, dd) < (today.tm_year, today.tm_mon, today.tm_mday):
        return "Expired"
    return "Active"


def _pipe_text(html: str) -> list[dict]:
    txt = re.sub(r"<script[\s\S]*?</script>", "|", html, flags=re.I)
    txt = re.sub(r"<[^>]+>", "|", txt)
    txt = re.sub(r"&nbsp;", " ", txt)
    txt = re.sub(r"\|{2,}", "|", txt)
    txt = re.sub(r"\s+", " ", txt)
    rows = []
    for m in _TDLR_ROW_RE.finditer(txt):
        lic, exp, owner, city = m.groups()
        owner = owner.strip(" |,").strip()
        if owner.lower() in ("expired", "active", "inactive"):
            owner = ""
        rows.append({
            "license_number": lic,
            "expire_date": exp,
            "owner": owner,
            "city": city.strip().title(),
            "zip": "",
            "county": "",
            "phone": "",
            "status": status_from_expiry(exp),
        })
    return rows


def normalize_status(raw: str) -> str:
    up = (raw or "").strip().upper()
    if "EXPIRED" in up:
        return "Expired"
    if "ACTIVE" in up or up == "A":
        return "Active"
    return raw.title() if raw else ""


class TxSession:
    def __init__(self, impersonate: str = "chrome", delay: float = POLITE_DELAY):
        self.http = cr.Session(impersonate=impersonate)
        self.delay = delay
        self._warm = False

    def _ensure(self) -> None:
        if not self._warm:
            self.http.get(BASE, timeout=60)
            time.sleep(self.delay)
            self._warm = True

    def _post(self, data: dict) -> str:
        self._ensure()
        r = self.http.post(POST_URI, data=data, timeout=90, headers={"Referer": REFERER})
        r.raise_for_status()
        time.sleep(self.delay)
        return r.text

    def search(self, name: str = "", city: str = "", county: str = "", zip_: str = "",
               lic_num: str = "", page: int = 1) -> list[dict]:
        data = {
            "pht_lic": lic_num or "",
            "pht_expdt": "",
            "pht_oth_name": name or "",
            "phy_zip": zip_ or "",
            "tdlr_status": "-1",
            "phy_city": city or "-1",
            "phy_cnty": county or "-1",
            "B1": "Search",
        }
        if page != 1:
            # each page needs its own POST with page param set by the search POST url
            data["pageNo"] = str(page)
        return _pipe_text(self._post(data))

    def sweep(self, prefixes: str, **kw) -> Iterator[dict]:
        seen: set[str] = set()
        for letter in prefixes:
            page = 1
            while True:
                rows = self.search(name=letter, page=page, **kw)
                fresh = 0
                for row in rows:
                    key = (row.get("license_number", ""), row.get("owner", ""))
                    if key[0] and key not in seen:
                        seen.add(key)
                        fresh += 1
                        yield row
                if rows and fresh:
                    page += 1
                else:
                    break
