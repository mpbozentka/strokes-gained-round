# strokes-gained-round

A Claude skill that turns a golfer's spoken round narration into a reconciled shot ledger and calculates strokes gained against the published 2003–2010 PGA TOUR benchmark (Broadie / ShotLink).

You describe the round the way you'd describe it to a friend — "driver, 157 in the rough, wedge to the back bunker, splashed out to 10 feet, two-putted" — and it produces a shot-by-shot ledger, category totals (off the tee, approach, around the green, putting), club attribution, and a per-hole reconciliation figure you can check.

## What makes it different

Most strokes-gained tools quietly invent the facts you didn't give them. This one doesn't. When a required detail is missing it has exactly two legal moves: group the strokes across the unknown position, or ask you. Every assumption that survives into the report is printed in the report.

It also catches its own inputs being wrong. If your reported nine or round total disagrees with the hole-by-hole narration, that's a finding, not a footnote. Same for a stated shot distance that contradicts the stated remaining distances.

## Install

The same files work in Claude Code, Codex, and Cursor — all three read the `SKILL.md`
format. Only the folder differs.

| Tool | Clone into |
|---|---|
| Claude Code / Claude Desktop | `~/.claude/skills/strokes-gained-round` |
| Codex CLI | `~/.codex/skills/strokes-gained-round` |
| Cursor | `~/.cursor/skills/strokes-gained-round` |

```bash
# pick the line for your tool
git clone https://github.com/mpbozentka/strokes-gained-round.git ~/.claude/skills/strokes-gained-round
git clone https://github.com/mpbozentka/strokes-gained-round.git ~/.codex/skills/strokes-gained-round
git clone https://github.com/mpbozentka/strokes-gained-round.git ~/.cursor/skills/strokes-gained-round
```

If the `skills` folder doesn't exist yet, `git clone` creates it.

Claude Code picks the skill up on the next session. Codex and Cursor want a restart;
in Codex, `/skills` lists what loaded, and in Cursor the skill shows in the slash-command
menu. In Cursor you can also put it in a project instead of your home folder, at
`.cursor/skills/strokes-gained-round/`, which is the better choice if you want it
committed alongside a repo.

### Without git

Download the ZIP from the green **Code** button on the repo page, unzip it, and move the
folder into the table's path for your tool. GitHub names the unzipped folder
`strokes-gained-round-main` — rename it to `strokes-gained-round`, since the folder name
is the skill name.

Or from a terminal:

```bash
curl -L https://github.com/mpbozentka/strokes-gained-round/archive/refs/heads/main.tar.gz \
  | tar -xz && mv strokes-gained-round-main ~/.claude/skills/strokes-gained-round
```

Keep the inner folder structure exactly as it is — `SKILL.md` resolves `scripts/` and
`references/` by relative path and breaks if they move.

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

## Describe your round

Once the skill is installed, type or dictate this to your assistant:

> Use the strokes-gained-round skill to analyze my round. I’ll describe each hole, including the hole length, par, each shot’s starting distance and lie, penalties, and final score. Ask me for any essential missing details.

You can describe your round one hole at a time. Include the distance remaining to the hole and whether the ball was on the tee, fairway, rough, sand, green, or another surface before each shot. Say when you finish the hole and give your final score.

The skill calculates where you gained or lost strokes against the historical PGA TOUR benchmark. If details are missing, it groups strokes where possible or asks for clarification.

## Requirements

Python 3. Nothing else — no packages, no network, no API keys. Everything runs locally.

## Caveats worth knowing

- It's the **published 2003–2010 TOUR benchmark**, not a current field-adjusted TOUR result.
- One round is one round. Don't turn a single result into a durable diagnosis of a player.
- Putting also gets scored against a scratch golfer and a 90-golfer, reported separately. For a student, the 90-golfer number is usually the useful one.
- When too much of the round is grouped across unknown positions, the category split stops being a safe basis for a conclusion — the output says so, and names the missing facts.

See `references/methodology.md` for the full treatment.
