from pathlib import Path
import csv
import json
from datetime import datetime

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.gridspec import GridSpec


BASE = Path(r"C:\Users\alexm\Downloads\kbot\my-kalshi-app\csv data\match_price_history")
CSV_DIR = BASE / "csvprice data"
JSON_DIR = BASE / "json data"
PNG_DIR = BASE / "png charts"

PNG_DIR.mkdir(exist_ok=True)


def safe_float(x):
    try:
        if x is None:
            return None
        s = str(x).strip().replace("$", "").replace("%", "").replace("c", "")
        if s == "":
            return None
        return float(s)
    except Exception:
        return None


def pick_first(d, keys, default=""):
    for k in keys:
        if k in d and d[k] not in [None, ""]:
            return d[k]
    return default


def read_json(path):
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def detect_columns(fieldnames):
    lower = {f.lower().strip(): f for f in fieldnames}

    def find(candidates):
        for c in candidates:
            if c in lower:
                return lower[c]
        for f in fieldnames:
            lf = f.lower().strip()
            for c in candidates:
                if c in lf:
                    return f
        return None

    ts_col = find(["timestamp", "time", "datetime", "date"])
    player_col = find(["player_price", "price", "yes_price", "market_price"])
    opp_col = find(["opponent_price", "other_price", "opponent yes price"])

    return ts_col, player_col, opp_col


def read_csv_rows(path):
    rows = []

    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        if not reader.fieldnames:
            return rows

        ts_col, player_col, opp_col = detect_columns(reader.fieldnames)

        for row in reader:
            p = safe_float(row.get(player_col)) if player_col else None
            o = safe_float(row.get(opp_col)) if opp_col else None

            if p is None:
                continue

            if o is None:
                o = 100.0 - p

            ts = row.get(ts_col, "") if ts_col else ""

            rows.append({
                "timestamp": ts,
                "player_price": p,
                "opponent_price": o,
            })

    return rows


def normalize_pair(row, places=4):
    return (
        round(float(row["player_price"]), places),
        round(float(row["opponent_price"]), places),
    )


def trim_filler_edges(rows):
    """
    Removes repeated filler prices at the beginning and end.
    Keeps one anchor row on each side so the chart still starts/ends cleanly.
    """
    n = len(rows)

    if n <= 2:
        return rows, 0, 0

    start = 0
    first_pair = normalize_pair(rows[0])

    while start + 1 < n and normalize_pair(rows[start + 1]) == first_pair:
        start += 1

    end = n - 1
    last_pair = normalize_pair(rows[-1])

    while end - 1 >= 0 and normalize_pair(rows[end - 1]) == last_pair:
        end -= 1

    if start > end:
        return rows, 0, 0

    trimmed = rows[start:end + 1]
    trimmed_head = start
    trimmed_tail = (n - 1) - end

    return trimmed, trimmed_head, trimmed_tail


def fmt_time(ts):
    s = str(ts).strip()

    if not s:
        return ""

    for candidate in [s, s.replace("Z", "+00:00")]:
        try:
            dt = datetime.fromisoformat(candidate)
            return dt.strftime("%H:%M")
        except Exception:
            pass

    return s[-5:] if len(s) >= 5 else s


def time_labels(rows):
    return [fmt_time(r["timestamp"]) for r in rows]


def sets_from_score(score_text):
    import re
    pairs = re.findall(r"(\d+)\s*-\s*(\d+)", str(score_text or ""))
    return len(pairs)


def winner_and_loser_names(meta, player_end, opp_end):
    player_name = pick_first(meta, ["player_name", "player", "name"], "Player 1")
    opp_name = pick_first(meta, ["opponent_name", "opponent"], "Player 2")

    meta_winner = pick_first(meta, ["winner_name", "winner"], "")

    if meta_winner:
        winner = meta_winner
        loser = opp_name if meta_winner == player_name else player_name
        return player_name, opp_name, winner, loser

    if player_end >= opp_end:
        winner = player_name
        loser = opp_name
    else:
        winner = opp_name
        loser = player_name

    return player_name, opp_name, winner, loser


