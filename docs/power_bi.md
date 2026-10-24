# Power BI — the same figures, in the tool a ministry already has

`bi/FloodPolicyKit.pbip` is a Power BI **project** (the text format: a
semantic model in TMDL and a report in PBIR, one JSON file per page and per
visual), so it lives in git and a change shows up as a diff. Save it as
`.pbix` from Power BI Desktop to hand it on.

It computes nothing of its own. Every number comes from
`scripts/export_bi.py`, which reads the two frozen parquets with the app's
own helpers; `tests/test_export_bi.py` checks that the EU-27 headline comes
out unchanged (25,737,003 people at RP100) and that the model declares
exactly the columns the export writes.

## Open it — five minutes

1. Export the data (again after any rebuild of the frozen tables):
   `.venv\Scripts\python.exe scripts\export_bi.py`
   This writes `bi/data/regions.csv`, `bi/data/exposure.csv` and, when
   `data/processed/regions.geojson` exists, `bi/data/regions.topojson`.
   `bi/data/` is not committed.
2. Open `bi/FloodPolicyKit.pbip` in Power BI Desktop (a 2026 release: the
   report is in PBIR).
3. If the repository is not at `D:\Users\Siegried\Desktop\Becode\flood-policy-kit`:
   **Transform data → Edit parameters → DataFolder**, set it to the full path
   of `bi\data\`, ending with a backslash. Then **Refresh**.
4. To share: **File → Save as → .pbix**.

## The story, page by page

Six pages, 52 visuals, 1280 × 720. Each story page opens with a claim as its
title and a "what to look at" line under it. Pages 1-5 carry a page filter
**EU-27 = True**, because the brief quotes the EU-27 - clear it in the
Filters pane to see all 37 countries. The return-period tiles are one slicer
synced across pages 1-3: pick one and the others follow; none picked means
1-in-100.

| Page | Title (the claim) | Visuals |
|---|---|---|
| 1. Headline | 25.7 million people in the EU-27 live where a 1-in-100-year river flood reaches | return-period tiles, the return period shown, four cards (people exposed, share exposed, share in a shared basin, expected annual exposure), people exposed by return period - the tiles do not filter this chart, so it always shows the nesting - and the "undefended figures" note |
| 2. Where | Four countries hold three in five of the EU's exposed - the highest shares are elsewhere | tiles, a bar chart on the Geography hierarchy (length = people, colour = share exposed on the YlOrBr ramp), a table of regions ranked by share exposed, the Shape map placeholder, the EuroGeographics credit |
| 3. Downstream of someone else | Nearly two in three of the EU's exposed live in a river basin shared with another country | tiles, three cards, people exposed in shared basins by main basin (drills to regions), a table of regions and their partner countries |
| 4. Who is exposed | Older and poorer regions are not more exposed - the link is weak, and if anything the other way | two scatters, one dot per region sized by people exposed: share exposed against the over-65 share, and against the poverty rate; a caption on what regional averages cannot say |
| 5. Declared vs exposed | Declared risk areas do not follow exposure: Belgium declares almost all its land, Germany and Spain almost none | the median region's declared share by country (drills to regions), a scatter of declared share against share exposed, a caption on why declarations are not comparable |
| Region detail | (drillthrough) | back button, the region's name, four cards, exposure across the nine return periods, its profile (age, poverty, declared share, main shared basin, partners) and its 2041-2070 climate signal (median, quartiles, whether all simulations agree) |

The titles are true at 1-in-100 for the EU-27, measured on 2026-10-24 from
the export: 59 % of the exposed live in Germany, France, Italy and the
Netherlands, while the highest national shares are the Netherlands (14.8 %),
Latvia and Hungary; 63.3 % of the EU-27's exposed live in a shared basin
(57.0 % over all 37 countries, whose non-EU members report no basins); the
regional rank correlation of share exposed is -0.13 with the over-65 share
and -0.16 with the poverty rate; the median Belgian region declares 99.99 %
of its area, the median German one 0.03 %, the median Spanish one 0.004 %. A
title is static text: pick another return period and the cards move, the
title does not.

## Drill down and drill through

- **Drill down** (inside one chart). The bar charts of pages 2 and 5 sit on
  the `Regions[Geography]` hierarchy, Country then Region; page 3's on basin
  then region. Use the arrows in the chart's header: the single down arrow
  turns on drill-on-click - then click a country to open its regions - the
  double arrow opens every country one level down, the up arrow goes back.
- **Drill through** (to another page). Right-click a region - a bar at the
  Region level, a table row, a scatter dot - then **Drill through → Region
  detail**. The page shows that region alone; its back button (top left;
  Ctrl+click while editing in Desktop) returns to where you came from. The
  page is bound to `Regions[region]` and hidden from the tabs in view mode.
  It does not take the source page's other filters
  (`acceptsFilterContext: None`), so its chart shows all nine return periods
  whatever the tiles said. One name covers two regions, Jura (CH025 and
  FRC22): drilling through on it shows both added up, and the region card
  says so.

## The model

| Table | Grain | What it holds |
|---|---|---|
| `Regions` | one row per NUTS3 region (1,345) | names, country, `is_eu27`, population, over-65 share, poverty rate, expected annual exposure, shared basins (`shared_basin_share`, `shared_with`, `shared_basins`, `main_shared_basin`), declared risk area (`apsfr_*`), GDP, density, income, climate change in reference discharge (median, quartiles, sign agreement, three horizons); the hierarchy `Geography` (Country → Region) |
| `Exposure` | one row per region and return period (12,105) | `return_period`, `annual_probability`, `exposed_pop`, `hazard_coverage` |

One relationship, `Exposure[nuts_id]` → `Regions[nuts_id]`, many to one,
filtering from `Regions` to `Exposure`. Lists are joined with `"; "` because a
basin name can carry a comma.

## The measures

21 measures, all on `Exposure`.

| Measure | Use it for | The rule it enforces |
|---|---|---|
| `Exposed population` | every headcount | **One return period at a time: the one selected, RP100 when none is, blank when several are.** The extents are nested, so a sum over return periods counts the same people several times. `exposed_pop` has no default summarisation for the same reason. |
| `Population` | denominators | residents of the regions in the filter |
| `Share exposed` | maps, rankings | one return period |
| `Exposed in shared basins` / `Share in shared basins` / `Regions in shared basins` | the cross-border argument | a floor: non-EU states do not report basins |
| `Expected annual exposure` | the headline card | the sampled band RP10-RP500 only: a lower bound, never called an expected annual damage |
| `Regions measured` | tooltips | the regions in the filter |
| `Share over 65` / `Poverty rate` | page 4, the region profile | weighted by population, regions without the figure left out of both sides. **Regional** figures, not the age or income of the exposed: the kit has no population grid by age, so a "share of the exposed over 65" is deliberately not computed |
| `Declared share of area` | the region scatter, the profile | one region only - blank above, because the export carries no region areas to weight with |
| `Median declared share` | the country bars | the median region; blank, not zero, for Ireland and Lithuania, which report no declared areas |
| `Regions with a declared risk area` | tooltips | declarations are not comparable across countries |
| `Median change in discharge 2041-2070`, `Lower quartile …`, `Upper quartile …` | the climate card | medians and quartiles only, never a mean |
| `Regions where simulations agree 2041-2070` / `Simulations agree on direction 2041-2070` | the climate card | "No data" where the layer has no value, never "No" |
| `Selected return period` / `Return period label` | titles and cards | RP100 when none is selected |
| `Region shown` | the drillthrough page | names the region, or says when a name covers two |

## The theme

`bi/FloodPolicyKit.Report/StaticResources/RegisteredResources/FloodPolicyKit.json`,
registered in `definition/report.json` as the custom theme
(`themeCollection.customTheme` and a `RegisteredResources` resource package).
Light grey page, white cards with a thin border, Segoe UI; exposure in the
YlOrBr ramp of the Streamlit map (`src/svgmap.py`), dark orange `#CC4C02` for
a headcount, one accent - blue `#1F6FEB` - for the cross-border figures,
grey for the declared areas. If Desktop opens the report without it (no grey
page), apply it once by hand: **View → Themes → Browse for themes →** that
file.

