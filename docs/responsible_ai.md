# The responsible-AI deliverable

One of the four scored outputs is a reflection on the responsible use of AI in
your workflow. Most teams will write three vague sentences about bias at 17:00 on
Friday. This is the cheapest place to stand out, because it can be prepared in
advance and filled in as you work.

## Use the jury's own framework

FARI co-organises the event, and its manifesto commits explicitly to the **HLEG
Ethics Guidelines for Trustworthy AI** — seven key requirements. Structuring the
section as that grid means the jury recognises its own vocabulary.

The seven requirements (verify the exact wording against the source before the
event — see `config/sources.yaml`):

1. Human agency and oversight
2. Technical robustness and safety
3. Privacy and data governance
4. Transparency
5. Diversity, non-discrimination and fairness
6. Environmental and societal well-being
7. Accountability

## What to write under each, concretely

| Requirement | What you can actually claim, if you do the work |
|---|---|
| Human agency and oversight | Every figure in the brief was traced to its source dataset by a named person. The AI proposed; the team decided the thresholds, the weights and the ranking. |
| Technical robustness | The pipeline has tests; the retrieval layer **refuses** rather than guessing when no source supports an answer. |
| Privacy and data governance | Only aggregated, open data. Population grids, not individuals. No personal data entered any prompt. Each input's licence is recorded and respected — see below. |
| Transparency | Public repo, AI usage log in annex, and `sources.yaml` carrying a URL and a stated purpose for all 42 declared inputs — with a **verification date on 34 of the 42** and an explicit `licence:` on **11** (re-derived 2026-10-07; the counts are of declared entries, not of the files they expand to) — which is where redistribution is a live question. Five `access: download` entries still carry no `licence:` (`gisco_nuts3`, `gisco_lau`, `statbel_income`, `cems_emsr517_germany_2021`, `cems_emsr518_belgium_2021`), so the honest claim is the narrower one. Claim the coverage you have: "every input is traceable to a URL and a stated purpose, and four fifths carry a verification date" survives a jury opening the file. "Licence for every input", and "a licence on every dataset we redistribute", do not. |
| Diversity and fairness | The equity lens: exposure broken down by age and income, not only a total. Plus: who is *missing* from the data (undocumented residents, people in temporary housing). |
| Environmental and societal well-being | The token budget you measured (`toon_io.token_report`), and the choice of a small model where a large one was not needed. |
| Accountability | Named owner per deliverable; the limits section states what the work cannot claim. |

## Data governance is also licence hygiene

The cheap version of this requirement is "we used open data". The version a JRC
jury can check is: which licence, and what it forbids.

- **The Walloon trap.** The *aléa d'inondation* records are CC-BY 4.0 and
  redistributable. The neighbouring "Zones inondables – période de retour"
  records are CPU Type A SPW: the data may **not** be passed to a third party,
  and printing is capped at 1:10,000. A published map built on them is fine; a
  public repository containing them is not. This repository goes public, so it
  uses the CC-BY records — and reproduces the SPW attribution string verbatim,
  because CC-BY is a condition, not a courtesy.
- **Credentialed sources are not open data.** The Risk Data Hub needs an EU Login
  token, so what the repo ships is the derived figure and the query, never a
  bulk copy of the Hub's rows. Its values are also averages across DFO, EM-DAT
  and HANZE, which makes attributing them correctly part of transparency rather
  than a footnote.
- **A missing number must stay missing.** `src/rdh.py` raises rather than
  returning an empty list when it has no token: "we did not look" and "we looked
  and found nothing" are different statements, and collapsing them is how an
  absence of data becomes a claim of absence in a brief.

## Tracing: let the tool keep the log

LangGraph traces every node automatically once `LANGSMITH_TRACING=true` and
`LANGSMITH_API_KEY` are set — no code to write. Each LLM call then has its
prompt, its output, its latency and its token count recorded and inspectable
afterwards.

That is HLEG requirement 7 (accountability) as evidence rather than a claim, and
it is the hand-written AI usage log produced automatically instead of
reconstructed at 17:00 on Friday. `src.workflow.tracing_status()` reports whether
it is actually on, including the half-configured case — tracing asked for with no
key records nothing and warns about nothing.

**State the cost in the brief, not in a footnote.** Traces are sent to
LangChain's servers, so prompts and model outputs leave the machine. That is
acceptable here because the corpus is public EU documents and the exposure table
is open data. It would not be acceptable on anything you would not publish, and
saying so out loud is itself the responsible-AI point: you knew what left, and
why it was allowed to.

Keep the hand-written log as well. The trace records what the machine did; the
log records **what a human checked and what they rejected**, which is the part no
tool can produce.

## The AI usage log

Keep this as you go, in `docs/ai_usage_log.md`. It is the annex, and writing it
live costs nothing while reconstructing it at the end is both painful and
dishonest.

| Time | Tool / model | Task | What a human checked | Outcome |
|---|---|---|---|---|
| Thu 11:20 | [model] | Draft the zonal-stats function | Ran it against a hand-computed 3×3 raster | Accepted after 1 fix |
| Thu 15:40 | [model] | Summarise Art. 7 of the Floods Directive | Read the article; the citation was correct | Accepted |
| Fri 10:05 | [model] | Propose recommendation wording | Rejected: it invented a cost figure | Rewritten by hand |

**Include at least one rejection.** A log with no rejection reads as a log nobody
actually kept. The rejection is the evidence of oversight.

## Say what AI must not decide

FARI's manifesto is explicitly anti-hype: it warns against investing in models
that cannot serve the common good. The strongest line in the pitch is a limit,
not a capability.

In this work, AI should **not** decide:

- **Who gets protected first.** The ranking of communes is a political choice
  about which lives and livelihoods come first. The analysis informs it; it does
  not make it.
- **The vulnerability weights.** They encode a value judgement about whose
  exposure counts more. They must be explicit, documented, and tested for
  sensitivity.
- **The depth threshold** at which a cell counts as flooded. It changes the
  headline number and must be a stated, defended choice.
- **Anything a resident would experience directly** — an evacuation order, an
  alert — without a human in the loop.

## One caution on the AI Act

It is tempting to assert that a flood-risk tool is "high-risk under Annex III".
Check the actual text before claiming it: the annex is specific, and a jury that
includes JRC lawyers will know it better than you. Say what you verified and
nothing more. `docs/policy_context.md` carries the researched position.

A safer and still strong framing: the system is a **decision-support tool for a
public authority**, so regardless of its formal classification the team applied
the transparency and human-oversight expectations that the AI Act and the HLEG
guidelines set out.
