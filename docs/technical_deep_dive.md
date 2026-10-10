# Technical deep dive

The README answers *what this is and how to run it*. This answers *how it works
and why it is built this way* — the questions a technical juror asks after the
three minutes are up, and the questions you will ask yourself at 02:00 when a
number looks wrong.

Everything here is re-derived from the code and the config as they stand on
6 October 2026. Where a figure comes from a measurement rather than from the
repository, it says so. `docs/decisions.md` carries the dated record of every
change to what a number means; this file describes the current state only.

---

## 1. The pipeline, end to end

```
config/sources.yaml          one file owns every URL
        │
        ▼
python -m src.fetch          52 files, ≈3.82 GiB, idempotent, robots-aware
        │
        ├───────────────┬──────────────┐
        ▼               ▼              ▼
build_exposure.py  build_context.py  build_geometry.py
 hazard ×           built-up, basins,  boundaries →
 population         future discharge,  simplified polygons
 per NUTS3 × RP     GDP, per NUTS3
 + Eurostat
   indicators
        │               │              │
        ▼               ▼              ▼
exposure.parquet   context.parquet   regions.geojson
        │               │              │
        └───────────────┴──────┬───────┘
                               ▼
                 api/main.py           11 JSON routes over src/
                       │
        ┌──────────────┴──────────────┐
        ▼                             ▼
   web/ (React)              app/streamlit_app.py
   5 tabs, SVG choropleth     6 tabs, no map, reads the
                              parquets directly, no build step
```

Two properties of this shape are deliberate.

**The two derived files are separate.** The exposure table is a multi-hour
continental pass over 300 MB rasters; the geometry is seconds over one 25 MB
boundary file. Re-running the slow one to redraw a map would be absurd, and
coupling them would guarantee it happened.

**Both UIs read the same frozen table.** They cannot disagree about a number,
because there is only one number - `app/streamlit_app.py` reads the parquet
directly rather than going through the API, which is why it needs neither the
server nor `npm`. They do NOT show the same views: React has three tabs
(Exposure, Vulnerability, Draft) and draws the choropleth inside the first;
Streamlit has four, adding the AI usage log, and its Exposure tab has no map.
The React UI is the one to demo.

---

## 2. Four coordinate systems, and which one does what

This is the section to read before touching anything. The most expensive
geospatial bug is silent: a layer in the wrong CRS still plots, still joins, and
still produces a number. It is just the wrong number.

| CRS | Where | Used for |
|---|---|---|
| **EPSG:3035** (ETRS89-LAEA) | `data_io.WORKING_CRS` | every area, distance and zonal computation |
| **EPSG:4326** | JRC hazard rasters; `data_io.WEB_CRS` | the hazard's own grid; the last step before display |
| **ESRI:54009** (World Mollweide) | GHS-POP | the population grid, and the grid exposure is computed on |
| **EPSG:27704** (Equi7 Europe) | JRC observed flood depth | the validation layer's own grid |

Three rules follow. The first is enforced in `src/data_io.py`; the second is
enforced where it matters rather than centrally - `scripts/build_exposure.py`
asserts the boundary CRS before opening a raster, and `exposed_population`
reprojects the polygons to the population grid itself. `data_io.check_alignment`
exists for the third-party case and is currently called by nothing, which is
worth knowing before relying on it.

- **A file with no CRS raises.** Guessing one is how a whole analysis lands
  silently in the wrong place. `load_vector` refuses rather than assuming 4326.
- **Reproject the polygons to the raster, never the raster to the polygons.**
  Reprojecting a raster of *counts* moves people between cells. `check_alignment`
  fails loudly when the two disagree, because `rasterstats` will otherwise return
  zeros for every polygon — a result that reads as "nobody is exposed" rather
  than as an error.
- **A tolerance is a distance, so it is applied in a metric CRS.** A degree is
  not a distance: 0.01° is about 1.1 km north–south everywhere but ~700 m
  east–west at Belgian latitudes and under 500 m in northern Finland.
  `build_geometry.py` therefore simplifies in 3035 and converts to 4326
  afterwards.

The hazard rasters are 3 arc-seconds — about **92 m north–south but 60 m
east–west** at Belgian latitudes. The cells are not square, so any area computed
in 4326 is wrong. `docs/geospatial_crash_course.md` works this through.

