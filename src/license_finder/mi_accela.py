"""MI LARA Accela (construction trades) adapter - browser-driven.

Verified flow (real browser needed for the update-panel postbacks):
  1. GET https://aca-prod.accela.com/lara/GeneralProperty/PropertyLookUp.aspx?isLicensee=Y&TabName=APO
  2. select license type + fill business name + Enter  -> grid ("Showing 1-10 of N")
  3. click "Download results" (__doPostBack export)     -> CSV of the whole result set
  CSV columns: License Number, License Type, Business Name, First Name, Middle Initial,
               Last Name, License Expiration Date, City, State, Zip
"""
from __future__ import annotations

import csv
import io
import json
import os
import re
import sys
import time
from typing import Iterator

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

FORM_URL = "https://aca3.accela.com/lara/GeneralProperty/PropertyLookUp.aspx?isLicensee=Y&TabName=APO"
INFRA = r"C:\Users\Gafar\Gafar Grinds\license-finder\.pwtmp"
PROFILE = INFRA + "\\chrome-mi"   # sweep() makes a per-process copy; MI needs no server-side session
CHROME = INFRA + r"\browsers\chromium-1243\chrome-win64\chrome.exe"
COOKIE_CACHE = INFRA + r"\fl_cookies.json"
POLITE_DELAY = 2.0


def _pw_ctx(p):
    for env_key in ("TMPDIR", "TMP", "TEMP", "PLAYWRIGHT_BROWSERS_PATH"):
        val = {"TMPDIR": INFRA, "TMP": INFRA, "TEMP": INFRA, "PLAYWRIGHT_BROWSERS_PATH": INFRA + r"\browsers"}.get(env_key)
        if val:
            os.environ[env_key] = val
    return p.chromium.launch_persistent_context(
        PROFILE, executable_path=CHROME, headless=False,
        args=["--no-sandbox"])


def _pipeline(page, prefix: str, license_type: str) -> str:
    """Run one search + export in the browser; capture the CSV via expect_download."""
    holder = {"csv": "", "url": "", "post": ""}

    def grab(resp):
        try:
            if "PropertyLookUp.aspx" in (resp.url or "") and resp.request.method == "POST":
                ct = (resp.headers or {}).get("content-type", "")
                if "csv" in ct or "octet" in ct or "download" in ct:
                    holder["url"] = resp.url
                    holder["post"] = resp.request.post_data or ""
                    holder["csv"] = resp.text()
                elif "License Number" in (resp.text() or "")[:400]:
                    holder["csv"] = resp.text()
        except Exception:
            pass

    page.on("response", grab)
    try:
        page.goto(FORM_URL, wait_until="networkidle", timeout=120000)
        page.wait_for_timeout(5000)
        sel = page.locator("select[name*='ddlLicenseType']")
        if sel.count():
            sel.select_option(license_type)
        box = page.locator("input[name*='txtBusiName']")
        box.click()
        box.fill(prefix)
        page.keyboard.press("Enter")
        page.wait_for_timeout(12000)
        anchor = page.locator("a[id*='gdvRefLicenseeListtop4btnExport']").first
        if not anchor.count():
            raise RuntimeError("no export button: search failed")
        with page.expect_download(timeout=90000) as dli:
            anchor.click()
        internal = dli.value.path()
        out = open(internal, encoding="utf-8", errors="replace").read()
        try:
            os.remove(internal)
        except Exception:
            pass
        if not out:
            raise RuntimeError("empty export")
        return out
    finally:
        try:
            page.remove_listener("response", grab)
        except Exception:
            pass


def parse_csv_rows(text: str, license_type_guess: str = "") -> list[dict]:
    reader = csv.DictReader(io.StringIO(text))
    out = []
    for row in reader:
        first = (row.get("First Name") or "").strip()
        mi = (row.get("Middle Initial") or "").strip()
        last = (row.get("Last Name") or "").strip()
        person = " ".join(x for x in (first, mi, last) if x)
        biz = (row.get("Business Name") or "").strip()
        name = biz or person
        exp = (row.get("License Expiration Date") or "").strip()
        out.append({
            "license_number": (row.get("License Number") or "").strip(),
            "name": name.strip(),
            "board": (row.get("License Type") or license_type_guess).strip(),
            "classes": (row.get("License Type") or "").strip(),
            "city": (row.get("City") or "").title(),
            "state": (row.get("State") or "MI").strip().upper(),
            "zip": (row.get("Zip") or "").strip(),
            "expire_date": exp,
            "status": status_from_expiry(exp),
            "contact": person,
        })
    return out


def status_from_expiry(exp: str) -> str:
    """Accela's export carries expiry, not status; derive liveness from the date."""
    m = re.match(r"^(\d{1,2})/(\d{1,2})/(\d{4})$", (exp or "").strip())
    if not m:
        return ""
    mm, dd, yy = int(m.group(1)), int(m.group(2)), int(m.group(3))
    today = time.localtime()
    return "Expired" if (yy, mm, dd) < (today.tm_year, today.tm_mon, today.tm_mday) else "Active"


def sweep(prefixes: str, license_type: str = "Electrical Contractor", **kw) -> Iterator[dict]:
    """Browser pass per prefix; each sweep gets a FRESH chrome profile:
    MI Accela tolerates zero-profile fresh sessions but cannot survive
    re-launches against a reused one (verified: reused profile -> TargetClosed)."""
    global PROFILE
    os.environ["TMP"] = INFRA
    os.environ["TEMP"] = INFRA
    os.environ["TMPDIR"] = INFRA
    os.environ["PLAYWRIGHT_BROWSERS_PATH"] = INFRA + r"\browsers"
    runtime_profile = INFRA + f"\\chrome-mi-{os.getpid()}-{int(time.time())}"
    PROFILE = runtime_profile
    seen: set[str] = set()
    try:
        from playwright.sync_api import sync_playwright

        with sync_playwright() as p:
            ctx = _pw_ctx(p)
            page = ctx.pages[0] if ctx.pages else ctx.new_page()
            for prefix in prefixes:
                try:
                    csv_text = _pipeline(page, prefix.upper(), license_type)
                except Exception as e:
                    print(f"  [warn] {prefix}: {type(e).__name__} {str(e)[:70]}")
                    time.sleep(2)
                    continue
                rows = parse_csv_rows(csv_text, license_type)
                for row in rows:
                    key = row.get("license_number")
                    if key and key not in seen:
                        seen.add(key)
                        yield row
                time.sleep(POLITE_DELAY)
            ctx.close()
    finally:
        PROFILE = INFRA + "\\chrome-mi"
        import shutil
        try:
            shutil.rmtree(runtime_profile, ignore_errors=True)
        except Exception:
            pass
