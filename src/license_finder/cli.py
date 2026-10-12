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
        "label": "California Contractors State License Board (CSLB)",
        "transferLayer": "cslb",
    },
}


def _rows_from_board(board: str) -> type:
    if board != "ca-contractors":
        raise SystemExit(f"unknown board: {board}; catalog shows the supported ones")
    from . import cslb as board_mod

    return board_mod


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
            print(f"{key:16s} {cfg['label']}")
        print("catalog grows as more boards are verified. see README limits.")
        return 0

    mod = _rows_from_board(args.board)
    if args.cmd == "detail":
        session = CslbSession(delay=0.45)
        d = session.license_detail(args.license)
        import pprint
        pprint.pprint(d)
        return 0

    prefixes = [p for p in args.prefix.split(",") if p]

    s = CslbSession(delay=args.delay)
    status = normalize_status(args.status) if (args.status and normalize_status(args.status)) else args.status
    counts = {"prefixes": len(prefixes), "rows": 0, "status_pass": 0,
              "class_pass": 0, "written": 0}
    collected = []
    for row in s.sweep(prefixes, details=not args.no_details, status=status):
        counts["rows"] += 1
        counts["status_pass"] += 1
        if args.class_filter and args.class_filter.lower() not in row.classes.lower():
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


if __name__ == "__main__":
    raise SystemExit(main())
