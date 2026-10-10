# Decisions

The dated record of every change to **what a number means**. Code comments say
why a measurement is defined the way it is; this file says when it changed and
what it was before, so a figure quoted from an older run can be placed.

Newest first.

---

## 2026-10-07 (late evening) — the far-future period gets its second model chain

**MEASUREMENT CHANGE — `change_pct_ensemble_median_2071_2100`.** The CDS archive
held `VIC-WUR-EUR-11` for 2011-2040 and 2041-2070 and not for 2071-2100, so the
far-future period ran on `E-HYPEgrid-EUR-11` alone. Its two files arrived today
and `context.parquet` was rebuilt. Measured before and after, 1,198 regions:

| period | members | median | regions agreeing on sign |
|---|---|---|---|
| 2011-2040 | 2 | +12.2% | 976 (81.5%) |
| 2041-2070 | 2 | +19.9% | 994 (83.0%) |
| 2071-2100 **before** | 1 | **+25.6%** | **0, by construction** |
| 2071-2100 **after** | 2 | **+20.3%** | **943 (78.7%)** |

**The single member overstated the median by 5.3 percentage points.** That is the
number to carry: any 2071-2100 figure quoted from a build before today is one
model chain's opinion, and it was the higher of the two.

**And the period becomes quotable.** With one chain,
`ensemble_agrees_on_sign_2071_2100` was False for all 1,345 regions - not because
the models disagreed but because nothing was compared - so no sentence about the
direction of the change was licensed. There are now 943 regions where both
chains point the same way. Among them the median rise is **+26.3%**, with a
typical member spread of **+15.9% to +35.5%**: a direction, a size, and an
interval a jury can ask about.

Note that the agreement rate at 78.7% is the LOWEST of the three periods, below
2011-2040's 81.5% and 2041-2070's 83.0%. The far future is where the chains
diverge most, which is what anyone would expect and what the one-member table
could not have shown.

**What was missing was never a period.** The time coverage went to 2100
throughout; the hole was one cell of the model-by-period grid, which is easy to
miss when the periods all look present. `docs/datasets.md` now carries that grid
explicitly, and `scripts/fetch_cds_member.py` makes the request reproducible and
verifies every downloaded filename against what was asked before anything enters
the ensemble directory.

---

## 2026-10-07 (night) — nine return periods, and what two of them were hiding

**MEASUREMENT CHANGE — `expected_annual_exposure`.** `exposure.parquet` carried
RP100 and RP500 only, since the first continental build. Nine rasters were on
disk; seven had never been measured. The table is now all nine — 10, 20, 30, 40,
50, 75, 100, 200, 500 — at 1,345 regions each, 12,105 rows.

`src/exposure.py::expected_annual_exposure` integrates exposure over the annual
probability by trapezoid. With two points it spanned p from 0.002 to 0.01: **0.8%
of the probability axis**, and the 0.8% furthest from where the people are. A
100-year flood happens once a century; a 10-year flood happens ten times as often
and floods 19.3 million people rather than 29.7 million, so it dominates the
integral. Measured on the real table, same code, same regions:

| | probability span | total expected annual exposure |
|---|---|---|
| two points (RP100, RP500) | 0.002 – 0.01 | **260,849** |
| nine points (RP10 – RP500) | 0.002 – 0.1 | **2,335,501** |

**A factor of nine.** Any figure quoted from `expected_annual_exposure` before
this build understated it by about 89%.

**And it was not a uniform understatement, which is the worse half.** The
ranking moves, so the two-point table did not merely report a small number - it
named different regions as the priority. Among the top ten on nine points:
NL364 (Delft en Westland) was **14th** on two points and is **6th**; DE300
(Berlin) moves 10th to 7th; AT130 (Wien) moves 3rd to 8th. A region whose
exposure grows fastest between the frequent floods is invisible when only the
rare ones are measured.

**The nesting holds**, which is the check that the nine builds agree with
physics: 19.3M at RP10, 22.9M, 24.8M, 26.0M, 26.9M, 28.6M, 29.7M at RP100, then
RP200 and RP500 above it — strictly increasing, 7 unmeasured regions in every
period, median hazard coverage 1.0 throughout.

**Stripe independence confirmed at continental scale.** RP100 came back at
**29,727,887** exposed, to the person, against the 6 October build that ran at a
different window count. `tests/test_stripes.py` asserts the figure does not
depend on the windowing; this is that claim measured on the real rasters rather
than on a fixture.

The build ran as nine separate processes inside a 16 GB WSL2 VM at `--stripes
72`, peaking around 7.5 GB, with each period parked as it finished. See the entry
below for why that matters.

---

## 2026-10-07 (evening) — a finished return period is written before the next one starts

**NOT a measurement change.** No figure moves. What changed is where the build
writes, and it changed because the old answer cost an hour of compute.

`scripts/build_exposure.py` accumulated every return period in memory and wrote
`exposure.parquet` once, at the end. Measured today: running all nine periods
under WSL2 at `--stripes 24`, the Linux OOM killer took the process during RP100
at **15.7 GB resident against a 16 GB cap**, after RP10, RP20, RP30, RP40, RP50
and RP75 had all completed. Every one of them was lost, because none had been
written. A continental pass is about eight minutes, so the crash cost one period
and the design cost six more.

Each period is now parked in `data/processed/exposure_parts/` as it finishes, and
a rerun reuses what is already there unless `--rebuild` is passed. An
interruption now costs the period it interrupted.

**The part name carries the parameters that change the numbers** —
`rp100_fraction_d0.5_m2.parquet` — because a part built at another depth
threshold, in another mode, or with different masks is a different measurement,
and resuming onto it silently would be worse than recomputing. Pinned in
`tests/test_exposure.py`.

**On the memory itself.** `--stripes` exists for this: the windows are disjoint,
so the result does not depend on the count, and `tests/test_stripes.py` holds
that. 24 was not enough for the larger extents — a rarer return period floods
more cells, so RP100, RP200 and RP500 are the heavy ones, not RP10. The rebuild
runs at 72. The machine's `.wslconfig` caps the VM at 16 GB deliberately, because
Docker Desktop shares it, and that cap was not touched.

**473 tests** at the close of the day, up from 452 when the Eurostat join landed:
thirteen in `test_apsfr.py`, three in `test_climate.py` for the member fetcher,
four across the two UI suites for the coverage caveat and the gap table, and two
here for the part naming and the assembly. All 473 pass under WSL2; on Windows
433 collect and 431 pass, which is Smart App Control and not the code.

---

## 2026-10-07 (late afternoon) — what the State declared, beside what the model shows

`src/apsfr.py` adds the Areas of Potential Significant Flood Risk the Member
States designated under Article 5 of the Floods Directive. Every other hazard
layer in the kit measures what the water does; this one measures what a
government said about it, and the corpus already carried the Directive's text
without the reporting behind it. The pair is the point: a region with exposed
residents and no declared area is a compliance question, which is a different
kind of finding from a high exposure count.

**It is not an accusation.** A State may have assessed an area under Article 4
and concluded the risk is not significant, which the Directive allows. The
defensible sentence names the exposure and the absence of a designation and
leaves the conclusion to a human, so the table carries `apsfr_declared` and
`apsfr_share` and draws no inference.

**Three properties of the service, each measured because each produces a wrong
number quietly.**

*Two reporting cycles in one layer.* `cYear` is 2010 for 496 polygons across 5
countries and 2018 for 12,173 across 25, and AT, DE, ES and FR appear in BOTH.
A query that does not pin the cycle designates the same ground twice and a share
can exceed 1. The default is the current cycle, and `cycles()` exists because the
cost is real: Lithuania reported in 2010 and not in 2018, so the current cycle
alone shows it as having declared nothing.

*Generalisation is mandatory, and a coarse tolerance deletes the layer rather
than simplifying it.* Ungeneralised the service answers 50 polygons in 18.7 MB
and refuses any `cYear` query with HTTP 500 — under `f=json`, a 200 whose body is
a 500. But the features are small, a median of about 0.001 km2. Measured on 300
Italian polygons:

| tolerance | payload | survive a structure repair | median area |
|---|---|---|---|
| 0.001 (~110 m) | 1.35 MB | 169 of 300 | 0.0008 km2 |
| 0.0001 (~11 m) | 5.51 MB | 300 of 300 | 0.0010 km2 |
| 0.00002 (~2 m) | 15.7 MB | 300 of 300 | 0.0011 km2 |
| none | HTTP 500 | — | — |

At 110 m, 44% of the layer collapses to zero width and is dropped, and the first
run of this code reported **Germany, Spain and France as having declared
nothing** — the strongest claim the module can make, produced entirely by a
tolerance. The kit uses 0.0001.

*The overlay, not a union.* The obvious implementation unions all 12,173 polygons
and intersects each region against the result; it does not finish. The work here
is a spatially indexed overlay followed by a dissolve per region — and it is a
dissolve rather than a sum because APSFRs reported under different units of
management overlap, so adding the intersected pieces puts a share above 1 on a
delta.

**`src/basins.py::_repair` is now `repair`, and takes a `method`.** 48% of the
generalised polygons self-intersect, and shapely's default linework repair
returns collections mixing lines with polygons that the overlay rejects outright
("Overlay input is mixed-dimension"). The structure method guarantees polygonal
output. It is opt-in, and `basins` still uses linework, so **no basin share
moves**: changing the repair under a published figure is exactly what this
project does not do silently.