## Add the map — the one thing done by hand

Page 2 keeps a labelled box for it. Insert a **Shape map**: Location
`Regions[nuts_id]`, Color saturation `Share exposed`, then **Format → Map
settings → Custom map →** `bi/data/regions.topojson`, and resize it over the
note. In Desktop the Shape map may need **Options → Preview features → Shape
map visual**. It is not generated because the Shape map stores the TopoJSON
inside the report, and the boundaries are not committed (GISCO terms, see
`data/processed/DATA_NOTICE.md`). The page already carries the credit
"© EuroGeographics for the administrative boundaries".

## How the report is built and checked

- `scripts/build_bi_report.py` writes every PBIR file, the theme and
  `definition.pbir` from one grid and one palette. Once the report is edited
  and saved in Desktop, the saved files are the source: running the script
  again overwrites them, and `test_the_committed_report_is_what_the_generator_writes`
  fails until script and files agree again - port the change into the script,
  or retire the test.
- `scripts/validate_bi_report.py` checks every JSON file of the project
  against the schema its `$schema` names - `definition.pbir`:
  definitionProperties 2.0.0; `version.json`: versionMetadata 1.0.0;
  `report.json`: report 3.3.0; `pages.json`: pagesMetadata 1.1.0; each
  `page.json`: page 2.1.0; each `visual.json`: visualContainer 2.13.0; the
  `.pbip` and `.pbism`: their 1.0.0 schemas; the theme: the report theme
  schema of Desktop 2.159 - and each visual's formatting names and values
  against that theme schema, offline. The schemas are vendored in
  `bi/schemas/` from microsoft/json-schemas and
  microsoft/powerbi-desktop-samples, both MIT; the licences are beside them.
- What no schema checks: the data roles a visual uses (`Category`, `Y`, `X`,
  `Size`, `Values`, `Tooltips`) and how a page looks. Those need Desktop.

## Before showing it to anyone

- **Credit on every map page:** "© EuroGeographics for the administrative
  boundaries" (GISCO terms) - already on page 2.
- **Never show a figure "for all return periods".** Every headcount is blank
  when several are selected; the tiles are single-select.
- **Prefer the Shape map to the Map / Filled map visuals:** those two send the
  data to Bing / Azure Maps and need the network; the Shape map draws the
  local TopoJSON.
- **Publish to web is public.** These are public data, but a published report
  is outside the team's control; share the `.pbix` instead.
