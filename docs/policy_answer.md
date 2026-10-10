# The answer: what we are asked, what we found, who has to act

**Written 2026-10-08.** Every figure here was re-derived on that date from
`data/processed/exposure.parquet`, `data/processed/context.parquet`, the cached
APSFR layer and the Floods Directive text in `data/raw/scrape/`. Re-derive them
rather than quoting this page: the parquets are rebuilt and the counts move.

This page is the spine of the brief and the pitch. `docs/strategy.md` argues what
*would* win; this one records what the kit can actually support today, and names
the authority for each recommendation. Data sources stay declared in
`config/sources.yaml`; what is new here is the **institutional layer** — the
instruments, the deadlines and the bodies — which no dataset carries.

---

## 1. The question actually asked

From the FARI event page for the European AI Challenge 2026 (29-30 October 2026,
FARI then JRC):

> *L'IA peut-elle aider l'Europe a mieux anticiper les risques d'inondation ?*
> — and, centrally, *comment l'IA peut-elle etre utilisee de maniere responsable
> pour aider les gouvernements* a se preparer aux urgences climatiques.

So the question is **not** "where is flood risk highest". It is a question about
**government preparation**, and about the **responsible** use of AI in getting
there. Two of the four scored deliverables are about the reasoning, not the map:

| Deliverable | What it is scored on |
|---|---|
| A map, dashboard or visualisation | one thing pointed at, not a legend narrated |
| A **two-page** policy brief | a decision with an addressee and a date |
| A reflection on responsible AI use | what the AI was *not* allowed to decide |
| A presentation to a jury | three minutes |

Also on that page: about 60 students, teams, English, free, open to bachelor's
and master's students of Belgian universities, *hautes ecoles* and *hogescholen*
(and, where relevant, other European institutions — secondary pupils too). The
page welcomes AI, data science, engineering, environmental science, political
science, communication and journalism. Prizes to the top three; first prize
includes an internship and a trip to the JRC site at Ispra. The page contradicts
itself on whether registration is open or opens "prochainement" — so write to
info@fari.brussels rather than infer.

## 2. What we answer, in one line

> **Being at risk of flooding and being unprepared for it are two different
> maps. Europe governs the first one and reports the second one badly.**

That is answerable with what is already built, it is a finding about
*preparation* (which is what was asked), and it puts the limitation section at
the centre instead of in an apology at the end.

## 3. The measured base, 2026-10-08

`exposure.parquet`: **12,105 rows** = **<!-- numbers:nuts3_regions -->1,345<!-- /numbers -->** NUTS3 regions x **9** return
periods, 15 columns, 37 country codes. `context.parquet`: 1,345 rows, 29 columns.

| Figure, 1-in-100-year river flood | Value |
|---|---|
| Population exposed, EU-27 | **25,737,004** |
| EU-27 population in the table | 446,267,469 |
| Share exposed, EU-27 | **5.77 %** |
| Population exposed, whole file (37 countries) | 29,727,887 |
| Regions with no measured figure | 7 of 1,345 |
| Regions with hazard coverage below 1.0 | 11 of 1,345 |

**Scenario sensitivity**, EU-27 exposed population: RP10 **16,704,818** ->
RP100 **25,737,004** -> RP500 **30,730,197**. Quote the return period with every
headcount; the extents are nested, so no figure is ever "all periods".

**The ten most exposed EU-27 regions by share of their own population** (RP100,
regions above 50,000 inhabitants) are Dutch, Italian and German: Zuidoost-Zuid-
Holland 70.8 %, Zuidwest-Gelderland 68.9 %, Rovigo 61.1 %, Landshut 50.1 %,
Groot-Rijnmond 42.2 %, Arnhem/Nijmegen 41.8 %, Oost-Zuid-Holland 40.3 %,
Ferrara 36.3 %, Gross-Gerau 35.7 %, Csongrad-Csanad 35.2 %.

## 4. The four findings, with their caveats attached

### 4.1 The Member States' own risk declaration is not comparable between them