**The layer does not cover every Member State, and that decides what it can
say.** Measured against the service 2026-10-07: 26 country codes across both
cycles, and **Ireland is not one of them** - zero polygons, for a State that
certainly designates areas under Article 5. So `apsfr_declared == False` has two
causes that are identical in the data and completely different in meaning: the
State designated nothing there, or this dataset never carried its reporting.
`declared_by_region` therefore returns `apsfr_country_reported` and leaves the
share **NaN** where the country was never covered, because 0.0 would read as a
finding. Without that column the compliance question this layer exists to ask
would have been asked of Ireland on the strength of Ireland's absence.

Relatedly, a region can intersect a NEIGHBOUR's declared area, since rivers are
shared: on the real run, regions in AL, CH, ME, MK, RS and TR come back with a
declared share although none of those States reports here. Geometrically honest,
and it belongs in the caption.

**The overlay runs on the exact geometry, and the obvious optimisation was
measured and removed.** It takes **1,071 s** for 1,345 regions, which is slow
enough to want thinning the polygons first - `simplify(25 m,
preserve_topology=True)` after the repair, predicted to be a fourth-decimal
effect on regions kilometres across. It shipped here for about an hour. Measured
end to end on the real layer it is wrong twice:

| | wall time | max share deviation | regions past 0.001 |
|---|---|---|---|
| exact geometry | **1,071 s** | — | — |
| thinned at 25 m | **4,683 s** | 0.004 | 44 of 1,147 |

**4.4x slower, and it moves the numbers.** `simplify` on 12,173 detailed polygons
costs more than the overlay it was meant to cheapen, and it can re-introduce
self-intersections into geometry that was just repaired, which makes the overlay
slower again. The knob is gone rather than defaulted off, and the reason is in
`src/apsfr.py` so nobody re-adds it from the same intuition. The test that
"proved" it was free ran on ten-metre boxes, where 25 m of thinning is a
different operation entirely - the fixtures are now at a real regional scale.

**Two more sources declared and deliberately not used.** `eea_natura2000_sites`
(verified: 23,799 Habitats Directive sites, anonymous access) and
`copernicus_corine_land_cover` (product page verified; the download needs a
registered account, so it is a pre-event errand with a human in it). Article 6(5)
of the Floods Directive asks for the consequences to the environment and to
cultural heritage, and this kit measures residents and built-up surface and
nothing else. They are declared so the gap is traceable instead of silent, and
both `caveat` fields say DECLARED, NOT YET USED. No figure may be quoted from
them until something computes one.

---

## 2026-10-07 (afternoon) — the vulnerability index has a second and third axis

`config/sources.yaml` had declared `eurostat_population_by_age`, `eurostat_poverty`
and `eurostat_gdp_nuts3` from the start, all three `access: api`, and no code in
the repo called any of them. The cost was not a missing column: the composite
index had one indicator, which is the defect recorded in the entry above.

`src/demographics.py` now fetches them, caches the responses under
`data/processed/eurostat_cache/`, and `scripts/build_exposure.py` joins two of
them onto the frozen table. Measured on the real build, 7 October 2026:

| | before | after |
|---|---|---|
| indicators offered | `exposed_pop` | `exposed_pop`, `share_over_65`, `poverty_rate` |
| `share_over_65` coverage | — | 2,672 of 2,690 rows, Eurostat 2025 |
| `poverty_rate` coverage | — | 2,396 of 2,690 rows, Eurostat 2025 |

The coverage figures above are against the **two-period** table of that moment,
2,690 rows. The nine-period build later the same day carries the same join at
12,024 and 10,782 of 12,105 rows: the share per region is identical, there are
simply nine rows per region instead of two.
| confidence at p=0.3, RP100 | 1,338 `single_indicator` | 6 `robust`, 1,332 `indicative` |

**NOT a measurement change to anything that already existed.** `exposed_pop`,
`total_pop` and every raster figure are untouched. What changed is that the
ranking now has axes to be sensitive to, so `sensitivity` reports a result
instead of a tautology.

**The trap in `demo_r_pjangrp3`, measured rather than assumed.** The dataset
publishes `Y85-89`, `Y_GE85` and `Y_GE90` side by side and they are not disjoint:
on BE332 in 2025, Y85-89 = 10,832 and Y_GE90 = 6,723, summing to exactly
Y_GE85 = 17,555. Taking "every code from 65 upwards" counts the over-85s twice
and reports **22.76% against a true 20.01%** — 2.76 percentage points, in the
direction that makes a region look more vulnerable. `AGES_65_PLUS` is the
disjoint set, and `Y_GE65` is not a way out: it exists as a code and returns an
empty series at NUTS3.

**`ilc_li41` is a NUTS2 figure applied to NUTS3 children**, and the table says so
in `poverty_rate_level` rather than in a doc nobody opens beside the number. The
assumption is defensible; hiding it is not.

**Vintages are stored as TEXT.** `vulnerability_indicators` picks the index's
inputs by scanning for numeric columns, so `share_over_65_year` as an integer
would have become an indicator meaning "a more recent census makes residents more
vulnerable" — the `total_pop` trap of 6 October, a third time. Stored as text it
is excluded by dtype rather than by remembering to maintain a list.

**GDP is not an indicator.** A region is not vulnerable for being rich, so
`gdp_meur` goes to `context.parquet`, where it turns an absolute loss into a
share of regional wealth. Eurostat publishes it for 536 NUTS3 units against 1,336
for population, and the missing ones stay missing.

**452 tests**, up from 441: eleven in `test_demographics.py`. All 452 pass under
WSL2; on Windows 414 collect and 412 pass, which is Smart App Control and not the
code.

---

## 2026-10-07 (midday) — one indicator is not a weighting, and is no longer certified robust

**MEASUREMENT CHANGE — the `confidence` label.** `sensitivity` perturbs the
weights of a composite index and labels a rank by how often it survives. With a
single indicator there is nothing to perturb: `w * (1 + U(-p, p))` rescales the
one term and never reorders it, so every row sits in the same top n on every
draw, `top_n_frequency` is 1.0 by construction, and the row was labelled
**"robust"** — at any perturbation.

That is not a rounding error in a corner case. `data/processed/exposure.parquet`
as frozen on 6 October carries exactly one column that `vulnerability_indicators`
will offer, `exposed_pop`: everything else is an identifier, a denominator
(`total_pop`) or raster bookkeeping (`cells_counted`, `hazard_coverage`), all
excluded for reasons recorded below. So the flagship ranking ran on one
indicator, and **all 1,338 measured regions came back "robust" at perturbation
0.9**. The label failed in the reassuring direction, which is the one nobody
questions: a reader takes "robust" for "this survived a stress test" when
nothing was stressed.

There is now a sixth label, `single_indicator`, between `no_discrimination` and
`robust`. Measured on the real table, before and after:

| | before | after |
|---|---|---|
| one indicator (`exposed_pop`), p=0.9 | 1,338 `robust` | 1,338 `single_indicator` |
| two indicators, p=0.9 | — | 4 `robust`, 1,334 `indicative` |

`top_n_frequency` is unchanged and still reported: being in the top n is a true
statement about the index, it is simply not evidence about the weights.

This is the same defect class as `ensemble_agrees_on_sign` in `src/climate.py`,
and it is fixed the same way — one member cannot agree with itself, one indicator
cannot outvote itself.

**What it does not fix.** The ranking still has one indicator. The socio-economic
layers that would give it something to weigh — `eurostat_population_by_age`,
`eurostat_poverty`, `eurostat_gdp_nuts3`, `statbel_income` — are declared in
`config/sources.yaml` and joined by nothing. The label now says so instead of
hiding it.

**441 tests**, up from 439: two in `test_vulnerability.py`, one per side of the
new boundary.

---

## 2026-10-07 (morning) — the context table reaches a reader, and a one-member period is not model disagreement

`scripts/build_context.py` has been writing `data/processed/context.parquet`
since 6 October — 1,345 regions, 23 columns — and nothing read it. Neither
`api/main.py`, nor `app/streamlit_app.py`, nor `src/rag.py`: all three opened
`exposure.parquet` only. So the kit's built-up exposure, its shared-basin shares
and its only forward-looking layer were computed and never shown. That is now
`GET /api/context`, a Streamlit tab and a React tab.

**NOT a measurement change.** No figure in either table moved. What changed is
that three groups of figures are now visible, and one of them arrives with a
caveat it did not have before.

**The caveat, and why it needed a field of its own.** The CDS archive on disk
holds two hydrological model chains for 2011–2040 and 2041–2070 and **one** for
2071–2100 — `E-HYPEgrid-EUR-11` is there, `VIC-WUR-EUR-11` was never requested
for the far-future period. `src/climate.py` already refused to call a single
member agreement with itself, so `ensemble_agrees_on_sign_2071_2100` is `False`
for all 1,345 rows. Measured on the real table:

| Period | Regions measured | Median of the regional medians | Chains | Regions agreeing on sign |
|---|---|---|---|---|
| 2011–2040 | 1,198 | +12.2% | 2 | 976 |
| 2041–2070 | 1,198 | +19.9% | 2 | 994 |
| 2071–2100 | 1,198 | +25.6% | **1** | **0** |

