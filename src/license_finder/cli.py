"""license-finder CLI.

One command family:
  license-finder catalog                          board registry + yields
  license-finder list   --board ca-contractors ... run a board sweep -> clean CSV
  license-finder detail --board ca-contractors N  one full license record
"""
from __future__ import annotations

import argparse
import json
import pathlib
import sys

from .cslb import CslbSession, normalize_status
from .export import write_csv

_CLASSES_FILE = pathlib.Path(__file__).parent / "ca_classes.json"

BOARDS = {
    "ca-contractors": {
        "label": "CA: Contractors State License Board (CSLB)",
        "impl": "cslb",
    },
    "tx-trades": {
        "label": "TX: TDLR License Data Search (AC, plumbers, electricians, ...)",
        "impl": "tdlr",
    },
    "nc-electrical": {
        "label": "NC: Board of Examiners of Electrical Contractors",
        "impl": "arl",
    },
    "nc-plumbing": {
        "label": "NC: Board of Examiners of Plumbing / HVAC / Fire Sprinkler",
        "impl": "arl",
    },
    "nc-general": {
        "label": "NC: Licensing Board for General Contractors",
        "impl": "arl",
    },
    "nc-all": {
        "label": "NC: all trade boards unified (electrical + plumbing + general)",
        "impl": "arl",
    },
    "nyc-construction": {
        "label": "NY (NYC): DOB construction-trades licenses (Socrata)",
        "impl": "nyc_dob",
    },
    "fl-cilb": {
        "label": "FL: Construction Industry Licensing Board (bulk register)",
        "impl": "fl_cilb",
    },
    "pa-pals": {
        "label": "PA: statewide professional licensing (PALS, all boards)",
        "impl": "pals",
    },
    "pa-pals-facility": {
        "label": "PA: businesses/facilities only (PALS)",
        "impl": "pals",
    },
}

PENDING_BOARDS = {
    "FL-other": "Other FL DBPR boards (barbers, real estate, ...) share the same bulk-record host: catalog rows as requested",
    "GA": "verify.sos.ga.gov - Cloudflare 403 (browser-mode build)",
    "IL": "IDFPR - Human Verification gate on lookup endpoint",
    "MI": "LARA val app - search API not yet decoded",
    "OH": "OCILB eLicense - webforms popup/async pattern not yet decoded",
}


def _rows_from_board(board: str):
    if board not in BOARDS:
        raise SystemExit(f"unknown board: {board}; catalog shows the supported ones")
    from . import cslb, ncbeec, nyc_dob, tdlr, arl, pals, fl_cilb
    mods = {"cslb": cslb, "tdlr": tdlr, "ncbeec": ncbeec, "nyc_dob": nyc_dob, "arl": arl, "pals": pals, "fl_cilb": fl_cilb}
    return mods[BOARDS[board]["impl"]]


