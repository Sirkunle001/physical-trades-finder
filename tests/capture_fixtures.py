"""Captures real CSLB HTML into tests/fixtures for offline parser tests. Run before pytest."""
import re, sys, pathlib

sys.path.insert(0, r"C:\Users\Gafar\Gafar Grinds\linkedin-social-listener\.venv\Lib\site-packages")
from curl_cffi import requests as cr

FIX = pathlib.Path(__file__).parent / "fixtures"
s = cr.Session(impersonate="chrome")

r = s.get("https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx", timeout=30)
(FIX / "search_form.html").write_text(r.text, encoding="utf-8")

data = {
    "__VIEWSTATE": re.search(r'id="__VIEWSTATE"[^>]*value="([^"]*)"', r.text).group(1),
    "__VIEWSTATEGENERATOR": re.search(r'id="__VIEWSTATEGENERATOR"[^>]*value="([^"]*)"', r.text).group(1),
    "ctl00$MainContent$NextName": "AB",
    "ctl00$MainContent$Contractor_Business_Name_Button": " ",
}
evm = re.search(r'id="__EVENTVALIDATION"[^>]*value="([^"]*)"', r.text)
if evm:
    data["__EVENTVALIDATION"] = evm.group(1)
r2 = s.post("https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx", data=data, timeout=40)
(FIX / "results_ab.html").write_text(r2.text, encoding="utf-8")

lic = re.findall(r"LicenseDetail\.aspx\?LicNum=(\d+)", r2.text)[2]
r3 = s.get(
    f"https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/LicenseDetail.aspx?LicNum={lic}",
    timeout=30,
    headers={"Referer": "https://www.cslb.ca.gov/OnlineServices/CheckLicenseII/CheckLicense.aspx"},
)
(FIX / "license_detail.html").write_text(r3.text, encoding="utf-8")
print("fixtures captured:", len(r2.text), len(r3.text), "lic", lic)