A reader seeing only that last zero reads "the models disagree about 2071–2100".
The true statement is "nothing was ever compared", and the two license different
sentences: the first is a finding, the second is a gap. So
`api/main.py::climate_periods` reports `single_member` beside the count, both UIs
branch on it, and the ranking of largest increases sits on the far side of that
branch — there is deliberately no way to read a direction off a one-chain
period. The median still shows, because it is a real measurement; it is simply
not a projection. Downloading `VIC-WUR-EUR-11` for 2071–2100 is what makes the
far-future period quotable, and both UIs name that member.

**Context is a separate table, and never merged into the exposure frame.**
`vulnerability_indicators` picks the composite index's inputs by scanning numeric
columns — the trap that already caught `total_pop` on 6 October. A climate
percentage or a basin share joined onto an exposure row would be one selection
away from becoming a min-max-scaled term in a weighted mean, i.e. "this region's
rivers rise faster, therefore its residents are more vulnerable". Two separate
loaders, two separate routes, pinned by a test in `test_api.py` and another in
`test_streamlit_app.py` that assert the context columns never reach the
indicator list.

**A test harness that was passing for the wrong reason.** `tests/test_streamlit_app.py`
patched `pd.read_parquet` for the whole process and keyed `Path.exists` to the
exposure path only. A second loader would therefore have been handed the
*exposure* table under climate headings, and `Path.exists` would have fallen
through to the real filesystem — "present" on this machine, "absent" in CI.
`_frozen` now keys both paths and dispatches `read_parquet` on which one it was
asked for, with context absent by default, which is CI's shape.

**439 tests**, up from 426: +9 in `test_api.py` and +4 in `test_streamlit_app.py`.
Run in both conditions, parquets present and parquets moved aside, with the same
result. 399 pass locally and 2 fail; the 2 are `test_climate.py` hitting Windows
Smart App Control, which went to enforcement on this machine at 08:01 on
7 October and blocks rasterio's unsigned DLLs, and 38 further tests in
`test_assets.py`, `test_exposure.py` and `test_stripes.py` cannot be collected
for the same reason. None of it is a code defect — CI runs Linux and is green.

---

## 2026-10-06 (later) — the extrapolation is weighted by people, and three windowing bugs are closed

An adversarial review of the same day's windowing rewrite found four defects,
all reproduced by running code. They are recorded together because the first is
a change to what `exposed_pop` means and the other three decided whether the
figure was stable at all.

**MEASUREMENT CHANGE — the extrapolation denominator.** `exposed_pop` divided the
population-weighted numerator by the UNWEIGHTED mean of `hazard_coverage` over a
unit's cells. That is only unbiased if population is independent of coverage,
and at the layer's edge it is the opposite: the uncovered part is sea or another
continent and holds nobody. Measured on a two-cell unit with 1,000 people in the
observed cell and none in the unobserved one, the true answer 1,000 was reported
as **2,000**. The division is now by the share of the unit's PEOPLE that were
looked at - `pop_observed / pop_total`, both new columns - so an empty
unobserved area extrapolates onto nothing. Where every populated cell was looked
at, which is almost everywhere on a pan-European run, it is the identity.
`hazard_coverage` is unchanged and still reports the area share, as the
qualifier it has always been.

**Three bugs, each now pinned by a test:**

* `--stripes 1` read **four of 110,162 hazard columns**. The population grid is
  global Mollweide and its bounding box is ~900 m wider than the projection's
  valid domain, so `transform_bounds` received `inf` at the corners, dropped
  them, and returned `left == right == 0.0`. The build wrote a parquet without
  complaining. It under-reported longitude at every window count - 17 degrees a
  side at ten windows - and only worked because the JRC raster stops at 67 E,
  inside the under-estimate. The hazard window is now narrowed in ROWS only, at
  full width: in Mollweide y depends on latitude alone, so that bound is exact.

* **A window the hazard did not reach was dropped from the denominators.** Its
  population cells never entered `cells_counted` or the unit's total, both of
  which divide the figure. Measured on one fixture, the same data gave 36,000 to
  144,000 people depending on the window count - a 3x spread - and a coverage of
  0.75 for a unit the layer covered a quarter of.

* **`mode="binary"` was divided by coverage** by the build script, although
  `exposed_population` explicitly refuses to and says why in a comment. Through
  the script it produced a third figure that was neither the binary count nor
  anything documented.

**Also fixed, same review:** `assets.built_share_exposed` divided an
extrapolated numerator by an un-extrapolated denominator and reached **2.0** -
200% of a unit's built-up surface "exposed". It now uses the observed numerator,
which is in range by construction.

The continental figure of 29,727,889 recorded in the entry below was produced
BEFORE these four fixes, at ten windows. It is not invalidated by the stripe
bugs, which do not bite at ten windows on this raster, but the weighted
extrapolation moves whichever of the ten edge units had coverage below 0.999.
Re-derive before quoting it.

---

## 2026-10-06 — the fractional extrapolation moved from the cell to the unit, and the windowed build is now exact

**What changed.** In `mode="fraction"`, `src/exposure.py` divided each population
cell's flooded share by that cell's own coverage before summing the unit. It now
sums the observed figure first and divides once, per unit. A new column
`exposed_pop_observed` carries the un-extrapolated figure, which is what
`scripts/build_exposure.py` accumulates across stripes. `mode="binary"` is
untouched and still never extrapolates.

**Why.** The per-cell division is not additive. A population cell lying across
two hazard stripes had its flooded fraction extrapolated to the whole cell once
per stripe, and the two were then added, so the figure depended on a memory
setting. `scripts/build_exposure.py` called that sum *exact*; it was not.

**Measured, RP100 over all 1,345 NUTS3 regions, before the change:**

| stripes | exposed population |
|---|---|
| 13 | 29,808,232 |
| 3 | 29,732,746 |

75,486 people apart, 0.25%. 215 regions disagreed, the worst (PL514) by 14.7%,
and more stripes always meant more people — the signature of double counting at
the internal boundaries rather than of rounding.

**What this invalidates.** Every `fraction`-mode figure produced before today was
computed with the per-cell extrapolation AND with whatever stripe count the run
used. Figures quoted from an older run are not comparable with one produced now,
and the RP100 Benelux numbers recorded in the 2026-10-06 entries below are among
them.

**How it was fixed.** By cutting the right raster. The build now takes row
windows over the POPULATION grid and reads whatever hazard region covers each
one, with a two-cell margin so the warp is never short of source. A population
cell belongs to exactly one window by construction, so nothing is written twice
and the sum is additive whatever the window count — the property the old
docstring claimed. `scripts/build_exposure.py --stripes` still exists and still
trades memory for passes; it no longer trades accuracy for them.

`tests/test_stripes.py` pins the invariant at 1, 2, 3, 5, 7 and 13 windows and
passes. It did not exist before today, which is why the error survived.

**Proved at continental scale.** The same RP100 build, 1,345 NUTS3 regions, run
twice after the fix:

| windows | exposed population |
|---|---|
| 13 | 29,727,889.31 |
| 3 | 29,727,889.31 |

The two differ by 0.000001 people in total and by 0.0000018 on the worst single
region - float64 rounding, nothing else. Before the fix the same pair differed by
75,486 people.

**The corrected figure is 29,727,889**, below both of the wrong ones, which is
the direction the diagnosis predicted: fewer boundaries meant less double
counting, so the striped totals were inflated and the 3-stripe run was merely
less wrong than the 13-stripe one. Any RP100 exposure figure quoted from before
today is high by up to a quarter of a percent, and by much more on individual
regions.

---

## 2026-10-06 — the choropleth's polygons are a derived file, simplified at 1 km

`api/main.py` served `data/processed/regions.geojson` on `/api/geometry` and
nothing in the repo produced it. The endpoint answered 404, `Choropleth.jsx`
returned null, and the map — the first deliverable a jury looks at — rendered
nothing on a clean checkout while reporting no error. `scripts/build_geometry.py`
is the missing producer.

**No figure in the brief changes.** Every number is computed in EPSG:3035 from
`exposure.parquet`, before this file exists; the geometry only decides what is
drawn. It is recorded here anyway because two of its choices are visible to a
reader and would otherwise be invisible to a reviewer:

* **Simplified at 1 km, in EPSG:3035 and not in degrees.** A tolerance is a
  distance, and a degree is not one: simplifying in 4326 thins northern Europe
  harder than the south, at the same nominal tolerance. 1 km is under one screen
  pixel at a continental viewport and takes the file from 25 MB to 2.8 MB.
* **All 1,345 polygons are kept, EU-27 and not.** Dropping regions would change
  what the map shows twice over: the missing regions, and the colours of all the
  others, because the legend's classes are quantiles over whatever is present.

The error messages for both derived files used to point at `docs/scope.md`, which
described neither. They now name the script that builds the file, and `scope.md`
has the section they were reaching for.

---

## 2026-10-06 — permanent water bodies and spurious areas are masked out, and the depth threshold defaults to 0.5 m

`scripts/build_exposure.py`

**Before.** The frozen table counted a population cell as flooded if the hazard
raster put *any* water on it (`--min-depth-m` defaulted to 0.0), and no mask was
applied, although the kit downloads two.

**After.** `Europe_permanent_water_bodies.tif` and
`Europe_spurious_depth_areas.tif` are set to the hazard's nodata before each
stripe is measured, and `--min-depth-m` defaults to **0.5**.

