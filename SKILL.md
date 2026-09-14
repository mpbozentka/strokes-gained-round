---
name: strokes-gained-round
description: Calculate PGA TOUR-benchmark strokes gained from a golfer's naturally narrated hole or full round, using each shot's starting distance, lie, club, penalties, and next position. Use for shot-by-shot scoring, category or club summaries, and identifying missing shot details; not for live PGA TOUR tournament statistics.
---

# Strokes Gained Round

Turn a golfer's narration into a reconciled shot ledger and calculate strokes gained against the bundled PGA TOUR benchmark.

**Required supporting files.** This skill does not work from SKILL.md alone. The skill directory must also contain `scripts/calculate_strokes_gained.py`, `references/pga-tour-baselines.csv`, and `references/methodology.md`. If the script is not present, say so and stop — do not calculate by hand as a substitute.

## Never supply a fact the golfer did not

This is the rule the whole skill rests on. Do not estimate an unsupported distance, infer a lie, or fill a gap with a plausible number so the calculator will run. A fabricated input produces a confident, wrong, unfalsifiable answer — the exact failure this skill exists to prevent, and it is invisible in the output once made.

When a required fact is missing there are two legal moves and no third: **group** the strokes across the unknown position (see Grouping), or **ask**. Every assumption that survives into the report must appear in the report.

### When to ask

Ask because an answer would change a number, not because something felt unclear. Uncertainty is abundant in narration; questions the golfer will actually answer are scarce. Spend them where the arithmetic says they matter.

**Ask before calculating — at most two or three questions — only when the unknown is a start state, where grouping has nothing to group across:**

- a lie that is genuinely unknown, where the golfer named a shot type but no surface;
- a distance whose unit is ambiguous and where feet and yards are both plausible;
- whether the hole was completed at all.

These produce a wrong number rather than a flagged one. If the golfer does not answer, reject that hole rather than guessing; the per-hole rejection path is built for it.

**Everything else waits until after the run.** Encode conservatively, group across the unknown positions, calculate, then report the ranked list in `open_questions`. The calculator orders those by the strokes each answer would reallocate, so the list is the same on every run and on every model. Present the top few, not all of them — a grouped segment worth 0.07 strokes is not worth a question — and offer to recalculate.

Running first means the golfer gets a complete, honest answer whether or not they ever reply.

**Never ask about something the arithmetic can settle.** See Distances.

## Capture the round

Each narrated position is the **start of a shot or grouped segment**. Preserve, per hole:

- hole number and par when known;
- distance to the hole and unit;
- starting lie;
- club as spoken by the golfer;
- penalty strokes attached to the preceding played shot;
- number of strokes when the golfer groups a completed segment, such as "two-putted from 15 feet";
- explicit confirmation that the hole was completed, plus the golfer's reported score when known.

Also capture any nine or round total the golfer states, as `reported_front_nine`, `reported_back_nine` and `reported_total`. A golfer's own summary frequently disagrees with their hole-by-hole narration, and nothing else in the pipeline can catch that.

The club is attribution metadata; it never changes the benchmark value.

Do not silently finish a hole. "I hit it to 15 feet" describes a new starting position, not a made putt. Mark `completed: true` only when the golfer says the ball was holed, gives a final putting count, or provides enough narration to establish completion.

## Lies and surfaces

The benchmark defines six conditions: `tee`, `fairway`, `rough`, `sand`, `recovery`, `green`.

- Bunker maps to `sand`. Trouble, trees, or a materially obstructed route maps to `recovery` — ordinary rough is not recovery.
- **Fringe, collar and apron are written as `fringe` (or `collar`, `apron`) and left alone.** The calculator maps them to the fairway curve, converts feet to yards, and flags the segment. Do not convert or reclassify them yourself: hand-conversion is where two runs of the same round stop agreeing.
- `green` means the ball was on the putting surface. A putt struck from the fringe is not a putting stroke; it is a fringe stroke played with a putter.
- A shot type — chip, pitch, punch, putt — never establishes a lie. Ask what surface the ball was on when it matters.

