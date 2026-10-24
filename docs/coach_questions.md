# What to ask the coaches

Several coaches, several backgrounds, a few minutes each. A coach's time is
the scarcest input of the two days, so every question here is one whose
answer **changes what we write**. Questions are grouped by the coach who can
answer them; ask the first one in each group first.

## How to use a coach

- **Arrive with a claim, not a topic.** "We found that Belgium declares 99.9 %
  of its territory and Spain 0.004 % — is that a known artefact or news to
  you?" gets a real answer. "What do you think of flood risk?" gets a lecture.
- **Ask what would make them disagree.** The best answer is the objection the
  jury will raise on Friday, heard on Thursday.
- **Write the answer down at once**, in the team's notes, with the coach's
  name and role. A coach's remark that changes a figure or a claim goes into
  `docs/ai_usage_log.md` too if it overrode something an AI produced.
- **Never ask a coach to debug.** Use the time on the question and the claims.
- **End with:** "Who else here should we ask about this?"

## Every coach, whatever the background

1. Here is our decision question in one sentence: *[read it]*. Who would
   actually make that decision, and would they recognise it as theirs?
2. Which of our three recommendations would you cut first, and why?
3. What would a jury member from your field ask that we have not prepared for?

## The JRC hazard and data scientist

*Most likely on Friday morning ("mentoring from JRC experts"). The person who
knows the data better than anyone else in the building.*

1. **The JRC Floods page says about 160,000 people in the EU+UK are exposed
   to river flooding each year; we count 25.7 million inside the RP100
   footprint.** Ours is undefended (the maps model no dykes, per Dottori et
   al. 2022) and not weighted by probability; theirs is both. Is that the
   whole difference, and **which figure would you lead with in a brief** —
   and is our residual figure (behind the PESETA IV protection standards)
   the bridge between the two?
2. We read the river-flood hazard maps at nine return periods and sum
   population per NUTS3. **Is RP100 the period you would quote to a
   policymaker**, or would you lead with expected annual exposure?
3. Some regions have fewer people exposed at RP500 than at RP100, because each
   period is a separate model run. **How do you phrase that** for a
   non-specialist without undermining the map?
4. The maps cover river floods in basins above about 150 km², not surface
   runoff. **For the July 2021 Vesdre flood, how much of the damage does that
   leave out**, in your experience?
5. We compare the model with the Member States' declared risk areas (APSFR).
   **Is the 23,000-fold spread in declared territory a known reporting
   artefact** at the JRC, or new?
6. Is there a **newer version of the hazard maps or of the Risk Data Hub
   figures** than the one we used, that we should cite instead?
7. Which JRC or Copernicus dataset **would you have used** for this question
   that we did not?

## The policy and EU-law coach

1. Ireland is in no cycle of the published APSFR layer, and Lithuania only in
   the 2010 one. **Is that a known gap, and is there a reason** (a separate
   submission, a different service) we are missing?
2. **Has Article 8(5) of the Floods Directive ever been used** — a Member State
   reporting an issue it cannot resolve alone, with the Commission answering
   within six months? If not, why not?
3. Is the **Working Group on Floods** the right body for recommendation 1, and
   is 2026 still early enough to reach the 22 December 2027 plan review?
4. Flood competence in Belgium is regional. **For a Meuse recommendation, who
   speaks for Belgium** — the federal level, the Walloon Region, or the
   International Meuse Commission?
5. What is the **most politically sensitive sentence** in our brief, and how
   would you soften it without losing the finding?

## The environmental-science or climate coach

1. We report the change in reference discharge as **medians and quartiles of
   eight simulations**, never the mean or maximum. Is that how you would
   present it, and is "the simulations agree on the sign" a fair confidence
   statement?
2. **Which is the stronger planning signal for 2041-2070**: a +20 % median
   change in discharge, or the 87 regions already highly exposed and still
   rising?
3. What does **"Natura 2000 on flood-prone ground"** mean to an ecologist —
   a risk, or the floodplain doing its job? How should we word it?

## The data-science or GIS coach

1. Our unit is NUTS3, and the cross-border figure counts a region as shared
   when any part of it lies in a cross-border basin. **Would you threshold
   that** (a share of the region's area), and where?
2. We weight a vulnerability index (age, income, exposure) and run a
   sensitivity check on the weights. **Is a one-at-a-time sensitivity enough**
   for a jury, or would you expect something else?
3. Is there a **map design convention** at the JRC or EEA we should follow
   (classes, colours, projection on screen)?

## The responsible-AI coach (FARI)

1. We log every AI use with what a human checked, and we list **four things
   the AI was not allowed to decide**. Is that what you mean by human
   oversight, or is something missing?
2. Our assistant **refuses to answer** when the policy corpus does not support
   a claim. Would you show that refusal in the pitch?
3. Under the AI Act, how would you **classify a flood-risk decision-support
   tool** used by a public authority — and is it wise to say so in the brief?

## The communication or policy-brief coach

1. *[Show the title and the three key messages.]* **After 30 seconds, what
   would a reader remember?** Is that what we want them to remember?
2. **Which single number** should open the pitch?
3. Is our figure readable **printed in greyscale**?
4. Is a **frank finding** — Member States' declarations cannot be compared,
   two are missing — an asset or a risk in front of this jury, and how do we
   say it so it is heard as help?

## The economics or insurance angle (if a coach has it)

1. Is the **insurance protection gap** a lever a public authority can actually
   pull for flood, or is it a market question?
2. For a shared basin, **would you frame upstream retention as an externality**
   — and is there an EU instrument that pays an upstream state for a
   downstream benefit?

## After each conversation

| Coach (name, role) | Question | Answer | What we change |
|---|---|---|---|
| | | | |