**Why, with the measurements that forced it.**

* The permanent water bodies are the river channel, the lakes and the sea —
  already water before any flood — and they are patched into the depth rasters
  at exactly **1.00 m**, so they cleared every threshold up to and including the
  damage threshold. On the Benelux at RP10 they were **21.3% of all wet cells**.
  Removing them at RP100 moves BE/NL/LU from **5,065,526 to 4,344,955** people,
  **−14.2%**.
* The spurious-depth layer is the JRC's own flag for cells whose modelled depth
  is an artefact. Keeping them meant presenting the publisher's known-bad values
  as findings.
* At 0.0 m the figure answered "who stands on ground the model puts any water
  on", which includes a centimetre of sheet flow across a field. 0.5 m is the
  usual threshold for damage to buildings, the depth at which a ground floor
  becomes uninhabitable and an adult cannot walk. The threshold moves the
  headline by a factor of two with no change of data: BE/NL/LU at RP100 is
  **5,065,526** at any water, **3,949,210** at ≥ 0.5 m, **2,610,894** at ≥ 1.0 m.

**What it does not fix.** Flood defences are still absent from the model, and
there is no European dataset of defence standards to add. The figure remains an
**undefended** extent, which biases every country the same way **except the
Netherlands** — protected to 1-in-10,000-year standards and the country the
ranking puts first. Say "undefended" when quoting any absolute number.

**Both older readings stay reachable**, so a figure can be reproduced:
`--keep-permanent-water`, `--keep-spurious-areas`, `--min-depth-m 0`.

---

## 2026-10-06 — fraction mode stopped double-counting on sparse hazard rasters (`nodata_means_dry`)

`src/exposure.py`

**Before.** `exposed_population(mode="fraction")` derived "where the hazard layer
looked" from the raster's valid mask. The EFAS/JRC `Europe_RP*_filled_depth.tif`
rasters are **sparse** — they store a depth *only where there is inundation*
(README D03: "Only land areas are covered"; measured on RP100 over 1,468,800
cells of Belgian land, 4.85% carry a value and 100% of those are deeper than
0 m). So "looked at" *was* the flood footprint, the flooded share divided by
itself, and the result was 1.0 in every covered cell.

**Consequences, on real data, the 85 NUTS3 regions of BE/NL/LU at RP100:**

* **13,771,935** reported against a correct **5,065,526** — **2.72×** — and
  bit-identical to `mode="binary"`, the mode this function's own docstring calls
  a bad over-estimate at 1 km.
* Worst single region `NL363` Agglomeratie Leiden en Bollenstreek: **265,014
  against 26,452 — 10.0×**. Also `BE213` Turnhout 9.5×, `BE224` Hasselt 6.8×.
* `hazard_coverage` became "the flooded share of the region" (median 0.0856), so
  the table told the reader that ~91% of every European region was unobserved —
  a false statement about a dataset covering all European land.
* Inverted failure for the very case the missing value was introduced for: a
  region inside the domain with no flood pixels reported `exposed_pop = None`
  ("nobody looked") where the truth is a measured **0.0**.

**After.** New keyword `nodata_means_dry: bool = True`. Under the default,
nodata is ground the layer looked at and found dry, so the observation mask is
all-ones inside the domain and the extrapolation only acts at its edge. Binary
mode takes its coverage from the raster's own extent rather than its wet mask,
and still never reads the band.

**`nodata_means_dry=False` is the correct reading for an AOI-clipped layer** —
Copernicus EMSR delineations, the Walloon 2021 layers — where nodata genuinely
means "outside the area studied". Pass it explicitly for those.

Verified against an independent re-implementation of the whole pipeline:
**maximum absolute difference 0** across all 85 regions.

---

## 2026-10-06 — `cells_counted` and `hazard_coverage` are not vulnerability indicators

`api/main.py`, `app/streamlit_app.py`

**Before.** `NON_INDICATOR_COLUMNS` excluded only `return_period` and
`annual_probability`, so every other numeric column was offered as a
vulnerability indicator. `cells_counted` and `hazard_coverage` are numeric and
sit *before* `exposed_pop` in the table, so they led the offered list — and both
UIs default to its first three entries. The composite index was being built out
of raster bookkeeping rather than out of the people living there.

**After.** Both are excluded. `hazard_coverage` belongs **next to** a figure as
its qualifier — the share of the unit the hazard layer actually observed — never
inside one.

**Side effect to watch.** With them gone, the default `indicators[:3]` is
`total_pop, exposed_pop, share_over_65`, so the default index now ranks partly on
raw population. Choose indicators deliberately before quoting a ranking.

---

## 2026-10-06 — the NUTS3 denominator: say which one

`config/sources.yaml`, `README.md`, `docs/scope.md` and four other docs

**Before.** Several documents said "~1,166 NUTS3 regions".

**After.** The GISCO `NUTS_RG_01M_2024_3035_LEVL_3.geojson` holds **1,345**
polygons: **1,165** in the EU-27 (`EU_STAT == "T"`), **46** in EFTA (CH 26,
NO 17, IS 2, LI 1) and **134** in the candidate and potential-candidate
countries (TR 81, RS 25, AL 12, MK 8, ME 1, XK 7).

**Two errors were stacked in 1,166.** It is an EU-only figure applied to a file
that also carries EFTA and the candidates, dropping 180 regions. And even
corrected for scope it is the **NUTS 2021** count: on this 2024 vintage the EU
count is **1,165**, because `DEG0P` (Eisenach) was absorbed into the
Wartburgkreis, taking Germany from 401 to 400.

Any count now states whether it is EU-only or the whole file.

---

## 2026-10-06 — the shared-basin figure: the basin, not the polygon

`src/basins.py`, `config/international_basins.yaml` (new), `scripts/build_context.py`

The layer that answers *"is this region flooded by water it does not govern"*
was measuring something else. Three defects, all proven before being repaired.

**It could not run at all.** The module required a `CNTR_CODE` column; the kit's
own `boundaries()` returns `nuts_id, region, country`. Every real call raised
`ValueError`, and `build_context.py` reported the basin half as a *missing
dataset* rather than as a bug. Both names are accepted now.

**A border sliver made a basin international.** The districts and the NUTS3
regions are independent renderings of the same borders, so their edges disagree
by a few hundred metres everywhere. Measured against the 1,345 regions: **109 of
the 182 districts the frame reaches touched two or more countries, and one
touched eight**. A country must now hold **50 km²** of a district to count; with
that floor, exactly one district spans a border — `DE2000`, the German Rhine.

**And the question itself was unanswerable from the source.** The WFD publishes
**one polygon per member state per basin**, and those polygons are disjoint: the
three Belgian and Dutch Scheldt rows overlap by **0 km²** and measure 12,025,
3,773 and 3,164 km². Each lies in one country, so grouping by polygon reported
**every international basin in Europe as unshared** — the opposite of the truth,
delivered as `0.0`, which reads as a finding rather than an absence. The service
has no international-basin key: all 25 fields were listed. Names do not rescue
it — `MEUSE`, `MAAS`, `LA MEUSE` and `INTERNATIONAL RIVER BASIN DISTRICT OF THE
MEUSE` are one basin under four strings, 180 distinct values for 196 rows.

**After.** `config/international_basins.yaml` declares **68 districts in 22
international basins**, each justified by the layer's own `nameTextInternational`
and each listing the districts it deliberately does *not* group, with the reason —
including the Croatian and Slovenian "Adriatic" pair, which a naive name match
joins and which are two coastal districts rather than one basin.

Because it is declared rather than measured, it is the one thing here that has to
be falsifiable. `src.basins.check_crosswalk()` refuses a code the layer does not
carry, a district claimed twice, a basin inside one country, and a basin whose
portions do not reach the same ground. **All 22 pass.** The contiguity test is
"every district reaches the largest piece", not "the union is one piece": the
strict form failed the Rhine, whose six districts share one body of 168,166 km²
beside six fragments of **0 km²** left by the geometry repair, and the Nemunas,
which has a detached 720 km² outlier holding no district at all.

**What changes in a number.** `shared_basin_share` now means *the share of a
region lying in a basin reported by more than one country*, not *in a polygon
that crosses a border*. Measured on the 1,345 NUTS3 regions:

| | by polygon | by basin |
|---|---|---|
| regions with any cross-border share | 224 | **810** |
| regions wholly inside a shared basin | 124 | **603** |
| shares above 1.0 | 0 | 0 |

A factor of 3.6, and the difference is not a rounding: Namur now reads
`shared_with = [DE, FR, LU, NL]`, and Aalst, Oudenaarde and Roeselare read
`[FR, NL]`. Before, they read `[]`.

It remains a **floor**: Switzerland, Belarus, Ukraine and Serbia hold large parts
of the Rhine, the Nemunas, the Vistula and the Danube and do not report under the
WFD.

**One incidental finding.** `returnGeometry=false` returns all 196 districts with
their attributes in **one request, under a second**. The eight pages, the two
minutes and the 289 MiB are the geometry alone.

---

## 2026-10-06 — raw population is not a vulnerability indicator

`api/main.py`, `tests/test_api.py`, `tests/test_streamlit_app.py`