def build_series(rows, meta):
    player_name = pick_first(meta, ["player_name", "player", "name"], "Player 1")
    opp_name = pick_first(meta, ["opponent_name", "opponent"], "Player 2")

    player_prices = [float(r["player_price"]) for r in rows]
    opp_prices = [float(r["opponent_price"]) for r in rows]

    player_end = player_prices[-1]
    opp_end = opp_prices[-1]

    _, _, winner_name, loser_name = winner_and_loser_names(meta, player_end, opp_end)

    if winner_name == player_name:
        winner_prices = player_prices
        loser_prices = opp_prices
        winner_start = player_prices[0]
        loser_start = opp_prices[0]
    else:
        winner_prices = opp_prices
        loser_prices = player_prices
        winner_start = opp_prices[0]
        loser_start = player_prices[0]

    return {
        "player_name": player_name,
        "opponent_name": opp_name,
        "winner_name": winner_name,
        "loser_name": loser_name,
        "winner_prices": winner_prices,
        "loser_prices": loser_prices,
        "winner_start": winner_start,
        "winner_end": winner_prices[-1],
        "loser_start": loser_start,
        "loser_end": loser_prices[-1],
    }


def make_chart(csv_path):
    dataset_id = csv_path.stem
    json_path = JSON_DIR / f"{dataset_id}.json"
    png_path = PNG_DIR / f"{dataset_id}.png"

    meta = read_json(json_path)
    raw_rows = read_csv_rows(csv_path)

    if len(raw_rows) < 2:
        return False, f"{dataset_id}: not enough rows"

    trimmed_rows, trimmed_head, trimmed_tail = trim_filler_edges(raw_rows)

    if len(trimmed_rows) < 2:
        trimmed_rows = raw_rows
        trimmed_head = 0
        trimmed_tail = 0

    total_trimmed = trimmed_head + trimmed_tail

    series = build_series(trimmed_rows, meta)

    winner_prices = series["winner_prices"]
    loser_prices = series["loser_prices"]

    x = list(range(len(trimmed_rows)))
    labels = time_labels(trimmed_rows)

    source_file = pick_first(meta, ["source_workbook", "source_file", "workbook", "source"], csv_path.name)
    final_score = pick_first(meta, ["final_score", "score", "match_score"], "")
    sets_n = pick_first(meta, ["sets"], "")

    if sets_n in ["", None]:
        sets_n = sets_from_score(final_score)

    trigger = pick_first(meta, ["trim_trigger", "trigger"], "")
    if trigger == "":
        trigger = "edge_repeat_trim"

    start_time = labels[0] if labels else ""
    end_time = labels[-1] if labels else ""

    bg = "#050b16"
    plot_bg = "#0b1524"
    footer_bg = "#101928"
    grid_c = "#394456"
    grey_v = "#8e99ab"
    cyan_v = "#00e5ff"
    win_c = "#fbbf24"
    lose_c = "#49a8ff"
    text_main = "#f3f4f6"
    text_sub = "#aab3c2"

    fig = plt.figure(figsize=(10.2, 5.85), dpi=100, facecolor=bg)
    gs = GridSpec(2, 1, height_ratios=[8.6, 1.65], hspace=0.18)

    ax = fig.add_subplot(gs[0])
    footer = fig.add_subplot(gs[1])

    ax.set_facecolor(plot_bg)
    footer.set_facecolor(footer_bg)

    ax.plot(x, winner_prices, color=win_c, linewidth=1.35, zorder=3, antialiased=False)
    ax.plot(x, loser_prices, color=lose_c, linewidth=1.35, zorder=3, antialiased=False)

    ax.scatter([x[0]], [winner_prices[0]], s=26, color=win_c, edgecolors="white", linewidths=0.5, zorder=5)
    ax.scatter([x[0]], [loser_prices[0]], s=26, color=lose_c, edgecolors="white", linewidths=0.5, zorder=5)
    ax.scatter([x[-1]], [winner_prices[-1]], s=50, color=win_c, edgecolors="white", linewidths=0.6, zorder=6)
    ax.scatter([x[-1]], [loser_prices[-1]], s=50, color=lose_c, edgecolors="white", linewidths=0.6, zorder=6)

    ax.set_xlim(0, len(x) - 1)
    ax.set_ylim(0, 100)

    for y in [0, 20, 40, 60, 80, 100]:
        ax.axhline(y, color=grid_c, linewidth=0.7, alpha=0.6, zorder=1)

    if len(x) > 3:
        p1 = round((len(x) - 1) / 3)
        p2 = round((len(x) - 1) * 2 / 3)
        mid = round((len(x) - 1) / 2)

        ax.axvline(p1, color=grey_v, linewidth=0.7, alpha=0.9, zorder=2)
        ax.axvline(p2, color=grey_v, linewidth=0.7, alpha=0.9, zorder=2)
        ax.axvline(mid, color=cyan_v, linewidth=1.4, alpha=1.0, zorder=2)

    for spine in ax.spines.values():
        spine.set_color("#243041")
        spine.set_linewidth(0.8)

    tick_count = min(6, len(x))

    if tick_count >= 2:
        ticks = [round(i * (len(x) - 1) / (tick_count - 1)) for i in range(tick_count)]
        ax.set_xticks(ticks)
        ax.set_xticklabels([labels[i] for i in ticks], fontsize=8.5, color=text_main)
    else:
        ax.set_xticks([])

    ax.set_yticks([0, 20, 40, 60, 80, 100])
    ax.set_yticklabels(["0", "20", "40", "60", "80", "100"], fontsize=8.5, color=text_main)

    ax.tick_params(axis="x", length=0, pad=6)
    ax.tick_params(axis="y", length=0, pad=20)

    ax.text(
        -0.065,
        0.995,
        "c",
        transform=ax.transAxes,
        ha="left",
        va="top",
        fontsize=9,
        color=text_sub
    )

    title_text = f"{series['winner_name']} vs {series['loser_name']}"
    subtitle_text = (
        f"Source: {source_file}"
        + (f" | Final: {final_score}" if final_score else "")
        + (f" | Sets: {sets_n}" if str(sets_n) not in ["", "0"] else "")
        + (f" | Winner: {series['winner_name']}" if series["winner_name"] else "")
    )

    ax.text(
        0.0,
        1.11,
        title_text,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=10.2,
        color=text_main
    )

    ax.text(
        0.0,
        1.045,
        subtitle_text,
        transform=ax.transAxes,
        ha="left",
        va="bottom",
        fontsize=8.5,
        color=text_sub
    )

    footer.set_xlim(0, 1)
    footer.set_ylim(0, 1)
    footer.set_xticks([])
    footer.set_yticks([])

    for spine in footer.spines.values():
        spine.set_color("#243041")
        spine.set_linewidth(0.8)

    footer.scatter([0.028], [0.67], s=68, color=lose_c)
    footer.text(
        0.045,
        0.67,
        f"{series['loser_name']}: {series['loser_start']:.2f}c -> {series['loser_end']:.2f}c",
        color=text_main,
        fontsize=8.5,
        va="center",
        ha="left"
    )

    footer.scatter([0.42], [0.67], s=68, color=win_c)
    footer.text(
        0.437,
        0.67,
        f"{series['winner_name']}: {series['winner_start']:.2f}c -> {series['winner_end']:.2f}c",
        color=text_main,
        fontsize=8.5,
        va="center",
        ha="left"
    )

    footer.text(
        0.045,
        0.25,
        f"Time: {start_time} -> {end_time}   Rows: {len(trimmed_rows)}/{len(raw_rows)}   "
        f"Trimmed: {total_trimmed}   Trigger: {trigger}",
        color=text_sub,
        fontsize=8.3,
        va="center",
        ha="left"
    )

    fig.savefig(
        png_path,
        facecolor=bg,
        edgecolor=bg,
        bbox_inches="tight",
        pad_inches=0.22
    )

    plt.close(fig)

    return True, f"{dataset_id} -> {png_path.name}"


def main():
    files = sorted(CSV_DIR.glob("*.csv"))

    if not files:
        print("No CSV files found in:", CSV_DIR)
        return

    made = 0
    failed = 0

    print("CSV source :", CSV_DIR)
    print("JSON source:", JSON_DIR)
    print("PNG output :", PNG_DIR)
    print("Files      :", len(files))
    print("")

    for i, csv_path in enumerate(files, 1):
        try:
            ok, msg = make_chart(csv_path)

            if ok:
                made += 1
                print(f"[{i}/{len(files)}] OK {msg}")
            else:
                failed += 1
                print(f"[{i}/{len(files)}] FAIL {msg}")

        except Exception as e:
            failed += 1
            print(f"[{i}/{len(files)}] ERROR {csv_path.name}: {e}")

    print("")
    print("DONE")
    print("PNG charts made:", made)
    print("Failed:", failed)


if __name__ == "__main__":
    main()
