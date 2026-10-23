# Day of — 29 and 30 October 2026

The detailed programme comes from the organisers; this is the shape to hold
regardless of what the timetable says.

## Before you leave home

- [ ] Rasters and policy corpus **already downloaded** onto the laptop — all 38
      downloadable geodata files, ≈5.52 GiB (the `geodata` section's 52 jobs
      include 14 runtime API calls that store nothing), or 65 files and ≈5.56 GiB
      counting the policy corpus and context sections (measured on disk 23 October 2026;
      re-derive, the config still grows). Check the count, not the folder:
      `/vsicurl/` is no fallback at European scale (35,525 tiles for the EU27+EFTA
      bbox).
- [ ] The Risk Data Hub cache filled **the day before**
      (`data/processed/rdh_cache/`):
      `.venv\Scripts\python.exe -c "from src import rdh; rdh.flood_losses(country='BE')"`.
      A cached query is read before any token is asked for, so the cache alone
      carries the demo. A **fresh bearer token** in `.env` is needed only for a
      query the cache does not hold — it expires after 10 hours, so yesterday's
      is dead. No token then means `RdhUnavailable`, not a silent zero.
- [ ] The kit runs **offline**: `.venv\Scripts\python.exe -m pytest -q` green
      with the Wi-Fi off, *and*
      `.venv\Scripts\python.exe scripts\check_offline_readiness.py --strict`
      exits 0 (the ambient `python` has neither pytest nor rasterio) — `--strict`,
      because without it an `ANTHROPIC_API_KEY` or `GROQ_API_KEY` still in `.env` is only a caveat and
      the verdict still reads "runs offline". The two answer
      different questions — the suite mocks the network away, which is exactly
      what hides a missing 300 MB raster, so only the script can tell you whether
      the files, the Risk Data Hub cache and the local model are actually on this
      laptop. It reports byte counts rather than a reassurance, and names any
      `.part` leftover, which is how you tell an interrupted download from one
      that never started.
- [ ] The local model pulled and served: `ollama pull llama3.2:3b`, then
      `ollama serve` (or the tray app). Not optional — the readiness check FAILs
      while Ollama is unreachable, because it is what answers when the venue
      blocks an API or a rate limit hits mid-demo. `OLLAMA_MODEL` picks another
      model.
- [ ] Laptop charger, a power strip (hackathon venues never have enough
      sockets), and a phone hotspot.
- [ ] The repo is public and the URL fits on a slide.

## Thursday 29 — FARI

| Time | What | The thing that actually matters |
|---|---|---|
| 09:00–10:30 | Team forms, roles split | **Write the decision-maker's question on the whiteboard in one sentence.** Everything is judged against it. Do not start coding before it is written. |
| 10:30–13:00 | Data | Get to one real number early, even a rough one. A team with a number at noon is calm; a team with a pipeline at noon is not. |
| 14:00–17:00 | Analysis | Add the **equity lens** (who, not how many) and one **sensitivity check**. These two are what separate the top three teams. |
| 17:30 | **Freeze the numbers** | Everything written after this quotes the frozen table. No exceptions. |
| Evening | Draft the brief's bottom line | Writing it tonight reveals whether the analysis actually supports a recommendation, while there is still a morning to fix it. |

## Friday 30 — JRC

| Time | What | The thing that actually matters |
|---|---|---|
| Morning | Map and brief, in parallel | Two owners, one each. They check each other's numbers against the frozen table once, at 12:00. |
| 13:30 | **Freeze the brief** | |
| 14:00–15:00 | Two full rehearsals | Timed, out loud, standing. The first one always runs long. |
| Afternoon | Jury | |

## The pitch — 3 minutes

1. **A human hook** (15 s). July 2021, one concrete image. Not a definition of
   flood risk.
2. **The number** (20 s). One figure, with its scope. Say it slowly and stop
   talking for a beat.
3. **The map** (40 s). Point at one thing on it. Do not narrate the legend.
4. **The three recommendations** (60 s). Who acts, by when. This is the part
   they are scoring.
5. **How AI was used, and checked** (30 s). Name one thing the AI was *not*
   allowed to decide. This lands better than any capability claim.
6. **Stop.** Leave silence for questions rather than filling the time.

## Questions to have an answer ready for

- *"Why does Loire-Atlantique have fewer people exposed at RP500 than at
  RP100?"* → Because each JRC return period is a separate model run, not a
  bigger copy of the smaller one: the maps are nested in intent, not cell by
  cell. Four regions dip; EU totals still rise with the period. It is in
  [`limitations.md`](limitations.md), and it is why no figure is ever summed
  across periods.

- *"Why these weights in your vulnerability index?"* → Because [reason], and here
  is how the ranking changes if we move them: [sensitivity result]. The honest
  answer with a number beats a confident answer without one.
- *"Your hazard map disagrees with the official Walloon one."* → Yes, by X%, and
  that is itself a finding: the JRC maps model river flooding only, not surface
  runoff. (Know this before they ask it.) The Walloon *aléa* layer lets you put a
  number on it: it is one dataset with a class code, and `CLASSEMENT` 2xx and 3xx
  are precisely the runoff and the mixed cases the JRC maps cannot contain.
- *"Where do your loss figures come from?"* → The JRC Risk Data Hub, filtered to
  one `admin_unit_level` — its rows are nested, so an unfiltered sum counts the
  same event four times (114 casualties for July 2021 instead of 29.67) — and
  quoted as its averaged estimate across DFO, EM-DAT and HANZE, not as an
  official toll.
- *"Did the AI write this?"* → Here is the usage log, and here is what it was not
  allowed to decide.
- *"What would you do with another week?"* → One specific thing, not a list.

## The two failure modes to actively avoid

- **A beautiful map with no recommendation.** The deliverable is a decision, not
  a visualisation.
- **A recommendation the numbers do not support.** This is why the freeze at
  17:30 exists, and why the brief's bottom line gets drafted on Thursday night.
