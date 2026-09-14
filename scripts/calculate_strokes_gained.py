#!/usr/bin/env python3
"""Calculate shot-by-shot strokes gained from normalized round JSON."""

from __future__ import annotations

import argparse
import csv
import json
import math
import sys
from bisect import bisect_left
from collections import defaultdict
from pathlib import Path


VALID_LIES = ("tee", "fairway", "rough", "sand", "recovery", "green")

# Surfaces the golfer names that are not benchmark conditions. The benchmark has
# no fringe curve; fringe and collar are closely mown, so they are valued on the
# fairway curve and always flagged. Distances given in feet are converted here so
# the conversion cannot vary between runs.
SURFACE_ALIASES = {"fringe": "fairway", "collar": "fairway", "apron": "fairway"}

FEET_PER_YARD = 3.0

# Tolerance, in yards, before a stated advance is treated as contradicting the
# stated remaining distances.
ADVANCE_TOLERANCE = 5.0

# Alternate putting curves. Putting is the one category whose expected-strokes
# values are self-contained -- every segment starts and ends on the green -- so
# it can be scored against a non-TOUR benchmark without touching the rest.
PUTTING_BENCHMARKS = {
    "scratch": ("green_scratch", "scratch golfer (Every Shot Counts Table 3.10, p.55)"),
    "90golfer": ("green_90golfer", "90-golfer (Every Shot Counts Table 3.10, p.55)"),
}

# Lies whose curve is flat enough below its lowest anchor that clamping is
# preferable to extending the table. Short bunker shots are not materially
# easier than 10-yard bunker shots.
CLAMP_SHORT_LIES = ("sand",)

# Flags that mean the expected-strokes value was not read from, or interpolated
# between, two published anchors.
ESTIMATE_FLAGS = frozenset({"clamped_short", "clamped_long", "tee_fallback", "extended_anchor"})


def whole_number(value: object, name: str, minimum: int, maximum: int | None = None) -> int:
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not float(value).is_integer()
    ):
        raise ValueError(f"{name} must be a whole number")
    result = int(value)
    if result < minimum or (maximum is not None and result > maximum):
        range_text = f"{minimum}-{maximum}" if maximum is not None else f"at least {minimum}"
        raise ValueError(f"{name} must be {range_text}")
    return result


def load_baselines(path: Path) -> dict[str, list[tuple[float, float, str]]]:
    curves: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for lie in VALID_LIES:
                if row[lie]:
                    curves[lie].append(
                        (float(row["distance"]), float(row[lie]), row["source"])
                    )
    for points in curves.values():
        points.sort()
    return dict(curves)


def load_putting_benchmarks(path: Path) -> dict[str, list[tuple[float, float, str]]]:
    """Load the alternate green curves keyed by benchmark name."""
    alt: dict[str, list[tuple[float, float, str]]] = defaultdict(list)
    with path.open(newline="", encoding="utf-8") as handle:
        for row in csv.DictReader(handle):
            for name, (column, _) in PUTTING_BENCHMARKS.items():
                if row.get(column):
                    alt[name].append((float(row["distance"]), float(row[column]), row["source"]))
    for points in alt.values():
        points.sort()
    return dict(alt)


def putting_comparison(
    normalized_shots: list[dict],
    curves: dict[str, list[tuple[float, float, str]]],
    putting_curves: dict[str, list[tuple[float, float, str]]],
) -> dict[str, dict]:
    """Strokes gained putting against each alternate benchmark.

    Reported separately and never folded into the round total: a total may only
    mix segments measured against one benchmark.
    """
    out: dict[str, dict] = {}
    for name, points in putting_curves.items():
        swapped = dict(curves)
        swapped["green"] = points
        total = 0.0
        counted = 0
        skipped = 0
        for index, shot in enumerate(normalized_shots):
            if shot["lie"] != "green":
                continue
            last = index + 1 >= len(normalized_shots)
            if not last and normalized_shots[index + 1]["lie"] != "green":
                skipped += 1  # putted off the green; would mix benchmarks
                continue
            start_e, _, _ = expected_strokes(shot["lie"], shot["distance"], shot["unit"], swapped)
            if last:
                end_e = 0.0
            else:
                nxt = normalized_shots[index + 1]
                end_e, _, _ = expected_strokes(nxt["lie"], nxt["distance"], nxt["unit"], swapped)
            charged = int(shot.get("strokes", 1)) + int(shot.get("penalties", 0))
            total += start_e - charged - end_e
            counted += 1
        out[name] = {
            "label": PUTTING_BENCHMARKS[name][1],
            "strokes_gained_putting": total,
            "segments": counted,
            "segments_skipped": skipped,
        }
    return out


