# strokes-gained-round

A Claude skill that turns a golfer's spoken round narration into a reconciled shot ledger and calculates strokes gained against the published 2003–2010 PGA TOUR benchmark (Broadie / ShotLink).

You describe the round the way you'd describe it to a friend — "driver, 157 in the rough, wedge to the back bunker, splashed out to 10 feet, two-putted" — and it produces a shot-by-shot ledger, category totals (off the tee, approach, around the green, putting), club attribution, and a per-hole reconciliation figure you can check.

## What makes it different

Most strokes-gained tools quietly invent the facts you didn't give them. This one doesn't. When a required detail is missing it has exactly two legal moves: group the strokes across the unknown position, or ask you. Every assumption that survives into the report is printed in the report.

It also catches its own inputs being wrong. If your reported nine or round total disagrees with the hole-by-hole narration, that's a finding, not a footnote. Same for a stated shot distance that contradicts the stated remaining distances.

## Install

**Claude Code** (or any tool reading `~/.claude/skills/`):

```bash
git clone https://github.com/mpbozentka/strokes-gained-round.git ~/.claude/skills/strokes-gained-round
```

**Codex:** clone to `~/.codex/skills/strokes-gained-round` instead.

The skill is discovered on the next session — no restart needed in Claude Code.

## Verify the install

From inside the skill directory:

```bash
python3 scripts/calculate_strokes_gained.py examples/sample-round.json --pretty
```

Exit code 0, and the summary should report:

| | |
|---|---|
| score | 95 |
| strokes gained | −24.36 |
| holes calculated | 18 of 18 |
| round_errors | 2 |
| advance_conflicts | 1 |
| open_questions | 5 |

Those errors are intentional. The sample round contains a golfer's miscounted back nine and a contradictory distance — catching them is the point of the skill. Different numbers mean a file is missing or altered.

Exit codes: `0` all holes calculated, `1` some rejected, `2` none usable.

## Layout

These paths are referenced by `SKILL.md` and will break if moved.

```
SKILL.md                              the skill itself
scripts/calculate_strokes_gained.py   the calculator — no dependencies
references/pga-tour-baselines.csv     the benchmark table
references/methodology.md             the math, and its limits
examples/sample-round.json            the verification round
```

## Requirements

Python 3. Nothing else — no packages, no network, no API keys. Everything runs locally.

## Caveats worth knowing

- It's the **published 2003–2010 TOUR benchmark**, not a current field-adjusted TOUR result.
- One round is one round. Don't turn a single result into a durable diagnosis of a player.
- Putting also gets scored against a scratch golfer and a 90-golfer, reported separately. For a student, the 90-golfer number is usually the useful one.
- When too much of the round is grouped across unknown positions, the category split stops being a safe basis for a conclusion — the output says so, and names the missing facts.

See `references/methodology.md` for the full treatment.