**Before.** `vulnerability_indicators` offers every numeric column not named in
`NON_INDICATOR_COLUMNS`. The continental rebuild added `total_pop`, so the offer
list became `["total_pop", "exposed_pop"]` — **`total_pop` first**. Both UIs
default to the head of that list, so the default composite score changed because
a column was added to a parquet file. The entry above this one had flagged the
risk as a "side effect to watch"; watching it was not enough.

**After.** `total_pop` is named in `NON_INDICATOR_COLUMNS`. Min-max scaled into
an equally weighted mean it ranks a region as vulnerable for being populous, and
it is absent from `vulnerability.DEFAULT_WEIGHTS`, which is where this index
declares what it is made of — so offering it contradicted the module's own
definition.

**The rule this leaves.** Any column added to `exposure.parquet` is judged
against that set in the same pass. A numeric column that nobody excludes is an
indicator, silently.

---

## 2026-10-08 — a border sliver named a partner country the share denied

`src/basins.py`, `tests/test_basins.py`

**Before.** `shared_with` was read off every basin a region's polygon touched.
The country lists it reads are built behind `MIN_COUNTRY_AREA_M2` (50 km²), the
floor that stops two independent renderings of the same border reporting 109 of
182 districts as international. The *pieces* `shared_with` iterated were not
behind that floor. So a region overhanging a neighbour's district by less than
50 km² collected that neighbour as a partner, while the very same sliver was
correctly discarded when the basin's countries were counted.

The result was a row that contradicted itself: `shared_basin_share` 0.0,
`basin_countries_max` 1, and `shared_with` `[EL]`. Measured on
`context.parquet`: **58 of 1,345 regions** carried a partner list their own
share denied — three Albanian, three Bulgarian and five Greek regions naming
each other across the same border, five Swiss naming FR, two German naming DK.

**After.** `_others` reads the countries of the region's **shared** basins only,
so the list and the share are taken off the same basins by construction.
Re-measured on the real layer: **34 regions change, 33 of them losing a list
that was entirely sliver**, and one (BG413) dropping a spurious `EL` from a list
of twelve. The headline cases are untouched — Namur still reads
`[DE, FR, LU, NL]`, Groot-Rijnmond `[AT, BE, CH, DE, FR, LU]`, Wien its eleven.

**What this changes about a number.** `shared_with` is now a statement about
basins the pipeline classified as crossing a border, not about polygons that
touch. Regions with a non-empty list fall from 929 to 896 on a rebuild of
`context.parquet`; `shared_basin_share` itself is unchanged, because it always
filtered on `is_shared`. The 810/603 counts in the 2026-10-07 entry above are
share-based and therefore stand.

**Rebuilt 2026-10-08** (`scripts/build_context.py --stripes 40`; 40 rather than
the default 10 because WSL has 15 GB and a continental pass peaks near 20 GB -
stripes are memory only and the result does not depend on them). The prediction
held exactly: non-empty `shared_with` **810**, `shared_basin_share > 0` **810**,
contradictions **0**, and Namur still reads `[DE, FR, LU, NL]`.

Tests: 431 passed / 2 failed before, **432 passed / 2 failed after** (Windows,
three rasterio modules deselected). The two failures are `test_climate.py`
hitting the blocked rasterio DLL, not this change.

---

## 2026-10-08 — two indicators, two scales, and that is deliberate

`src/demographics.py`, `src/apsfr.py`, `app/streamlit_app.py`,
`tests/test_demographics.py`

Found by reading an export of `exposure.parquet` at RP50: `share_over_65` 0.19
beside `poverty_rate` 14.0 for the same region.

**Measured.** On the real table, `poverty_rate` spans **1.4 to 50.7** and
`share_over_65` **0.027 to 0.372**. Both are offered as vulnerability
indicators. Neither column name carries a unit.

**Not changed, and why.** Eurostat publishes the at-risk-of-poverty rate as
14.6, not 0.146, and a brief quoting "14.6%" has to match its source. The
composite index is unaffected: `vulnerability._min_max` rescales each indicator
from its own extremes, so a linear change of unit cannot reorder anything. The
defect is confined to what a reader sees in a table or a CSV.

**Done instead.** The unit is now stated in `poverty_rate`'s docstring against
its sibling's, and `test_the_two_indicators_keep_their_published_units` pins both
scales so that "normalising" one later is a deliberate act with a failing test in
front of it rather than a tidy-up.

**Still open, and it is a naming decision rather than a bug:** the columns could
say their unit (`poverty_rate_pct`), which would touch `api/main.py`,
`app/streamlit_app.py`, `scripts/build_exposure.py` and the tests, and would
change a column name every older export carries.

**Also recorded in the same pass:** `apsfr_share` is comparable *within* a
Member State and not *between* two. The Directive sets what must be designated
under Article 5 and leaves the geometry convention national, so the declared
share of national territory runs from **99.908 %** (BE, essentially one polygon
over the whole country) to **0.004 %** (ES, CY), a factor of **23,095**. The
shape index — perimeter over that of an equal-area circle — separates the
conventions: 1.5 for Belgium and Croatia against 51 for Germany and 74 for
Luxembourg, a river reach reported as a ribbon rather than a zone. Germany's 648
polygons total 76 km²; Belgium's 28 total 30,695 km². The measurement is now in
the `src/apsfr.py` docstring and in the Streamlit panel's caption, and the
reading it forbids is any cross-country ranking of `apsfr_share`.

**And a reporting hole, verified live on the EEA service 2026-10-08:** the 2010
cycle holds 496 polygons across AT, DE, ES, FR and LT; the 2018 cycle holds
12,173 across 25 countries. **Ireland is in neither.** Lithuania is in 2010 only,
which `src/apsfr.py` already documents. So the layer omits two EU-27 Member
States, and the service says nothing about it.

Tests: **433 passed / 2 failed** (Windows, three rasterio modules deselected;
the two failures are the blocked rasterio DLL).

---

## 2026-10-08 — the first scored deliverable was missing: there was no map

`src/svgmap.py` (new), `app/streamlit_app.py`, `tests/test_svgmap.py` (new),
`tests/test_streamlit_app.py`

**Before.** The Streamlit tab was called `map_tab`, its heading said "Exposed
population", and it drew a **bar chart and a table**. No geography, no colour.
`folium` and `streamlit-folium` were declared in `requirements.txt` and
**nothing imported them**; `src/data_io.py::to_web` carried a docstring saying
"for folium/leaflet, as the last step before display" for a display that was
never written. The only choropleth in the repo was `web/src/components/
Choropleth.jsx`, which needs the API running and a Vite build. So the deliverable
the challenge scores first did not exist in the app that runs with no build step.

**Why not folium, now that it is decided.** A Leaflet map fetches basemap tiles
from a tile server, and `docs/day_of.md` requires the kit to run with the Wi-Fi
off in front of a jury. That is almost certainly why the import was never
written. The two packages stay declared for now, unused, rather than being
removed in the same pass as a feature lands.

**After.** `src/svgmap.py` draws an inline SVG choropleth: no network, no build
step, no key. Three measured decisions in it:

* **EPSG:3035, not raw degrees.** Plotting longitude directly stretches the map
  east-west by 1/cos(latitude); the kit computes in 3035 everywhere else, so the
  picture and the numbers now agree about where things are.
* **Quantile classes, not a linear ramp.** The exposure share is severely
  skewed. Measured at RP100, the six class bounds are 0.84 %, 1.90 %, 3.39 %,
  5.61 %, 9.22 %, 70.82 % — a linear ramp over that range paints all but the
  Dutch tail in the palest colour. The bounds are printed in the legend so a
  reader can see the classes are relative.
* **The outermost regions do not set the viewport.** French Guiana is in South
  America, Réunion and Mayotte in the Indian Ocean, the Azores, Madeira and the
  Canaries in the Atlantic, Svalbard and Jan Mayen in the Arctic. Measured on the
  GISCO NUTS 2024 file: with them the extent is **12,850 × 9,486 km**, without
  it is **4,680 × 4,029 km** — 6.5 times the area, so continental Europe would
  occupy about a seventh of the picture. They are still **drawn** and the caption
  **names all 16 of them**, because a region dropped from a picture with no note
  reads as a region with nothing to report. Ceuta and Melilla are deliberately
  not in that list: they are in Africa but 15 km off the Spanish coast and move
  the extent by nothing at all, so calling them off-map would have been a caption
  that was untrue.
* **A region with no measurement is grey, never the colour of zero.** Seven regions at RP100 (this entry first said eight, a miscount: re-measured 2026-10-08 on the frozen table, `exposed_pop` is empty on 7 of the 1,345 RP100 rows, and 7 is what the map greys).

**A test-harness hole closed with it.** `_frozen()` keyed the exposure and
context parquets explicitly and let everything else fall through to the real
disk — so a geometry test would have drawn a real choropleth of Europe on this
machine and taken the "nothing to draw" branch on the runner, which is the exact
shape of bug that harness exists to prevent. `regions.geojson` is now keyed too
and defaults to absent.

**Also in this pass.** The "Region identifier" selectbox offered one option on
every pan-European run — a control that asks the reader to choose and then gives
them no choice. With one identifier present it is now stated as a caption; the
selector returns when the table really carries two.

Tests: 433 passed / 2 failed before, **449 passed / 2 failed after** (Windows,
three rasterio modules deselected; the two failures are the blocked rasterio
DLL). Thirteen of the sixteen new tests are `tests/test_svgmap.py`.

---

## 2026-10-08 — the draft tab could never have worked, for three reasons