def _source_flags(source: str) -> set[str]:
    lowered = source.lower()
    flags: set[str] = set()
    if "approximate" in lowered:
        flags.add("approximate_anchor")
    if "estimated" in lowered:
        flags.add("extended_anchor")
    return flags


def expected_strokes(
    lie: str,
    distance: float,
    unit: str,
    curves: dict[str, list[tuple[float, float, str]]],
) -> tuple[float, list[str], set[str]]:
    """Return (expected strokes, warnings, flags) for a start or end state.

    Distances outside the published range are clamped or valued on a fallback
    curve rather than raising, so that one unsupported shot cannot abort a
    whole round. Every such value is flagged so it can be disclosed.
    """
    if lie not in VALID_LIES:
        raise ValueError(f"unsupported lie {lie!r}; use one of {VALID_LIES}")
    if distance < 0:
        raise ValueError("distance cannot be negative")
    required_unit = "feet" if lie == "green" else "yards"
    if unit != required_unit:
        raise ValueError(f"{lie} distance must be in {required_unit}, not {unit}")
    if lie == "green" and distance <= 1:
        return 1.0, [], set()

    warnings: list[str] = []
    flags: set[str] = set()
    curve_lie = lie
    points = curves[lie]

    # A tee shot shorter than the published tee table plays like a shot from
    # the fairway at the same distance; the tee curve is also non-monotonic at
    # its short end because of the driver/wedge mix, so clamping it is worse.
    if lie == "tee" and distance < points[0][0]:
        curve_lie = "fairway"
        points = curves["fairway"]
        warnings.append(
            f"tee shot at {distance:g} {unit} is below the published tee table "
            f"(starts at {curves['tee'][0][0]:g} {unit}); valued on the fairway curve"
        )
        flags.add("tee_fallback")

    lowest, highest = points[0][0], points[-1][0]
    lookup = distance

    if distance < lowest:
        lookup = lowest
        reason = (
            "curve is flat at this end" if curve_lie in CLAMP_SHORT_LIES else "no shorter anchor available"
        )
        warnings.append(
            f"{curve_lie} distance {distance:g} {unit} is shorter than the lowest anchor "
            f"({lowest:g} {unit}); clamped to that anchor ({reason})"
        )
        flags.add("clamped_short")
    elif distance > highest:
        lookup = highest
        warnings.append(
            f"{curve_lie} distance {distance:g} {unit} is longer than the highest anchor "
            f"({highest:g} {unit}); clamped to that anchor"
        )
        flags.add("clamped_long")

    index = bisect_left([point[0] for point in points], lookup)
    if index < len(points) and points[index][0] == lookup:
        value = points[index][1]
        flags |= _source_flags(points[index][2])
    else:
        left_d, left_e, left_source = points[index - 1]
        right_d, right_e, right_source = points[index]
        fraction = (lookup - left_d) / (right_d - left_d)
        value = left_e + fraction * (right_e - left_e)
        warnings.append("linear interpolation between benchmark anchors")
        flags.add("interpolated")
        flags |= _source_flags(left_source) | _source_flags(right_source)

    if "approximate_anchor" in flags:
        warnings.append("value uses an approximate author-supplied anchor")
    if "extended_anchor" in flags:
        warnings.append(
            "value uses an estimated short-game extension of the published table, not a published TOUR average"
        )
    return value, warnings, flags


