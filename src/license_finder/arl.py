"""ARL Systems public-license-search adapter (one adapter, many NC boards).

Verified ARL-family portals (all keyless, identical shape):
  - https://arls-public.ncbeec.org/public/       NC electrical contractors
  - http://public.nclicensing.org/Public/         NC plumbing/ HVAC / fire sprinkler
  - https://portal.nclbgc.org/public/             NC general contractors

Flow:
  POST {base}/public/_search/  (or /Public/_Search/)
  fields: {idfield}: definition id, CompanyName/FirstName/LastName/City/...
  returns the Search Results fragment (pipe-splittable rows).
"""
from __future__ import annotations

import re
import sys
import time
from html import unescape
from typing import Iterator

import curl_cffi.requests as cr

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

POLITE_DELAY = 0.4


class ARLBoard:
    def __init__(self, board: str, base: str, form_path: str, idfield: str = "ClassificationDefinitionIdnt",
                 label: str = ""):
        self.board = board
        self.base = base.rstrip("/") + "/"
        self.idfield = idfield
        self.label = label
        self.form_url = self.base + form_path.lstrip("/")
        self.search_url = re.sub(r"[Ss]earch$", "_Search/", self.form_url)

    def session(self, impersonate: str = "chrome124", delay: float = POLITE_DELAY) -> "ARLSession":
        return ARLSession(self, impersonate, delay)


# verified NC family (ARL Systems)
NC_ELECTRICAL = ARLBoard(
    "nc-electrical", "https://arls-public.ncbeec.org/", "Public/Search",
    idfield="AccountDefinitionIdnt", label="NC Electrical Contractors",
)
NC_PLUMBING = ARLBoard(
    "nc-plumbing", "http://public.nclicensing.org/", "Public/Search",
    idfield="ClassificationDefinitionIdnt", label="NC Plumbing / HVAC / Fire Sprinkler",
)
NC_GENERAL = ARLBoard(
    "nc-general", "https://portal.nclbgc.org/", "public/search",
    idfield="ClassificationDefinitionIdnt", label="NC General Contractors",
)
NC_FAMILY = [NC_ELECTRICAL, NC_PLUMBING, NC_GENERAL]


_ACCOUNT_RE = re.compile(r"[A-Z]\.\d{3,6}")


def _pipe_text(html: str) -> str:
    txt = re.sub(r"<script[\s\S]*?</script>", "|", html, flags=re.I)
    txt = re.sub(r"<[^>]+>", "|", txt)
    txt = re.sub(r"&nbsp;", " ", txt)
    return re.sub(r"\s+", " ", txt)


def parse_rows(html: str, board: str = "", label: str = "") -> list[dict]:
    """One result-fragment -> rows {account, owner, classification, status, board, label}.

    Row shape (pipe-collapsed):  Account# | status-note? | classification | Owner [+ AKA]
    Status-note may be present ("License Not Active"), may be absent; classification
    varies by board ("Intermediate Classification License" on electrical, plain
    "License" on plumbing/general when unfiltered).
    """
    txt = _pipe_text(html)
    out: list[dict] = []
    for seg in _ACCOUNT_RE.split(txt)[0:]:  # keep whole text; split below
        pass
    parts = re.split(rf"(\b[A-Z]\.\d{{3,6}}\b)", txt)
    i = 1
    while i < len(parts) - 1:
        account = parts[i]
        body = parts[i + 1]
        i += 2
        cells = [p.strip() for p in body.split("|") if p.strip() and p.strip().lower() != "view"]
        if not cells:
            continue
        row = {"account": account, "owner": "", "classification": "",
               "status": "Unknown", "board": board, "label": label}
        cls_idx = None
        for k, piece in enumerate(cells):
            low = piece.lower()
            if low.endswith("license") or low == "license":
                cls_idx = k
                break
        if cls_idx is not None:
            note = " ".join(cells[:cls_idx])
            if "not active" in note.lower() or "unlicensed" in note.lower():
                row["status"] = "Inactive"
            else:
                row["status"] = "Active"
            row["classification"] = unescape(cells[cls_idx])
            owner_parts = cells[cls_idx + 1:]
        else:
            owner_parts = [c for c in cells if _ACCOUNT_RE.match(c) is None and len(c) > 3]
        for op in owner_parts:
            if op.lower().startswith("aka:"):
                if len(owner_parts) > owner_parts.index(op) + 1:
                    row["aka"] = unescape(owner_parts[owner_parts.index(op) + 1])
                continue
            if not row["owner"] and re.search(r"[A-Za-z]", op) and "&" in op or " " in op or re.match(r"^[A-Z][a-z]+,", op):
                row["owner"] = unescape(op)
                break
        if row["owner"] or row["status"] != "Unknown":
            out.append(row)
    return out


class ARLSession:
    def __init__(self, board: ARLBoard, impersonate: str = "chrome124", delay: float = POLITE_DELAY):
        self.board = board
        self.http = cr.Session(impersonate=impersonate)
        self.delay = delay

    def classifications(self) -> list[tuple[str, str]]:
        r = self.http.get(self.board.form_url, timeout=40)
        r.raise_for_status()
        opts = re.findall(rf'<option[^>]*value="([^"]*)"[^>]*>\s*([A-Za-z][^<]{{2,70}})', r.text)
        out = []
        for val, name in opts:
            low = name.lower()
            if val and ("contractor" in low or "technician" in low or "classification" in low):
                out.append((val.strip(), unescape(name.strip())))
        return out

    def search(self, company_name: str = "", first_name: str = "", last_name: str = "",
               city: str = "", classification: str = "", retries: int = 2) -> list[dict]:
        data = {
            self.board.idfield: classification or "",
            "AccountSearch": "Y",
            "CompanyName": company_name or "",
            "FirstName": first_name or "",
            "LastName": last_name or "",
            "City": city or "",
            "AccountTypeID": "",
            "AccountNumber": "",
            "PhoneNumber": "",
            "Email": "",
        }
        last_err: Exception | None = None
        for attempt in range(retries + 1):
            try:
                r = self.http.post(self.board.search_url, data=data, timeout=60)
                r.raise_for_status()
                time.sleep(self.delay)
                return parse_rows(r.text, board=self.board.board, label=self.board.label)
            except Exception as e:
                last_err = e
                time.sleep(1.5 * (attempt + 1))
        print(f"  [warn] {self.board.board}: {type(last_err).__name__} after {retries + 1} attempts")
        return []

    def sweep(self, prefixes: str, **kw) -> Iterator[dict]:
        seen: set[str] = set()
        for letter in prefixes:
            for row in self.search(company_name=letter, **kw):
                key = (row.get("account"), row.get("owner"))
                if key in seen:
                    continue
                seen.add(key)
                yield row


def unify_nc(prefixes: str, boards: list[ARLBoard] | None = None, **kw) -> Iterator[dict]:
    """Run every ARL NC board and yield a merged, deduped stream with a board column."""
    boards = boards or NC_FAMILY
    seen: set[tuple[str, str]] = set()
    for board in boards:
        s = board.session()
        for row in s.sweep(prefixes, **kw):
            key = (board.board, row.get("account", ""))
            if key in seen:
                continue
            seen.add(key)
            yield row
