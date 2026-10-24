# Your five hats, and a team plan that works whoever turns up

## Why you are the integrator

The teams are formed on the day, with students from other backgrounds: AI, data
science, engineering, environmental science, urban studies, political science,
public policy, communication, journalism, linguistics. The organisers say
plainly that *no single profile is expected to do everything*.

That design creates one predictable failure: the technical half and the policy
half work in parallel for a day and a half, then discover at 16:00 on Friday that
the numbers do not support the recommendations. Someone has to hold the two
together from hour one.

You are a **Solvay commercial engineer** (economics, strategy) who then became
**business analyst, data analyst and AI engineer** — five hats, with strategy
and economics from Solvay. That is not five skills to show off; it is one role:
**integrator / product owner**. Claim it by doing, not by announcing a title: after the scenario
briefing, you are the one who writes **the decision-maker's question** on the
whiteboard in a single sentence, and keeps pointing at it.

## Hat 0 — Strategist (Solvay): who is in the room, and what they can do with it

Every other hat answers *what is true*. This one answers *who hears it, and
what they can do on Monday*. Know the room:

| Who | What they are | What they want to hear | What not to do |
|---|---|---|---|
| **JRC** (Disaster Risk Management Knowledge Centre; the hazard maps, the Risk Data Hub, EFAS) | The Commission's science service — and the **author of the data you use** | That their data answered a policy question they had not seen asked; uncertainty stated in their own terms; the Science4Policy vocabulary (`policy_craft.md` §2.1) | Criticise the JRC hazard maps as wrong. State their documented limits (river floods only, basins > 150 km²) as limits, and they become allies |
| **FARI** (AI for the Common Good Institute, VUB-ULB, Brussels) | The co-organiser; AI for public good; **offers the internship** | Responsible AI shown in practice: the usage log, what the AI was *not* allowed to decide, refusals | An AI capability show. "The model wrote the brief" loses here |
| **The addressees in the brief** — DG ENV, the EEA, river basin commissions | Not in the room, but the jury reads as them | A recommendation slotted into an existing instrument and cycle (Floods Directive Art. 5, 8(5), 14; the 22 Dec 2027 review) | "Europe should": name the body, the article, the date |
| **The coaches** | Several backgrounds, there to help | Precise questions — see `docs/coach_questions.md` | Asking them to debug. Use them on the question and the claims |

**Three strategic moves:**

1. **The critique points at the reporting layer, never at the JRC.** The
   brief's findings are about the comparability of the Member States'
   *declarations* (an EEA-served layer), with the JRC's model as the yardstick.
   That puts the JRC on your side of the argument.
2. **Turn the prize into a conversation.** The first prize is a FARI internship
   and a trip to Ispra: talk to the FARI and JRC people at the two drinks
   (Thursday 18:00 at FARI, Friday after the awards at the JRC) about the
   *work*, not the prize. Bring the repo URL on your phone.
3. **Pre-empt the hardest question.** For each of the three recommendations,
   know who would say no and why (cost, competence, sovereignty), and have one
   sentence ready. A recommendation that has survived its own objection reads
   as advice, not as a wish.

## Hat 1 — Economist (Solvay): what it costs and what it saves

The thing most teams will lack entirely, and what turns a map into a decision.

- **Frame risk the way the JRC does**: `Risk = Hazard × Exposure × Vulnerability`.
  It is close to credit risk framing (probability × exposure × loss given
  default), so it should feel familiar.
- **Think in cost–benefit**: the cost of a measure (dyke, retention basin,
  warning system) against the damage avoided. The term of art is *Expected Annual
  Damage* — the damage of each scenario weighted by its annual probability
  (`1 / return period`). A 100-year flood has a 1% chance per year;
  `expected_annual_exposure` in the kit is the same integral on people.
- **The insurance angle**: the *protection gap*, the share of losses that are
  uninsured. A live European file (EIOPA dashboard), a genuine lever for a
  public authority, and almost no student team will raise it.
- **Externalities**: a basin shared between countries is a textbook one —
  upstream retention benefits the downstream state. That is the economics behind
  recommendation 3 of `docs/brief_draft.md`, and 57 % of the EU's exposed
  population sits in such basins.
- **Equity**: who bears the risk, not only how many — the poverty and over-65
  columns are there for this.

## Hat 2 — Business analyst: the question, the actors, the priorities

- **The decision question**, in one sentence, with a named decision-maker and a
  date. Everything is scored against it.
- **The stakeholder map**: Commission (DG ENV), EEA, JRC, Member States,
  regions (flood competence is regional in Belgium), river basin commissions,
  communes, insurers, citizens. Each recommendation names which one acts.
- **The prioritisation matrix**: impact × urgency × feasibility, and for each
  recommendation an **owner**, a **deadline** and an **order of magnitude of
  cost**. A recommendation without an owner and a date is a wish.
