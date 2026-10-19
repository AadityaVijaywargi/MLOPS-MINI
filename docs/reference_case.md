# Section 4.1 reference case (Evaluation 1)

> "Residential building proposed on a small plot abutting a narrow road."

## Test values

| Field | Value |
|---|---|
| Jurisdiction / zone | BBMP-Bengaluru, Residential (Main), Ring III |
| Use | residential single dwelling |
| Plot | 9.0 m wide x 12.0 m deep = 108 sq.m |
| Abutting road | 6.0 m |
| Building | Stilt + GF + 3 (`floors_above_ground: 4`, `has_stilt: true`), height 12.5 m |
| FAR / coverage | 1.70 / 60 % |
| Setbacks | front 1.5 m, rear 1.0 m, left 1.0 m, right 1.0 m |

File: `eval/examples/reference_case.json` (scenario `S01` in `eval/scenarios.yaml`).

## Passages the case depends on

All from *BDA RMP-2015 Zoning Regulations* (`ZR2015`); ids are the chunk ids the system cites.

| # | Clause (chunk id, page) | Text | Role |
|---|---|---|---|
| 1 | §4.1.2 Table 10 note (ii)(b) - `ZR2015:T10:ii.b`, p.28 | "If the road width is less than 9.0 m, then the maximum height is restricted to 11.5 meters or Stilt +GF+2 floors (whichever is less) irrespective of the FAR permissible" | **the separately stated road-width limit** - printed under the *FAR* table of the zone, not referenced from the setback table |
| 2 | §3.1(ii)-(iii) - `ZR2015:s3.1:ii`, `ZR2015:s3.1:iii`, p.20 | "Up to 11.5 m height, the setbacks are calculated as percentages of depth and width of the plot, as per Table.8." / "Table.9 shall be referred for Buildings which are more than 11.5 m in height to fix the setbacks." | height threshold that switches setback tables |
| 3 | Table 9 - `ZR2015:T9`, p.21 | "Above 11.5m up to 15m 5.00" | setbacks for 12.5 m: 5.0 m all round |
| 4 | Table 8 - `ZR2015:T8`, p.20 | "Above 6.0 up to 9.0 1.0 m on all sides" / "Above 9.0 m 8 % 8% 12% 8 %" | the setback table a single search returns; satisfied by these setbacks *if* the building were <= 11.5 m |
| 5 | Table 10 row 1 - `ZR2015:T10`, p.28 | "1. Up to 360 Up to 75 % 1.75 Up to 12.0" | FAR 1.75 / coverage 75 % for plots <= 360 sq.m on roads <= 12 m |
| 6 | §3.8(ii) - `ZR2015:s3.8:ii`, p.23 | "FAR and height of the building shall be regulated according to the width of public street or road only." | general link between height and road width |

## Reference answer

**Route: `revise-and-recheck`**

| Provision | Required | Proposed | Finding |
|---|---|---|---|
| Table 10 note (ii)(b) - height on a road < 9.0 m | <= 11.5 m and <= Stilt+GF+2 | 12.5 m, Stilt+GF+3 | **violated** |
| §3.1(iii) + Table 9 - setbacks above 11.5 m | 5.0 m all round | 1.5 / 1.0 / 1.0 / 1.0 m | **violated** |
| Table 8 - setbacks up to 11.5 m | sides 1.0 m, front 12 % x 12 = 1.44 m, rear 8 % x 12 = 0.96 m | 1.0 / 1.5 / 1.0 m | not applicable at 12.5 m (would be satisfied at <= 11.5 m) |
| Table 10 - FAR | <= 1.75 | 1.70 | satisfied |
| Table 10 - ground coverage | <= 75 % | 60 % | satisfied |

The interaction the brief describes is exactly here: read alone, Table 8 says the setbacks
are fine and Table 10 says FAR is fine. Only the note under Table 10, which the setback
table never mentions, caps the height at 11.5 m on this 6 m road. Exceeding 11.5 m also
moves the building into Table 9, so the setbacks fail as well. Reducing the design to
Stilt+GF+2 at <= 11.5 m (scenario `S02`, 10.5 m) clears both and routes
`clear-for-submission`.

## Why one retrieval pass misses it (measured on this index)

Top-6 results from `/v1/search` for three phrasings (2026-10-19, index of 881 chunks):

| Query | Mode | `ZR2015:T10:ii.b` in top 6 |
|---|---|---|
| "setbacks for residential building on 9 m x 12 m plot" | hybrid / dense | no / no (returns Table 8, Table 9, notes of other zones) |
| "Residential building proposed on a small plot abutting a narrow road" (the brief's wording) | hybrid / dense | no / no |
| "maximum height of building restricted by road width" (query the modifier check derives) | hybrid / dense | **rank 1 / rank 1** |

A query that already contains every variable ("...road width 6 m height 12.5 m...") also finds
it, but a request phrased about setbacks does not. That is why the research agent has an
explicit modifier-check step that derives "<limit> restricted by <variable>" queries from the
provisions it has already read (see `docs/architecture.md`).