def normalize_shot(shot: dict) -> dict:
    if not isinstance(shot, dict):
        raise ValueError("each shot must be an object")
    normalized = dict(shot)
    lie = str(shot["lie"]).strip().lower()
    unit = str(shot["unit"]).strip().lower()
    if isinstance(shot["distance"], bool):
        raise ValueError("distance must be a positive number")
    distance = float(shot["distance"])
    if not math.isfinite(distance) or distance <= 0:
        raise ValueError("distance must be a positive finite number")

    flags: set[str] = set()
    warnings: list[str] = []
    if lie in SURFACE_ALIASES:
        target = SURFACE_ALIASES[lie]
        if unit == "feet":
            distance /= FEET_PER_YARD
            unit = "yards"
        warnings.append(
            f"{lie} is not a benchmark condition; valued on the {target} curve "
            f"at {distance:.1f} yards"
        )
        flags.add("surface_alias")
        normalized["_source_lie"] = lie
        lie = target

    advance = shot.get("advance_stated")
    if advance is not None:
        if isinstance(advance, bool) or not isinstance(advance, (int, float)) or not math.isfinite(float(advance)):
            raise ValueError("advance_stated must be a number")
        normalized["advance_stated"] = float(advance)

    normalized["lie"] = lie
    normalized["unit"] = unit
    normalized["distance"] = distance
    normalized["_flags"] = flags
    normalized["_warnings"] = warnings
    return normalized


def category_for(shot: dict, par: int | None) -> str:
    if shot["lie"] == "green":
        return "putting"
    if shot["lie"] == "tee":
        if par in (4, 5):
            return "off_the_tee"
        if par == 3:
            return "approach"
        return "off_the_tee_assumed"
    if shot["distance"] <= 30:
        return "around_the_green"
    return "approach"


def state_label(shot: dict) -> str:
    base = f'{float(shot["distance"]):.4g} {shot["unit"]} {shot["lie"]}'
    source = shot.get("_source_lie")
    return f"{base} (from {source})" if source else base


