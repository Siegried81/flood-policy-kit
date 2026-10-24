# Day of — 29 and 30 October 2026

The programme below is the organisers' (FARI practical-information PDF and the
e-mail of 12 October 2026); the right-hand column is what to do inside it.

## Access — no ID, no entry

- **Thursday 29:** FARI, Kantersteen 10-12, 1000 Brussels (BeCentral campus).
  Ring the doorbell. Registration 08:15-09:00, breakfast served; latecomers
  may not be let in. Day 1 is **mandatory** to take part in Day 2.
- **Friday 30:** JRC, Rue du Champ de Mars 21, 1050 Ixelles. Registration
  08:00-09:00 per the PDF, 08:15 per the e-mail: be there at 08:00.
- **V-PASS:** the Commission's visitor registration. The link arrives by e-mail
  a few days before (check spam); register at once. The QR code it returns is
  the entry ticket, on the phone or printed - bring both.
- **The same ID document** as the one given to V-PASS, on Friday.
- **A second e-mail**, a couple of days before, carries the dataset access and
  the **AI licences**. Read it the evening it arrives: the datasets it names
  may not be the ones this kit downloaded, and that is better found at home.

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

## Thursday 29 — FARI (08:15-19:00)

Teams are formed on the day, with students from other backgrounds. This kit is
something you bring, not something the team has agreed to: show it once the
scenario is known, as an offer, and let the question lead.

| Time | Programme | The thing that actually matters |
|---|---|---|
| 09:00-12:30 | Welcome (FARI & JRC), introduction to the flood datasets, **scenario briefing**, session "How to write an impactful policy brief" | Listen for the decision-maker and the scale in the scenario. **Write the decision-maker's question in one sentence** before lunch; everything is judged against it. |
| 13:30-18:00 | Data exploration and analysis, mentoring (technical & policy), drafting visual outputs and the brief | Get to one real number early. Then add the **equity lens** (who, not how many) and one **sensitivity check** - these separate the top three teams. Use the mentors on the question, not on debugging. |
| 17:30 | **Freeze the numbers** | Everything written after this quotes the frozen table. No exceptions. |
| 18:00-19:00 | Drinks at FARI | |
| Evening | Draft the brief's bottom line | Writing it tonight reveals whether the analysis supports a recommendation, while there is still a morning to fix it. |

## Friday 30 — JRC (08:00-18:00)

| Time | Programme | The thing that actually matters |
|---|---|---|
| 09:00-13:30 | Final analysis and synthesis, mentoring from JRC experts, finalising visual outputs and the brief | Map and brief in parallel, two owners. They check each other's numbers against the frozen table once, at 12:00. **Freeze the brief at 13:30.** |
| 14:00-17:00 | **Final submission:** the 2-page policy brief, the visual outputs, the AI usage summary; then the jury | Submit first, rehearse after: two timed run-throughs, out loud, standing. The AI usage summary is `docs/ai_usage_log.md`, kept as you go. |
| After | Award ceremony, drinks at the JRC | |

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
