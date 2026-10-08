# Your three hats, and how to split the team

## Why you are the integrator

The teams are deliberately multidisciplinary: AI, data science, engineering,
environmental science, urban studies, political science, public policy,
communication, journalism, linguistics. The organisers say plainly that *no
single profile is expected to do everything*.

That design creates one predictable failure: the technical half and the policy
half work in parallel for a day and a half, then discover at 16:00 on Friday that
the numbers do not support the recommendations. Someone has to hold the two
together from hour one.

You have three profiles at once — **Solvay commercial engineer**, **data
scientist**, **GenAI engineer**. That is not three skills to show off; it is one
role: **integrator / product owner**. Claim it in the first thirty minutes, and
claim it by doing, not by announcing a title.

The way you claim it: in the first half hour, you are the one who writes **the
decision-maker's question** on the whiteboard in a single sentence, and keeps
pointing at it.

## Hat 1 — Solvay: the decision framing

This is your signature and the thing most teams will lack entirely.

- **Frame risk the way the JRC does**: `Risk = Hazard × Exposure × Vulnerability`.
  It is also close to credit risk framing, so it should feel familiar.
- **Think in cost–benefit**: the cost of a measure (dyke, retention basin,
  warning system) against the damage avoided. The term of art is *Expected Annual
  Damage* — the damage of each scenario weighted by its annual probability
  (`1 / return period`). A 100-year flood has a 1% chance per year.
- **Build a prioritisation matrix**: impact × urgency × feasibility, and for each
  recommendation an **owner**, a **deadline** and an **order of magnitude of
  cost**. A recommendation without an owner and a date is a wish.
- **Bring the insurance angle**: the *protection gap*, the share of losses that
  are uninsured. It is a live European file (EIOPA), it is a genuine lever for a
  public authority, and almost no student team will raise it. Your banking
  background is a real edge here — use it.
- **Map the stakeholders**: Commission, national crisis centre, regions,
  communes, insurers, citizens. Each recommendation must name which of them acts.

## Hat 2 — Data scientist: the exposure analysis

- Geospatial pipeline: `geopandas`, `rasterio`, `rasterstats`, aggregated per
  commune (LAU) or NUTS region.
- **Composite vulnerability index**: exposed population, critical
  infrastructure, density, age, income. Then — and this is the part that earns
  credit — a **sensitivity analysis** on the weights. A jury of scientists
  rewards honesty about uncertainty far more than a confident single number.
- **Compare scenarios** across return periods (RP10 / RP100 / RP500), because the
  policy answer differs: RP10 is an operational problem, RP500 is a land-use
  planning problem.

## Hat 3 — GenAI engineer: the responsible accelerator

- **Reuse your grounded-rag "cite or refuse" engine** over the policy corpus
  (Floods Directive, flood risk management plans, JRC reports). Every claim in
  the brief then carries a source, and the refusal behaviour is itself the
  demonstration of responsible AI. This is your strongest card.
- **Natural-language access to the exposure table** (your Text-to-SQL experience)
  so the non-technical members can interrogate the data without waiting for you.
  This is what makes you an accelerator for the team rather than a bottleneck.
- **Keep an AI usage log**: tool, task, what a human verified. It *is* the
  responsible-AI deliverable, written as you go instead of invented at 17:00.

## Splitting a 5-person team

| Role | Who | Owns |
|---|---|---|
| Integrator / PO | you | the decision question, the numbers freeze, the final story |
| Geo-analyst | DS / engineering profile | hazard × exposure, the maps |
| Policy lead | public policy / political science | the brief, the stakeholder map |
| Comms | journalism / communication | the pitch, the visual language |
| Floater | whoever is left | the responsible-AI section, fact-checking |

**Two rules that save the deliverable:**

1. **Freeze the numbers at 17:30 on Thursday.** Everything written afterwards
   quotes the frozen table. Teams lose because a figure changes at 16:00 on
   Friday and the brief, the map and the pitch stop agreeing.
2. **One person owns the brief's final text.** Collective writing under time
   pressure produces mush.