def calculate_hole(
    hole: dict,
    curves: dict[str, list[tuple[float, float, str]]],
    seen_holes: set[int],
    putting_curves: dict[str, list[tuple[float, float, str]]] | None = None,
) -> dict:
    if not isinstance(hole, dict):
        raise ValueError("each hole must be an object")
    hole_number = hole.get("hole")
    if hole_number is not None:
        hole_number = whole_number(hole_number, "hole number", 1, 18)
        if hole_number in seen_holes:
            raise ValueError(f"duplicate hole number {hole_number}")
        seen_holes.add(hole_number)
    if hole.get("completed") is not True:
        raise ValueError(
            "hole must be explicitly marked completed=true; "
            "do not treat an unfinished narration as holed"
        )
    shots = hole.get("shots")
    if not isinstance(shots, list) or not shots:
        raise ValueError("hole has no shots")
    par = hole.get("par")
    if par is not None:
        par = whole_number(par, "par", 3, 5)
    reported_score = hole.get("reported_score")
    if reported_score is not None:
        reported_score = whole_number(reported_score, "reported score", 1)
    normalized_shots = [normalize_shot(shot) for shot in shots]
    if normalized_shots[0]["lie"] != "tee":
        raise ValueError(
            "hole must begin from the tee; partial-hole data cannot produce full-hole SG"
        )

    # A stated advance and the stated remaining distances must agree. When they
    # do not, one of the two numbers the golfer gave is wrong and the SG for that
    # shot is wrong with it, so it is surfaced rather than silently resolved.
    advance_conflicts: list[str] = []
    for index, shot in enumerate(normalized_shots):
        advance = shot.get("advance_stated")
        if advance is None or index + 1 >= len(normalized_shots):
            continue
        nxt = normalized_shots[index + 1]
        if shot["unit"] != "yards" or nxt["unit"] != "yards":
            continue
        implied = shot["distance"] - nxt["distance"]
        if abs(implied - advance) > ADVANCE_TOLERANCE:
            advance_conflicts.append(
                f"segment {index + 1}: stated advance of {advance:g} yards disagrees with the "
                f"stated distances ({shot['distance']:.4g} to {nxt['distance']:.4g} implies "
                f"{implied:.4g}); the distances were used"
            )

    ledger = []
    hole_categories: dict[str, float] = defaultdict(float)
    hole_estimated: dict[str, int] = defaultdict(int)
    hole_score = 0

    for index, shot in enumerate(normalized_shots):
        strokes = whole_number(shot.get("strokes", 1), "strokes", 1)
        penalties = whole_number(shot.get("penalties", 0), "penalties", 0)
        start_e, start_warnings, start_flags = expected_strokes(
            shot["lie"], shot["distance"], shot["unit"], curves
        )

        if index + 1 < len(normalized_shots):
            next_shot = normalized_shots[index + 1]
            end_e, end_warnings, end_flags = expected_strokes(
                next_shot["lie"], next_shot["distance"], next_shot["unit"], curves
            )
            end_label = state_label(next_shot)
        else:
            end_e, end_warnings, end_flags, end_label = 0.0, [], set(), "holed"

        charged = strokes + penalties
        sg = start_e - charged - end_e
        grouped_unallocated = strokes > 1 and shot["lie"] != "green"
        category = "unallocated_grouped" if grouped_unallocated else category_for(shot, par)
        reported_club = str(shot.get("club", "unspecified")).strip() or "unspecified"
        club = "grouped/unspecified" if grouped_unallocated else reported_club
        input_warnings = list(shot.get("_warnings", []))
        input_flags = set(shot.get("_flags", set()))
        if index + 1 < len(normalized_shots):
            input_warnings += list(normalized_shots[index + 1].get("_warnings", []))
            input_flags |= set(normalized_shots[index + 1].get("_flags", set()))
        warnings = sorted(set(start_warnings + end_warnings + input_warnings))
        flags = start_flags | end_flags | input_flags
        estimated = bool(flags & ESTIMATE_FLAGS)
        if grouped_unallocated:
            warnings.append(
                "multiple non-putting strokes were grouped; total SG is valid but category and club attribution are unallocated"
            )
        ledger.append(
            {
                "segment": index + 1,
                "start": state_label(shot),
                "club": club,
                "reported_club": reported_club,
                "end": end_label,
                "played_strokes": strokes,
                "penalties": penalties,
                "strokes_charged": charged,
                "category": category,
                "expected_start": start_e,
                "expected_end": end_e,
                "strokes_gained": sg,
                "estimated": estimated,
                "flags": sorted(flags),
                "warnings": warnings,
            }
        )
        hole_score += charged
        hole_categories[category] += sg
        if estimated:
            hole_estimated[category] += 1

    initial_e = ledger[0]["expected_start"]
    hole_sg = sum(row["strokes_gained"] for row in ledger)
    reconciled_sg = initial_e - hole_score
    if abs(hole_sg - reconciled_sg) > 1e-9:
        raise RuntimeError("failed reconciliation: shot SG does not sum to expected tee strokes minus score")
    if reported_score is not None and reported_score != hole_score:
        message = (
            f"reported score of {reported_score} does not match the ledger total of {hole_score}; "
            "the narration is incomplete or was parsed incorrectly"
        )
        # A one-stroke shortfall on a hole with a penalty is nearly always an
        # unnarrated stroke-and-distance re-hit: going back costs two strokes,
        # and golfers routinely describe only one of them.
        if reported_score - hole_score == 1 and any(row["penalties"] for row in ledger):
            message += (
                ". This hole has a penalty and is short by exactly one stroke, which usually means "
                "a stroke-and-distance re-hit was played but not narrated (going back costs two: "
                "the penalty plus the replayed shot). Ask whether they replayed from the previous "
                "spot or took relief near the penalty area"
            )
        raise ValueError(message)

    return {
        "hole": hole_number,
        "par": par,
        "advance_conflicts": advance_conflicts,
        "putting_vs": putting_comparison(normalized_shots, curves, putting_curves or {}),
        "score": hole_score,
        "strokes_gained": hole_sg,
        "reconciliation": reconciled_sg,
        "categories": dict(hole_categories),
        "estimated_segments": dict(hole_estimated),
        "ledger": ledger,
    }