`src/rag.py`, `src/toon_io.py`, `app/streamlit_app.py`, `tests/test_rag.py`,
`tests/test_toon_io.py`, `tests/test_streamlit_app.py`

Found by pressing the button: `No model reachable: 413 Client Error: Payload Too
Large`.

**1. The 413 is a rate limit wearing the wrong status code.** Measured against
the live endpoint: Groq refuses anything over **8,000 tokens per minute** for
`openai/gpt-oss-120b` on the `on_demand` tier, and says so in the body —
`Limit 8000, Requested 14931`. The model's own context window is 131k, so this
had nothing to do with context length. `_fallback_reason` treated it as a
configuration error and re-raised, which sent the tab to "No model reachable" on
a machine with a working local model pulled. It now falls back and quotes the
provider's own numbers, because "Limit 8000, Requested 14931" says how much to
cut and "too large" does not.

**2. The prompt was 29,718 characters of the wrong rows.** `exposure.head(200)`
is the first 200 rows of a 12,105-row table in FILE order: **AL011 to DE132**,
Albania through Germany, all at the **10-year** period whatever the reader had
selected above — in a page whose own docstring promises "one scenario at a time".
Now the prompt is built from `view` (the selected period), ranked by the share of
each region's own population exposed, and trimmed by
`toon_io.fit_rows` to whatever budget is left after the retrieved passages. The
prompt it produces is **10,913 characters, about 5,323 tokens**, and the live
call succeeds: 68% lexical grounding, no invalid citations.

The budget is in **characters, not tokens**, because `token_report` needs
tiktoken and a token-budgeted prompt would be unbudgeted wherever the tokenizer
cannot load. TOON measures at about 2.05 characters per token on the real table.

**3. The prompt did not say what the table was.** Forty rows with no label is an
invitation to quote a European total from them. The table is now introduced as
"the N most exposed of M NUTS3 regions at the 1-in-R year return period, ranked
by the share of their own population exposed… do not state a European total or a
count of regions from it".

**And the five keys.** `.env` carries `GROQ_API_KEY` through `GROQ_API_KEY_5`,
all set, and `rag.py` read only the first. `OPENROUTER_API_KEY`,
`OPENROUTER_MODEL` and `LLM_PROVIDER` are also set and **no code reads any of
them** — still true, and still a decision rather than a bug.

Measured against the live endpoint: the five keys belong to **five different
organisations**, each reporting its own `Limit 8000` under its own `org_...` id.
So `_groq` now rotates through them. The rotation is deliberately narrow:

* **429** — that organisation has spent its minute, another has not. Rotate.
* **413** — the request is larger than any one minute's budget, and every key
  reports the same 8,000. Rotating would burn four more calls to learn nothing,
  so it does not. The prompt has to get smaller; see (2).
* **401/403** — a dead key. Rotate, but the error still surfaces if they all fail.

The last exception is re-raised **unchanged** rather than wrapped, because
`complete_with_provider` falls back to the local model on
`requests.RequestException` and a `RuntimeError` around it would have silently
disabled the offline path. Only key NAMES ever reach a message.

**One hygiene fix this forced.** `src/__init__.py` loads the project `.env` on
import, so every key is in `os.environ` during the suite. Once `_groq` rotated,
a test that overrode only `GROQ_API_KEY` reached for the developer's real second
key and printed it in a pytest traceback. The `transcript` fixture now clears all
five, which is also what makes those tests mean the same thing in CI.

Tests: 449 → **508 passed, 0 failed**.

---

## 2026-10-08 — the map was in the DOM and invisible, then it grew a horizon

`src/svgmap.py`, `app/streamlit_app.py`, `tests/test_svgmap.py`,
`tests/test_streamlit_app.py`

**`st.html` sanitises, and it strips SVG.** The choropleth landed earlier today
and the reader still saw no map. Verified in the browser: the page carried the
heading, the caption "1,338 regions coloured, 7 grey" and the off-map note, while
the DOM held **zero `stHtml` nodes**, 56 `<svg>` elements (all icons) and no
element with more than 50 paths. No console error. `st.html` passes its body
through DOMPurify, the whole `<svg>` came back empty, and the caption underneath
went on reporting a map that was not there — the worst shape of failure: a
confident number beside nothing.

Now rendered with `st.components.v1.html`, which iframes the markup as given.
Verified in the browser: **1,345 paths, 1088 x 749 px, seven distinct fills.**

Two consequences of the iframe, both fixed because neither is cosmetic:

* An iframe inherits neither the app's text colour nor its theme, so the
  legend's `fill="currentColor"` resolved to black and vanished on a dark
  background. The legend now uses a class with a `prefers-color-scheme` rule.
* An `<svg>` with only a viewBox and `width="100%"` has no intrinsic height in
  some containers and collapses to nothing, which is indistinguishable from a
  map that was never drawn. `height` is now explicit as well.

**The horizon layer.** The reader asked to see the danger zones change with the
horizon. The map now switches between two quantities, and they are not the same
quantity, which is the whole reason the switch is explicit:

* **Exposed population, today** — the share of residents exposed at the selected
  return period. Sequential palette.
* **Change in river discharge, by horizon** — the median of the per-region
  ensemble medians against the 1971-2000 reference, on a diverging palette. It
  is **discharge, not depth or extent**, so it is never a future headcount: a
  future flow in m3/s does not index into the inundation maps the exposure
  figures come from, and the caption says so on every render.

**A third state on that layer, and it is the point.** A region where the model
chains disagree about the SIGN of the change has a median like any other.
Painting it flat states a direction the ensemble does not support; greying it
says "not measured", and it was. So it keeps its colour and takes diagonal
hatching, with its own legend entry. Verified in the browser at 2041-2070:
**1,198 regions coloured, 147 grey, 204 hatched**, legend running `-35% to +4%`
through `+42% to +166%` — and 994 regions agreeing on the sign, which matches
the figure in `docs/policy_answer.md`.

**A bug the new test caught before a jury could.** `climate_periods` reports a
period for a reader — `2041-2070` — while `build_context.py` suffixes the columns
`2041_2070`. Using the display form as a column key raised `KeyError` on the far
horizon, which is the one a jury asks about.

**Also: no more dead controls.** The "Region identifier" selectbox offered one
option on every pan-European run. Replacing it with a label just moved the dead
control one step along, so the identifier now rides in the freeze banner beside
the row count and the timestamp, and the return period gets the full width. The
layer radio appears only when there are two layers to choose between, for the
same reason.

**`folium` and `streamlit-folium` stay declared and unused** — and now there is a
reason written down: Leaflet fetches basemap tiles from a tile server, and the
kit has to run with the Wi-Fi off. Removing them is a separate decision.

Tests: **508 passed, 0 failed**, of which 13 are `tests/test_svgmap.py`.

---

## 2026-10-08 — One name, two meanings: the draft tab crashed on every machine that had run the pipeline

Found by the cloud review, reproduced before being touched.

`app/streamlit_app.py` is one script, and `with tab:` opens no scope. Streamlit
re-runs the whole file top to bottom on every interaction, so a name a tab binds
is a module-level name the tabs below it inherit. `measured` was bound twice: the
map tab set it to a bool (`"exposed_pop" in view.columns`), the context tab
rebound it to a **frame** of the regions carrying a declared APSFR share, and the
draft tab — 440 lines further down — tested it for truth.

**Measured before the repair**, with a context table present:
`ValueError: The truth value of a DataFrame is ambiguous`, raised at the
`ranked = (...)` expression in the draft tab. The real
`data/processed/context.parquet` carries `apsfr_share` with 1,147 non-null values
of 1,345 rows, so the condition that triggered it was the normal case: typing any
question into the draft tab crashed it on any machine that had run the pipeline.

Every existing draft test passed `context=None`, which is exactly how the whole
tab could be broken while the section stayed green. The harness defaults context
to absent on purpose — the dev machine has the parquet and CI does not — and that
same default hid this.

**Repair.** One flag, `has_exposure`, defined beside `view` where both tabs can
read it and no tab can shadow it, and the context tab's frame renamed to
`with_share` for what it holds. Renaming the frame alone would have closed this
collision and left the cross-tab coupling in place for the next one.

**Also from the same review**, and worse than it read: `src/svgmap.py`,
`tests/test_svgmap.py`, `docs/policy_answer.md` and `src/usage_log.py` were on
disk but **untracked**, so `from src import rag, svgmap, translate, usage_log`
named two modules that did not exist in the repository. From a clone the app
could not start and `tests/test_streamlit_app.py` could not be collected. Staged,
not committed.

**And one shared constant.** The 8,000-token-per-minute ceiling was re-derived in
the UI as a bare `11_000`. It is now `rag.PROMPT_CHAR_BUDGET`, defined once beside
`GROQ_KEY_VARS` where the 413 is raised, and read by the app and the test. The
number has already moved once.

Tests: **511 passed, 0 failed**, one of them new and failing before the repair.

## 2026-10-08 — a control nobody could use, and a link that reopened the whole app

Three defects reported by the reader of the page rather than by a test, and all
three measured in a real browser before anything was changed.

