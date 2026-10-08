# The docs, and where to start

These pages record what the kit measures, why it is built the way it is, and
what a jury at the European AI Challenge 2026 (JRC x FARI, 29-30 October) is
scoring: a map, a two-page policy brief, a reflection on the responsible use of
AI, and a three-minute pitch. Seventeen files, 385 KB measured on 2026-10-08.
Most of that is background written before the data was frozen; the argument
itself is short, and this page exists so a reader opens it first rather than a
60 KB reference.

**Twenty minutes:** [`policy_answer.md`](policy_answer.md) (the spine: the
question as asked, four measured findings, three recommendations with an
article, an addressee and a date), [`responsible_ai.md`](responsible_ai.md)
(the HLEG grid and what the AI was not allowed to decide),
[`ai_usage_log.md`](ai_usage_log.md) (the annex: twenty rows, nine of them
rejections) and [`limitations.md`](limitations.md) (what none of it claims).
[`decisions.md`](decisions.md) is the appendix: the dated record behind every
figure the first four quote.

## What each file holds

Sizes measured on 2026-10-08 with `os.path.getsize`; they move with every edit,
so re-measure rather than quote.

| Path | Holds | KB |
|---|---|---|
| [`policy_answer.md`](policy_answer.md) | The question the organisers ask, the measured base at RP100 (25,737,004 people exposed in the EU-27), four findings with their caveats, the Directive's calendar, three recommendations with the authority and the date behind each, and what the page does not claim. | 19.2 |
| [`responsible_ai.md`](responsible_ai.md) | The HLEG seven-requirement grid with what the kit can honestly claim under each, licence hygiene, tracing, the usage-log format, and the four things AI must not decide. | 7.6 |
| [`ai_usage_log.md`](ai_usage_log.md) | Annex A: one row per model use on 2026-10-08, what a human checked and what was rejected, every rejection settled by a measurement. | 10.2 |
| [`limitations.md`](limitations.md) | What the figures cannot say, what was designed and not built, what an authority would still have to do, and the risks accepted to ship in ten days, each bullet pointing at its source. | 21.9 |
| [`decisions.md`](decisions.md) | The dated record of every change to what a number means, newest at the bottom, with the before and after measurement and the test count at each step. | 67.1 |
| [`technical_deep_dive.md`](technical_deep_dive.md) | How the pipeline works and why: the four CRSs, what the exposure columns mean, why windows are cut on the population grid, the UI contract, validation, the LLM layer, and the test suite. | 21.4 |
| [`scope.md`](scope.md) | Why the unit is NUTS3 and the study area is Europe, what that changes about population, boundaries and demographics, the alignment rule, and why Belgium is kept only as the rehearsal. | 10.1 |
| [`strategy.md`](strategy.md) | What would win: the observed satellite flood-depth series most teams will not find, the comparison questions, and the "risk of being unprepared" framing the brief adopts. | 8.4 |
| [`datasets.md`](datasets.md) | Every declared source, verified against the live host: CRS, unit, size, licence and the specific trap each one sets, plus the two sources declared and not yet used. | 45.9 |
| [`geospatial_crash_course.md`](geospatial_crash_course.md) | A ten-minute glossary for the non-GIS teammate, then the ways this project's data returns a plausible wrong number: CRS, non-square cells, units, counts versus densities, zonal statistics, NUTS nesting, IoU. | 30.9 |
| [`policy_context.md`](policy_context.md) | The EU flood-risk policy framework researched for the RAG corpus and the brief: the Floods Directive cycle, Sendai, civil protection, the insurance gap, the July 2021 figures, the AI Act, with a verification flag on every claim and twelve open items. | 63.3 |
| [`policy_craft.md`](policy_craft.md) | How a brief, a pitch and a decision-maker's map are judged: BLUF, the recommendation sentence template, the two-page skeleton, uncertainty wording, and why teams lose. | 52.9 |
| [`workflow.md`](workflow.md) | Why the brief pipeline is a fixed five-node graph and not an agent: the four guards, the approval gate, idempotent fetching, and verification done in Python rather than by a model. | 5.4 |
| [`roles.md`](roles.md) | The three hats of the integrator (decision framing, exposure analysis, GenAI), how a five-person team splits, and the two rules that save the deliverable. | 4.4 |
| [`plan.md`](plan.md) | The 23-day preparation calendar from 6 October: registration, the download, the kit, the GenAI layer, and the dress rehearsal on a region nobody prepared. | 5.5 |
| [`day_of.md`](day_of.md) | The checklist before leaving home, the hour-by-hour shape of the two days, the three-minute pitch, and the questions to have an answer ready for. | 5.1 |
| [`README.md`](README.md) | This index. | 6.1 |

## Full reading order

1. [`policy_answer.md`](policy_answer.md): the whole argument, with the
   numbers, in one sitting.
2. [`limitations.md`](limitations.md): what those numbers do not support,
   before any of them is repeated.
3. [`responsible_ai.md`](responsible_ai.md) then
   [`ai_usage_log.md`](ai_usage_log.md): the reflection and its evidence.
4. [`scope.md`](scope.md) and [`strategy.md`](strategy.md): why Europe at
   NUTS3, and why the brief asks about preparation rather than water.
5. [`technical_deep_dive.md`](technical_deep_dive.md): what each column means
   and how the pipeline keeps the headline additive.
6. [`workflow.md`](workflow.md): why there is a human gate and no agent.
7. [`datasets.md`](datasets.md) and
   [`geospatial_crash_course.md`](geospatial_crash_course.md): the reference
   half, read when a source or a number needs checking.
8. [`policy_context.md`](policy_context.md),
   [`policy_craft.md`](policy_craft.md), [`roles.md`](roles.md),
   [`plan.md`](plan.md), [`day_of.md`](day_of.md): the preparation material,
   written before the freeze.

When a figure here and a figure in the code disagree, the code and
`config/sources.yaml` are right. [`decisions.md`](decisions.md) is the dated
record of every such change, and [`limitations.md`](limitations.md) is what the
kit does not claim.