- **Scope control**: you say "not in this brief" so the team finishes.

## Hat 3 — Data analyst: the numbers and their honesty

- The frozen tables answer most questions in seconds; the Streamlit app puts
  them in front of the team without code.
- **Scenarios across return periods** (RP10 / RP100 / RP500), because the
  policy answer differs: RP10 is an operational problem, RP500 a land-use
  planning problem.
- **One sensitivity check** on the vulnerability weights. A jury of scientists
  rewards honesty about uncertainty far more than a confident single number.
- **The freeze**: you own the table every figure is quoted from.

## Hat 4 — AI engineer: the responsible accelerator

- **The "cite or refuse" RAG** over the policy corpus (Floods Directive, plans,
  JRC reports): every claim in the brief carries a source, and the refusal
  behaviour is itself the demonstration of responsible AI.
- **"Ask the table"** in natural language, so the non-technical members query
  the data without waiting for you. You are an accelerator, not a bottleneck.
- **The AI usage log** (`docs/ai_usage_log.md`) — tool, task, what a human
  verified. It is one of the three submitted items, written as you go.

## The team plan — roles by profile, not by name

You will not know who is in your team until Thursday morning. So the plan is a
set of role cards: hand each card to whoever fits it best, and merge cards when
the team is small.

| Role card | Best fit | Owns, on paper | First task, Thursday 13:30 |
|---|---|---|---|
| **Integrator / PO** | you | the decision question, the freeze, the final story, the AI usage summary, the coach questions | Question on the whiteboard; walk the team through the app in 10 minutes |
| **Hazard & climate scientist** | environmental science, geography, hydrology, engineering | that the physics is right: what a return period means, what the hazard maps leave out (surface runoff, basins < 150 km²), climate trends read as medians | Read the scenario against `docs/limitations.md`; list what the maps cannot say for this question |
| **Policy lead** | public policy, political science, law, EU studies | the brief's final text, the addressees, the legal hooks (Floods Directive Art. 5, 8(5), 14) | Rewrite the brief's key messages for the scenario's decision-maker, starting from `docs/brief_draft.md` |
| **Geo / data analyst** | **you by default**; a second technical profile if the team has one | the map and the figures, checked against the frozen table | Produce the one map of the brief, and the one number |

**Why the Geo/data card is yours by default, and when to hand it over.** The
map and the key number are already built: the app draws the choropleth, and
the frozen table holds every figure. For you this card is an hour of work,
not a day. Keep **the number** in any case — it comes from the table you
freeze. Hand **the map** over only if a second technical profile is there and
idle: give them the app's map to adapt to the scenario, and keep your time for
the question, the coaches and the 16:00 check that the numbers support the
recommendations. The one risk is becoming the bottleneck: if three people are
waiting on you, give the map away.
| **Storyteller** | communication, journalism, linguistics, design | the pitch, the visual language, plain English in the brief | Find the human hook (July 2021, one place, one image); draft the 3-minute pitch |

**Merging the cards when the team is small:**

- **3 people:** you take Integrator + Geo/data; the scientist adds Storyteller;
  the policy profile keeps Policy lead.
- **4 people:** you take Integrator + Geo/data; if someone else codes, hand
  them the map, keep the number and the AI and economics work.
- **6 or more:** split Policy lead into *brief writer* and *fact-checker*
  (every figure and every article cited, against the source), and give the
  fact-checker the AI usage log too.

**If nobody has the profile of a card**, it falls to you, in this order of
importance: Policy lead's legal check (with the RAG), then the Hazard card's
limits list (`docs/limitations.md` already holds it), then the Storyteller's
hook. The map is not on this list because it is never a gap: it already
exists in the Streamlit and React apps (and in Power BI), so at worst the
team uses it as it is.

## How the cards meet

| When | Who meets | About what |
|---|---|---|
| Thu 12:30, lunch | everyone | the scenario, the decision question, who holds which card |
| Thu 16:00 | Integrator + Policy lead + Scientist | do the numbers support the recommendations? |
| Thu 17:30 | everyone | **freeze the numbers** |
| Fri 12:00 | Geo/data + Policy lead | every figure in the brief checked against the frozen table |
| Fri 13:30 | everyone | **freeze the brief**; submit, then rehearse |

**Two rules that save the deliverable:**

1. **Freeze the numbers at 17:30 on Thursday.** Everything written afterwards
   quotes the frozen table. Teams lose because a figure changes at 16:00 on
   Friday and the brief, the map and the pitch stop agreeing.
2. **One person owns the brief's final text** — the Policy lead. Collective
   writing under time pressure produces mush.

**One rule about the kit:** it is yours, not the team's. Offer it after the
scenario briefing as a shortcut to the data, and let the team's question lead.
A team that feels it was handed a finished answer stops contributing, and the
jury sees it in the Q&A.
