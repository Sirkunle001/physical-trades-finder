# Physical Trades Finder

Build prospect lists of local trade businesses across US states: every electrician,
plumber, roofer, HVAC company, solar installer, builder and more, exported as a clean
CSV that is ready for your CRM, dialer or mail merge.

The data comes straight from the state boards that issue the licenses, read directly.
No API key, no account, no paid data vendor.

```
license-finder catalog          # every state and board it can read right now
license-finder classes          # California: the board's 46 official trade classes
license-finder list --board ca-contractors --prefix ACME,REDWOOD --out ca.csv
```

## What it covers today

| board | state | source | you get |
|---|---|---|---|
| `ca-contractors` | CA | Contractors State License Board | license #, business name, 46 trade classes, city, zip, street, phone, entity, status, issue + expiry |
| `tx-trades` | TX | TDLR license search | license #, business name, city, status, expiry (HVAC, electrical, plumbing, elevators and more in one register) |
| `fl-cilb` | FL | DBPR construction register (bulk) | license #, name, trade type, city, zip, street, issue + expiry, status |
| `il-idfpr` | IL | IDFPR professional register (4.37M rows) | license #, name, business name, license type, description, city, zip, county, issue + expiry, status |
| `pa-pals` / `pa-pals-facility` | PA | PA Licensing System (PALS) | license #, name, board, license type, city, county, zip, phone, email, status |
| `mi-trades` | MI | LARA construction trades (Accela) | license #, business name, trade type, contact person, city, zip, expiry, status |

## Command examples

```
# California: all active electricians named "Watt" (C-10)
license-finder list --board ca-contractors --prefix WATT --class-filter C-10 --out ca_electricians.csv

# Texas: everything plumbing-named in the TDLR register
license-finder list --board tx-trades --prefix PLUMB --status all --out tx_plumbing.csv

# Florida: the whole active construction register
license-finder list --board fl-cilb --status Active --out florida_contractors.csv

# Illinois: every roofing contractor in the register
license-finder list --board il-idfpr --prefix ROOFING --out il_roofing.csv

# Pennsylvania: every license held by a surname, plus the business-side search
license-finder list --board pa-pals --prefix MILLER --out pa_miller.csv
license-finder list --board pa-pals-facility --prefix CONTRACT --out pa_facility.csv

# Michigan: electrical contractors (license type chosen with --class-filter)
license-finder list --board mi-trades --prefix ELECTRIC --class-filter "Electrical Contractor" --out mi_electricians.csv
```

## How the flags work

`--prefix` is a sweep or a filter, depending on the board:

- CA, TX, MI, PA: business-name / surname prefixes (`ACME,REDWOOD` sweeps both).
- IL: a license-type filter (`ROOFING`).
- FL: an optional business-name filter; omit it and you get the whole register.

`--status` defaults to `Active`. Pass `all` to keep expired, cancelled and deceased
licenses too. Where a state's grid has no status column (TX, MI), the tool derives
Active/Expired from the expiry date rather than guessing.

`--class-filter` narrows by trade: `C-10` on CA, a license type on MI, a description
fragment on IL.

Every run prints its funnel (`rows -> status_pass -> class_pass -> written`) so you can
see exactly what was dropped, and rows are deduped by license number before writing.

## Install

```
pip install -e .
```

Florida and Michigan read through a browser session (one state portal gates automated
requests, the other renders results client-side):

```
playwright install chromium
```

Every other board runs on plain HTTP.

## Notes

- All data is public record, published by the state boards. The tool reads it, normalizes
  statuses and dedupes; it does not enrich contacts beyond what the state publishes
  (Pennsylvania is the only board that publishes emails).
- Registers refresh on the states' own schedules; Illinois and NYC-style Socrata datasets
  move daily, bulk files move with each board cycle.
- Built for list building, not verification. A license status is a point-in-time read.

## License

MIT.