**The horizon could not be chosen.** Reported as "I cannot choose the date, it
stays on 2070". Measured on the running app: `st.select_slider` renders its
handle as a **12 × 12 px** dot with the value label **18 px above it**, so a
reader aiming at the period they can read clicks the label and nothing moves.
Worse, the moment the climate layer is selected the layer radio and the heading
push the handle to y = 633 in a 639 px viewport — **below the fold**. A
full-width drag left the committed value on the default; the keyboard arrows
moved it correctly and the map followed, which is how it was established that the
widget was wired right and the *control* was wrong.

Replaced with a horizontal `st.radio`. Three named periods are three click
targets, not a scale to drag along, and it is the same control as the layer
selector immediately above it. The default stays the middle horizon.

**The log's own links reopened the app.** `docs/ai_usage_log.md` links its
sibling docs relatively — `[`docs/decisions.md`](decisions.md)` — which is
correct in the repository and wrong in the app: it resolves against the app's own
origin and Streamlit answers an unknown path with the app shell, so clicking it
opened a second copy of the whole kit in a new tab. Absolute GitHub URLs are not
the fix: the kit has to work with the Wi-Fi off, and a dead link is not better
than no link. `src.usage_log.unlink_relative_docs` drops the link and keeps the
text, which in this file already names the file. `http(s)` targets are untouched.

**A logged entry landed outside the table.** The "Add entry" form appended to the
end of the *file*, and the file ends with the closing section on what the AI was
not allowed to decide — so a new row rendered as a paragraph with pipe characters
in it. `src.usage_log.append_row` inserts after the last table row instead.

**And a trap this repo already documents, walked into anyway.** The first version
of the two tests imported `app.streamlit_app` to reach the helpers, and importing
that script executes the whole page. They passed here and **failed with
`data/processed/` hidden** — which is what CI sees. That is why the helpers are in
`src/usage_log.py` and not in the app. Verified both ways: 43 passed on that
module with the tables present and 43 with them moved aside.

Tests: **511 passed, 0 failed**, three of them new.

## 2026-10-08 — the page cached "there is no table" and never looked again

Reported from the running app: *"No exposure table yet. Build one with
`src.exposure.exposure_by_return_period`…"* with
`data/processed/exposure.parquet` present on disk, 245,583 bytes, 12,105 rows.

**Cause, and it is mine.** The three loaders were `@st.cache_data` functions that
did their own `exists()` check and returned `None` when the artefact was missing.
`cache_data` memoises the RETURN VALUE, so `None` was cached like any other
answer: once a page had run while a table was absent, that process kept saying
the table was absent for the rest of its life. It was triggered by a test of mine
that moves the three artefacts aside for about seventy seconds to check the suite
the way CI sees it — any server that reran in that window was stuck until
restarted.

The failure mode is worse than the trigger. The message tells the reader to run a
build, and the build's output is exactly what the cached answer then refuses to
read: a reader who follows the instruction on screen sees no change and has no
reason to suspect the process rather than their own command.

**Repair.** Each loader is in two halves: `_build_state(path)` returns the
artefact's mtime or `None`, uncached, and the cached half takes that mtime as its
key. Absence is therefore never memoised, and a *rebuilt* table is a cache miss
rather than a stale hit — which the freeze banner needs anyway, since it claims
to name the run on screen.

**The harness was hiding it.** `tests/test_streamlit_app.py` answered every
`Path.stat` with a stand-in result whatever the test had declared present, so all
three artefacts read as present once presence was tested with `stat`. It now
raises `FileNotFoundError` for an artefact the test declares absent, as the real
filesystem does.

Measured: the new test runs the app twice in one session with no cache clear
between — which is what a rerun is — and flips the file into existence in
between. It fails against the previous loader and passes against this one.

Tests: **513 passed, 0 failed.**

---

## 2026-10-08 — The map's legend was off-screen, and the call that drew it is past its removal date

Both found by reading the Streamlit server log, which had been running with its
output piped into `head` and was therefore saying this to nobody.

**`st.components.v1.html` is deprecated**: the server logs "will be removed after
2026-06-01" on every render, a date already four months behind us. It was the
map's only rendering path, so one `pip install -U streamlit` on a demo machine
removes the first scored deliverable. Replaced with `st.iframe`, which embeds a
string matching no URL pattern as raw HTML — which is what the SVG is. `st.html`
remains unusable here: it sanitises with DOMPurify and strips the whole `<svg>`.

**And the legend was never visible.** Measured in the browser at 1,104px of
column: the SVG carries `width:100%;height:auto` over a `0 0 900 620` viewBox, so
it renders 739px tall, and the iframe was a fixed `height=640` with
`scrolling=False`. All seven class labels sat at y=718 — below the frame, with no
scrollbar to reach them. On the climate layer the clipped row included "models
disagree on the direction", which is the one caveat on that layer that must not
be optional.

This had been true since the map was built. The earlier entry's verification read
the legend out of the SVG source, which proves the markup contains a legend and
not that a reader can see one.

**Repair:** `height="content"`, never a pixel count. Streamlit measures the
embedded document, so the frame follows the column: measured 755px for a 739px
SVG, zero clipped labels, on both layers (exposure: 1,345 paths; discharge at
2041-2070: 1,549 paths of which 204 hatched).

**What the tests can and cannot hold.** A new test reads the iframe's `srcdoc`
through `AppTest.get("iframe")` and counts one `<title>` per region — the first
assertion in this suite that can tell a drawn map from a confident caption about
one. Proved by reverting to `st.html`: it fails with "0 iframes; the map is the
only one". The HEIGHT is not assertable — it does not appear among the element
proto's set fields — so the clipping stays a browser check, written down here
rather than guarded by a test that would only look like one.

Tests: **513 passed, 0 failed**, measured after this change. Two of them are new
here - `test_the_svg_actually_reaches_the_page_not_just_the_caption` and
`test_the_draft_survives_a_context_table_being_present` - but the total is not
this entry's arithmetic to claim: a second session was appending to the same
tree while this was written, so only the measured total above is mine to report.

## 2026-10-08 — The app said "RP500" to an authority whose maps say "low probability", and never said it was not the statutory map

