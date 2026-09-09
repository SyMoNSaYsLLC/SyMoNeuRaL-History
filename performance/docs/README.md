# docs/

Architecture, decisions and benchmark reports.

Belongs here:

- `PERFORMANCE-ROADMAP.md` — the phase order and the reason for it
- architecture of the lab and of the eventual adapter layer
- decision records: what was chosen, on what evidence, and what the runner-up
  did better
- written benchmark reports drawing on tracked summaries in `results/`

**Record what the runner-up did better.** A decision record that only argues for
the winner is advocacy, and it makes the choice hard to revisit when the next
measurement disagrees. The roadmap's P7 exists so P6 stays revisitable; these
documents are what make revisiting it cheap.

**Do not write a predicted winner into this directory.** A prediction recorded
before the measurement becomes the thing the measurement gets compared against,
and disagreeing results then look like mistakes. `engines/CANDIDATES.md` holds
every candidate at the same status for the same reason.
