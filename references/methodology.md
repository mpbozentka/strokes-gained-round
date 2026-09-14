# Methodology and benchmark limits

## Formula

For a shot that begins at state `(distance, lie)` and ends at the next state:

`SG = E(start) - strokes charged - E(end)`

`strokes charged` is the played stroke plus any associated penalty strokes. For the final or grouped hole-out segment, `E(end) = 0`. This is Mark Broadie's published formula `J(start) - J(end) - 1`, generalized to grouped strokes and penalties.

The sum telescopes. For a completed hole with `n` actual strokes, including penalties:

`hole SG = E(initial tee state) - n`

This identity is the required reconciliation check.

## Benchmark

The off-green anchors in `pga-tour-baselines.csv` reproduce Table 9 of Mark Broadie's *Assessing Golfer Performance on the PGA TOUR*. The paper estimates average strokes to hole out by distance and condition from more than eight million ShotLink shots recorded from 2003 through 2010. It defines the conditions as green, tee, fairway, rough, sand, and recovery.

Primary source: Mark Broadie, [*Assessing Golfer Performance on the PGA TOUR*](https://columbia.edu/~mnb2/broadie/Assets/strokes_gained_pga_broadie_20110408.pdf), especially equation 1, section 3, and Appendix Table 9.

The green anchors are the conventional expected-putts values published from the same Broadie/ShotLink benchmark curve. The paper explains the fitted putting model and reports important checks: 50% one-putt probability at eight feet, average two putts at 33 feet, and the curve shown in Figure 4. The individual anchor values through 90 feet are commonly reproduced from Broadie's published table; the current PGA TOUR does not expose a complete, downloadable, current expected-strokes table publicly.

## Interpolation and coverage

- Use exact anchors when available.
- Use linear interpolation between adjacent anchors of the same lie.
- Do not round until display.
- Off-green distances are yards. Green distances are feet.
- Published Table 9 anchors cover 10–600 yards. Broadie's author Q&A adds approximate five-yard values for rough (2.15) and sand (2.37); these are labeled separately in the data.
- Distances outside the published range are valued rather than refused, because refusing one shot would break the telescoping identity for its whole hole. Every such value carries a flag and sets `estimated: true` on the segment.

### Short off-green shots

The one-yard row — fairway 2.02, rough 2.10, recovery 2.30 — is an estimated extension of the published table, labeled as such in the CSV. It exists because the fairway and rough curves are steepest inside ten yards, and clamping there would credit a golfer with expected strokes they never had: a three-yard chip clamped to the ten-yard fairway value of 2.18 gains roughly 0.13 strokes that were not played, in the same direction every time, and lands entirely in around-the-green. The anchors are reasoned from the shot itself — from a yard off the green a TOUR player leaves roughly three feet and holes out, net of occasional chip-ins — not observed in ShotLink. Treat them as an interpolation aid, not as data.

Sand is clamped to its five-yard anchor instead. A two-yard bunker shot is not materially easier than a ten-yard one, so the flat assumption is closer to the truth than an invented downward slope.

### Tee shots under 100 yards

Valued on the fairway curve at the same distance. The published tee table starts at 100 yards and is non-monotonic at its short end — it rises from 2.92 at 100 yards to 2.99 at 120 — because the tee sample mixes drivers with wedges. Clamping to 2.92 would therefore be worse than the fairway value, and a ball teed up plays at least as well as the same distance from the fairway.

### Long shots

Putts beyond 90 feet and off-green shots beyond 600 yards are clamped to the longest anchor. The putting curve gains about 0.006 strokes per foot at that end, so a 110-foot putt is understated by roughly 0.06 strokes. The error is immaterial and the alternative is extrapolating a curve past every observation supporting it.

Interpolation produces estimates between published points; it does not create newly observed TOUR averages. Course, weather, slope, lie quality, stance, green speed, and shot difficulty beyond distance and broad lie are not directly modeled.

## Fringe, collar and apron

The benchmark has six conditions and fringe is not one of them. Fringe, collar and apron are valued on the fairway curve at the same distance, converted at three feet per yard, and flagged `surface_alias`.

Fairway rather than green is the conservative choice: expected strokes from just off the putting surface are worse than from the same distance on it, so the green curve would credit the golfer for a surface they were not on. Broadie's Table 6.6 counts the fringe within "greens hit", which argues the other way; that is a green-in-regulation counting convention, not an expected-strokes claim, and it is not evidence about strokes to hole out.

The conversion is performed by the calculator, not by whoever prepares the input. Three independent runs of the same round were observed to produce category totals spanning 4.6 strokes around the green purely because fringe was resolved differently each time. A fixed rule in code removes that variance; a fixed rule in prose does not.

Most fringe shots land inside ten yards, where the fairway curve relies on the estimated short-game extension above. Those segments are flagged on both counts.

## Stated advances

`advance_stated` records a distance the golfer says a shot travelled, alongside the distances to the hole. The calculator compares it against the implied advance and reports a conflict beyond five yards.

The stated distances win, because the next narrated position is what defines the previous shot's ending state. The conflict is reported rather than resolved because either number could be the wrong one, and if the remaining distance is wrong then so is that shot's strokes gained.

## Reported nine and round totals

`reported_front_nine`, `reported_back_nine` and `reported_total` are checked against the sum of hole scores. The per-hole `reported_score` check cannot catch a golfer whose every hole is narrated correctly but whose nine total is not; that error otherwise passes straight through a fully reconciled ledger.

A mismatch is a round-level finding in `round_errors`. Nothing is excluded and no total is adjusted: the extra or missing stroke cannot be assigned to a hole without knowing which one.

## Input and attribution details

- A narrated next position supplies the previous shot's ending state.
- Every hole must be explicitly marked complete. A final narrated position is not automatically evidence that the next shot was holed.
- A full-hole ledger must begin on the tee. A partial sequence can be described separately, but it does not reconcile to full-hole strokes gained.
- When available, `reported_score` is checked against the sum of played and penalty strokes. A mismatch means the narration is incomplete or was parsed incorrectly. That hole is rejected into `hole_errors` and excluded from the totals; the rest of the round still calculates, so every bad hole surfaces in one run.
- A grouped “two-putt from 15 feet” is calculated exactly as a putting segment: `E(15 feet, green) - 2`. The first and second putt cannot be separated without the leave distance.
- Multiple grouped strokes beginning off the green retain a valid combined SG total, but their category and club attribution are reported as `unallocated_grouped` because intermediate positions may cross categories or use different clubs.
- A penalty must include the position from which play resumed. For a drive followed by one penalty stroke and a drop, charge two strokes to that transition: one played stroke plus one penalty.
- For out of bounds or a lost ball, the next state is the stroke-and-distance re-hit position. Do not count a provisional when the original ball is found and the provisional is abandoned.
- Recovery means the route to the hole was materially obstructed, not merely that the ball was in ordinary rough.
- Category labels are attribution rules, separate from the expected-strokes formula.

## Amateur putting benchmark

`green_scratch` and `green_90golfer` reproduce the "average number of putts" panel of Table 3.10 in Mark Broadie's *Every Shot Counts* (p. 55), covering 2 to 60 feet. That table's TOUR column matches all fifteen overlapping values already in this file, which is the check that the transcription and the existing curve agree.

These are the only published amateur expected-strokes values available for this skill. There is no published amateur equivalent of Table 9 for off-green shots, so no amateur baseline exists for off the tee, approach, or around the green, and no amateur round total can be produced. Table 8.2 (p. 179) gives amateur strokes-to-hole-out at 30 and 80 yards from fairway and rough, and Tables 9.12-9.15 (pp. 201-203) give median leave by distance, lie, and golfer group; together those are enough to *construct* amateur off-green curves with a shot-outcome model, validated against Table 8.2. That would be a model, not published data, and is not implemented here.

Distances beyond 60 feet clamp, as with the TOUR curve. A putt of one foot or less is 1.00 for every benchmark.

## Interpretation

This skill compares a golfer with a historical PGA TOUR benchmark. It is not a handicap-adjusted comparison and is not identical to current PGA TOUR field-adjusted statistics. A single round identifies where strokes were gained or lost in that round; it does not establish a persistent strength or weakness.

Broadie's five-yard answer and penalty treatment: [Every Shot Counts author Q&A](https://everyshotcounts.com/248-2/).
