from pathlib import Path
import csv
import json
import re

BASE = Path(r"C:\Users\alexm\Downloads\kbot\my-kalshi-app\csv data\match_price_history")

JSON_DIR = BASE / "json data"
PNG_DIR = BASE / "png charts"

MANIFEST_CSV = BASE / "master_player_manifest.csv"
MASTER_INDEX_JSON = BASE / "master_player_index.json"
INDEX_HTML = BASE / "index.html"

THRESHOLDS = [10, 20, 30, 40, 50, 60]


def safe_float(x, default=0.0):
    try:
        if x is None:
            return default
        s = str(x).strip().replace("$", "").replace("%", "").replace("c", "")
        if s == "":
            return default
        return float(s)
    except Exception:
        return default


def read_json(path):
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def write_json(path, obj):
    path.write_text(
        json.dumps(obj, indent=2, ensure_ascii=False),
        encoding="utf-8"
    )


def normalize_tags(value):
    if isinstance(value, list):
        return [str(x).strip() for x in value if str(x).strip()]

    if isinstance(value, str):
        if "|" in value:
            return [x.strip() for x in value.split("|") if x.strip()]
        if "," in value:
            return [x.strip() for x in value.split(",") if x.strip()]
        if value.strip():
            return [value.strip()]

    return []


def add_tag(tags, tag):
    tag = str(tag).strip()
    if tag and tag not in tags:
        tags.append(tag)


def get_id(record, fallback=""):
    return str(
        record.get("id")
        or record.get("dataset_id")
        or record.get("player_id")
        or fallback
    ).strip()


def get_side(record):
    return str(record.get("player_side", "")).lower().strip()


def derive_price_fields(record):
    start = safe_float(record.get("starting_price"))
    end = safe_float(record.get("ending_price"))

    opp_start = safe_float(
        record.get("opponent_starting_price"),
        100.0 - start
    )

    opp_end = safe_float(
        record.get("opponent_ending_price"),
        100.0 - end
    )

    side = get_side(record)

    if "fav" in side:
        player_is_favorite = True
    elif "dog" in side or "under" in side:
        player_is_favorite = False
    else:
        player_is_favorite = start >= opp_start

    if player_is_favorite:
        favorite_start = start
        favorite_end = end
        underdog_start = opp_start
        underdog_end = opp_end
    else:
        favorite_start = opp_start
        favorite_end = opp_end
        underdog_start = start
        underdog_end = end

    price_move = end - start
    abs_price_move = abs(price_move)

    favorite_price_move = favorite_end - favorite_start
    underdog_price_move = underdog_end - underdog_start

    price_expansion = favorite_price_move > 0 and underdog_price_move < 0
    price_contraction = favorite_price_move < 0 and underdog_price_move > 0

    return {
        "price_move": round(price_move, 4),
        "abs_price_move": round(abs_price_move, 4),
        "favorite_starting_price": round(favorite_start, 4),
        "favorite_ending_price": round(favorite_end, 4),
        "underdog_starting_price": round(underdog_start, 4),
        "underdog_ending_price": round(underdog_end, 4),
        "favorite_price_move": round(favorite_price_move, 4),
        "underdog_price_move": round(underdog_price_move, 4),
        "price_expansion": bool(price_expansion),
        "price_contraction": bool(price_contraction),
    }


def add_price_move_tags(record):
    tags = normalize_tags(record.get("tags"))
    fields = derive_price_fields(record)

    move = fields["price_move"]

    if move > 0:
        add_tag(tags, "price_move_up")
        add_tag(tags, "positive_price_move")

        for threshold in THRESHOLDS:
            if move >= threshold:
                add_tag(tags, f"price_move_up_{threshold}")
                add_tag(tags, f"move_up_{threshold}")
                add_tag(tags, f"plus_{threshold}_up")

    elif move < 0:
        add_tag(tags, "price_move_down")
        add_tag(tags, "negative_price_move")

        for threshold in THRESHOLDS:
            if move <= -threshold:
                add_tag(tags, f"price_move_down_{threshold}")
                add_tag(tags, f"move_down_{threshold}")
                add_tag(tags, f"minus_{threshold}_down")

    if fields["price_expansion"]:
        add_tag(tags, "price_expansion")
        add_tag(tags, "favorite_up_underdog_down")

    if fields["price_contraction"]:
        add_tag(tags, "price_contraction")
        add_tag(tags, "favorite_down_underdog_up")

    record.update(fields)
    record["tags"] = tags

    dataset_id = get_id(record)

    if dataset_id:
        record["id"] = dataset_id

        files = record.get("files")
        if not isinstance(files, dict):
            files = {}

        files["png"] = f"png charts/{dataset_id}.png"
        record["files"] = files
        record["png_file"] = f"png charts/{dataset_id}.png"

    return record