## Distances

- **A bare number after a shot is distance travelled. "Leaving", "left", "to the pin", "to the hole", "out" following a remaining-distance phrase mark distance remaining.** "Hit driver 240 yards" and "leaving 240 yards" are opposite facts.
- When a number could be either, **resolve it by arithmetic, not by asking**: compute the hole both ways and keep the reading under which the remaining distances reconcile. "Smoked driver, 240 yards out" on a 502-yard hole, followed by a topped shot that advanced 110 and left 152, resolves cleanly — 502 minus 240 is 262, and 262 minus 110 is exactly 152, while reading 240 as remaining misses by 22. Ask only when neither reading reconciles.
- When the golfer states both an advance and a remaining distance, record the advance as `advance_stated` on the shot that was played. The calculator checks it against the stated distances and reports a conflict. The stated distances win; the conflict is surfaced, never resolved silently.
- Normalize `foot`/`feet`/`ft` to feet and `yard`/`yards`/`yd`/`yds` to yards. Convert at three feet per yard only between units the golfer explicitly gave. Do not guess distances stated as steps or paces.

## Penalties

- Attach the penalty to the shot or decision that caused it; the next state is the position from which play resumed.
- Out of bounds or a lost ball under stroke and distance: one penalty on the played shot, and the next state is the re-hit position. A provisional abandoned because the original was found does not count.
- **When the golfer does not say where they dropped, group the penalty stroke with the following shot** rather than inventing a drop position. Charge the played strokes plus the penalty to that one segment.

## Grouping

Grouping is how the skill stays honest about missing facts. It is not a convenience, and it is not free: a grouped non-green segment keeps a valid combined SG total but loses all category and club attribution.

- **Group only across positions the golfer did not state. Never group across one they did.** "Rolled back down the bank to my feet" is a stated end position; collapsing it hides that a full stroke bought nothing.
- Keep groups as small as the missing facts require. Do not sweep an adjacent known shot into a group to tidy the ledger.
- Never group a penalty stroke together with unrelated shots when the penalty's cost is the thing worth seeing.
- Putting groups remain putting, because every stroke in them begins on the green.
- The round summary reports `unallocated_share_of_loss`. **Above roughly 20%, the category split is not a safe basis for a conclusion** — say so, name the specific missing fact behind each grouped segment, and offer to recalculate once the golfer supplies them.

## Other ambiguities

- Count whiffs and every other attempted stroke. Ignore mulligans and practice balls only when they were not the scored ball in play.
- `reported_score` means gross strokes actually counted, including penalties — not net, Stableford, or "net par".
- A pickup or unfinished hole cannot produce full-hole SG. A conceded putt was not attempted; do not present its estimated result as measured putting. Team scrambles do not produce an individual's SG.
- A full-hole calculation must begin from the tee and end holed. Never present a partial sequence as that hole's strokes gained.

## Build calculator input

```json
{
  "reported_front_nine": 48,
  "reported_back_nine": 47,
  "reported_total": 95,
  "holes": [
    {
      "hole": 1,
      "par": 4,
      "completed": true,
      "reported_score": 5,
      "shots": [
        {"distance": 450, "unit": "yards", "lie": "tee", "club": "driver", "advance_stated": 293},
        {"distance": 157, "unit": "yards", "lie": "rough", "club": "pitching wedge"},
        {"distance": 30, "unit": "feet", "lie": "fringe", "club": "putter"},
        {"distance": 15, "unit": "feet", "lie": "green", "club": "putter", "strokes": 2}
      ]
    }
  ]
}
```

`strokes` defaults to 1, `penalties` to 0. The next array item is the previous shot's ending position; the last item ends in the hole. `advance_stated` and the three reported totals are optional.