---

## 3. Exposure: what the number means

`Risk = Hazard × Exposure × Vulnerability`. This repository computes the middle
term and gives the third its own module; the first arrives as data.

### 3.1 The two modes

`src/exposure.py` offers `fraction` and `binary`, and they answer different
questions.

- **`fraction`** (default) thresholds the hazard at its own resolution, then
  averages the 0/1 wet mask over each population cell. A cell 30% flooded
  contributes 30% of its people. Right at 1 km, where one population cell holds
  roughly 185 hazard cells at Belgian latitudes.
- **`binary`** counts a population cell's whole population as soon as any part of
  it is flooded. Coarser, and an over-estimate by construction.

The order matters in `fraction` mode: **threshold first, average second.**
Averaging depths and thresholding afterwards answers "is the *mean* depth above
the threshold?", which systematically under-reports small deep floods.

### 3.2 `nodata_means_dry`, the argument that decides what the figure means

The JRC hazard maps are sparse: they store a depth **only** where there is
inundation. Measured on RP100 over a 1,468,800-cell window of Belgian land,
4.85% of cells carry a value and 100% of those are deeper than 0 m. On such a
layer the valid mask **is** the flood footprint.

- `nodata_means_dry=True` (default) — nodata is ground the layer looked at and
  found dry. The flooded share is the wet mask over the **whole** cell.
- `nodata_means_dry=False` — nodata is ground nobody looked at, which is what an
  AOI-clipped delineation (Copernicus EMSR, the Walloon 2021 layers) gives you.
  The share is measured over the observed part and extrapolated onto the unit.

Passing `False` for a sparse layer collapses the two: every cell holding any
water reads as wholly flooded, and the "fractional" figure becomes the binary
over-estimate under another name — **13,771,935 people against 5,065,526** over
BE/NL/LU at RP100, bit-identical to what `mode="binary"` returns. Passing `True`
for an AOI-clipped layer reports unobserved ground as dry. Neither is recoverable
from the output, so neither is inferred.

### 3.3 Four columns, and why `None` is not `0.0`

| Column | Meaning |
|---|---|
| `exposed_pop` | people on flood-prone ground, extrapolated onto the whole unit where the layer covered only part of it, or `None` when nothing was measured |
| `exposed_pop_observed` | the same count with **no extrapolation in it**. This is the one that is additive over disjoint windows, so a windowed build sums this and divides once at the end |
| `cells_counted` | population cells whose **centre** falls in the unit |
| `hazard_coverage` | the share of the unit, in [0, 1], the hazard layer covers |

A unit the population grid covers but the hazard raster does not would otherwise
report a measured `0.0`. That is the one error that must never reach a brief,
because it reads as reassurance. `None` means "not measured"; `0.0` with a
positive coverage means "measured, nobody exposed", which is a real finding.

`all_touched=False` on the zonal statistics: a cell belongs to the unit
containing its centre. `True` would count every boundary cell in *both*
neighbours, so the sum over all units would exceed the national total.

**Report `hazard_coverage` next to `exposed_pop`.** Below 1.0 the figure is an
extrapolation from the observed part onto the whole unit, and the reader is
entitled to know that.

### 3.4 Windowing: the population grid, not the hazard raster

A continental pass over one return period needs ~64 GiB if done in one go —
51,992 x 110,162 cells is 21.3 GiB per float32 array, and the band plus its
two derived masks are three of them. It is
therefore cut into pieces — and **which raster gets cut is a correctness
question, not a performance one.**

`scripts/build_exposure.py` takes row windows over the **population grid** and
reads whatever hazard region covers each one, with a two-cell margin so the warp
is never short of source. A population cell belongs to exactly one window by
construction, so nothing is written twice and the per-unit sums are additive
whatever the window count.