def main(argv: list[str] | None = None) -> int:
    if sys.stdout and hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    ap = argparse.ArgumentParser(prog="license-finder")
    sub = ap.add_subparsers(dest="cmd", required=True)

    sub.add_parser("catalog", help="list supported boards")
    sub.add_parser("classes", help="ca-contractors: the board's official license classes")

    lp = sub.add_parser("list", help="board sweep -> clean CSV")
    lp.add_argument("--board", default="ca-contractors", choices=list(BOARDS))
    lp.add_argument("--prefix", required=True, help="comma-separated name prefixes (e.g. AB,SC)")
    lp.add_argument("--status", default="Active", help="row status filter (Active default)")
    lp.add_argument("--class-filter", default="", dest="class_filter",
                    help="substring filter on classifications (e.g. C-10)")
    lp.add_argument("--no-details", action="store_true", help="skip per-license detail fetches")
    lp.add_argument("--out", default="licensees.csv")
    lp.add_argument("--delay", type=float, default=0.45)

    dp = sub.add_parser("detail", help="fetch one license record")
    dp.add_argument("--board", default="ca-contractors", choices=list(BOARDS))
    dp.add_argument("license")

    args = ap.parse_args(argv)

    if args.cmd == "classes":
        data = json.loads(_CLASSES_FILE.read_text(encoding="utf-8"))
        for c in data["classes"]:
            print(f"{c['code']:6s} {c['name']}")
        print(f"source: {data['source']} (captured {data['captured']})")
        return 0

    if args.cmd == "catalog":
        for key, cfg in BOARDS.items():
            print(f"live    {key:16s} {cfg['label']}")
        for st, note in PENDING_BOARDS.items():
            print(f"pending {st:16s} {note}")
        return 0

    mod = _rows_from_board(args.board)
    if args.cmd == "detail":
        session = CslbSession(delay=0.45)
        d = session.license_detail(args.license)
        import pprint
        pprint.pprint(d)
        return 0

    prefixes = [p for p in args.prefix.split(",") if p]

    # board dispatch: cslb keeps its own session type; others return dicts
    from .cslb import CslbSession
    if BOARDS[args.board]["impl"] == "cslb":
        s = CslbSession(delay=args.delay)
        rows = s.sweep(prefixes, details=not args.no_details, status=normalize_status(args.status) if args.status else None)
        collected = []
        counts = {"prefixes": len(prefixes), "rows": 0, "status_pass": 0, "class_pass": 0, "written": 0}
        for row in rows:
            counts["rows"] += 1
            if args.class_filter and args.class_filter.lower() not in (getattr(row, "classes", "") or "").lower():
                continue
            counts["class_pass"] += 1
            collected.append(row)
        from .export import dedupe
        deduped = dedupe(collected)
        counts["written"] = len(deduped)
        write_csv(deduped, args.out, source_col="")
        print(" -> ".join(f"{k}:{v}" for k, v in counts.items()))
        print(f"out: {args.out}")
        return 0

    if BOARDS[args.board]["impl"] == "arl":
        from .arl import NC_FAMILY, unify_nc
        if args.board == "nc-all":
            rows = unify_nc(prefixes)
        else:
            board = next(b for b in NC_FAMILY if b.board == args.board)
            rows = board.session().sweep(prefixes)
    elif BOARDS[args.board]["impl"] == "pals":
        from .pals import PalsSession
        session = PalsSession(delay=args.delay)
        rows = session.sweep(prefixes, facility=args.board == "pa-pals-facility")
    elif BOARDS[args.board]["impl"] == "fl_cilb":
        from .fl_cilb import all_rows
        rows = all_rows(status=args.status or "Active")
    elif BOARDS[args.board]["impl"] == "tdlr":
        from .tdlr import TxSession
        session = TxSession(delay=args.delay)
        rows = session.sweep(prefixes)
    elif BOARDS[args.board]["impl"] == "ncbeec":
        from .ncbeec import NcSession
        session = NcSession(delay=args.delay)
        rows = []
        for letter in prefixes:
            rows.extend(session.search(company_name=letter))
    else:
        from .nyc_dob import all_rows
        rows = all_rows(status=args.status)

    collected = []
    counts = {"prefixes": len(prefixes), "rows": 0, "status_pass": 0, "class_pass": 0, "written": 0}
    status = normalize_status(args.status) if (args.status and args.status not in ("all", "All")) else ""
    from .cslb import LicenseRow
    for row in rows:
        counts["rows"] += 1
        st = row.get("status", "")
        if status and st and st != status:
            continue
        counts["status_pass"] += 1
        classes_txt = row.get("classes", "") or row.get("classification", "") or row.get("license_type", "")
        if args.class_filter and args.class_filter.lower() not in classes_txt.lower():
            continue
        counts["class_pass"] += 1
        collected.append(row)

    from .export import write_csv_rows
    seen = set()
    deduped = []
    for row in collected:
        key = row.get("license_number") or row.get("account") or row.get("name")
        if key in seen:
            continue
        seen.add(key)
        deduped.append(row)
    counts["written"] = len(deduped)
    write_csv_rows(deduped, args.out)
    print(" -> ".join(f"{k}:{v}" for k, v in counts.items()))
    print(f"out: {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