def calculate(
    round_data: dict,
    curves: dict[str, list[tuple[float, float, str]]],
    putting_curves: dict[str, list[tuple[float, float, str]]] | None = None,
) -> dict:
    if not isinstance(round_data, dict):
        raise ValueError("input must be an object")
    if not isinstance(round_data.get("holes"), list) or not round_data["holes"]:
        raise ValueError("input must contain a non-empty 'holes' array")

    result: dict = {"benchmark": "PGA TOUR 2003-2010 (Broadie/ShotLink)", "holes": []}
    round_categories: dict[str, float] = defaultdict(float)
    round_clubs: dict[str, float] = defaultdict(float)
    round_estimated: dict[str, int] = defaultdict(int)
    all_warnings: set[str] = set()
    hole_errors: list[dict] = []
    seen_holes: set[int] = set()
    round_score = 0
    round_sg = 0.0

    # Every hole is evaluated independently so that one unusable hole reports
    # itself without discarding the other seventeen.
    for position, hole in enumerate(round_data["holes"], start=1):
        label = hole.get("hole") if isinstance(hole, dict) else None
        try:
            calculated = calculate_hole(hole, curves, seen_holes, putting_curves)
        except (KeyError, TypeError, ValueError, RuntimeError) as error:
            hole_errors.append(
                {
                    "hole": label,
                    "position": position,
                    "error": str(error) if not isinstance(error, KeyError) else f"missing field {error}",
                }
            )
            continue

        result["holes"].append(calculated)
        round_score += calculated["score"]
        round_sg += calculated["strokes_gained"]
        for category, value in calculated["categories"].items():
            round_categories[category] += value
        for category, count in calculated["estimated_segments"].items():
            round_estimated[category] += count
        for row in calculated["ledger"]:
            round_clubs[row["club"]] += row["strokes_gained"]
            all_warnings.update(row["warnings"])

    # Reported nine and round totals are checked against the ledger. A golfer's
    # summary can disagree with their own hole-by-hole narration, and that error
    # is invisible to the per-hole check.
    round_errors: list[str] = []
    calculated_numbers = {h["hole"] for h in result["holes"] if h["hole"] is not None}

    def _check(label: str, key: str, holes: range | None) -> None:
        stated = round_data.get(key)
        if stated is None:
            return
        try:
            stated_int = whole_number(stated, key, 1)
        except ValueError as error:
            round_errors.append(str(error))
            return
        if holes is None and hole_errors:
            round_errors.append(
                f"{label} of {stated_int} not checked: {len(hole_errors)} hole(s) were rejected, "
                "so the ledger total does not cover the whole round"
            )
            return
        wanted = set(holes) if holes is not None else calculated_numbers
        if holes is not None and not wanted.issubset(calculated_numbers):
            round_errors.append(
                f"{label} of {stated_int} not checked: not every hole in that nine was calculated"
            )
            return
        actual = sum(h["score"] for h in result["holes"] if h["hole"] in wanted)
        if actual != stated_int:
            round_errors.append(
                f"{label} reported as {stated_int} but the hole scores total {actual}; "
                "the summary disagrees with the hole-by-hole narration"
            )

    _check("front nine", "reported_front_nine", range(1, 10))
    _check("back nine", "reported_back_nine", range(10, 19))
    _check("round total", "reported_total", None)

    if not result["holes"]:
        result["status"] = "failed"
    elif hole_errors:
        result["status"] = "partial"
    else:
        result["status"] = "ok"

    putting_totals: dict[str, dict] = {}
    for calculated in result["holes"]:
        for name, block in calculated.get("putting_vs", {}).items():
            agg = putting_totals.setdefault(
                name,
                {"label": block["label"], "strokes_gained_putting": 0.0, "segments": 0, "segments_skipped": 0},
            )
            agg["strokes_gained_putting"] += block["strokes_gained_putting"]
            agg["segments"] += block["segments"]
            agg["segments_skipped"] += block["segments_skipped"]

    result["hole_errors"] = hole_errors
    result["round_errors"] = round_errors
    result["round"] = {
        "holes_calculated": len(result["holes"]),
        "holes_rejected": len(hole_errors),
        "score": round_score,
        "strokes_gained": round_sg,
        "categories": dict(round_categories),
        "estimated_segments": dict(round_estimated),
        "clubs": dict(round_clubs),
        "advance_conflicts": [
            f'hole {h["hole"]}: {c}' for h in result["holes"] for c in h.get("advance_conflicts", [])
        ],
        "warnings": sorted(all_warnings),
    }
    # Questions worth asking the golfer, ranked by the strokes each one would
    # reallocate. Derived from what the calculator measured rather than from a
    # reader's sense of unease, so the same round yields the same list every run.
    open_questions = []
    for calculated in result["holes"]:
        for row in calculated["ledger"]:
            if row["category"] != "unallocated_grouped":
                continue
            open_questions.append(
                {
                    "hole": calculated["hole"],
                    "segment": row["segment"],
                    "strokes_at_stake": abs(row["strokes_gained"]),
                    "strokes_charged": row["strokes_charged"],
                    "start": row["start"],
                    "end": row["end"],
                    "missing_fact": (
                        f'the position(s) between {row["start"]} and {row["end"]}'
                    ),
                    "question": (
                        f'Hole {calculated["hole"]}: {row["strokes_charged"]} strokes were played from '
                        f'{row["start"]} to {row["end"]} with no stated position in between. '
                        f'Where did the ball finish after each? '
                        f'({abs(row["strokes_gained"]):.2f} strokes would be reallocated.)'
                    ),
                }
            )
    open_questions.sort(key=lambda q: q["strokes_at_stake"], reverse=True)
    result["open_questions"] = open_questions

    # Share of the round's loss that carries no category. Above roughly a fifth,
    # the category split is not a safe basis for a conclusion.
    unallocated = round_categories.get("unallocated_grouped", 0.0)
    total_loss = sum(v for v in round_categories.values() if v < 0)
    result["round"]["unallocated_share_of_loss"] = (
        round(unallocated / total_loss, 4) if total_loss < 0 and unallocated < 0 else 0.0
    )
    result["putting_vs"] = putting_totals
    result["putting_vs_note"] = (
        "Supplementary comparison only. Putting is scored against these benchmarks because every "
        "putting segment starts and ends on the green; the other categories have no published "
        "amateur curve, so these figures must not be added to the round total."
    )
    return result


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="normalized round JSON")
    parser.add_argument("--pretty", action="store_true", help="pretty-print JSON output")
    args = parser.parse_args()
    baseline_path = Path(__file__).resolve().parent.parent / "references" / "pga-tour-baselines.csv"
    try:
        with args.input.open(encoding="utf-8") as handle:
            round_data = json.load(handle)
        output = calculate(
            round_data,
            load_baselines(baseline_path),
            load_putting_benchmarks(baseline_path),
        )
    except (OSError, KeyError, TypeError, ValueError, json.JSONDecodeError) as error:
        print(f"error: {error}", file=sys.stderr)
        return 2
    json.dump(output, sys.stdout, indent=2 if args.pretty else None)
    print()
    if output["status"] == "failed":
        print("error: no hole could be calculated; see hole_errors", file=sys.stderr)
        return 2
    if output.get("round_errors"):
        for message in output["round_errors"]:
            print(f"warning: {message}", file=sys.stderr)
    if output["status"] == "partial":
        print(
            f'warning: {len(output["hole_errors"])} hole(s) rejected; see hole_errors',
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