Cutting the hazard raster instead cannot have that property, and this repository
shipped that version until 6 October 2026. A population cell lying across two
hazard stripes is written by both, and `Resampling.average` renormalises over
whatever source area each piece happens to hold — so both pieces reported a
coverage near 1 for the same cell instead of roughly a half each. Summed coverage
reached **1.08 at two stripes and 1.17 at three**, when it must be 1, and the
continental RP100 total moved by **0.25% between 3 and 13 stripes**: 29,808,232
against 29,732,746 people, with 215 of 1,345 regions disagreeing and the worst
(PL514) by 14.7%. `tests/test_stripes.py` pins the invariant at 1, 2, 3, 5, 7 and
13 windows. See `docs/decisions.md` for the dated record.

Three running totals are accumulated, and which one is summed matters:

- `exposed_pop_observed` — the figure with **no extrapolation in it**. Summing
  `exposed_pop` instead would apply the extrapolation once per window.
- `cells_counted` — summed, because the windows are disjoint.
- `hazard_coverage × cells_counted` — so a unit's coverage is the cell-weighted
  mean over its windows, not a mean of means that would weight a window holding
  three cells like one holding three thousand.

The extrapolation onto unobserved ground then happens **once**, over the whole
unit. Under `nodata_means_dry` coverage is 1 everywhere but the layer's own edge,
so for a pan-European run it is the identity.

### 3.5 What is masked out, and why

Two companion rasters ship on the same grid as the depths, and both are applied
by default:

- **Permanent water bodies** — the river channel, the lakes and the sea, already
  water before any flood. They are patched into the depth rasters at exactly
  1.00 m, so they survive every threshold up to and including 0.5 m. Measured on
  the Benelux at RP10 they are 21.3% of wet cells; masking them moves the RP100
  figure by **−14.2%**.
- **Spurious depth areas** — cells the JRC itself flags as modelling artefacts.

`--min-depth-m` defaults to **0.5 m**, the usual threshold for damage to
buildings. Pass `0` for the any-water upper bound, and say which you used.

---

## 4. The two derived files, and the UI contract

### 4.1 `exposure.parquet`

One row per region × return period. Long rather than wide because every consumer
wants it that way — plotting, the LLM prompt, and the expected-annual-damage
integration, which needs the probability attached to each row.

**Return-period extents are nested**: the 100-year zone contains the 10-year one.
These rows must never be added together — RP10 + RP100 + RP500 triple-counts the
core floodplain. Report each separately, or integrate over probability with
`expected_annual_exposure`. `/api/exposure` enforces this by narrowing to one
period server-side and saying so in `defaulted_return_period`.

### 4.2 `regions.geojson`

`scripts/build_geometry.py` simplifies the 1,345 GISCO NUTS3 polygons at
**1 km** in EPSG:3035, converts to 4326, keeps two properties and rounds
coordinates to four decimals. 25 MB becomes 2.8 MB.

Two choices are load-bearing and both fail silently if got wrong:

- **The property names are the join key.** `Choropleth.jsx` reads
  `feature.properties[idKey]`, where `idKey` is whatever `/api/exposure` reports —
  `nuts_id` for a NUTS3 run, `lau_id` for a LAU zoom. GISCO's own spelling is
  `NUTS_ID`. Shipping that draws all 1,345 regions in the "not measured" grey,
  because the join finds nothing and nothing errors.
- **All 1,345 polygons are kept**, EU-27 or not. Dropping regions changes the map
  twice over: the missing regions, and the colour of every other one, because the
  legend's classes are quantiles over whatever is present.

### 4.3 The eleven routes

`/api/health`, `/api/meta`, `/api/exposure`, `/api/context`, `/api/geometry`,
`/api/vulnerability`, `/api/search`, `/api/draft`, `/api/languages`,
`/api/translate`, `/api/approve`.

`/api/context` serves the second frozen table, and it is a separate route rather
than extra columns on `/api/exposure` for a reason that is structural:
`vulnerability_indicators` picks the composite index's inputs by scanning numeric
columns, so a climate percentage or a basin share arriving on an exposure row
would be one selection away from becoming a min-max-scaled term in a weighted
mean — "this region's rivers rise faster, therefore its residents are more
vulnerable". The two tables are loaded separately and never merged server-side.
Its `climate_periods` block carries `single_member`, which is the field that
separates "one model chain, so nothing was compared" from "the chains disagree":
both read as zero regions agreeing on the sign, and only the first is true of
2071–2100.

