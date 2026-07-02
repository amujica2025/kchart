#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import math
import re
from collections import defaultdict
from pathlib import Path

from PIL import Image, PngImagePlugin

BASE = Path(r"C:\Users\alexm\Downloads\kbot\my-kalshi-app\csv data\match_price_history")

CSV_DIR = BASE / "csvprice data"
JSON_DIR = BASE / "json data"
NPY_DIR = BASE / "npy data"
PNG_DIR = BASE / "png charts"

MASTER_CSV = BASE / "master_player_manifest.csv"
MASTER_JSON = BASE / "master_player_index.json"


def clean_tag(value):
    return re.sub(r"[^a-z0-9]+", "_", str(value).lower()).strip("_")


def safe_float(value, default=0.0):
    try:
        x = float(value)
        if math.isnan(x):
            return default
        return x
    except Exception:
        return default


def price_bucket(price):
    p = int(round(safe_float(price)))
    p = max(0, min(100, p))
    lo = (p // 10) * 10
    hi = min(100, lo + 9)
    if p == 100:
        return "100"
    return f"{lo:02d}_{hi:02d}"


def count_sets(score):
    return len(re.findall(r"\d+\s*-\s*\d+", str(score or "")))


def parse_sets(score):
    return [(int(a), int(b)) for a, b in re.findall(r"(\d+)\s*-\s*(\d+)", str(score or ""))]


def has_tiebreak(score):
    return bool(re.search(r"\b7\s*-\s*6\b|\b6\s*-\s*7\b", str(score or "")))


def load_csv(csv_path):
    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = list(csv.DictReader(f))
    prices = [safe_float(r.get("player_price")) for r in rows]
    opp_prices = [safe_float(r.get("opponent_price")) for r in rows]
    return rows, prices, opp_prices


def volatility(prices):
    if len(prices) < 2:
        return 0.0
    return sum(abs(prices[i] - prices[i - 1]) for i in range(1, len(prices))) / (len(prices) - 1)


def max_step(prices):
    if len(prices) < 2:
        return 0.0
    return max(abs(prices[i] - prices[i - 1]) for i in range(1, len(prices)))


def count_crossings(prices, level):
    c = 0
    for i in range(1, len(prices)):
        a = prices[i - 1]
        b = prices[i]
        if (a < level <= b) or (a > level >= b):
            c += 1
    return c


def first_cross_pct(prices, level):
    if len(prices) < 2:
        return ""
    for i, p in enumerate(prices):
        if p >= level:
            return round(i / (len(prices) - 1) * 100, 2)
    return ""


def count_direction_flips(prices, min_move=1.0):
    dirs = []
    for i in range(1, len(prices)):
        d = prices[i] - prices[i - 1]
        if abs(d) >= min_move:
            dirs.append(1 if d > 0 else -1)
    return sum(1 for i in range(1, len(dirs)) if dirs[i] != dirs[i - 1])


def shape_tags(prices):
    tags = []
    if len(prices) < 4:
        return ["shape_unknown"]

    start = prices[0]
    end = prices[-1]
    high = max(prices)
    low = min(prices)
    rng = high - low
    flips = count_direction_flips(prices)
    vol = volatility(prices)

    if rng <= 5:
        tags.append("flat_shape")
    elif flips >= 20:
        tags.append("highly_oscillating_shape")
    elif flips >= 10:
        tags.append("oscillating_shape")
    elif flips >= 5:
        tags.append("jagged_shape")
    else:
        tags.append("smooth_trend_shape")

    if end > start + 20:
        tags.append("uptrend_finish")
    elif end < start - 20:
        tags.append("downtrend_finish")
    else:
        tags.append("sideways_finish")

    if low < start - 15 and end > start:
        tags.append("v_shape_recovery")

    if high > start + 15 and end < start:
        tags.append("inverted_v_failed_spike")

    if rng >= 60:
        tags.append("huge_range")
    elif rng >= 40:
        tags.append("large_range")
    elif rng >= 20:
        tags.append("medium_range")
    else:
        tags.append("small_range")

    if vol >= 4:
        tags.append("very_high_volatility")
    elif vol >= 2.5:
        tags.append("high_volatility")
    elif vol >= 1:
        tags.append("medium_volatility")
    else:
        tags.append("low_volatility")

    return tags


def set_tags(meta):
    tags = []
    score = meta.get("final_score", "")
    sets = parse_sets(score)
    n = count_sets(score)

    if n:
        tags.append(f"{n}_sets")
    else:
        tags.append("sets_unknown")

    if n == 2:
        tags.append("straight_sets")
    elif n == 3:
        tags.append("three_set_match")

    if has_tiebreak(score):
        tags.append("tiebreaker")
    elif score:
        tags.append("no_tiebreaker")
    else:
        tags.append("tiebreaker_unknown")

    for i, (a, b) in enumerate(sets[:3], start=1):
        if a == 7 and b == 6 or a == 6 and b == 7:
            tags.append(f"set_{i}_tiebreaker")
        else:
            tags.append(f"set_{i}_no_tiebreaker")

    player = str(meta.get("player_name", "")).strip().lower()
    winner = str(meta.get("match_winner", "")).strip().lower()
    player_is_match_winner = bool(player and winner and player == winner)

    # Assumption: final_score is from match winner perspective when match_winner exists.
    for idx, label in [(0, "first_set"), (1, "second_set"), (2, "third_set")]:
        if len(sets) <= idx or not winner:
            tags.append(f"{label}_unknown")
            continue

        a, b = sets[idx]
        winner_won_set = a > b
        player_won_set = winner_won_set if player_is_match_winner else not winner_won_set
        tags.append(f"{label}_winner" if player_won_set else f"{label}_loser")

    return tags


def build_tags(meta, prices, opp_prices):
    tags = []

    player = meta.get("player_name", "unknown_player")
    opponent = meta.get("opponent_name", "unknown_opponent")

    start = safe_float(meta.get("starting_price"))
    end = safe_float(meta.get("ending_price"))
    opp_start = safe_float(meta.get("opponent_starting_price"))
    opp_end = safe_float(meta.get("opponent_ending_price"))
    high = max(prices) if prices else start
    low = min(prices) if prices else start
    rng = high - low
    vol = volatility(prices)
    mx_step = max_step(prices)
    flips = count_direction_flips(prices)

    tags.append(f"player_{clean_tag(player)}")
    tags.append(f"opponent_{clean_tag(opponent)}")

    # Favorite / underdog by starting price.
    if start >= 75:
        tags.append("heavy_favorite")
    elif start >= 60:
        tags.append("favorite")
    elif start >= 50.5:
        tags.append("slight_favorite")
    elif start >= 40:
        tags.append("slight_underdog")
    elif start >= 25:
        tags.append("underdog")
    else:
        tags.append("heavy_underdog")

    tags.append("winner" if end >= opp_end else "loser")

    tags.append(f"starting_price_{int(round(start)):04d}")
    tags.append(f"ending_price_{int(round(end)):04d}")
    tags.append(f"starting_bucket_{price_bucket(start)}")
    tags.append(f"ending_bucket_{price_bucket(end)}")

    # Outcome-style path tags.
    if start < 25 and end >= 95:
        tags.append("longshot_comeback_winner")
    if start >= 75 and end <= 5:
        tags.append("favorite_collapse_loser")
    if end >= 95:
        tags.append("resolved_near_100")
    if end <= 5:
        tags.append("resolved_near_0")
    if high >= 90 and end <= 10:
        tags.append("near_certain_loser")
    if low <= 10 and end >= 90:
        tags.append("near_dead_winner")
    if high >= start + 25 and end < start:
        tags.append("failed_spike")
    if low <= start - 25 and end > start:
        tags.append("drawdown_recovery")

    # Range / volatility / movement.
    if rng >= 70:
        tags.append("extreme_range")
    elif rng >= 50:
        tags.append("large_range")
    elif rng >= 25:
        tags.append("medium_range")
    else:
        tags.append("small_range")

    if vol >= 4:
        tags.append("very_high_volatility")
    elif vol >= 2.5:
        tags.append("high_volatility")
    elif vol >= 1:
        tags.append("medium_volatility")
    else:
        tags.append("low_volatility")

    if mx_step >= 30:
        tags.append("huge_single_move")
    elif mx_step >= 15:
        tags.append("large_single_move")
    elif mx_step >= 8:
        tags.append("medium_single_move")
    else:
        tags.append("small_single_move")

    if flips >= 20:
        tags.append("many_reversals")
    elif flips >= 10:
        tags.append("moderate_reversals")
    elif flips >= 3:
        tags.append("few_reversals")
    else:
        tags.append("low_reversal_count")

    tags.extend(shape_tags(prices))
    tags.extend(set_tags(meta))

    # Crossings.
    for level in [10, 20, 25, 30, 40, 50, 60, 70, 75, 80, 90]:
        crosses = count_crossings(prices, level)
        if crosses:
            tags.append(f"crossed_{level}")
            if crosses >= 3:
                tags.append(f"multi_crossed_{level}")

    if first_cross_pct(prices, 50) != "":
        pct = first_cross_pct(prices, 50)
        if pct <= 33:
            tags.append("early_cross_50")
        elif pct <= 66:
            tags.append("middle_cross_50")
        else:
            tags.append("late_cross_50")
    else:
        tags.append("never_crossed_50")

    return sorted(set(tags)), {
        "volatility_score": round(vol, 4),
        "max_single_move": round(mx_step, 4),
        "direction_flips": flips,
        "range_points": round(rng, 4),
        "crossings_25": count_crossings(prices, 25),
        "crossings_50": count_crossings(prices, 50),
        "crossings_75": count_crossings(prices, 75),
        "first_cross_50_pct": first_cross_pct(prices, 50),
    }


def tag_csv(csv_path, tags, metrics):
    rows, prices, opp_prices = load_csv(csv_path)

    fieldnames = list(rows[0].keys()) if rows else ["timestamp", "player_price", "opponent_price"]

    extra_fields = [
        "tags",
        "volatility_score",
        "max_single_move",
        "direction_flips",
        "range_points",
        "crossings_25",
        "crossings_50",
        "crossings_75",
        "first_cross_50_pct",
    ]

    for f in extra_fields:
        if f not in fieldnames:
            fieldnames.append(f)

    tag_string = "|".join(tags)

    for r in rows:
        r["tags"] = tag_string
        for k, v in metrics.items():
            r[k] = v

    with csv_path.open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=fieldnames)
        w.writeheader()
        for r in rows:
            w.writerow(r)


