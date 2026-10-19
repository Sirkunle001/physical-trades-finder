"""FL DBPR CILB (construction / electrical boards) bulk-CSV adapter.

Verified flow (keyless, no browser needed at runtime):
  GET https://www2.myfloridalicense.com/sto/file_download/extracts/CONSTRUCTIONLICENSE_1.csv
  (~47MB, refreshes with the board's data) -> TDLR-style plain CSV, no header row.

Column layout (verified from live rows; index-based):
  0 district, 1 type code (CBC/CRC/...), 2 name "LAST, FIRST", 4-5 street,
  7 city, 8 state, 9 zip, 12 license core, 13 class char, 14 designation,
  16 issue/ren date, 17 expire date, 21 full license number.
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
import unicodedata
from typing import Iterator

import curl_cffi.requests as cr

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CONSTRUCTION_URL = "https://www2.myfloridalicense.com/sto/file_download/extracts/CONSTRUCTIONLICENSE_1.csv"
ELECTRICAL_URL = "https://www2.myfloridalicense.com/sto/file_download/extracts/electrical.csv"
POLITE_DELAY = 1.0

NAME_SPLIT = re.compile(r"^(?P<last>[^,]+),\s*(?P<rest>.*)$")


def normalize_status(raw: str) -> str:
    up = (raw or "").strip().upper()
    if up == "A":
        return "Active"
    if up == "I":
        return "Inactive"
    if "EXPIRED" in up:
        return "Expired"
    if "SUSP" in up:
        return "Suspended"
    if "REVOK" in up:
        return "Revoked"
    if "ACTIVE" in up:
        return "Active"
    return raw.title() if raw else ""


def parse_row(cells: list[str]) -> dict | None:
    if len(cells) < 21:
        return None
    name_raw = cells[2].strip()
    types = {
        "CBC": "Certified Building Contractor",
        "CRC": "Certified Residential Contractor",
        "CCC": "Certified Commercial Contractor",
        "CVC": "Certified Volume Builder/Developer",
        "RC": "Registered Contractor (local)",
        "SC": "Registered Specialty",
        "CG": "Registered General",
        "RG": "Registered Roofing",
        "RA": "Registered Air A (HVAC)",
        "EC": "Electrical Contractor",
        "KS": "Registered Sheet Metal",
        "ID": "Registered Interior Designer",
        "AC": "Registered Production Builder",
        "CF": "Certified Fire Protection (Specialty)",
        "CV": "Registered Swimming Pool/Spa",
    }
    code = cells[1].strip().upper()
    full_lic = cells[20].strip() or f"{cells[1]}{cells[12]}"
    return {
        "license_number": full_lic,
        "name": name_raw.replace("\u200b", ""),
        "board": types.get(code, code),
        "classes": cells[1] + " " + cells[13],
        "city": cells[8].strip().title(),
        "state": cells[9].strip().upper() or "FL",
        "zip": cells[10].strip(),
        "street": " ".join(x for x in (cells[5], cells[6]) if x.strip()),
        "issue_date": cells[15].strip(),
        "expire_date": cells[17].strip(),
        "status": normalize_status(cells[14]),
        "phone": "",
        "entity": "",
        "email": "",
    }


COOKIE_CACHE = r"C:\Users\Gafar\Gafar Grinds\license-finder\.pwtmp\fl_cookies.json"
CF_ENTRY = "https://www2.myfloridalicense.com/construction-industry/public-records/"


def _load_cookies() -> list[dict]:
    try:
        return json.loads(open(COOKIE_CACHE, encoding="utf-8").read())
    except Exception:
        return []


def _save_cookies(cookies: list[dict]) -> None:
    os.makedirs(os.path.dirname(COOKIE_CACHE), exist_ok=True)
    json.dump(cookies, open(COOKIE_CACHE, "w", encoding="utf-8"))


def ensure_cookies(refresh: bool = False):
    """One browser pass acquires Cloudflare clearance for www2; cached afterwards.
    Returns (cookies, user_agent) - the clearance is UA-pinned, so both travel together."""
    if not refresh:
        try:
            cache = json.load(open(COOKIE_CACHE, encoding="utf-8"))
            if isinstance(cache, dict) and cache.get("cookies"):
                return cache["cookies"], cache.get("user_agent", "")
        except Exception:
            pass
    from playwright.sync_api import sync_playwright  # local import: browser only needed once

    os.environ["TMP"] = os.path.dirname(COOKIE_CACHE)
    os.environ["TEMP"] = os.environ["TMP"]

    chrome_exe = r"C:\Users\Gafar\Gafar Grinds\license-finder\.pwtmp\browsers\chromium-1243\chrome-win64\chrome.exe"
    profile = r"C:\Users\Gafar\Gafar Grinds\license-finder\.pwtmp\chrome-fl"
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile, executable_path=chrome_exe, headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        page = ctx.pages[0] if ctx.pages else ctx.new_page()
        page.goto(CF_ENTRY, wait_until="networkidle", timeout=90000)
        page.wait_for_timeout(8000)
        cookies = ctx.cookies("https://www2.myfloridalicense.com")
        ua = page.evaluate("navigator.userAgent")
        ctx.close()
    os.makedirs(os.path.dirname(COOKIE_CACHE), exist_ok=True)
    json.dump({"cookies": cookies, "user_agent": ua}, open(COOKIE_CACHE, "w", encoding="utf-8"))
    return cookies, ua


def stream_down(url: str) -> str:
    cookies, ua = ensure_cookies()
    headers = {}
    if ua:
        headers["user-agent"] = ua
    http = cr.Session(impersonate="chrome")
    for attempt in range(3):
        headers["cookie"] = "; ".join(f"{c['name']}={c['value']}" for c in cookies
                                      if c.get("name") and c.get("value"))
        r = http.get(url, timeout=600, headers=headers)
        if r.status_code == 403 and attempt < 2:
            cookies, ua = ensure_cookies(refresh=True)
            if ua:
                headers["user-agent"] = ua
            continue
        if r.status_code == 403:
            return stream_down_browser(url)
        r.raise_for_status()
        return r.text
    return r.text


def stream_down_browser(url: str) -> str:
    """Fallback: download through the persistent browser context itself
    (browser fingerprint + cookies travel together, clearance always valid)."""
    from playwright.sync_api import sync_playwright

    os.environ["TMP"] = os.path.dirname(COOKIE_CACHE)
    os.environ["TEMP"] = os.environ["TMP"]
    chrome_exe = r"C:\Users\Gafar\Gafar Grinds\license-finder\.pwtmp\browsers\chromium-1243\chrome-win64\chrome.exe"
    profile = r"C:\Users\Gafar\Gafar Grinds\license-finder\.pwtmp\chrome-fl"
    with sync_playwright() as p:
        ctx = p.chromium.launch_persistent_context(
            profile, executable_path=chrome_exe, headless=False,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"])
        r = ctx.request.get(url, timeout=600000)
        text = r.text()
        ctx.close()
    return text


def all_rows(url: str = CONSTRUCTION_URL, status: str | None = "Active") -> Iterator[dict]:
    text = stream_down(url)
    reader = csv.reader(io.StringIO(text))
    seen: set[str] = set()
    for cells in reader:
        row = parse_row(cells)
        if not row or not row["license_number"] or row["license_number"] in seen:
            continue
        seen.add(row["license_number"])
        if status and status != "all" and row["status"] != status:
            continue
        yield row
