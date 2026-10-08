# Why a workflow and not an agent

Applying the BXL-Gebru-1 GenAI course (`04-Workflows`, `03-AI_agents`) to this
deliverable. This page is also your answer when the jury asks "what stopped the
model from writing the brief itself?".

## The distinction, and why it decides the design

An **agent** chooses its own next step. A **workflow** follows a path the author
fixed in advance.

For a document a public authority might act on, the path has to be inspectable
*before* it runs and explainable *after*. An agent that can decide to skip
verification because it judged the draft good enough is exactly the autonomy this
deliverable should not have.

So `src/workflow.py` is a fixed graph:

```
retrieve ──► draft ──► verify ──┬──► approve ──► END
               ▲                │
               └────────────────┘   (bounded redraft)
```

One LLM call per node. No tool loop. The graph cannot take an action nobody
designed, and that sentence is worth more to a jury than any capability claim.

## Trigger → Process → Action

The course's mental model, mapped onto the brief pipeline:

| Stage | Here |
|---|---|
| **Trigger** | A frozen exposure table plus a question |
| **Process** | retrieve → draft → verify |
| **Action** | Write a brief section — **but only past a human approval gate** |

The action is the only step with a consequence outside the system, and it is the
one behind the gate. That is the whole design in one line.

## The four guards, and what each prevents

| Guard | Value | Prevents |
|---|---|---|
| `RECURSION_LIMIT` | 8 | A confused graph cycling until the API budget is gone |
| `MAX_REDRAFTS` | 2 | A model that cannot ground its draft looping on the same failure |
| `MIN_GROUNDING` | 0.7 | A plausible but unsupported paragraph reaching the brief |
| `interrupt()` | — | Anything at all reaching the brief without a human reading it |

The redraft limit matters more than it looks: past the limit the **flagged** draft
still goes to the human. A person reading a draft marked "weakly grounded" is a
better outcome than a workflow that never finishes.

## Human-in-the-loop: which pattern, and why

The course lists four HITL patterns. This pipeline uses two, deliberately:

- **Approval gate** — the graph pauses at `approve` until a person resumes it.
  This is HLEG requirement 1 (human agency and oversight) made executable instead
  of asserted.
- **Confidence threshold** — below `MIN_GROUNDING`, redraft rather than pass.
  Automate when the result is strong; escalate when it is not.

One detail worth defending out loud: when the human edits rather than approves,
the edit is used **as-is**. It is not fed back to the model to rewrite, because
that would hand the last word back to the machine.

## Idempotency, in `src/fetch.py`

The course's framing: "add £50" versus "make sure the balance is £50". Running
`fetch_all()` twice must not download twice.

So `_fetch_one` checks for a non-empty file on disk first and returns its hash
without touching the network. A hackathon connection drops often enough that you
*will* run collection several times, and a half-finished run should only cost you
the files that are actually missing.

**Idempotency is only as good as what counts as "already fetched".** Five entries
in `sources.yaml` used to point at the *directory* holding their files, and a
directory listing is valid HTML comfortably above the minimum document size — so
`_fetch_one` stored the listing as the data, and the disk check then declared the
source permanently done. A silent success, repeated on every later run, with no
data in it. `expand()` is the fix: an entry's `files:` list becomes one job per
file, ids become `<entry id>/<file stem>`, and the count `fetch_all` prints is
the number of jobs (49 for `geodata`, of which 37 are files to download at
≈3.78 GiB and 12 are runtime API calls; 64 jobs and 52 files at ≈3.82 GiB across
all three sections, derived from `sources.yaml` on 7 October 2026) rather than of
declared entries, of which there are 42. Entries with no `files:` key pass through untouched, so every
single-file source keeps its previous on-disk path.

## Verification is not an LLM call

`_verify` checks citations and lexical grounding offline, in Python. Asking a
model to grade its own output is not a check — it is a second opinion from the
same source, and it costs money and latency to be told what you want to hear.

This is the same cite-or-refuse machinery as the `grounded-rag` project, which
means it is already tested and you can explain it from memory.

## What to say in the pitch

> The pipeline is a fixed graph, not an agent. It retrieves, drafts, verifies,
> and then stops: nothing reaches the brief until one of us has read it and
> approved it. Verification is offline Python, not a second model grading the
> first. And the model never saw a number we had not already frozen.

## Running it

```bash
.venv/bin/pip install langgraph langchain-core
```

```python
from src.workflow import run
from src.toon_io import to_toon

state = run("Which communes should be prioritised for a warning system?",
            to_toon(frozen_exposure_table, "exposure"))
print(state["__interrupt__"])     # the draft awaiting your decision
```

Resume with `Command(resume="approve")`, or with your edited text.
