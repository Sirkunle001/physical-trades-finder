# license-finder

Keyless lookups against state professional-license boards, returned as clean,
deduped CSVs instead of webpage fragments.

Most licensing boards in the US publish their full licensee registers as
searchable websites. Each board, though, has its own interface, its own output
format, and its own idea of "status". People selling to a profession usually
want one thing from this data: a clean, filterable list of the operators worth
talking to. Going board to board and re-formatting results by hand is the slow
part; license-finder does the parsing, dedupe, and status normalisation for the
boards included in its catalog.

## What it does

Every supported board gives you:

```
license-finder catalog
license-finder list   --board ca-contractors --prefix ACME,REDWOOD --out.csv
license-finder detail --board ca-contractors 1098046
```

`list` runs a board sweep (comma-separated name prefixes), applies status and
classification filters, fetches the full record for each surviving row, dedupes
by license number, and writes:

```
license_number,name,name_type,classes,city,state,zip,street,phone,
entity,status,issue_date,expire_date
```

Fan counts are printed at every stage so you always know what got dropped and
why.

Example output (real CSLB records):

```
license_number,name,classes,city,state,zip,phone,entity,status,issue_date,expire_date
898355,WATT ELECTRIC,C10 - ELECTRICAL,HOLLISTER,CA,95023,(831) 637-1000,Corporation,Active,06/13/2007,05/31/2027
1098046,REDWOOD ADU LLC,B - GENERAL BUILDING,SACRAMENTO,CA,95817,(916) 619-9585,Ltd Liability,Active,10/24/2022,10/31/2028
```

## Supported boards

| board | state | trade | provenance |
|---|---|---|---|
| `ca-contractors` | CA | Contractors (CSLB) | verified live, keyless |

Every license class the board issues is listed inside the tool:

```
license-finder classes
```

46 classes ship with it (A General Engineering, B General Building, B-2
Residential Remodeling, plus 43 specialty C-codes from C-2 Insulation to
C-61 Limited Specialty), captured from the board's own classifications page
with the source URL and capture date stored in the data file. Each class is
its own slice for `--class-filter`.

The catalog only lists boards with a verified, tested, keyless access path and
unit-tested parsers with recorded fixtures. It will grow; unknown states or
trades guard against silently degraded access.


## Install

```
pip install license-finder   # or: pip install -e .
```

Requires Python 3.10+.

## License

MIT.