def update_json_files():
    updated = 0

    for path in sorted(JSON_DIR.glob("*.json")):
        record = read_json(path)

        if not isinstance(record, dict):
            continue

        if not get_id(record):
            record["id"] = path.stem

        record = add_price_move_tags(record)
        write_json(path, record)
        updated += 1

    print("JSON files updated:", updated)


def update_records_in_obj(obj):
    updated = 0

    if isinstance(obj, list):
        for record in obj:
            if isinstance(record, dict):
                add_price_move_tags(record)
                updated += 1

    elif isinstance(obj, dict):
        list_keys = [
            "players",
            "records",
            "datasets",
            "items",
            "data",
            "player_datasets",
            "index"
        ]

        hit_list = False

        for key in list_keys:
            if isinstance(obj.get(key), list):
                hit_list = True
                for record in obj[key]:
                    if isinstance(record, dict):
                        add_price_move_tags(record)
                        updated += 1

        if not hit_list:
            for value in obj.values():
                if isinstance(value, dict):
                    add_price_move_tags(value)
                    updated += 1

    return updated


def update_master_index():
    if not MASTER_INDEX_JSON.exists():
        print("Master index missing:", MASTER_INDEX_JSON)
        return

    obj = read_json(MASTER_INDEX_JSON)
    updated = update_records_in_obj(obj)
    write_json(MASTER_INDEX_JSON, obj)

    print("Master index records updated:", updated)


def update_manifest_csv():
    if not MANIFEST_CSV.exists():
        print("Manifest CSV missing:", MANIFEST_CSV)
        return

    with MANIFEST_CSV.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        rows = list(reader)
        fieldnames = list(reader.fieldnames or [])

    extra_fields = [
        "price_move",
        "abs_price_move",
        "favorite_starting_price",
        "favorite_ending_price",
        "underdog_starting_price",
        "underdog_ending_price",
        "favorite_price_move",
        "underdog_price_move",
        "price_expansion",
        "price_contraction",
        "png_file",
        "tags",
    ]

    for field in extra_fields:
        if field not in fieldnames:
            fieldnames.append(field)

    updated = 0

    for row in rows:
        dataset_id = get_id(row)

        if not dataset_id:
            continue

        row["id"] = dataset_id

        # Prefer JSON tags if available because JSON is the richer record.
        json_path = JSON_DIR / f"{dataset_id}.json"
        json_record = read_json(json_path)

        if isinstance(json_record, dict) and json_record:
            json_record = add_price_move_tags(json_record)

            for key in extra_fields:
                if key == "tags":
                    row[key] = "|".join(normalize_tags(json_record.get("tags")))
                elif key in json_record:
                    row[key] = json_record[key]

        else:
            row = add_price_move_tags(row)
            row["tags"] = "|".join(normalize_tags(row.get("tags")))

        row["png_file"] = f"png charts/{dataset_id}.png"
        updated += 1

    with MANIFEST_CSV.open("w", encoding="utf-8", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)

    print("Manifest rows updated:", updated)


