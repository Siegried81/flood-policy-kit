# Scope: Europe, not Belgium

The challenge asks for **European regions**. The 2021 floods in Belgium, the
Netherlands and Germany are the motivation in the call text, not the study area.
A team that hands in a Belgium-only analysis has answered a question nobody
asked — and has also thrown away the one thing that makes a European dataset
worth using, which is that it lets you compare countries.

This page is the design that follows from that, and it is the reason the data
choices differ from an obvious Belgian pipeline.

## The unit of analysis: NUTS3

| Level | Count (EU) | Use it for |
|---|---|---|
| NUTS0 | 27 | A headline for the brief's first line |
| NUTS2 | ~240 | Where Eurostat income and poverty data lives |
| **NUTS3** | **1,165** (1,345 in the GISCO file, incl. EFTA + candidates) | **The working unit: provinces/arrondissements** |
| LAU | **95,066** (97,987 in the GISCO file, incl. EFTA + candidates) | Only for a zoom-in on one named valley |

**NUTS3 is the right default.** It is fine enough to rank and to map
meaningfully, coarse enough that a pan-European run finishes in minutes, and it
is the level EU regional policy actually operates on — a jury of JRC staff thinks
in NUTS.

Drop to LAU only for the worked example (one valley, one country). Stay at NUTS3
for anything you present as a European finding.

## What the NUTS3 choice produces on disk

Two files, both derived and neither committed — `data/` is ignored, so a fresh
checkout has to build them. Until they exist the API answers 404, and the React
choropleth renders nothing while reporting no error at all.

| File | Built by | Holds |
|---|---|---|
| `data/processed/exposure.parquet` | `python scripts/build_exposure.py` | one row per region x return period |
| `data/processed/regions.geojson` | `python scripts/build_geometry.py` | the polygons the choropleth draws |

They are separate on purpose: the exposure table is a multi-hour continental run
over the hazard rasters, the geometry is seconds over one 25 MB boundary file,
and re-running the slow one to redraw the map would be absurd. They join on the
region identifier — `nuts_id` here, `lau_id` for a LAU zoom — which is why
`build_geometry.py` renames GISCO's `NUTS_ID` rather than passing it through.

The geometry is simplified to 1 km, in EPSG:3035 so that the tolerance is a real
distance. That is below one screen pixel at a continental viewport, and it takes
the file from 25 MB to under 3 MB. Lower it for a single-country zoom, where the
viewport is roughly twenty times tighter.

## What this changes about the data

### Population: 1 km, not 100 m

`GHS_POP_E2025_GLOBE_R2023A_54009_1000_V1_0.zip` — **323 MB, one global file,
verified downloadable**. At NUTS3, where a region is hundreds of km², 1 km
population is entirely adequate, and it removes the whole tile-mosaicking problem
(Europe spans roughly two dozen 100 m tiles, with the trap that the row boundary
cuts through countries).

Keep the 100 m tiles only for the zoom-in.

### Boundaries: GISCO NUTS, not national sources

`NUTS_RG_01M_2024_3035_LEVL_3.geojson` (25,247,626 B) or the same layer as a
shapefile, `NUTS_RG_01M_2024_3035_LEVL_3.shp.zip` (7,324,754 B) — both measured
by `Content-Length` on 6 October 2026. The GeoJSON is what `sources.yaml`
declares, and it is the larger of the two by a factor of three: that is the
format's text encoding, not more detail. EPSG:3035, one file, every country, one
vintage. Statbel, the Walloon geoportal
and their equivalents are national: useful for validating one country, useless
for comparing twenty-seven.

**Pin the vintage and say which.** NUTS 2021 and NUTS 2024 are different
geometries *and* different code sets.

### Demographics: Eurostat, not Statbel

The equity lens has to work in every country, so it has to come from one
harmonised source:

| Need | Eurostat dataset | Level | State |
|---|---|---|---|
| Population by age | `demo_r_pjangrp3` | NUTS3 | Declared in `sources.yaml`; checked live 2026-10-06 (BE332 total = 637,220) |
| At-risk-of-poverty rate | `ilc_li41` | NUTS2 | Declared in `sources.yaml`; checked live 2026-10-06 (BE33 = 14.6) |
| GDP | `nama_10r_3gdp` | NUTS3 | Declared in `sources.yaml`; checked live 2026-10-06 (BE332 = 26,435.29 MIO_EUR, flagged provisional) |
| Population density | `demo_r_d3dens` | NUTS3 | Candidate, not yet declared or checked |
| Disposable household income | `nama_10r_2hhinc` | NUTS2 | Candidate, not yet declared or checked |

The first three are the ones a figure can be built on today — and on the GDP
endpoint, **pin the unit**: `MIO_EUR`, `MIO_PPS` and `EUR_HAB` are three
different numbers, mixing them is silent, and recent years carry a provisional
flag that has to be read rather than dropped. The last two are plausible codes
that nothing in this repo has called yet, so treat their level column as an
expectation rather than a fact until one of them returns data.

