# flood-policy-kit

Preparation toolkit for the **European AI Challenge 2026 — From Data to Policy**
(JRC × FARI, Brussels, 29–30 October 2026).

Turns European flood hazard and population data into the four things a jury
actually scores: a **map**, a **2-page policy brief**, a **responsible-AI
reflection**, and a **3-minute pitch**.

> **Scope is Europe, not Belgium.** The challenge asks about European regions;
> the 2021 floods in Belgium, the Netherlands and Germany are the motivation in
> the call, not the study area. The working unit is **NUTS3**: the GISCO NUTS
> 2024 file holds **1,345** NUTS3 polygons, of which **1,165** are in the EU-27
> and the rest in EFTA and the candidate countries.
> Belgium is kept only as the dress rehearsal, because it is the one place with
> *observed* flood extent to validate the model against. See
> [`docs/scope.md`](docs/scope.md).

> **Expect to be asked whether "European" means the EU-27 or the continent.**
> The ranking returns Turkish regions (Antalya, Sakarya) alongside Dutch, Italian,
> French and German ones, because the GISCO file covers Europe rather than the
> Union. That is defensible — the challenge says European — but it has to be
> stated rather than discovered by a juror. The answer: **1,345 polygons in the
> file, of which 1,165 are in the EU-27, 46 in EFTA (CH, NO, IS, LI) and 134 in
> the candidate and potential-candidate countries (TR, RS, AL, MK, ME, XK).**
> Filter to `EU_STAT == "T"` for an EU-only figure, and say which of the two any
> headline number is.
>
> Beware the related trap: **1,166**, the figure usually quoted for "the number
> of NUTS3 regions", is the EU count for the **NUTS 2021** classification. On the
> NUTS 2024 vintage pinned here it is 1,165, because `DEG0P` (Eisenach) was
> absorbed into the Wartburgkreis. A denominator quoted without its vintage is
> wrong by one region and by three countries' worth of scope.

> **This is a generic toolkit, not a finished answer.** The scenario is handed
> out on the day. What is prepared here is plumbing — loading, reprojecting,
> zonal statistics, a brief template, a sourced policy corpus — so that the two
> days go on the analysis and the argument, not on CRS bugs. Say this plainly to
> your team on day 1; it is also the honest thing to do.

