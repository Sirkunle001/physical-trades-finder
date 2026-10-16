"""Captures real ARL System result fragments for the NC board family fixtures."""
import pathlib, re, sys, time

sys.path.insert(0, r"C:\Users\Gafar\Gafar Grinds\linkedin-social-listener\.venv\Lib\site-packages")
from curl_cffi import requests as cr

FIX = pathlib.Path(r"C:\Users\Gafar\Gafar Grinds\license-finder\tests\fixtures")
s = cr.Session(impersonate="chrome124", allow_redirects=True)

BOARDS = [
    ("nc_plumbing_results.html", "http://public.nclicensing.org/public/_search/",
     {"ClassificationDefinitionIdnt": "", "AccountSearch": "Y", "CompanyName": "DONALDSON",
      "FirstName": "", "LastName": "", "City": "", "AccountTypeID": "", "AccountNumber": "",
      "PhoneNumber": "", "Email": ""}),
    ("nc_general_results.html", "https://portal.nclbgc.org/public/_search/",
     {"ClassificationDefinitionIdnt": "", "AccountSearch": "Y", "CompanyName": "ROOFING",
      "FirstName": "", "LastName": "", "City": "", "AccountTypeID": "", "AccountNumber": "",
      "PhoneNumber": "", "Email": ""}),
    ("nc_electrical_results.html", "https://arls-public.ncbeec.org/public/_search/",
     {"AccountDefinitionIdnt": "", "AccountSearch": "Y", "CompanyName": "WOLF",
      "FirstName": "", "LastName": "", "City": "", "AccountTypeID": "", "AccountNumber": "",
      "PhoneNumber": "", "Email": ""}),
]

for fname, url, data in BOARDS:
    r = s.post(url, data=data, timeout=60)
    (FIX / fname).write_text(r.text, encoding="utf-8")
    print(fname, r.status_code, len(r.text))
    time.sleep(0.4)