Two sentences missing, both about the Directive's own vocabulary. Article 6(3) of
2007/60/EC names three flood hazard map scenarios and fixes a number for one of
them — (b) "floods with a medium probability (likely return period ≥ 100
years)"; (a) low probability / extreme and (c) high probability carry no figure.
The app offered RP10 to RP500 and placed none of them, so a brief could call the
1-in-500 year flood whatever it liked. A caption under the slider now quotes the
Article from `data/raw/scrape/floods_directive.html`, places the selected
period, and says that reading the periods below 100 as "high" and above 100 as
"low / extreme" is the kit's, not the law's — the lists are read off the table
on screen, never restated. Under the map, one caption says the page is a NUTS3
screening view and the statutory maps are the Member States' own, served by the
EEA Flood Risk Areas Viewer (https://discomap.eea.europa.eu/floodsviewer/) and
WISE-Freshwater. The same two sentences went into `README.md` and
`docs/policy_answer.md` §9. `CITATION.cff` added (0.1.0, 2026-10-08); **no
LICENSE file exists**, so it carries no licence field — choosing one is open.
No number changed meaning.

Tests: two new in `tests/test_streamlit_app.py` (45 → 47), the module re-run
with the three `data/processed/` artefacts hidden: 47 passed.

## 2026-10-08 — Every legal citation now has a CELEX, a URL and a test behind it

The brief's authority is a dozen articles of Directive 2007/60/EC and a handful
of other instruments, and until now each lived as prose in the docs while the
CELEX numbers and ELI URLs sat only in `docs/policy_context.md`.
`config/legislation.yaml` now holds one record per instrument (15: FD, WFD, AI
Act and its 2026 Omnibus, the machinery Regulation, UCPM and its 2021 amendment,
the Disaster Resilience Goals, GDPR, Habitats, Birds, COM(2021) 82, COM(2025)
280, SWD(2025) 24, and the Cloud and AI Development Act proposal COM(2026) 502),
and `src/legislation.py::cite("FD", "14(3)")` renders the citation with its URL.

**What was verified, and how.** eur-lex.europa.eu answers HTTP 202 with an empty
body to any scripted fetch, so the live check went through the Publications
Office Cellar SPARQL endpoint instead; all 15 CELEX numbers and dates were
confirmed there on this date. SWD(2021) 305 (Better Regulation Guidelines) has no
CELEX at all — Cellar 404 — and stays out rather than carry an invented one.

**What a number means.** The Article 14 deadlines in `docs/policy_answer.md` are
quoted from the Directive's own text (22 Dec 2018/2019/2021, "every six years
thereafter"); only the "next date" column is arithmetic, and the doc now says so.
A new test parses every "Article N" and every bare cell of the calendar table in
that doc and fails if the registry does not list it, which is what keeps the doc
and the registry from drifting apart.

Tests: 7 new in `tests/test_legislation.py`.

## 2026-10-08 — the docs got an index, and the limitations got one page

`docs/README.md` (new), `docs/limitations.md` (new)

**Before.** Fifteen Markdown files, 356.6 KB measured, and no index: a reader
opening `docs/` landed on `policy_context.md` (63.3 KB) or `policy_craft.md`
(52.9 KB) before the 19.2 KB spine. The limitations were real but scattered
across `policy_answer.md` §9-10, five module docstrings and this file.

**After.** `docs/README.md` names the twenty-minute read (policy_answer,
responsible_ai, ai_usage_log, limitations), carries one honest sentence and a
measured size per file, and an eight-step reading order. `docs/limitations.md`
consolidates with links back rather than duplicating: 25 bounded limitations,
12 designed-and-not-built items each with where its design lives, 10 things an
authority would still have to do, 11 accepted risks shown in the repo.

**NOT a measurement change.** No figure moved; every number on both pages is
quoted from its source with a link. Two disagreements between docs were found
on the way and are settled above and below: the map entry said eight grey
regions at RP100 where the frozen table says seven (corrected in place), and
the per-file test table in `technical_deep_dive.md` §7 summed to 473 over 22
files (rebuilt from measurement, 25 files). Checked: 132 relative links across
the two files, 0 broken. Tests: none added.

## 2026-10-08 — the same number typed in five places, and one copy was always stale

The suite count was corrected by hand seven times today — 441→473→508→510→
511→512→513 — across README.md, requirements.txt, docs/policy_answer.md and
docs/technical_deep_dive.md, and a 473 survived in one of them for hours after
the others moved. While this entry was written, parallel passes took the count
from 513 to 530 in three steps; each step left every typed copy wrong.

**Repair.** `scripts/docs_numbers.py` measures each fact from its artefact and
nothing else — `tests_collected` from `pytest --collect-only`, the three source
counts from `config/sources.yaml`, `nuts3_regions` from `exposure.parquet` — and
`--write` rewrites it into `<!-- numbers:KEY -->…<!-- /numbers -->` blocks, every
other byte untouched. `tests/test_docs_numbers.py` runs `--check` over the docs,
so a typed digit now fails the suite instead of waiting to be noticed.

**One measurement is redefined.** "Verified" sources are **34, not 36**: the
file has 36 `verified:` keys, two of which are `verified: null`
(`osm_critical_infrastructure`, `newsapi_recency`), and a null is the file's own
word for "not checked". Counts are of entries, never of the files they expand to.

Tests: 8 new in `tests/test_docs_numbers.py`; the suite's total is the marked
block in `README.md`, written by the script, and the per-file table in
`technical_deep_dive.md` §7 was rebuilt from the same collection.

## 2026-10-08 — "cannot measure here" was being read as "wrong"

The first CI run of `scripts/docs_numbers.py --check` failed the suite on the
runner: `nuts3_regions` is read from `data/processed/exposure.parquet`, CI has
no `data/`, so the fact came back `'unbuilt'` and the guard called the doc's
1,345 stale against it. The CLAUDE.md trap, in a script written to close a
different one. Measured: `1 failed, 529 passed` on the runner, green locally.

**Repair.** A fact that is not measurable on this machine is neither stale nor
writable: `rewrite` leaves the block as written and `main` says once, on stderr,
which fact was skipped and why. Two tests: the unit case, and `--check` over the
real docs with the table's path pointed at nothing — exit 0. Reproduced locally
with the parquet moved aside before the fix was trusted.

The two tests moved the suite to 532 and every marked block went stale at once;
`--write` put the new count everywhere, and the per-file table in
`technical_deep_dive.md` §7 was corrected by hand for the one row that changed
(8 → 10) and re-summed to the marked total.

Tests: **532 passed, 0 failed.**

## 2026-10-09 — the React map framed the overseas regions and shrank Europe to a strip

Reported with a screenshot: "the map looks like nothing, it has become tiny, and
I cannot zoom". The screenshot was the React front-end (`web/`), not the
Streamlit map repaired on 8 October, and `web/src/components/Choropleth.jsx` had
not changed since the first commit: it computed its viewBox over every feature,
so the Canaries, Madeira, the Azores, the French overseas regions and Svalbard
set the frame.

**Measured on `regions.geojson`** (1,345 features, 16 of them outermost): the
extent spans **119.0 × 102.2 degrees** with them and **69.3 × 36.6** without —
**4.8 times the area** given to a continent that fills a fifth of it. The same
defect `src/svgmap.py` closes with `OUTERMOST`, now mirrored in the React
component: the 16 regions are still drawn and still in every figure and the
table, they just no longer set the frame, and the caption says how many sit
outside it. Nothing in the code intercepts Ctrl+scroll; the browser zoom was
slow on a 1,345-path inline SVG and mostly needed because the continent was
small.

No measurement changed meaning: the map is display only; every number arrives
aggregated from the API in EPSG:3035. `npm run build` passes (there are no
front-end tests in this repo). Confirmed on screen by the reader.

## 2026-10-10 — the offline verdict could be green with the demo online, and "present" meant "non-empty"

Source: the Notion audit of 10 October (21 repos, one fiche per repo plus a
transverse one), read against the code on this branch rather than on `main`.
Four of its findings for this kit survived the check; two did not (HANZE's
seven `/content` URLs are already renamed in `sources.yaml` and pinned by a
test, and the manifest "audit trail" wording was fine). What changed:

**`scripts/check_offline_readiness.py` has three verdicts, not two.** It said
"The demo runs offline" over a WARN that `GROQ_API_KEY` routes every answer
through the venue Wi-Fi: true of the code, false of the demo. Now `READY`,
`READY WITH CAVEATS` (WARNs named, exit 0) and `BLOCKED` (exit 1); `--strict`
makes a caveat block, and the day-of checklist runs it that way. Two checks
were added for the caches `src.fetch` does not fill — the EEA basins layer and
the hand-downloaded CDS projections — both WARN, because the map and the brief
run without them. The README said "none of the three is covered" while
`run_checks()` already covered the RDH cache; the paragraph now says which is
which.

**A reused file has to pass the body check a fresh download passes.** The
idempotency rule in `src/fetch.py` was "exists and is non-empty", so a 31-byte
WAF page stored by an older run was reused with `ok=True`, a SHA-256 and a
clean manifest line. `why_not_a_document_on_disk` applies the same markers and
floor to the file on disk; one that fails is moved aside as `<name>.rejected`
(kept as evidence, excluded from the portable image) and fetched again. The
readiness table uses the same function, so the checker and the fetcher cannot
disagree about what "present" means. The reuse path also hashed with
`read_bytes()` — a whole 300 MB raster in memory to fingerprint it — while the
download beside it streamed; `sha256_of` streams both.

**Colliding declared paths are refused, not raced.** `path_collisions` runs in
`fetch_all` and returns a result per colliding job naming the file and the fix,
while the rest of the run proceeds. The config is fixed and tested; this closes
the naming rule itself, so the next API that serves every file under
`.../content` fails loudly on the first run.

**`token_report` catches a tokenizer that cannot fetch its table.** Measured on
a clean clone behind a proxy that refuses `openaipublic.blob.core.windows.net`:
`import tiktoken` succeeds, `get_encoding()` raises, and 12 tests failed through
`/api/draft` and the draft tab — the exact offline failure the kit is rehearsed
against, invisible to every check that was green. The call moved inside the
`try`; the unavailable shape is unchanged.

**CI.** `permissions: contents: read` on the workflow, and a second job that
builds the `app` stage, imports the native stack inside it and runs the
readiness script expecting `BLOCKED`. The README recorded the image as "never
built"; the image was built and run on the owner's machine the same morning
(Docker Desktop via `docker compose up --build`).

**The map legend says which sixth a class is.** Reported from the running
app: "the scales are odd" and "the risk is not near the sea — look at Norway
and Sweden". The second is the data, not a defect: the hazard layer models
river flooding only (`docs/datasets.md`), so a narrow glacial valley with its
whole population on the flood plain ranks high and a coast does not. The first
was the legend: the classes are quantiles (sixths of the regions present), and
a last swatch reading "10.6% to 75.5%" with nothing else reads as a danger band.
`src/svgmap.py` now prints the rank before the interval ("6/6 · 10.6% to
75.5%"), puts the region count per class in the swatch tooltip, and wraps the
legend onto rows that fit the viewBox — on one 150-unit pitch the seventh and
eighth entries ("not measured", the hatch) sat at x ≥ 912 in a 900-wide box,
drawn and clipped. The map stops above the legend band instead of running under
it. The React component (`web/src/components/Choropleth.jsx`) is left for the
same change on the owner's working tree. No figure changed.

**Revisit if** a reader still takes the top class for an absolute threshold —
then print the count in the label itself rather than the tooltip; or if the
75.5% region turns out to be a collapsed denominator (a region whose GHS-POP
total is tiny), which the per-region table can settle and this entry does not.

Not done, and for the audit's own reasons: `main` is unprotected on GitHub
(a repository setting, not a file), and no cost, p95 or restoration drill was
measured.

## 2026-10-10 — The Ollama default is the model the laptop has

**What.** `src/rag.py` falls back to `llama3.2:3b` instead of `llama3.1` when
`OLLAMA_MODEL` is unset; `.env.example`, the readiness checker's restated
constant and `docs/limitations.md` follow, and a test pins the constant to the
line in `rag.py`.

**Why.** The laptop has `llama3.2:3b` pulled and `.env` says so, but the
container reads no `.env`, so it asked Ollama for `llama3.1`, which is not
there: the demo worked on the host and failed in the image with "model not
found". One name everywhere removes the one-word trap the readiness check was
written to catch.

**Revisit if** a larger model is pulled for the day: change the constant in
`rag.py`, and the test says where else.

Also recorded: the `wallonia_observed_water_depth_2021` url is a one-off
download job of the Walloon geoportal and expires; `sources.yaml` now says so
in the entry's caveat, so the next 404 reads as "request the download again".