Income and poverty are published at NUTS2, not NUTS3. So a vulnerability index
mixing both levels must **say** that the income component is NUTS2 applied to its
NUTS3 children — an assumption that is defensible and must be stated, not hidden.

Access through the Eurostat API (`ec.europa.eu/eurostat/api/dissemination/...`),
which is open and needs no credentials.

### Hazard: unchanged

The JRC maps already cover Europe — that is what they are. Nine return periods,
272–350 MB each, measured 2026-10-06. Downloading all nine is **2.61 GiB**, and
the whole `geodata` section — 27 entries, 49 jobs once the multi-file ones are
expanded, 37 of them files to download and 12 of them runtime API calls — is
**≈3.78 GiB**, and the full fetch including the policy corpus (13) and context (2)
is **52 files** and **≈3.82 GiB**: one evening before the 25th, and
nothing on the day. The counts come from `src.fetch.expand()` over
`sources.yaml` as it stood on 6 October 2026, so re-derive them rather than
quoting this paragraph.

**At European scale the whole-file download is not a convenience, it is the only
option.** The files are tiled and range-readable, so `/vsicurl/` looks like it
should save the download. Measured on RP100: a Belgium window is 220 tiles and
2.4 MiB over the wire, but the EU27+EFTA bbox is 35,525 tiles and 172 MiB — 56%
of the file, in tens of thousands of requests, which at one request per second
per host is hours per return period. So `/vsicurl/` belongs to the Belgian
rehearsal; the European run reads local files.

## The alignment problem, and the honest way through it

The hazard is 3 arc-sec in EPSG:4326. Population is 1 km in Mollweide. Different
CRS, different resolution, different grid origin.

**The rule does not change: never resample the population counts.** So:

1. Threshold the hazard into a 0/1 wet mask **first**, at its own resolution.
2. Resample that mask onto the population grid with `average`, which gives the
   **fraction of each 1 km cell that is flooded** — a number in [0, 1].
3. `exposed = population × fraction_flooded`.
4. Zonal-sum per NUTS3 region.

Thresholding before averaging matters: averaging depths and thresholding after
answers a different question (*is the mean depth above the threshold?*) and
systematically under-reports small deep floods.

At 1 km with a 3 arc-sec input there are roughly **185** hazard cells per
population cell at Belgian latitudes, so the fraction is well resolved. The
figure is latitude-dependent, because a 3 arc-sec cell keeps its ~92.6 m
north-south height but its east-west width is 111,320 m × cos(latitude) / 1,200:
~58 m at 51°N for 5,407 m² and 185 cells per km², falling to ~142 cells at 35°N
and rising to ~275 at 65°N. Even the coarsest European case resolves the
fraction to better than a percent, which is the point; the exact number is not a
constant and should not be quoted as one. This is the step to explain if the jury
asks how you combined two incompatible grids.

## What a European scope buys you in the brief

A Belgium-only finding is a description. A European one supports a comparison,
and comparison is what a Commission audience acts on:

- **Which regions carry the most exposure per inhabitant**, not in absolute
  terms — absolute counts just rank by population and tell you nothing.
- **Where exposure and vulnerability coincide**, which is not where either is
  highest alone. This is the equity reading FARI asks for, and it is a genuinely
  European question.
- **Cross-border river basins**: the Meuse runs through France, Belgium and the
  Netherlands. A flood does not stop at NUTS boundaries, and pointing that out
  is an argument for EU-level action rather than national action — exactly the
  kind of conclusion this jury exists to hear.
- **Who is already covered by insurance and who is not** — the protection gap
  varies enormously across the EU, and that variation is a policy lever.

## Keep Belgium as the rehearsal, not the answer

Use the Vesdre valley and EMSR518 for the dress rehearsal in week 4: it is the
only place where you have **observed** flood extent to validate the modelled
hazard against. That validation is a methods result you can carry into the real
analysis — "we checked the model against the 2021 observations and it
under/over-estimates by X" — without the study area being Belgium.

Belgium is also the one place with **two independent observations** of the same
flood: Copernicus EMSR518 (four packages — a first delineation *and* a monitoring
pass per AOI, so the largest extent rather than the earliest) and the Walloon
administration's own July 2021 layers, one extent and one IDW-interpolated depth.
Scoring the two observations against each other first gives the uncertainty of
the ground truth, which is what makes "the model misses X%" a defensible number
instead of an artefact of one delineation.

One conversion to get right before any of that: the satellite-derived depth maps
are in **centimetres** and the hazard maps in **metres**. The validation is a
depth comparison, so this is exactly where a factor-100 error would hide behind a
plausible result.