Under **Article 5** of [Directive 2007/60/EC](https://eur-lex.europa.eu/eli/dir/2007/60/oj) each Member State designates its
Areas of Potential Significant Flood Risk and reports them to the Commission.
Measured on the EEA layer, current (2018) cycle — 12,173 polygons, 25 countries:

| Reporting style | Countries | Median polygon | Shape index | National territory declared |
|---|---|---|---|---|
| Whole territory | BE | one giant polygon + 27 slivers | 1.5 | **99.9 %** |
| Zones | HR, NL, HU, EL, IT, PL, FR, SE, FI, LV | 5-480 km2 | 1.1-2.3 | 1.4 - 59.6 % |
| River reaches as ribbons | ES, AT, CZ, CY, DE, RO, LU | 0.006-0.058 km2 | **23 - 74** | **0.004 - 0.2 %** |

The ratio between the largest and the smallest share of national territory
declared is **23,095** (Belgium 99.908 %, Spain and Cyprus 0.004 %). Germany's
648 polygons total **76 km2**; Belgium's 28 total **30,695 km2** — about the
whole country. Germany is not four hundred times safer than Belgium: the shape
index (perimeter over that of an equal-area circle) is 51 for Germany and 1.5
for Belgium, which is the signature of a river reach versus a zone.

**The honest claim.** The Article 5 declaration is a *legal act recorded with
national geometry conventions*, not a measurement. Any pan-European statistic
built on declared APSFR area — including "share of exposed population inside a
declared area" — ranks reporting styles, not risk. The kit shows it concretely:
Landshut is 50.1 % exposed at RP100 with an `apsfr_share` of 0.001, and
Gross-Gerau 35.7 % exposed with 0.000, while Dutch regions at a similar exposure
read 0.84-0.99.

**What it is not.** It is not evidence that any State under-declares. A State may
have assessed an area under Article 4 and concluded the risk is not significant,
which the Directive permits.

### 4.2 Two EU-27 Member States are absent from the Commission's own layer

Verified live on the EEA service, 2026-10-08:

| Cycle | Polygons | Countries |
|---|---|---|
| 2010 | 496 | AT (229), DE (75), ES (33), FR (30), **LT (129)** |
| 2018 | 12,173 | 25 — every EU-27 state except **IE** and **LT** |

Lithuania reported in 2010 and not in 2018, so pinning the current cycle (which
`src/apsfr.py` does, to avoid overlaying two declarations of the same ground)
drops it. **Ireland appears in neither cycle.** Ireland certainly designates
areas — it runs the CFRAM programme — so this is a gap in the *published
reporting infrastructure*, not in Irish policy. Said the other way: a
pan-European flood-preparedness indicator built on this layer silently omits two
Member States, and nothing in the service says so.

### 4.3 Most of Europe's exposed population is downstream of someone else

Off the WFD river basin districts, grouped into international basins by
`config/international_basins.yaml`:

- **810** of 1,345 regions have part of their area in a basin that crosses a
  national border; **603** lie wholly inside one.
- **16,945,579** people exposed at RP100 live in those regions — **57.0 %** of
  the European total.
- Namur reads `[DE, FR, LU, NL]`; Groot-Rijnmond `[AT, BE, CH, DE, FR, LU]`;
  Wien eleven partner countries.

This is a **floor**, twice over: Switzerland, Belarus, Ukraine and Serbia hold
large parts of the Rhine, the Nemunas, the Vistula and the Danube and do not
report under the [Water Framework Directive](https://eur-lex.europa.eu/eli/dir/2000/60/oj); and districts the crosswalk cannot
group stay national rather than being counted as shared.

### 4.4 The reference discharge is rising where people already live in the way

EURO-CORDEX, eight bias-adjusted simulations through E-HYPEcatch. Medians and
quartiles only — a relative change against a near-zero reference discharge is
unbounded, so a mean or a maximum is meaningless here.

| Horizon | Median of regional medians | Interquartile range | Regions where the ensemble agrees on the sign |
|---|---|---|---|
| 2011-2040 | **+12.2 %** | +0.5 ... +23.2 % | 976 of 1,345 |
| 2041-2070 | **+19.9 %** | +8.0 ... +33.9 % | 994 of 1,345 |
| 2071-2100 | **+20.3 %** | +4.5 ... +38.0 % | 943 of 1,345 |

**87 regions** are simultaneously in the top decile of exposure share today and
rising by 2041-2070 with the ensemble agreeing on the sign — Groot-Rijnmond,
Val-de-Marne, Wien, Rhone, Padova, Firenze, Hamburg among them. That set is a
planning list, not a ranking.

**Why this matters legally and not just physically:** **Article 14(4)** of the
Directive requires that "the likely impact of climate change on the occurrence
of floods shall be taken into account" in the review of the preliminary
assessment and of the management plans. This is the one finding the law
explicitly asks for.

## 5. The calendar — quoted from the Directive on disk

`data/raw/scrape/floods_directive.html`, Articles 14 to 16:

| Instrument | Article | Reviewed by | Then every | Next date |
|---|---|---|---|---|
| Preliminary flood risk assessment | 14(1) | 22 Dec 2018 | six years | 22 Dec **2030** (2024 passed) |
| Flood hazard and flood risk maps | 14(2) | 22 Dec 2019 | six years | 22 Dec **2031** (2025 just passed) |
| **Flood risk management plans** | 14(3) | 22 Dec 2021 | six years | **22 Dec 2027** |
| Member States inform the Commission | 15 | — | — | within the above dates |
| Commission report to Parliament and Council | 16 | 22 Dec 2018 | six years | 22 Dec **2030** |

The "reviewed by" and "then every" columns are the Article's own words, recorded
per paragraph in `config/legislation.yaml` (`src.legislation.cite("FD", "14(3)")`
returns the citation with its ELI URL); only the "next date" column is arithmetic.

**This is the hook.** A brief written in October 2026 lands fourteen months
before the **22 December 2027** review of the flood risk management plans. That
is the one instrument still open, and it is where a recommendation can actually
be absorbed. Say the date.

Three more articles do real work:

- **Article 7(4)** — "In the interests of solidarity", a plan in one Member State
  shall not include measures that significantly increase flood risk upstream or
  downstream in another country of the same basin, *unless coordinated and
  agreed under Article 8*. The solidarity clause, by name.
- **Article 8(5)** — where a Member State identifies an issue affecting its flood
  risk management that it **cannot resolve alone**, it may report the issue to
  the Commission and the other Member States concerned and recommend a solution;
  **the Commission shall respond within six months.** A named mechanism with a
  binding response time, and almost unused. Recommending its use is a concrete
  act, not a wish.
- **Article 8(3)** — where a basin extends beyond the Union, Member States only
  "shall endeavour" to produce a single plan. The weakest verb in the Directive
  sits exactly on the Rhine, the Danube, the Vistula and the Nemunas — which is
  finding 4.3 restated in the law's own words.

## 6. The measures: what, where, by whom, how, by when

Three recommendations, each tied to an instrument and an addressee. None of them
requires new legislation.

### R1 — Make the Article 5 declaration comparable before the 2027 review

| | |
|---|---|
| **What** | A reporting guidance note fixing the *geometry convention* for APSFR: minimum mapping unit, and whether a river reach is reported as a buffered area or as a line. Publish the declared share of territory alongside each national submission so the convention is visible. |
| **Where** | The WISE Floods Directive reporting schema and the APSFR layer served by the EEA. |
| **By whom** | DG Environment, through the **Working Group on Floods** of the WFD/FD Common Implementation Strategy, with the EEA as the layer's custodian. |
| **How** | The Working Group already issues reporting guidance for each cycle; this is an amendment to the next guidance, not a new process. |
| **By when** | In time for the **22 December 2027** plan review — so tabled at a 2026 Working Group on Floods meeting. |
| **Evidence** | 4.1: a 23,095-fold spread in declared territory, shape index 1.5 to 74. |

### R2 — Close the two reporting holes, and publish absence as absence

| | |
|---|---|
| **What** | Ireland's APSFR into the published layer; Lithuania's current-cycle submission reconciled so that pinning the current cycle does not delete a Member State. Where a State is absent, the service should say so rather than return nothing. |
| **Where** | The EEA Floods Directive discovery service. |
| **By whom** | The EEA, with the Irish Office of Public Works and the Lithuanian Environmental Protection Agency as reporters; DG ENV as the Directive's guardian. |
| **How** | Article 15 reporting, already the legal route. |
| **By when** | Before the Commission's next implementation report under **Article 16** (22 December 2030), which otherwise rests on a layer missing two members. |
| **Evidence** | 4.2, verified live 2026-10-08: 25 countries in the 2018 cycle, Ireland in neither cycle. |

### R3 — Use Article 8(5) on one named shared basin, as a test case

| | |
|---|---|
| **What** | One Member State formally reports, under Article 8(5), that it cannot resolve the coordination of flood risk in a basin whose upstream lies outside the Union — and recommends a solution. The Commission then owes an answer in six months. |
| **Where** | The Meuse is the right test case for a Brussels jury: five states, a Belgian secretariat, and a region (Namur) reading `[DE, FR, LU, NL]` — exactly the Commission's membership. For the non-EU upstream problem, the Rhine (Switzerland) or the Danube (Serbia) is the sharper case. |
| **By whom** | The **International Meuse Commission** (secretariat in Liege; parties France, Belgium, the Netherlands, Germany, Luxembourg plus the Walloon, Flemish and Brussels-Capital Regions) as the forum; one of its parties as the reporting Member State; the Commission as respondent. |
| **How** | Article 8(5) verbatim. No new body, no new money. |
| **By when** | A report lodged in 2026 obliges a Commission response inside the 2027 planning window. |
| **Evidence** | 4.3: 57.0 % of Europe's exposed population in a cross-border basin, and Article 8(3)'s "shall endeavour". |

## 7. The addressees, named

| Body | Role for this brief | URL |
|---|---|---|
| DG Environment — Floods | Guardian of Directive 2007/60/EC; convenes the Working Group on Floods | https://environment.ec.europa.eu/topics/water/floods_en |
| European Environment Agency — WISE | Serves the APSFR and river basin district layers | https://water.discomap.eea.europa.eu/ |
| International Meuse Commission | Meuse coordination forum, secretariat Liege | http://www.meuse-maas.be |
| International Scheldt Commission | Scheldt; six parties incl. the three Belgian Regions; secretariat Antwerp | https://www.isc-cie.org/en/ |
| ICPR — Rhine | Coordinates the Floods Directive in the Rhine basin above 2,500 km2 | https://www.iksr.org/en/eu-directives/floods-directive/flood-risk-management-plan/national-reports |
| ICPDR — Danube | Danube basin; Flood Action Programme since 2004; secretariat Vienna | https://www.icpdr.org/ |
| JRC — Risk Data Hub | The consequence layer, from the jury's own house | https://drmkc.jrc.ec.europa.eu/risk-data-hub |
| EEA — European Climate Risk Assessment (EUCRA) | 36 climate risks, March 2024; second assessment due 2028 | https://www.eea.europa.eu/en/analysis/publications/european-climate-risk-assessment/ |
| EU Solidarity Fund (DG REGIO) | Post-disaster allocation; over EUR 9.6 bn to 24 Member States and 4 accession countries | https://ec.europa.eu/regional_policy/funding/solidarity-fund_en |
| EIOPA | Natural-catastrophe insurance protection gap dashboard, 30 countries, 1980-2024 | https://www.eiopa.europa.eu/tools-and-data/dashboard-insurance-protection-gap-natural-catastrophes_en |
| [Union Disaster Resilience Goals](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX%3A32023H0215%2801%29) | Commission Recommendation of 8 Feb 2023: anticipate, prepare, alert, respond, secure | https://eur-lex.europa.eu/legal-content/EN/TXT/HTML/?uri=CELEX%3A32023H0215%2801%29 |

## 8. The responsible-AI layer, and the live legislation

The grid stays the HLEG seven requirements (see `docs/responsible_ai.md`); what
this page adds is the current legislative context a JRC jury will know:

- **[Regulation (EU) 2024/1689](https://eur-lex.europa.eu/eli/reg/2024/1689/oj)** (AI Act) — declared and fetched. Do not assert
  Annex III high-risk classification without reading the annex; the defensible
  framing is a decision-support tool for a public authority to which the
  transparency and human-oversight expectations were applied anyway.
- **[Cloud and AI Development Act](https://eur-lex.europa.eu/legal-content/EN/TXT/?uri=CELEX:52026PC0502)** — a **proposal for a regulation**, not adopted
  (page last updated 3 June 2026). It would create one EU sovereignty framework
  with four assurance levels, public bodies choosing a level from their own risk
  assessment, plus a common procurement framework and AI Experience and
  Acceleration Centres for administrations. Relevant in one sentence: a
  flood-risk decision-support tool run by a public authority is exactly the kind
  of system that would have to declare an assurance level.
  https://digital-strategy.ec.europa.eu/en/policies/cloud-and-ai-development-act
- **Commission AI portal** —
  https://commission.europa.eu/topics/artificial-intelligence_en
- **Data for Policy** — the research community this challenge sits in. The 2026
  edition (Barcelona, 8-10 September 2026, about 200 participants from 44
  countries, 123 contributions) ran the theme *Governance of/with AI*, with a JRC
  keynote; its Book of Abstracts is on Zenodo and its journal is *Data & Policy*
  (Cambridge University Press). https://dataforpolicy.org/data-for-policy-2026/
- **Council of Europe AI policy summit 2026** —
  https://www.coe.int/en/web/new-democratic-pact-for-europe/-/watch-live-2026-ai-policy-summit

## 9. What this document does not claim

- **No State is accused of under-declaring.** 4.1 and 4.2 are findings about the
  comparability and completeness of a *published layer*.
- **No casualty or loss figure** is quoted here. The Risk Data Hub's rows are
  nested by administrative level and its values are averages across DFO, EM-DAT
  and HANZE; an unfiltered sum counts the same event four times.
- **No prediction.** The hazard layer models river flooding only, for basins
  above about 150 km2, and does not contain surface runoff — which was a large
  part of what happened in Wallonia in July 2021.
- **The cross-border figures are a floor**, for the two reasons in 4.3.
- **The climate figures are medians and quartiles.** One ensemble member never
  counts as agreement with itself.

- **No figure here is a statutory flood hazard or risk map.** Every number is a NUTS3 screening statistic over the JRC hazard rasters. The maps that bind are the Member States' own under Article 6 of Directive 2007/60/EC, reported under Article 15 and served by the EEA Flood Risk Areas Viewer (https://discomap.eea.europa.eu/floodsviewer/) and WISE-Freshwater; where this page and a Member State's map disagree about a place, the Member State's map is the one the law reads. And when a return period is quoted, say which Article 6(3) class it is read in: the Article puts a number on the medium class only ("likely return period ≥ 100 years"); calling RP10–RP75 "high probability" and RP200–RP500 "low probability / extreme" is this kit's reading, not the Directive's.

## 10. Open, and known

- `context.parquet` was rebuilt on 2026-10-08 after the `shared_with` repair,
  and the two counts now coincide exactly as predicted: **810** regions with a
  partner, **810** with a cross-border share, **zero** contradictions.
- The columns could carry their unit in their name (`poverty_rate_pct`), which
  is a naming decision rather than a bug: `poverty_rate` is a percentage and
  `share_over_65` a fraction, both offered as indicators, neither saying so in
  its name. The unit is now in the docstring and pinned by a test; renaming
  would touch `api/main.py`, `app/streamlit_app.py`,
  `scripts/build_exposure.py`, the tests and every older export.
- Measured 2026-10-08, late morning: the full suite is **<!-- numbers:tests_collected -->550<!-- /numbers --> tests, all passing
  on Windows with nothing deselected**. Smart App Control had blocked `rasterio`
  since 2026-10-07 and allowed it again the next morning with nothing
  reinstalled, so the policy moves both ways and the only safe habit is to
  re-measure rather than quote this line. The WSL2 venv stays as the route that
  does not depend on it.
