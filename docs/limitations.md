# Limitations: what the kit does not claim

The kit is a ten-day build on open data, frozen on 2026-10-08. This page gathers
in one place what its figures cannot support, what was designed and not built,
what a public authority would still have to do before acting on it, and the
shortcuts accepted to ship it. Every bullet points at the file that holds the
reasoning and the measurement; this page quotes the bounding number and nothing
more, so re-derive from the source rather than from here when the parquets are
rebuilt. The findings and recommendations themselves are in
[`policy_answer.md`](policy_answer.md).

## 1. What the figures can't say

**The hazard**

- **River flooding only.** The JRC maps model fluvial flooding for basins above
  about 150 km2 and contain no surface runoff, which was a large part of what
  happened in Wallonia in July 2021. A region the model ranks low may still have
  flooded. [`policy_answer.md` §9](policy_answer.md#9-what-this-document-does-not-claim),
  [`src/events.py`](../src/events.py) module docstring.
- **Nine scenarios, never a sum.** The return periods are nested extents: EU-27
  exposed population reads 16,704,818 at RP10, 25,737,004 at RP100 and
  30,730,197 at RP500. A headcount quoted without its return period is not a
  number. [`policy_answer.md` §3](policy_answer.md#3-the-measured-base-2026-10-08),
  [`geospatial_crash_course.md`](geospatial_crash_course.md#return-period-what-a-100-year-flood-is-not).
- **The depth threshold is a choice, and it moves the headline.** The build
  counts a cell as flooded above 0.5 m, and masks permanent water bodies and the
  JRC's own spurious-depth areas; on the Benelux the water-body mask alone moves
  the RP100 figure by -14.2 %. The threshold is one of the four things the AI
  was not allowed to decide.
  [`technical_deep_dive.md` §3.5](technical_deep_dive.md#35-what-is-masked-out-and-why),
  [`responsible_ai.md`](responsible_ai.md#say-what-ai-must-not-decide).

**The exposure count**

- **`exposed_pop` carries an extrapolation; `exposed_pop_observed` does not.**
  Where the hazard layer covers only part of a region, the figure is scaled onto
  the whole unit by people (`x pop_total / pop_observed`), never by a cell-mean
  of coverage. At RP100, 7 of 1,345 regions carry no measured figure at all and
  11 have `hazard_coverage` below 1.0; report that column beside every count.
  [`technical_deep_dive.md` §3.3-3.4](technical_deep_dive.md#33-four-columns-and-why-none-is-not-00),
  [`src/exposure.py`](../src/exposure.py) `exposed_population` docstring,
  [`policy_answer.md` §3](policy_answer.md#3-the-measured-base-2026-10-08).
- **A population cell is wholly in or wholly out of a region.** The induced
  error scales with perimeter over area: around 1-3 % for a commune and 30-50 %
  for a Belgian statistical sector. Nothing smaller than a commune should be
  read off this pipeline. [`src/exposure.py`](../src/exposure.py) module
  docstring.
- **Which Europe.** The GISCO NUTS 2024 file holds 1,345 NUTS3 polygons, of
  which 1,165 are EU-27, 46 EFTA and 134 candidate countries. The usual "1,166"
  is the NUTS 2021 count. Every headline says which denominator it uses.
  [`scope.md`](scope.md#the-unit-of-analysis-nuts3), root
  [`README.md`](../README.md).
- **Built-up surface is square metres of footprint, not value.** A warehouse
  and a hospital of the same size are the same number; monetising it needs
  damage curves the kit does not carry. [`src/assets.py`](../src/assets.py)
  module docstring.

**The Member States' own declaration**

- **`apsfr_share` is comparable within one country and never between two.**
  The Floods Directive leaves the geometry convention national: the declared
  share of territory runs from 99.908 % (BE) to 0.004 % (ES, CY), a factor of
  23,095, and the shape index separates zones (1.5 for BE and HR) from river
  reaches drawn as ribbons (51 for DE, 74 for LU). Any cross-country ranking of
  the share ranks reporting styles. [`src/apsfr.py`](../src/apsfr.py) module
  docstring, [`policy_answer.md` §4.1](policy_answer.md#41-the-member-states-own-risk-declaration-is-not-comparable-between-them).
- **An undeclared area is not an under-declared one.** A State may have
  assessed an area under Article 4 and found the risk not significant, which the
  Directive permits; the kit shows the gap and leaves the conclusion to a human.
  [`src/apsfr.py`](../src/apsfr.py), [`policy_answer.md` §9](policy_answer.md#9-what-this-document-does-not-claim).
- **Two EU-27 Member States are absent from the layer.** Pinning the 2018 cycle
  (12,173 polygons, 25 countries) drops Lithuania, which reported in 2010 only;
  Ireland appears in neither cycle. Any pan-European APSFR statistic silently
  omits both. [`policy_answer.md` §4.2](policy_answer.md#42-two-eu-27-member-states-are-absent-from-the-commissions-own-layer),
  [`datasets.md`](datasets.md#eea-floods-directive--areas-of-potential-significant-flood-risk--verified-live--and-three-traps).

**The cross-border figure**

- **"Shared" is not "upstream".** The WFD districts are catchment boundaries
  with no flow topology, so the kit can say a region's basin lies in more than
  one country and nothing about direction. [`src/basins.py`](../src/basins.py)
  module docstring.
- **57.0 % of exposed people in a shared basin is a floor, twice over.**
  Switzerland, Belarus, Ukraine and Serbia hold large parts of the Rhine, the
  Nemunas, the Vistula and the Danube and do not report under the WFD; and
  districts the declared crosswalk (68 districts into 22 basins) cannot group
  stay national. [`policy_answer.md` §4.3](policy_answer.md#43-most-of-europes-exposed-population-is-downstream-of-someone-else),
  [`datasets.md`](datasets.md#the-limit-that-matters-a-district-is-a-national-portion),
  [`config/international_basins.yaml`](../config/international_basins.yaml).

**The future layer**

- **Medians and quartiles, never a mean or a maximum.** A relative change
  against a near-zero reference discharge is unbounded: on the real file the
  maximum is +16,452,833 % against a median of +16.9 %.
  [`src/climate.py`](../src/climate.py) module docstring.
- **Two model chains, one emissions pathway, one realisation.** The CDS dataset
  offers eight simulations; on disk every file is `ICHEC-EC-EARTH r12i1p1`
  under RCP 8.5 through E-HYPEgrid and VIC-WUR. The ensemble agrees on the sign
  in 976, 994 and 943 of 1,345 regions for the three horizons, and one member
  never counts as agreement with itself. Regions where the two chains disagree
  keep their colour on the map and are hatched, which is a third statement:
  measured, direction unsupported.
  [`datasets.md`](datasets.md#copernicus-cds--hydrology-projections--verified--and-unsupported),
  [`src/climate.py`](../src/climate.py) `ensemble` docstring,
  [`src/svgmap.py`](../src/svgmap.py) `render` docstring,
  [`policy_answer.md` §4.4](policy_answer.md#44-the-reference-discharge-is-rising-where-people-already-live-in-the-way).
- **It is discharge, not depth, and not a headcount.** A change in a 50-year
  flow cannot be layered onto the inundation maps; what travels is the direction
  and the size of the change. No future exposed-population figure exists in this
  kit. [`src/climate.py`](../src/climate.py) module docstring.

**Who is vulnerable**

- **The index is a value judgement wearing a number.** Weights are equal by
  default so that any other weighting is argued out loud; the ranking is never
  reported without its sensitivity under perturbed weights. Who gets protected
  first is a political choice the AI was not allowed to make.
  [`src/vulnerability.py`](../src/vulnerability.py) module docstring,
  [`responsible_ai.md`](responsible_ai.md#say-what-ai-must-not-decide).
- **Two indicators, two scales, and NUTS2 applied to NUTS3.** `poverty_rate` is
  a Eurostat percentage (1.4 to 50.7) published at NUTS2 and applied to each
  NUTS3 child; `share_over_65` is a fraction (0.027 to 0.372). Neither column
  name says so. [`decisions.md`, 2026-10-08 "two indicators, two scales"](decisions.md#2026-10-08--two-indicators-two-scales-and-that-is-deliberate),
  [`scope.md`](scope.md#demographics-eurostat-not-statbel).
- **Who is not in the data.** Undocumented residents, people in temporary
  housing and seasonal workers are absent from a residential population grid.
  The gap is stated, not estimated. [`strategy.md`](strategy.md#the-question-most-teams-will-not-ask),
  [`responsible_ai.md`](responsible_ai.md#what-to-write-under-each-concretely).

**Losses, validation and the model's blind spots**

- **No casualty or loss figure is official.** Risk Data Hub rows arrive once
  per administrative level, so an unfiltered sum of the July 2021 casualties
  reads 114.01 against 29.67 at any one level; the values are averages across
  DFO, EM-DAT and HANZE; and NUTS3 rows cover 84.3 % of the national total.
  [`src/losses.py`](../src/losses.py) module docstring,
  [`policy_answer.md` §9](policy_answer.md#9-what-this-document-does-not-claim).
- **Validation is one event, one country, extent only.** `src/validate.py`
  scores the model against the observed July 2021 extent in Belgium at 20 m,
  refusing units under 25 observed cells. The Walloon depth layer that would
  allow a depth-against-depth check answers HTTP 404 "Download Dataset Expired".
  Nothing validates the model elsewhere in Europe.
  [`technical_deep_dive.md` §5](technical_deep_dive.md#5-validation-the-credibility-half),
  [`datasets.md`](datasets.md#wallonia-observed-july-2021--the-second-ground-truth--one-layer-verified-one-dead).
- **Reported events are a probe, never evidence.** News coverage is biased by
  attention, language and population; nothing from `src/events.py` enters a
  ranking or a headline. [`src/events.py`](../src/events.py) module docstring.
- **Environment and cultural heritage are not measured.** Article 6(5) asks
  flood risk maps to show both; the kit measures residents and built-up surface
  only. [`datasets.md`](datasets.md#declared-and-not-yet-used-natura-2000-corine-land-cover).

**The map and the text**

- **The colour classes are quantiles of what is present.** At RP100 the six
  bounds are 0.84, 1.90, 3.39, 5.61, 9.22 and 70.82 %; the legend prints them so
  the reader sees the classes are relative. Grey is "not measured", never zero.
  [`src/svgmap.py`](../src/svgmap.py) module docstring,
  [`ai_usage_log.md`](ai_usage_log.md).
- **Sixteen regions are off the viewport.** The outermost regions (prefixes
  `FRY`, `PT20`, `PT30`, `ES70`, `NO0B`) are drawn but do not set the extent,
  which would otherwise grow 6.5-fold in area; the caption names them.
  [`src/svgmap.py`](../src/svgmap.py) `OUTERMOST`,
  [`decisions.md`, 2026-10-08 "there was no map"](decisions.md#2026-10-08--the-first-scored-deliverable-was-missing-there-was-no-map).
- **The retrieval layer cites only what it holds.** Diffed on 6 October 2026,
  at least thirteen documents cited in `policy_context.md` are declared nowhere
  in `config/sources.yaml` and are therefore unciteable by the kit itself. A draft is passed only above a 0.7 lexical grounding score and
  then only to a human. [`policy_context.md`](policy_context.md),
  [`workflow.md`](workflow.md#the-four-guards-and-what-each-prevents).

## 2. Designed and not built

Each item names where its design lives, so that finishing it starts from a
written intent rather than from memory.

- **Environment and heritage layers.** Natura 2000 and CORINE Land Cover are
  declared in `config/sources.yaml` with `DECLARED, NOT YET USED` in their
  caveat; no module reads either, and no figure may be quoted from them until
  one does. Design: [`datasets.md`](datasets.md#declared-and-not-yet-used-natura-2000-corine-land-cover).
- **Two further Eurostat indicators.** Population density (`demo_r_d3dens`) and
  disposable household income (`nama_10r_2hhinc`) are named as candidates and
  not yet declared or called. Design: [`scope.md`](scope.md#demographics-eurostat-not-statbel).
- **The full CDS ensemble.** Two of the eight offered simulations are on disk;
  `scripts/fetch_cds_member.py` fetches one member at a time and verifies the
  filename against the request. Design: [`datasets.md`](datasets.md#copernicus-cds--hydrology-projections--verified--and-unsupported),
  [`scripts/fetch_cds_member.py`](../scripts/fetch_cds_member.py).
- **Depth-against-depth validation.** Blocked on a re-minted download URL for
  the Walloon IDW depth layer. Design: [`datasets.md`](datasets.md#wallonia-observed-july-2021--the-second-ground-truth--one-layer-verified-one-dead).
- **The model-versus-observation map for Europe.** The satellite-derived flood
  depth series covers 2015-2025; only the July 2021 file is declared and
  fetched, so the "where is the model blind" comparison exists for Belgium only.
  Design: [`strategy.md`](strategy.md#the-find-that-changes-the-plan).
- **Three further components of "unpreparedness".** The insurance protection
  gap (EIOPA), Solidarity Fund allocation against modelled risk, and the
  uncounted population are argued as findings and have no module behind them.
  Design: [`strategy.md`](strategy.md#the-out-of-the-box-framing),
  [`policy_context.md` §5](policy_context.md).
- **Monetised built-up exposure.** Needs damage curves. Design:
  [`src/assets.py`](../src/assets.py) module docstring.
- **Units in column names.** `poverty_rate_pct` would touch `api/main.py`,
  `app/streamlit_app.py`, `scripts/build_exposure.py`, the tests and every older
  export; recorded as a naming decision, not a bug. Design:
  [`policy_answer.md` §10](policy_answer.md#10-open-and-known).
- **Natural-language access to the exposure table.** Named as a role for the
  GenAI engineer; nothing in `src/`, `api/` or `app/` implements it. Design:
  [`roles.md`](roles.md#hat-3--genai-engineer-the-responsible-accelerator).
- **The thirteen undeclared policy sources.** Listed by name so they can be
  added to `config/sources.yaml` and fetched. Design:
  [`policy_context.md`](policy_context.md).
- **The Docker images.** `Dockerfile` and `docker-compose.yml` are written and
  have never been built; the daemon was not running on the development machine.
  Design: root [`README.md`](../README.md).
- **The dress rehearsal on an unprepared region.** Scheduled for 26-28 October
  on Valencia 2024 or Emilia-Romagna 2023, precisely to find what is secretly
  hard-coded. Design: [`plan.md`](plan.md#week-4-why-the-dress-rehearsal-matters-most).

## 3. What a Member State or the Commission would still have to do

The three recommendations in [`policy_answer.md` §6](policy_answer.md#6-the-measures-what-where-by-whom-how-by-when)
name an instrument, an addressee and a date. Acting on them, or on any figure
here, still needs the following from the authority itself.

- **Re-derive every figure from the current build.** The parquets are rebuilt
  and the counts move; the page that quotes them says so in its first paragraph.
  [`policy_answer.md`](policy_answer.md), [`decisions.md`](decisions.md).
- **Decide the depth threshold and the vulnerability weights.** Both change the
  headline, both are value judgements, and the kit deliberately ships defaults
  (0.5 m, equal weights) rather than a position.
  [`responsible_ai.md`](responsible_ai.md#say-what-ai-must-not-decide),
  [`src/vulnerability.py`](../src/vulnerability.py).
- **Check the declaration gap against the Article 4 assessments.** Only the
  State knows whether an exposed, undeclared region was assessed and found not
  significant. [`src/apsfr.py`](../src/apsfr.py).
- **Reconcile the published layer with national data.** Ireland runs the CFRAM
  programme and is absent from the EEA service; Lithuania reported in 2010 only.
  R2 asks the EEA and the two national reporters to close that.
  [`policy_answer.md` §4.2 and R2](policy_answer.md#42-two-eu-27-member-states-are-absent-from-the-commissions-own-layer).
- **Table a geometry convention through the Working Group on Floods** before
  the 22 December 2027 review of the flood risk management plans (R1), and
  publish the declared share of territory beside each submission.
  [`policy_answer.md` R1](policy_answer.md#r1--make-the-article-5-declaration-comparable-before-the-2027-review).
- **Lodge an Article 8(5) report on one named shared basin** (R3). Only a
  Member State can; the Commission then owes an answer within six months.
  [`policy_answer.md` R3](policy_answer.md#r3--use-article-85-on-one-named-shared-basin-as-a-test-case).
- **Run the climate review on the full ensemble.** Article 14(4) requires the
  likely impact of climate change to be taken into account; two chains under one
  pathway support a direction in most regions and no magnitude for planning.
  [`policy_answer.md` §4.4](policy_answer.md#44-the-reference-discharge-is-rising-where-people-already-live-in-the-way).
- **Replace the averaged loss figures with official ones** before any casualty
  or damage number is printed. [`src/losses.py`](../src/losses.py).
- **Verify the dates and the legal texts** the brief relies on: the third-cycle
  deadlines are Article 14 arithmetic corroborated by national sources, and the
  AI Act articles were read through a mirror.
  [`policy_context.md`, open items 1 and 8](policy_context.md#open-items-and-flags).
- **Settle the AI Act classification by reading Annex III**, rather than
  asserting it; the kit's framing is a decision-support tool for a public
  authority to which the transparency and oversight expectations were applied
  anyway. [`policy_answer.md` §8](policy_answer.md#8-the-responsible-ai-layer-and-the-live-legislation),
  [`policy_context.md` §7](policy_context.md).

## 4. Risks accepted for a ten-day build

Only what the repository shows.

- **The data is not committed.** `data/` is ignored; a fresh clone has to fetch
  about 3.8 GiB and run a multi-hour continental build before the API answers
  anything but 404. CI therefore runs with no data, and a test that strays
  outside the frozen harness passes locally and fails on the runner.
  [`.gitignore`](../.gitignore), [`scope.md`](scope.md#what-the-nuts3-choice-produces-on-disk),
  [`decisions.md`, 2026-10-08 "cached there is no table"](decisions.md#2026-10-08--the-page-cached-there-is-no-table-and-never-looked-again).
- **The offline check fails today.** Run 2026-10-08: 51 of 52 declared files
  present (3.8 GiB), `wallonia_observed_water_depth_2021` missing behind a dead
  URL; `GROQ_API_KEY` set, so the draft tab goes over the network; the local
  model pulled is `llama3.2:3b` while `src/rag.py` defaults to `llama3.1`.
  Exit code 1. The check also skips every `access: api` source, so the Risk Data
  Hub, the basin districts and the CDS files are outside what it can certify.
  [`scripts/check_offline_readiness.py`](../scripts/check_offline_readiness.py),
  root [`README.md`](../README.md).
- **Dead configuration keys.** `OPENROUTER_API_KEY`, `OPENROUTER_MODEL` and
  `LLM_PROVIDER` are set in `.env` and read by no code; `folium` and
  `streamlit-folium` are pinned in `requirements.txt` and imported nowhere.
  Both are recorded as decisions rather than removed in the same pass as a
  feature. [`decisions.md`, 2026-10-08 "the draft tab could never have worked"](decisions.md#2026-10-08--the-draft-tab-could-never-have-worked-for-three-reasons),
  [`decisions.md`, 2026-10-08 "there was no map"](decisions.md#2026-10-08--the-first-scored-deliverable-was-missing-there-was-no-map),
  [`requirements.txt`](../requirements.txt).
- **Test counts are typed by hand.** The per-file table in
  `technical_deep_dive.md` §7 lists 22 files summing to 473 and omits
  `tests/test_svgmap.py`; `pytest --collect-only` on 2026-10-08 collects 513
  across 23 files. The total in the same section is right and the rows are
  stale. [`technical_deep_dive.md` §7](technical_deep_dive.md#7-the-test-suite).
- **Whether the suite runs on Windows depends on a policy that flipped twice.**
  Smart App Control blocked `rasterio`'s DLL on 2026-10-07 and allowed it again
  the next morning with nothing reinstalled; the WSL2 venv is the route that
  does not depend on it. Root [`README.md`](../README.md),
  [`technical_deep_dive.md` §7](technical_deep_dive.md#7-the-test-suite).
- **Five downloaded inputs carry no `licence:`.** `gisco_nuts3`, `gisco_lau`,
  `statbel_income`, `cems_emsr517_germany_2021`, `cems_emsr518_belgium_2021`;
  the honest claim is "every input is traceable to a URL and a purpose", not
  "a licence on every input". [`responsible_ai.md`](responsible_ai.md#what-to-write-under-each-concretely).
- **The prompt budget is in characters, not tokens.** Groq refuses above 8,000
  tokens per minute; the budget is `rag.PROMPT_CHAR_BUDGET` because `tiktoken`
  does not load everywhere, at a measured 2.05 characters per token on the real
  table. [`decisions.md`, 2026-10-08 "the draft tab could never have worked"](decisions.md#2026-10-08--the-draft-tab-could-never-have-worked-for-three-reasons).
- **Tracing, when on, sends prompts off the machine.** LangSmith traces leave
  for LangChain's servers; acceptable here because the corpus is public and the
  table is open data, and said so rather than hidden.
  [`responsible_ai.md`](responsible_ai.md#tracing-let-the-tool-keep-the-log).
- **Some documented absolute figures predate the windowing fix.** The Benelux
  counts in `technical_deep_dive.md` §8 were measured before 2026-10-06 on a
  build whose answer depended on its stripe count; the ratios survive, the
  absolutes do not. [`technical_deep_dive.md` §8](technical_deep_dive.md#8-where-the-numbers-in-this-file-come-from).
- **The map's visible height is a browser check, not a test.** The iframe
  height is not among the assertable element fields, so legend clipping is
  guarded by a written measurement rather than by the suite.
  [`decisions.md`, 2026-10-08 "the legend was off-screen"](decisions.md#2026-10-08--the-maps-legend-was-off-screen-and-the-call-that-drew-it-is-past-its-removal-date).
- **The two UIs show different views of the same table.** The React app is the
  one to demo and needs the API and a Vite build; the Streamlit app needs
  neither and reads the parquets directly. They cannot disagree on a number and
  do not show the same tabs. [`technical_deep_dive.md` §1](technical_deep_dive.md#1-the-pipeline-end-to-end).