def tag_png(png_path, tags, metrics):
    if not png_path.exists():
        return False

    try:
        img = Image.open(png_path)
        meta = PngImagePlugin.PngInfo()

        existing = img.info or {}
        for k, v in existing.items():
            if isinstance(v, str):
                meta.add_text(k, v)

        meta.add_text("tags", "|".join(tags))
        for k, v in metrics.items():
            meta.add_text(k, str(v))

        img.save(png_path, "PNG", pnginfo=meta, optimize=True)
        return True
    except Exception as e:
        print(f"PNG tag failed {png_path.name}: {e}")
        return False


def main():
    json_files = sorted(JSON_DIR.glob("*.json"))

    if not json_files:
        print("No JSON files found.")
        return

    manifest_rows = []
    master_index = []

    updated_json = 0
    updated_csv = 0
    updated_png = 0
    missing_png = 0
    missing_csv = 0

    for jf in json_files:
        try:
            meta = json.loads(jf.read_text(encoding="utf-8"))

            csv_name = meta.get("files", {}).get("csv", jf.with_suffix(".csv").name)
            npy_name = meta.get("files", {}).get("npy", jf.with_suffix(".npy").name)

            csv_path = CSV_DIR / csv_name
            npy_path = NPY_DIR / npy_name

            if not csv_path.exists():
                missing_csv += 1
                print(f"Missing CSV for {jf.name}: {csv_name}")
                continue

            rows, prices, opp_prices = load_csv(csv_path)
            tags, metrics = build_tags(meta, prices, opp_prices)

            meta["tags"] = tags
            meta.update(metrics)
            jf.write_text(json.dumps(meta, indent=2), encoding="utf-8")
            updated_json += 1

            tag_csv(csv_path, tags, metrics)
            updated_csv += 1

            # PNG file options:
            # 1. player-level png: 0011s.png
            # 2. match-level png from prior script: 0011s_match.png
            png_candidates = [
                PNG_DIR / f"{meta['id']}.png",
                PNG_DIR / f"{meta['id']}_match.png",
            ]

            png_found = False
            for pp in png_candidates:
                if pp.exists():
                    if tag_png(pp, tags, metrics):
                        updated_png += 1
                    png_found = True

            if not png_found:
                missing_png += 1

            record = {
                "id": meta.get("id"),
                "source_workbook": meta.get("source_workbook", ""),
                "player_name": meta.get("player_name", ""),
                "opponent_name": meta.get("opponent_name", ""),
                "player_side": meta.get("player_side", ""),
                "match_winner": meta.get("match_winner", ""),
                "final_score": meta.get("final_score", ""),
                "starting_price": meta.get("starting_price", ""),
                "ending_price": meta.get("ending_price", ""),
                "min_price": meta.get("min_price", ""),
                "max_price": meta.get("max_price", ""),
                "opponent_starting_price": meta.get("opponent_starting_price", ""),
                "opponent_ending_price": meta.get("opponent_ending_price", ""),
                "row_count": meta.get("row_count", ""),
                "trimmed_opening_rows": meta.get("trimmed_opening_rows", ""),
                "trimmed_ending_rows": meta.get("trimmed_ending_rows", ""),
                "start_timestamp": meta.get("start_timestamp", ""),
                "end_timestamp": meta.get("end_timestamp", ""),
                "csv_file": str(csv_path.relative_to(BASE)),
                "json_file": str(jf.relative_to(BASE)),
                "npy_file": str(npy_path.relative_to(BASE)) if npy_path.exists() else "",
                "png_file": "",
                "tags": "|".join(tags),
                **metrics,
            }

            for pp in png_candidates:
                if pp.exists():
                    record["png_file"] = str(pp.relative_to(BASE))
                    break

            manifest_rows.append(record)

            master_index.append({
                "id": record["id"],
                "player_name": record["player_name"],
                "opponent_name": record["opponent_name"],
                "source_workbook": record["source_workbook"],
                "starting_price": record["starting_price"],
                "ending_price": record["ending_price"],
                "min_price": record["min_price"],
                "max_price": record["max_price"],
                "tags": tags,
                "metrics": metrics,
                "files": {
                    "csv": record["csv_file"],
                    "json": record["json_file"],
                    "npy": record["npy_file"],
                    "png": record["png_file"],
                },
            })

        except Exception as e:
            print(f"Failed {jf.name}: {e}")

    if manifest_rows:
        fieldnames = list(manifest_rows[0].keys())
        with MASTER_CSV.open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fieldnames)
            w.writeheader()
            for r in manifest_rows:
                w.writerow(r)

    MASTER_JSON.write_text(json.dumps(master_index, indent=2), encoding="utf-8")

    print()
    print("DONE")
    print(f"JSON files tagged: {updated_json}")
    print(f"CSV files tagged: {updated_csv}")
    print(f"PNG files tagged: {updated_png}")
    print(f"Missing PNGs: {missing_png}")
    print(f"Missing CSVs: {missing_csv}")
    print(f"Master manifest CSV: {MASTER_CSV}")
    print(f"Master index JSON: {MASTER_JSON}")
    print(f"Player datasets indexed: {len(master_index)}")


if __name__ == "__main__":
    main()