def embed_png_tags():
    try:
        from PIL import Image
        from PIL.PngImagePlugin import PngInfo
    except Exception:
        print("Pillow not installed; skipping embedded PNG metadata.")
        return

    if not PNG_DIR.exists():
        print("PNG folder missing; skipping embedded PNG metadata.")
        return

    tagged = 0
    missing_json = 0
    failed = 0

    for png_path in sorted(PNG_DIR.glob("*.png")):
        dataset_id = png_path.stem
        json_path = JSON_DIR / f"{dataset_id}.json"

        if not json_path.exists():
            missing_json += 1
            continue

        record = add_price_move_tags(read_json(json_path))
        tags = normalize_tags(record.get("tags"))

        meta = PngInfo()
        meta.add_text("kchart_dataset_id", dataset_id)
        meta.add_text("kchart_tags", "|".join(tags))
        meta.add_text("kchart_player_name", str(record.get("player_name", "")))
        meta.add_text("kchart_opponent_name", str(record.get("opponent_name", "")))
        meta.add_text("kchart_source_workbook", str(record.get("source_workbook", "")))
        meta.add_text("kchart_final_score", str(record.get("final_score", "")))
        meta.add_text("kchart_starting_price", str(record.get("starting_price", "")))
        meta.add_text("kchart_ending_price", str(record.get("ending_price", "")))
        meta.add_text("kchart_price_move", str(record.get("price_move", "")))
        meta.add_text("kchart_abs_price_move", str(record.get("abs_price_move", "")))
        meta.add_text("kchart_price_expansion", str(record.get("price_expansion", "")))
        meta.add_text("kchart_price_contraction", str(record.get("price_contraction", "")))
        meta.add_text("kchart_png_file", f"png charts/{dataset_id}.png")

        try:
            with Image.open(png_path) as im:
                im.save(png_path, pnginfo=meta)

            tagged += 1

        except Exception as e:
            failed += 1
            print("FAILED PNG METADATA:", png_path.name, e)

    print("PNG files embedded with tags:", tagged)
    print("PNG files missing JSON:", missing_json)
    print("PNG metadata failures:", failed)