`/api/approve` is the only route that writes. `/api/translate` is the only one
that can refuse its own output: a translation that changed a figure or moved a
citation comes back as **422**, not as 200 with a warning field, so no client can
render it by ignoring a flag. The choropleth is drawn as **SVG
from GeoJSON** — no tile provider, no API key — so the map still renders with the
network unplugged. That is why there is no Google Maps layer here and never will
be: a Static Maps call needs a billed key and its terms forbid redistributing the
imagery in a document that circulates.

---

## 5. Validation: the credibility half

`src/validate.py` is the part that answers "why should we believe your map?". It
scores the modelled hazard against the **observed** July 2021 flood extent and
returns three numbers, every one of them `None` rather than `0.0` when its
denominator is empty:

| Metric | Reads as |
|---|---|
| `hit_rate` | of the water that really came, how much did the model find? |
| `false_alarm_ratio` | of the water the model claims, how much was not there? |
| `iou` | the two together, in one number |

Everything is resampled onto **EPSG:3035 at 20 m**, the finer of the two inputs.
Coarsening the observed layer to ~90 m instead would erase exactly the narrow
urban strips the 2021 event is remembered for. `MIN_OBSERVED_CELLS = 25` is the
floor below which a unit is not scored at all — 25 cells at 20 m is one hectare,
and a hit rate computed on three pixels is noise with a decimal point.

Belgium is kept for this and only this: it is the one place with observed extent
to validate against. The study area is Europe.

---

## 6. The LLM layer: a workflow, not an agent

`src/workflow.py` is a LangGraph graph with **five nodes** — retrieve, refuse,
draft, verify, approve — and a human gate before anything is written.

| Guard | Value | Prevents |
|---|---|---|
| `RECURSION_LIMIT` | 8 | a graph that loops |
| `MAX_REDRAFTS` | 2 | a model that rewrites forever |
| `MIN_GROUNDING` | 0.7 | a draft that cites nothing |

**Verification is not an LLM call.** `src/rag.py` grounds every claim in the
policy corpus and refuses rather than inventing; the grounding score is computed
arithmetically over content words, not asked of a model. A model that marks its
own homework is not a check.

The distinction from an agent is the point, and it is the one `docs/workflow.md`
argues at length: fixed nodes, fixed order, a bounded number of calls, and a
human who approves. Nothing here decides to do something that was not written
down in advance.

---

## 7. The test suite

**<!-- numbers:tests_collected -->550<!-- /numbers --> tests, offline**: no network, no model, no key. Measured 8 October 2026 on
Windows: all <!-- numbers:tests_collected -->550<!-- /numbers --> collect and pass, nothing deselected. Do not quote that as a
property of the platform — Smart App Control moved to enforcement on 7 October
2026 and refused rasterio's unsigned DLLs, which left 433 collectable and 431
passing on Windows while WSL2 ran the lot; by the next morning it allowed the
same wheel again with nothing reinstalled. **The policy moves both ways, so
re-measure instead of citing either state**, and keep the WSL2 venv for the
mornings it flips back — see the note in `requirements.txt`. The suite mocks the network
away, which is exactly what hides a missing 300 MB raster — so
`scripts/check_offline_readiness.py` answers the question `pytest` cannot, in
byte counts, and exits 1 when the demo would still need a connection.

The count above is not typed: it sits in a `<!-- numbers:tests_collected -->`
block that `scripts/docs_numbers.py --write` fills from `pytest --collect-only`,
and `tests/test_docs_numbers.py` fails the suite when any marked block in the
docs disagrees with the repository. Edit the prose, never the digit.

Per-file counts measured 10 October 2026 with
`pytest --collect-only -q | grep '::' | cut -d: -f1 | sort | uniq -c`; they sum to the
marked total above. Twenty-five files — the previous table listed twenty-two and
summed to 473, a figure that had survived three suite changes by being typed.

