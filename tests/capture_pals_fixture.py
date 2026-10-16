"""Captures a real PALS XML response for parser tests."""
import pathlib, sys

sys.path.insert(0, r"C:\Users\Gafar\Gafar Grinds\linkedin-social-listener\.venv\Lib\site-packages")
from curl_cffi import requests as cr

FIX = pathlib.Path(r"C:\Users\Gafar\Gafar Grinds\license-finder\tests\fixtures")
s = cr.Session(impersonate="chrome124")
body = {"OptPersonFacility": "Person", "LastName": "SMITH", "State": "", "Country": "ALL",
        "County": None, "IsFacility": 0, "PersonId": None, "PageNo": 1}
r = s.post("https://www.pals.pa.gov/api/Search/SearchForPersonOrFacilty", json=body, timeout=90)
(FIX / "pa_pals_results.xml").write_text(r.text, encoding="utf-8")
print("captured:", len(r.text), "status", r.status_code)
