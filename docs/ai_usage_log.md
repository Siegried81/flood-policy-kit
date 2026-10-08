# AI usage log

Annex A of the policy brief. One row per use of a model, written as the work
happened.

**What this log is.** The record of what a human checked and what a human
rejected. A trace tool records what the machine did — `LANGSMITH_TRACING=true`
does that automatically, and `src.workflow.tracing_status()` reports whether it
is actually on. No tool can record the other half: which proposals were refused,
and on what evidence. That is what this file is for, and it is why the
**Rejected** rows below are the point of it rather than an embarrassment.

**What this log is not.** It is not a stopwatch. The times are the *order* of the
work on the morning of **2026-10-08**, to the nearest five minutes as the session
ran; they are not instrumented timestamps and should not be read as such. Every
figure quoted in the table was measured in that session, and the dated record of
each measurement is in [`docs/decisions.md`](decisions.md).

| Time | Tool / model | Task | What a human checked | Outcome |
|---|---|---|---|---|
| 09:15 | Claude Opus 5 (Claude Code) | Run the suite to get a baseline before touching anything | Read the collection error instead of the summary line | **Finding, not a pass:** three test modules could not even be collected — Windows Smart App Control was blocking rasterio's DLL |
| 09:25 | Claude Opus 5 | Re-derive the source counts that `docs/responsible_ai.md` quotes | Counted the entries in `config/sources.yaml` carrying a `verified` and a `licence` field, one by one | Accepted: 42 declared, 34 verified, 11 with an explicit licence — the doc's figures held |
| 09:40 | Claude Opus 5 | Establish the Floods Directive's review deadlines | A web search returned 22 December 2027 as an *inference* from the six-year rhythm; read Articles 7, 8 and 14–16 in the local copy of the directive instead | Accepted after replacing the inference with the primary text — Art. 14(3) reviews the plans "by 22 December 2021 and every six years thereafter" |
| 09:55 | Claude Opus 5 | Propose the headline finding: regions heavily exposed but not designated under Article 5 | Checked the candidates by hand. Vaucluse reads 22.1 % of its population exposed at RP100 with an `apsfr_share` of 0.0 — but France declares in 68 of its 101 regions, so "France under-declares" could not be what the data said | **Rejected as an artefact.** Re-measured polygon shape: index 1.5 for Belgium and Croatia against 51 for Germany and 74 for Luxembourg. It is a reporting-convention difference. Reframed as a comparability finding |
| 10:05 | Claude Opus 5 | Draft the claim that Ireland does not designate areas of potential significant flood risk | Queried the EEA service live rather than inferring from absence: the 2010 cycle holds 496 polygons across AT, DE, ES, FR and LT; the 2018 cycle holds 12,173 across 25 countries; Ireland is in neither | **Rejected the wording.** Narrowed to "the published layer carries no Irish rows", which is what was actually verified. Ireland runs the CFRAM programme; the gap is in the reporting infrastructure |
| 10:15 | Claude Opus 5 | Investigate `shared_with` naming partner countries that `shared_basin_share` denied | Proved the bug before repairing it: 58 of 1,345 regions carried a contradictory list. Wrote the test first and confirmed it failed *without* the fix, by stashing the change | Accepted: 34 regions change, 33 of them losing an all-sliver list. The rebuild then confirmed the prediction exactly — 810 = 810, zero contradictions |
| 10:30 | Claude Opus 5 | Propose converting `poverty_rate` to a fraction, so it matches `share_over_65` | Checked the source: Eurostat publishes the at-risk-of-poverty rate as 14.6, not 0.146, and a brief quoting "14.6 %" has to match it | **Rejected.** The two scales were pinned by `test_the_two_indicators_keep_their_published_units` instead, so normalising one later is a deliberate act with a failing test in front of it |
| 10:40 | Claude Opus 5 | Propose `folium` for the missing choropleth — it is already in `requirements.txt` | Checked it against `docs/day_of.md`, which requires the kit to run with the Wi-Fi off in front of a jury. A Leaflet map fetches its basemap tiles from a tile server | **Rejected.** An inline SVG choropleth was written instead (`src/svgmap.py`): no network, no build step, no key |
| 10:50 | Claude Opus 5 | Colour the choropleth on a linear ramp from the minimum to the maximum | Measured the distribution before accepting it. The six quantile bounds at RP100 are 0.84 %, 1.90 %, 3.39 %, 5.61 %, 9.22 %, 70.82 % | **Rejected.** A linear ramp over that range paints everything but the Dutch tail the palest colour. Quantile classes, with the bounds printed in the legend so the reader sees they are relative |
| 10:55 | Claude Opus 5 | Frame the map on the full extent of the GISCO NUTS file | Measured the extent both ways: 12,850 × 9,486 km with the outermost regions, 4,680 × 4,029 km without — 6.5 times the area | **Rejected.** The viewport is set from continental Europe. The 16 off-map regions are still *drawn* and the caption names them, because a region dropped with no note reads as a region with nothing to report |
| 11:00 | Claude Opus 5 | Add Ceuta and Melilla to that exclusion list — they are in Africa | Measured their actual effect on the extent: none at all, 4,680 × 4,029 km either way | **Rejected.** They sit 15 km off the Spanish coast and are inside the frame already. Listing them as off-map would have been a caption that was simply untrue |
| 11:05 | Claude Opus 5 | Test that an unmeasured region is grey and not the colour of zero | Ran the assistant's own test: it failed, 2 ≠ 1 | **The test was wrong, not the code.** It counted the legend's own grey swatch as a region. Rewritten to match path fills only |
| 11:15 | `openai/gpt-oss-120b` (Groq) | Draft a brief section: when must Member States review their flood risk management plans, and what must the review take into account | Read the answer against the five retrieved passages; checked the grounding score and every citation | Accepted: 68 % lexical grounding, no invalid citations, and the cited obligation matched Article 14 — including 14(4) on climate change |
| 11:20 | Claude Opus 5 | Diagnose the draft tab's `No model reachable: 413 Payload Too Large` | Probed the live endpoint rather than trusting the status code. The body says `service tier 'on_demand' on tokens per minute (TPM): Limit 8000, Requested 14931` — a per-minute budget, while the model's context window is 131k | **The status code was misleading and the handling was wrong.** It is a rate limit, so it now falls back to the local model, and the prompt table is budgeted to fit instead of being a fixed 200 rows |
| 11:25 | Claude Opus 5 | Test that the prompt table carries only the selected return period | Ran the assistant's own test: it failed with an empty set | **The test was wrong again.** It guessed which column held the return period instead of reading the TOON header. Rewritten to parse the header, which is the only thing that knows the column order |
| 11:40 | Claude Opus 5 | Re-run the whole suite before reporting anything as done | Ran it with nothing deselected, rather than quoting the morning's figure | 501 passed, 0 failed. rasterio imports again — so the claim in `requirements.txt`, the README and `docs/policy_answer.md` that it is blocked is now **out of date and has to be re-measured** |
| 12:10 | Claude Opus 5 + cloud review agents | Review the whole branch before anything is committed | Checked each of the four findings against the working tree instead of trusting the report | **Rejected two of four as artefacts**: the review bundles only TRACKED files, so `src/svgmap.py` and `docs/policy_answer.md` looked missing to it. They exist and are untracked - which is a real warning about committing, not a defect in the code |
| 12:20 | Claude Opus 5 | Act on the review's second finding: a module variable called `measured` set twice | Wrote the failing test first. The map tab binds `measured` to a bool, the context tab rebinds the same name to a DataFrame, and Streamlit re-runs the whole script - so pressing Draft raised `ValueError: The truth value of a DataFrame is ambiguous` | Accepted after fix: renamed the context tab's binding to `covered`. 41 -> 42 tests on that module, the new one failing before and passing after |
| 12:40 | Claude Opus 5 | Diagnose "I cannot choose the horizon, it stays on 2070" | Driven in a real browser rather than reasoned about: the slider handle is 12x12 px with its value label 18 px ABOVE it, and on a 639 px viewport it lands below the fold. A full-width drag left the committed value on the default; the keyboard arrows moved it fine | Accepted after fix: three named periods became three click targets (`st.radio`), the same control as the layer selector above it |
| 12:50 | Claude Opus 5 | Add tests for the two usage-log fixes | Ran them the way `CLAUDE.md` says to - with `data/processed/` hidden, which is what CI sees | **Rejected its own first version.** Both passed here and failed with the data hidden, because they imported the Streamlit script and importing it runs the whole page. The helpers moved to `src/usage_log.py`; 43 passed both with and without `data/` |

**Twenty rows, nine of them rejections.** Three further rows are the
assistant's own work being overruled rather than a proposal refused: twice a
test written with assistance was itself wrong and the failure was read instead of
worked around, and once the handling of a provider error was wrong because the
status code was believed over the response body.

Every rejection was settled by a measurement, not by taste, and the pattern worth
naming in the brief is this: the model's first answer was usually *plausible* —
France under-declaring, a linear colour ramp, folium for a map — and the
measurement is the only thing that made it false.

## What the AI was not allowed to decide

Not repeated here, because it belongs with the reasoning:
[`docs/responsible_ai.md`](responsible_ai.md) names the four — who gets protected
first, the vulnerability weights, the depth threshold, and anything a resident
would experience directly. The rows above are the evidence that the boundary was
held in practice, and `docs/decisions.md` is the dated record behind each figure.