def patch_viewer():
    if not INDEX_HTML.exists():
        raise SystemExit("index.html not found.")

    html = INDEX_HTML.read_text(encoding="utf-8")

    patch_id = "KCHART ADVANCED FILTER PATCH V4"

    if patch_id in html:
        print("Viewer patch already present.")
        return

    patch_js = r'''
    /*
      KCHART ADVANCED FILTER PATCH V4

      Adds:
      - unlimited field-vs-field comparison filters
      - price move magnitude tags
      - price expansion / contraction tags
      - hides old minutes-based movement filter
    */

    const KCV_COMPARE_FIELDS = [
      ["starting_price", "Starting price"],
      ["ending_price", "Ending price"],
      ["price_move", "Price move"],
      ["abs_price_move", "Absolute price move"],
      ["favorite_starting_price", "Favorite start"],
      ["favorite_ending_price", "Favorite end"],
      ["favorite_price_move", "Favorite move"],
      ["underdog_starting_price", "Underdog start"],
      ["underdog_ending_price", "Underdog end"],
      ["underdog_price_move", "Underdog move"],
      ["volatility_score", "Volatility"],
      ["range_points", "Range"],
      ["direction_flips", "Direction flips"],
      ["max_single_move", "Max single move"],
      ["row_count", "Rows"],
      ["price_expansion", "Price expansion"],
      ["price_contraction", "Price contraction"]
    ];

    const KCV_COMPARE_CONSTANTS = [
      -100, -90, -80, -70, -60, -50, -40, -30, -20, -10,
      -5, -1, 0, 1, 5, 10, 20, 30, 40, 50, 60, 70, 80, 90, 100
    ];

    const KCV_COMPARE_OPERATORS = [
      ["<", "<"],
      ["<=", "<="],
      ["=", "="],
      [">=", ">="],
      [">", ">"],
      ["!=", "!="],
      ["-", "-  field1 minus field2 > 0"],
      ["+", "+  field1 plus field2 > 0"]
    ];

    let kcvCompareFilters = [];

    const kcvOriginalAllRecordTags = allRecordTags;

    allRecordTags = function(record) {
      return [...new Set([
        ...kcvOriginalAllRecordTags(record),
        ...kcvDerivedMoveTags(record)
      ])];
    };

    function kcvNum(value) {
      const x = Number(value);
      return Number.isFinite(x) ? x : 0;
    }

    function kcvPriceFields(record) {
      const start = kcvNum(record.starting_price);
      const end = kcvNum(record.ending_price);

      const oppStart = kcvNum(
        record.opponent_starting_price ??
        record.opponent_start ??
        (100 - start)
      );

      const oppEnd = kcvNum(
        record.opponent_ending_price ??
        record.opponent_end ??
        (100 - end)
      );

      const side = String(record.player_side || "").toLowerCase();

      let playerIsFavorite = false;

      if (side.includes("fav")) {
        playerIsFavorite = true;
      } else if (side.includes("dog") || side.includes("under")) {
        playerIsFavorite = false;
      } else {
        playerIsFavorite = start >= oppStart;
      }

      const favoriteStart = playerIsFavorite ? start : oppStart;
      const favoriteEnd = playerIsFavorite ? end : oppEnd;
      const underdogStart = playerIsFavorite ? oppStart : start;
      const underdogEnd = playerIsFavorite ? oppEnd : end;

      const priceMove = end - start;
      const favoriteMove = favoriteEnd - favoriteStart;
      const underdogMove = underdogEnd - underdogStart;

      return {
        starting_price: start,
        ending_price: end,
        price_move: priceMove,
        abs_price_move: Math.abs(priceMove),
        favorite_starting_price: favoriteStart,
        favorite_ending_price: favoriteEnd,
        favorite_price_move: favoriteMove,
        underdog_starting_price: underdogStart,
        underdog_ending_price: underdogEnd,
        underdog_price_move: underdogMove,
        price_expansion: favoriteMove > 0 && underdogMove < 0 ? 1 : 0,
        price_contraction: favoriteMove < 0 && underdogMove > 0 ? 1 : 0
      };
    }

    function kcvFieldValue(record, key) {
      const fields = kcvPriceFields(record);

      if (fields[key] != null) {
        return fields[key];
      }

      const m = metric(record, key);

      if (m !== "" && m != null) {
        return kcvNum(m);
      }

      return kcvNum(record[key]);
    }

    function kcvDerivedMoveTags(record) {
      const fields = kcvPriceFields(record);
      const tags = [];
      const move = fields.price_move;

      if (move > 0) {
        tags.push("price_move_up");
        tags.push("positive_price_move");

        [10, 20, 30, 40, 50, 60].forEach((threshold) => {
          if (move >= threshold) {
            tags.push("price_move_up_" + threshold);
            tags.push("move_up_" + threshold);
            tags.push("plus_" + threshold + "_up");
          }
        });
      }

      if (move < 0) {
        tags.push("price_move_down");
        tags.push("negative_price_move");

        [10, 20, 30, 40, 50, 60].forEach((threshold) => {
          if (move <= -threshold) {
            tags.push("price_move_down_" + threshold);
            tags.push("move_down_" + threshold);
            tags.push("minus_" + threshold + "_down");
          }
        });
      }

      if (fields.price_expansion) {
        tags.push("price_expansion");
        tags.push("favorite_up_underdog_down");
      }

      if (fields.price_contraction) {
        tags.push("price_contraction");
        tags.push("favorite_down_underdog_up");
      }

      return tags;
    }

    function kcvFieldOptions(selected) {
      return KCV_COMPARE_FIELDS.map(([key, label]) => {
        return `<option value="${key}" ${selected === key ? "selected" : ""}>${label}</option>`;
      }).join("");
    }

    function kcvOperatorOptions(selected) {
      return KCV_COMPARE_OPERATORS.map(([key, label]) => {
        return `<option value="${key}" ${selected === key ? "selected" : ""}>${label}</option>`;
      }).join("");
    }

    function kcvRightOptions(selected) {
      const fields = KCV_COMPARE_FIELDS.map(([key, label]) => {
        return `<option value="${key}" ${selected === key ? "selected" : ""}>${label}</option>`;
      }).join("");

      const constants = KCV_COMPARE_CONSTANTS.map((value) => {
        const key = "const:" + value;
        return `<option value="${key}" ${selected === key ? "selected" : ""}>${value}</option>`;
      }).join("");

      return fields + constants;
    }

    function kcvInstallCompareUi() {
      for (const h3 of document.querySelectorAll(".section h3")) {
        const text = h3.textContent.trim().toLowerCase();

        if (text === "time move filter") {
          h3.closest(".section").style.display = "none";
        }
      }

      if (document.getElementById("kcvCompareSection")) {
        return;
      }

      let insertAfter = null;

      for (const h3 of document.querySelectorAll(".section h3")) {
        if (h3.textContent.trim().toLowerCase() === "numeric filters") {
          insertAfter = h3.closest(".section");
        }
      }

      const html = `
        <div class="section" id="kcvCompareSection">
          <h3>Compare filters</h3>

          <div class="small" style="margin-bottom:8px">
            Build unlimited field-vs-field or field-vs-number rules.
            Example: Starting price &lt; Ending price.
          </div>

          <div id="kcvCompareRows"></div>

          <div class="controls" style="margin-top:8px">
            <button onclick="kcvAddCompareFilter()">+ Add filter</button>
            <button onclick="kcvClearCompareFilters()">Clear compare filters</button>
          </div>
        </div>
      `;

      if (insertAfter) {
        insertAfter.insertAdjacentHTML("afterend", html);
      }
    }

    function kcvAddCompareFilter(lhs = "starting_price", op = "<", rhs = "ending_price") {
      kcvCompareFilters.push({ lhs, op, rhs });
      kcvRenderCompareRows();
      applyFilters();
    }

    function kcvRemoveCompareFilter(index) {
      kcvCompareFilters.splice(index, 1);
      kcvRenderCompareRows();
      applyFilters();
    }

    function kcvUpdateCompareFilter(index, key, value) {
      if (!kcvCompareFilters[index]) {
        return;
      }

      kcvCompareFilters[index][key] = value;
      applyFilters();
    }

    function kcvClearCompareFilters() {
      kcvCompareFilters = [];
      kcvRenderCompareRows();
      applyFilters();
    }

    function kcvRenderCompareRows() {
      const box = document.getElementById("kcvCompareRows");

      if (!box) {
        return;
      }

      if (!kcvCompareFilters.length) {
        box.innerHTML = `<div class="small">No compare filters active.</div>`;
        return;
      }

      box.innerHTML = kcvCompareFilters.map((row, index) => {
        return `
          <div style="display:grid;grid-template-columns:1fr 78px 1fr 34px;gap:6px;margin:6px 0">
            <select onchange="kcvUpdateCompareFilter(${index}, 'lhs', this.value)">
              ${kcvFieldOptions(row.lhs)}
            </select>

            <select onchange="kcvUpdateCompareFilter(${index}, 'op', this.value)">
              ${kcvOperatorOptions(row.op)}
            </select>

            <select onchange="kcvUpdateCompareFilter(${index}, 'rhs', this.value)">
              ${kcvRightOptions(row.rhs)}
            </select>

            <button onclick="kcvRemoveCompareFilter(${index})">x</button>
          </div>
        `;
      }).join("");
    }

    function kcvResolveRightValue(record, token) {
      token = String(token || "");

      if (token.startsWith("const:")) {
        return kcvNum(token.slice(6));
      }

      return kcvFieldValue(record, token);
    }

    function kcvComparePass(record) {
      for (const row of kcvCompareFilters) {
        const a = kcvFieldValue(record, row.lhs);
        const b = kcvResolveRightValue(record, row.rhs);

        let ok = true;

        if (row.op === "<") ok = a < b;
        else if (row.op === "<=") ok = a <= b;
        else if (row.op === "=") ok = Math.abs(a - b) < 0.00001;
        else if (row.op === ">=") ok = a >= b;
        else if (row.op === ">") ok = a > b;
        else if (row.op === "!=") ok = Math.abs(a - b) >= 0.00001;
        else if (row.op === "-") ok = (a - b) > 0;
        else if (row.op === "+") ok = (a + b) > 0;

        if (!ok) {
          return false;
        }
      }

      return true;
    }

    const kcvOriginalBasePass = basePass;

    basePass = function(record, includeMovement) {
      if (!kcvOriginalBasePass(record, includeMovement)) {
        return false;
      }

      return kcvComparePass(record);
    };

    const kcvOriginalClearFilters = clearFilters;

    clearFilters = function() {
      kcvCompareFilters = [];
      kcvOriginalClearFilters();
      kcvRenderCompareRows();
    };

    try {
      quickTags.push(
        "price_move_up",
        "price_move_down",
        "price_move_up_10",
        "price_move_up_20",
        "price_move_up_30",
        "price_move_up_40",
        "price_move_up_50",
        "price_move_up_60",
        "price_move_down_10",
        "price_move_down_20",
        "price_move_down_30",
        "price_move_down_40",
        "price_move_down_50",
        "price_move_down_60",
        "price_expansion",
        "price_contraction"
      );
    } catch (error) {}

    kcvInstallCompareUi();
    kcvRenderCompareRows();
'''

    marker = "    loadData();"

    if marker not in html:
        raise SystemExit("Could not find loadData marker in index.html")

    html = html.replace(marker, patch_js + "\n\n" + marker)

    INDEX_HTML.write_text(html, encoding="utf-8")

    print("Viewer patched with advanced compare filters and new price tags.")


def main():
    update_json_files()
    update_manifest_csv()
    update_master_index()
    embed_png_tags()
    patch_viewer()

    print("")
    print("DONE")
    print("Added:")
    print("- unlimited compare filters")
    print("- price move up/down magnitude tags")
    print("- price expansion tags")
    print("- price contraction tags")
    print("- PNG embedded metadata tags")
    print("- viewer left-menu support for the new tags")


if __name__ == "__main__":
    main()