> **A screening view, never the statutory map.** Every figure in this kit is a
> NUTS3 zonal statistic over the JRC river flood hazard maps, built to decide
> where to look first. The flood hazard and flood risk maps that bind under
> Directive 2007/60/EC are the Member States' own, prepared under Article 6,
> reported to the Commission under Article 15 and served by the EEA Flood Risk
> Areas Viewer (https://discomap.eea.europa.eu/floodsviewer/) and
> WISE-Freshwater. Quote those for a statutory hazard or risk statement about
> any place; quote this kit only for a cross-regional comparison, and say which
> of the two a figure is.

## Why this exists

The challenge is **not** a coding contest. The winning team will be the one that
turns geospatial data into **three clear, costed, actionable recommendations**
for a public decision-maker. The most sophisticated model does not win.

The gap in most teams is the middle: political-science students cannot process a
raster, and computer-science students cannot write for a decision-maker. This
repo is built for whoever bridges the two.

## The one equation everything hangs on

```
Risk = Hazard × Exposure × Vulnerability
```

- **Hazard** — where the water goes, and how deep, for a given return period.
  (JRC river flood hazard maps.)
- **Exposure** — who and what is in that water. (GHS-POP population grid,
  OpenStreetMap critical infrastructure.)
- **Vulnerability** — who suffers most from the same water. (Age, income,
  building type, insurance coverage.)

A result that stops at exposure answers "how many people got wet". A result that
reaches vulnerability answers "who needs help first", which is the question a
decision-maker actually has.

## Layout

```
flood-policy-kit/
├── config/sources.yaml         # every dataset + document, with provenance
├── config/legislation.yaml     # every legal instrument cited: CELEX, ELI URL, dates, articles relied on
├── src/
│   ├── data_io.py              # loading + CRS harmonisation, one entry point
│   ├── exposure.py             # hazard × population, per admin unit
│   ├── vulnerability.py        # composite index + sensitivity analysis
│   ├── validate.py             # modelled hazard vs observed 2021 extent: hit rate, FAR, IoU
│   ├── rdh.py                  # JRC Risk Data Hub client, responses cached to disk
│   ├── losses.py               # RDH loss rows → a levelled, joinable table
│   ├── events.py               # blind-spot probe over reported coverage (not evidence)
│   ├── assets.py               # built-up surface exposed: the asset half of exposure
│   ├── climate.py              # future flood hazard per region, from the CDS projections
│   ├── basins.py               # river basin districts: exposed in a basin you do not control
│   ├── apsfr.py                # what the Member State declared at risk, vs what the model shows
│   ├── demographics.py         # Eurostat indicators at NUTS3: the axes the index weighs
│   ├── toon_io.py              # compact table encoding for LLM prompts
│   ├── fetch.py                # parallel, polite, idempotent collection
│   ├── workflow.py             # LangGraph brief pipeline with an approval gate
│   └── rag.py                  # grounded "cite or refuse" over the policy corpus
├── scripts/
│   ├── build_exposure.py            # freezes data/processed/exposure.parquet, one row per NUTS3 x RP
│   ├── build_context.py             # freezes data/processed/context.parquet, what qualifies an exposure figure
│   ├── fetch_cds_member.py          # one CDS ensemble member, verified against what was asked
│   ├── build_geometry.py            # freezes data/processed/regions.geojson, the choropleth's polygons
│   └── check_offline_readiness.py   # is this laptop demo-ready with the Wi-Fi off?
├── api/main.py                 # JSON API over src/, for the React UI
├── web/                        # React + Vite UI: choropleth, sensitivity, approval gate
├── app/streamlit_app.py        # six tabs, no build step: the React five plus the AI log
├── templates/policy_brief.md   # the 2-page deliverable
├── Dockerfile                  # Linux image: the portability answer, not a requirement here
├── docker-compose.yml          # Streamlit / API / tests / offline check / portable demo
├── docs/                       # read these before the event
└── tests/                      # pytest, offline, no network
```

Two of those earn a word here rather than being found by accident.
`src/validate.py` is the credibility half: it scores the modelled hazard layer
against the observed July 2021 extent and returns a hit rate, a false alarm ratio
and an IoU, every one of them `None` rather than `0.0` when its denominator is
empty. `scripts/check_offline_readiness.py` answers the question `pytest` cannot
— the suite mocks the network away, which is exactly what hides a missing 300 MB
raster — and answers it in byte counts, exiting 1 when the demo would still need
a connection.

`Dockerfile` and `docker-compose.yml` exist because `rasterio`, `pyogrio`,
`rasterstats` and `tiktoken` could not load their native libraries on this
Windows host. The `pyogrio`/`pyproj` caps in `requirements.txt` bought back three
of them. Windows Smart App Control then moved to enforcement on 2026-10-07 and
refused `rasterio`'s own GDAL build, which no pin fixed; by 2026-10-08 it allowed
the same wheel again with nothing reinstalled. **The policy moves both ways, so
measure rather than believe either state** — measured 2026-10-08, `import
rasterio` works and the whole suite runs on Windows: **<!-- numbers:tests_collected -->532<!-- /numbers --> passed, nothing
deselected**. The WSL2 venv stays anyway, because it is the only route that does
not depend on the policy's mood and it is where a continental raster build
belongs. **Neither container has ever been built:** the Docker daemon is not running on this machine, so both are
reviewed but untested, and the first build belongs in the dress-rehearsal week
rather than on the morning of the event.

## Docs, in reading order

| Doc | Read it for |
|---|---|
| [`docs/README.md`](docs/README.md) | **Start here.** The index: the twenty-minute read, one sentence per file with its measured size, and the full reading order |
| [`docs/strategy.md`](docs/strategy.md) | **Read first.** The question most teams will not ask, and the dataset almost nobody will find |
| [`docs/scope.md`](docs/scope.md) | **Read first.** Why NUTS3 and Europe, and what that changes about the data |
| [`docs/plan.md`](docs/plan.md) | The 23-day preparation calendar and what to do today |
| [`docs/datasets.md`](docs/datasets.md) | Every dataset: what it is, its CRS, its traps |
| [`docs/geospatial_crash_course.md`](docs/geospatial_crash_course.md) | CRS, zonal stats, raster alignment — the bugs that cost hours |
| [`docs/policy_context.md`](docs/policy_context.md) | Floods Directive, Sendai, the 2021 Belgian floods, the insurance gap |
| [`docs/policy_answer.md`](docs/policy_answer.md) | **The spine.** The question as the organisers ask it, the four findings with their measured figures, and the three recommendations with the article, the authority and the date behind each |
| [`docs/policy_craft.md`](docs/policy_craft.md) | How to write the brief and the pitch |
| [`docs/responsible_ai.md`](docs/responsible_ai.md) | The HLEG grid, the AI-usage log, what AI must not decide |
| [`docs/day_of.md`](docs/day_of.md) | Hour-by-hour plan for 29–30 October |
| [`docs/roles.md`](docs/roles.md) | Your three hats, and how to split a multidisciplinary team |
| [`docs/workflow.md`](docs/workflow.md) | Why a workflow and not an agent, and where the human gate sits |
| [`docs/decisions.md`](docs/decisions.md) | The dated record of every change to what a number means. Read it before quoting a figure from an older run |
| [`docs/limitations.md`](docs/limitations.md) | What the figures cannot say, what was designed and not built, what an authority would still have to do, and the risks accepted to ship in ten days |
| [`docs/ai_usage_log.md`](docs/ai_usage_log.md) | The AI-usage annex the responsible-AI deliverable asks for |
| [`docs/technical_deep_dive.md`](docs/technical_deep_dive.md) | How it works and why it is built that way: the four CRSs, what the exposure number means, why the windows are on the population grid, the UI contract, what each test guards |

## Quick start

```bash
python3 -m venv .venv && .venv/bin/pip install -r requirements.txt
.venv/bin/python -m pytest -q           # <!-- numbers:tests_collected -->532<!-- /numbers --> tests, offline: no network, no model
                                        # Measured 2026-10-08 on Windows, nothing
                                        # deselected. Smart App Control blocked
                                        # rasterio on 2026-10-07 and allowed it
                                        # again the next morning, so re-measure
                                        # rather than trust this number — see
                                        # requirements.txt for the whole story.
                                        #   wsl -d Ubuntu
                                        #   ~/.venvs/flood/bin/python -m pytest -q
.venv/bin/python -m src.fetch           # 37 geodata downloads + 13 policy_corpus
                                        # + 2 context = 52 files, ≈3.82 GiB
                                        # (before 25 Oct, once)
.venv/bin/python scripts/build_exposure.py --stripes 72 # -> data/processed/exposure.parquet
.venv/bin/python scripts/build_context.py  --stripes 72 # -> data/processed/context.parquet
.venv/bin/python scripts/build_geometry.py             # -> data/processed/regions.geojson
.venv/bin/python scripts/check_offline_readiness.py   # exits 1 if the demo needs the network
.venv/bin/python scripts/docs_numbers.py --check      # exits 1 if a doc's number no longer matches the code

# Either UI. Both read the same frozen table, so they cannot disagree on a number.
.venv/bin/streamlit run app/streamlit_app.py            # no build step
.venv/bin/uvicorn api.main:app --port 8010              # + cd web && npm run dev
```

`--stripes` is memory, not meaning: the windows are disjoint, so the figures do
not depend on it, and `tests/test_stripes.py` holds that. The default of 10 was
enough on a workstation and is not enough inside a 16 GB WSL VM — a nine-period
run at 24 was killed by the OOM killer on the 100-year period, which floods more
cells than the frequent ones. 72 peaks around 7.5 GB.

The exposure build **parks each return period** in `data/processed/exposure_parts/`
as it finishes and reuses what is already there, so an interrupted run costs one
period rather than all of them, and `--return-period` narrows what is computed
without ever shrinking the frozen table. `--rebuild` recomputes a parked period.

Ubuntu and WSL ship no `python` on `PATH`, only `python3`. Calling `.venv/bin/...`
directly instead of activating the venv keeps that distinction out of the way, and
removes the one failure mode of a hackathon morning: running against system Python
because the activation was forgotten.

The React UI is the one to demo: it draws the choropleth as **SVG from GeoJSON**,
with no tile provider and no API key, so the map still works with the network
unplugged. Streamlit is the fallback that needs no `npm`.

Data is **not** committed (`data/` is ignored): run `.venv/bin/python -m src.fetch` to
download what `config/sources.yaml` declares — **24 `geodata` entries that expand
to 49 jobs, of which 37 are downloadable files at ≈3.78 GiB** (the other twelve are
`access: api`, queried at runtime and never stored), or **52 files and ≈3.82 GiB**
once the `policy_corpus` (13 entries) and `context` (2) sections are included —
every one of those fifteen a `scrape`. Of the geodata, the nine return periods are
2.61 GiB. Do this **before 25 October** — the Wi-Fi of a 60-person hackathon will
not move gigabytes of raster. The run is idempotent, so an interrupted download
costs only the files that are still missing.

Those counts are `src.fetch.expand()` applied to `sources.yaml` as it stood on
6 October 2026, and the byte totals are the `Content-Length` the hosts returned
the same day — a reading of the config, not a property of the repo. Every entry
added later moves them, so re-derive rather than quoting this paragraph.

Three sources sit outside `python -m src.fetch`, and each for its own reason:

- **JRC Risk Data Hub** wants an EU Login bearer token that expires after 10
  hours, so the account is created now, the responses are cached the day before,
  and the token is refreshed on the morning of the event.
- **EEA river basin districts** is a REST service that takes about two minutes
  over 8 pages and answers HTTP 500 to a page it dislikes. `src/basins.py`
  caches it to `data/processed/basins_cache/` — 288 MiB, fetch it once before
  the event.
- **Copernicus CDS hydrology projections** are fetched by hand through the CDS
  download form, because that form is where a request's cost is checked against
  its 1000 cap. Drop the `.nc` files in
  `data/raw/download/cds_hydrology_projections/`.

None of the three is covered by `scripts/check_offline_readiness.py`, which skips
`access: api` entries — so a green readiness check does not mean these are in
place. See [`docs/datasets.md`](docs/datasets.md).