Distances must be positive finite numbers. Hole number, par, strokes, penalties and reported scores must be whole numbers; par 3-5; hole numbers unique within 1-18.

## Run the calculator

```bash
python3 scripts/calculate_strokes_gained.py round.json --pretty
```

Resolve the script relative to this skill directory. **Never compute strokes gained by hand or by reading values off the table.** Hand-computed ledgers do not satisfy the reconciliation identity and have been observed to drift by several strokes across a round while looking entirely plausible. The script is the only source of a number in the report.

Read `references/methodology.md` when auditing the math, explaining limitations, or modifying the benchmarks. The script loads `references/pga-tour-baselines.csv`.

## Validate before reporting

The calculator enforces, per hole:

`sum(shot SG) = expected strokes from the initial tee position - actual strokes including penalties`

**Print the reconciliation figure for every hole in the report.** It is the one number a fabricated ledger cannot reproduce, and showing it is what makes the result checkable.

Report at minimum:

1. a shot ledger with start, club, end, strokes charged, and SG;
2. totals for off the tee, approach, around the green, putting, and the round;
3. score by hole, penalty strokes, and any `round_errors` — a reported nine or total that disagrees with the holes is a finding, not a footnote;
4. `unallocated_share_of_loss`, plus the highest-ranked entries from `open_questions` — each names the missing fact and the strokes it would reallocate. Lead with the largest; drop anything trivial;
5. every assumption, `advance_conflicts`, estimated or clamped benchmark values with their category counts, and rejected holes.

Use two decimal places for display; sum unrounded values. Positive is better than the benchmark. Call this the **published 2003-2010 PGA TOUR benchmark**, not a current field-adjusted TOUR result. Do not convert a one-round result into a durable player diagnosis.

Note for interpretation: a round total is structurally immune to mid-hole parsing disputes — it reduces to expected strokes from each tee minus the score. Disagreements over lies and intermediate positions move the category split only.

## Category rules

- `putting`: every segment starting on the putting green.
- `off_the_tee`: tee shots on par 4s and par 5s.
- `around_the_green`: non-green shots starting 30 yards or closer.
- `approach`: all remaining shots, including par-3 tee shots and recovery shots beyond 30 yards.

If par is missing, label a tee shot `off_the_tee_assumed` and disclose the assumption.

## Outside the published range

The benchmark does not cover every distance. Such shots are not refused; they are valued on the nearest defensible basis, flagged `estimated: true`, and reported as estimates — never as published TOUR averages.

- Off-green shots inside the shortest published anchor use an estimated 1-yard extension of the fairway, rough and recovery curves. Sand clamps to its 5-yard anchor instead, because short bunker shots are not materially easier than 10-yard ones.
- Tee shots under 100 yards use the fairway curve at the same distance; the tee curve is non-monotonic at its short end.
- Putts beyond 90 feet and shots beyond 600 yards clamp to the longest anchor, where both curves are nearly flat.

A segment inherits the flag from its start or its end state. The round summary reports `estimated_segments` per category; surface that count whenever a category total leans on it.

## When a hole is rejected

Holes calculate independently. A hole that cannot be trusted — no tee start, not marked complete, a reported score that disagrees with the ledger, a failed reconciliation — lands in `hole_errors` and is excluded from every total while the rest still calculate. Exit 0 means all holes calculated, 1 some rejected, 2 none.

Fix every rejected hole in one pass. Never present a partial round as a full one: `round.holes_calculated` and `round.holes_rejected` say what the totals cover.

## Putting against an amateur benchmark

The output carries a supplementary `putting_vs` block scoring putting against a scratch golfer and a 90-golfer. Putting is the only category with a published amateur curve, and it is self-contained: every putting segment starts and ends on the green.

Report these as a separate line, never folded into the round total or summed with TOUR-based figures. A segment that putts off the green is excluded and counted in `segments_skipped`. For a student the 90-golfer figure is usually the one worth saying out loud; the TOUR figure is context.
