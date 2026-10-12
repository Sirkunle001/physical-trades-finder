# Physical Trades Finder

Build prospect lists of local trade businesses in California: every electrician,
plumber, roofer, landscaper, solar installer, pool builder, welder and 40 more
trades, exported as a clean CSV that is ready for your CRM, dialer or mail merge.

The data comes straight from the state's public contractors register, read
directly. No API key, no account, no headless browser.

## What you can build with it

- A list of every active electrician (C-10) in the state
- A list of HVAC companies (C-20) in the cities you serve
- A list of new businesses: anyone who got licensed in the last year
- A list of sole owners (the operator answers the phone themselves) vs
  companies (an office with staff)
- A renewal-timing list: license expiry dates tell you when each business is
  doing paperwork, which is a natural time to reach out

Every list is one command. Pick a trade, optionally filter by city, get the CSV.

```
# all active pool builders
license-finder list --prefix A*,B*,C*,D*,E*,F*,G*,H*,I*,J*,K*,L*,M*,N*,O*,P*,Q*,R*,S*,T*,U*,V*,W*,X*,Y*,Z* --class-filter "C-53" --status Active --out pool_builders.csv

# quick sample: everything named ACME
license-finder list --prefix ACME --out sample.csv

# one full record, every field
license-finder detail 1098046
```

Small slices come out in seconds. A whole trade is one command and a batch run.

## What is on each row

| column | what it tells you |
|---|---|
| `name` | the business name on the register |
| `classes` | the trade(s) the business is licensed for, e.g. C-10 ELECTRICAL |
| `city`, `state`, `zip`, `street` | where the business is located |
| `phone` | the phone on the register |
| `entity` | sole owner, corporation, LLC and so on |
| `status` | Active, Expired, Cancelled, Suspended (normalized, filterable) |
| `issue_date`, `expire_date` | when the license started, when it is up for renewal |
| `license_number` | the register's own ID, kept for reference and dedupe |

## The trades it covers

California has 46 trade classes and all of them are inside the tool, captured
from the board's own classifications page:

```
license-finder classes
```

A sample of what is in there:

- A: General Engineering
- B: General Building (remodelers, homebuilders, GCs)
- C-10: Electrical
- C-20: HVAC
- C-36: Plumbing
- C-39: Roofing
- C-46: Solar
- C-27: Landscaping
- C-53: Swimming Pool
- C-60: Welding
- C-49: Tree and Palm
- ... and 35 more, from insulation (C-2) to well drilling (C-57)

Each trade is its own list. The CSV's `classes` column carries the trade per
row, so one export can be sliced any way you want afterward.

## How it works for you

1. Pick the trade (or run `classes` to browse the 46).
2. Run the command. The tool sweeps the register by name prefix so nothing gets
   skipped, fetches the full record for every match, normalizes the statuses,
   dedupes, and prints exactly what it found and what it filtered.
3. Open the CSV. City and zip are columns, so territory slicing is a
   spreadsheet filter. Sole owner vs company is a column. Renewal date is a
   column.

## Install

```
pip install physical-trades-finder   # or: pip install -e .
```

Requires Python 3.10+.

## License

MIT.