| File | Tests | Guards |
|---|---|---|
| `test_offline_readiness.py` | 51 | the demo runs with the Wi-Fi off: the three verdicts, `--strict`, a rejected file is not present, the two caches `src.fetch` does not fill |
| `test_validate.py` | 50 | the scoring grid, the three metrics, `None` vs `0.0` |
| `test_api.py` | 48 | the eleven routes, the 404s that name their builder, the JSX guards |
| `test_streamlit_app.py` | 47 | the fallback UI, the translation tab, the climate and coverage caveats |
| `test_fetch.py` | 42 | robots, idempotency, multi-file expansion, a stale rejection page is quarantined, colliding paths are refused |
| `test_rag.py` | 31 | cite-or-refuse |
| `test_losses.py` | 29 | the RDH euro vintages and the levelling |
| `test_basins.py` | 27 | the shared-basin layer: the declared crosswalk, the sliver floor |
| `test_exposure.py` | 23 | the two modes, `nodata_means_dry`, the masks, the build checkpoint |
| `test_workflow.py` | 23 | the five nodes, the guards, the human gate |
| `test_climate.py` | 21 | the future layer: provenance, the median, the ensemble, the member fetcher |
| `test_vulnerability.py` | 21 | the composite index, its sensitivity, and what one indicator cannot prove |
| `test_rdh.py` | 16 | the paged client and its cache |
| `test_toon_io.py` | 15 | the compact table encoding for prompts, and a tokenizer that cannot fetch its table says so |
| `test_apsfr.py` | 13 | the two reporting cycles, the dissolve, the claim it must not make |
| `test_svgmap.py` | 16 | the offline choropleth: quantile classes, holes kept, the outermost regions out of the extent, hatching where the chains disagree, a legend that names its sixths and stays inside the viewBox |
| `test_demographics.py` | 12 | the sparse cube, the overlapping age buckets, the NUTS2 caveat |
| `test_translate.py` | 12 | a translated figure never moves |
| `test_events.py` | 11 | the coverage blind-spot probe |
| `test_stripes.py` | 9 | the figure does not depend on the window count |
| `test_assets.py` | 8 | the built-up surface: the archive, the unit, the share |
| `test_docs_numbers.py` | 10 | a number typed in a doc that no longer matches the code fails the suite |
| `test_legislation.py` | 7 | every legal citation has a CELEX and a URL, and `policy_answer.md` cites no article the registry lacks |
| `test_build_geometry.py` | 5 | the join key, the projection, the simplification |
| `test_data_io.py` | 3 | the CRS engine is alive |

`test_data_io.py` earns its three tests: a dead `pyproj` is the silent failure in
this stack. `geopandas` still imports, `GeoDataFrame(..., crs=...)` still returns
an object, and only a `UserWarning` says the CRS was dropped — after which every
zonal statistic is the right arithmetic on the wrong piece of Europe. Measured on
6 October 2026, the whole suite passed with `pyproj` stubbed out. Now it does not.

---

## 8. Where the numbers in this file come from

| Claim | Source |
|---|---|
| <!-- numbers:tests_collected -->550<!-- /numbers --> tests | `scripts/docs_numbers.py --write`, which runs `pytest --collect-only` and rewrites the marked blocks; the per-file counts are typed by hand |
| 52 files, ≈3.82 GiB | `src.fetch.expand()` over `config/sources.yaml` |
| <!-- numbers:sources_declared -->42<!-- /numbers --> declared inputs, <!-- numbers:sources_verified -->34<!-- /numbers --> with a verification date, <!-- numbers:sources_licensed -->11<!-- /numbers --> with an explicit `licence:` | `scripts/docs_numbers.py` over `config/sources.yaml`: entries with an `id`; `verified` not null; `licence` non-empty |
| 1,345 NUTS3 polygons | the GISCO NUTS 2024 file itself |
| the 0.25% stripe discrepancy | two continental RP100 builds, 6 October 2026 |
| 4.85% of cells carry a value | a 1,468,800-cell window of Belgian land, RP100 |
| the permanent-water figures | the Benelux at RP10 and RP100 |

**One caveat on the Benelux figures.** 5,065,526, 4,344,955, 13,771,935 and the
ratios drawn from them were all measured **before** the windowing fix of
6 October 2026, on a build whose answer depended on its stripe count. They are
kept because the comparisons they support — sparse-vs-AOI, masked-vs-unmasked —
are ratios between two runs of the same code, and those survive. The absolute
counts do not: re-derive any of them before putting it in a brief.

Re-derive rather than quoting this table. Every number above is a reading of the
repository at a moment, and the repository moves.
