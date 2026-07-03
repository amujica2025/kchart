from pathlib import Path

p = Path("index.html")

if not p.exists():
    raise SystemExit("index.html not found. Run this from the repo root.")

s = p.read_text(encoding="utf-8")

PATCH_ID = "KCHART EXPORT FILTERED ZIP PATCH V1"

if PATCH_ID in s:
    print("Export ZIP patch already installed.")
else:
    patch = r'''
    /*
      KCHART EXPORT FILTERED ZIP PATCH V1

      Adds:
      - Export Filtered ZIP button
      - ZIP includes:
        filters_applied.md
        filtered_datasets.csv
        missing_files.txt
        csv/<dataset_id>.csv
        png/<dataset_id>.png

      Notes:
      - Read-only. Does not alter source files.
      - ZIP is created in the browser.
      - Uses uncompressed ZIP entries for reliability.
    */

    function kczTextEncoder() {
      return new TextEncoder();
    }

    function kczDosTimeDate(date) {
      const year = date.getFullYear();
      const month = date.getMonth() + 1;
      const day = date.getDate();
      const hour = date.getHours();
      const minute = date.getMinutes();
      const second = Math.floor(date.getSeconds() / 2);

      const dosTime = (hour << 11) | (minute << 5) | second;
      const dosDate = ((year - 1980) << 9) | (month << 5) | day;

      return { dosTime, dosDate };
    }

    function kczMakeCrcTable() {
      const table = new Uint32Array(256);

      for (let i = 0; i < 256; i++) {
        let c = i;

        for (let k = 0; k < 8; k++) {
          c = c & 1 ? 0xedb88320 ^ (c >>> 1) : c >>> 1;
        }

        table[i] = c >>> 0;
      }

      return table;
    }

    const KCZ_CRC_TABLE = kczMakeCrcTable();

    function kczCrc32(bytes) {
      let crc = 0xffffffff;

      for (let i = 0; i < bytes.length; i++) {
        crc = KCZ_CRC_TABLE[(crc ^ bytes[i]) & 0xff] ^ (crc >>> 8);
      }

      return (crc ^ 0xffffffff) >>> 0;
    }

    function kczU16(value) {
      return [value & 255, (value >>> 8) & 255];
    }

    function kczU32(value) {
      return [
        value & 255,
        (value >>> 8) & 255,
        (value >>> 16) & 255,
        (value >>> 24) & 255
      ];
    }

    function kczBytesFromText(text) {
      return kczTextEncoder().encode(String(text ?? ""));
    }

    function kczConcat(parts) {
      const total = parts.reduce((sum, part) => sum + part.length, 0);
      const out = new Uint8Array(total);
      let offset = 0;

      for (const part of parts) {
        out.set(part, offset);
        offset += part.length;
      }

      return out;
    }

    function kczCreateZip(entries) {
      const localParts = [];
      const centralParts = [];
      let offset = 0;

      const now = new Date();
      const { dosTime, dosDate } = kczDosTimeDate(now);

      for (const entry of entries) {
        const nameBytes = kczBytesFromText(entry.name.replaceAll("\\", "/"));
        const data = entry.data instanceof Uint8Array
          ? entry.data
          : kczBytesFromText(entry.data);

        const crc = kczCrc32(data);
        const size = data.length;

        const localHeader = new Uint8Array([
          ...kczU32(0x04034b50),
          ...kczU16(20),
          ...kczU16(0),
          ...kczU16(0),
          ...kczU16(dosTime),
          ...kczU16(dosDate),
          ...kczU32(crc),
          ...kczU32(size),
          ...kczU32(size),
          ...kczU16(nameBytes.length),
          ...kczU16(0)
        ]);

        localParts.push(localHeader, nameBytes, data);

        const centralHeader = new Uint8Array([
          ...kczU32(0x02014b50),
          ...kczU16(20),
          ...kczU16(20),
          ...kczU16(0),
          ...kczU16(0),
          ...kczU16(dosTime),
          ...kczU16(dosDate),
          ...kczU32(crc),
          ...kczU32(size),
          ...kczU32(size),
          ...kczU16(nameBytes.length),
          ...kczU16(0),
          ...kczU16(0),
          ...kczU16(0),
          ...kczU16(0),
          ...kczU32(0),
          ...kczU32(offset)
        ]);

        centralParts.push(centralHeader, nameBytes);

        offset += localHeader.length + nameBytes.length + data.length;
      }

      const centralStart = offset;
      const centralBlob = kczConcat(centralParts);
      const centralSize = centralBlob.length;

      const end = new Uint8Array([
        ...kczU32(0x06054b50),
        ...kczU16(0),
        ...kczU16(0),
        ...kczU16(entries.length),
        ...kczU16(entries.length),
        ...kczU32(centralSize),
        ...kczU32(centralStart),
        ...kczU16(0)
      ]);

      return new Blob(
        [
          kczConcat(localParts),
          centralBlob,
          end
        ],
        { type: "application/zip" }
      );
    }

    function kczSanitizeFilename(name) {
      return String(name || "")
        .replace(/[<>:"/\\|?*\x00-\x1F]/g, "_")
        .slice(0, 160);
    }

    function kczCsvEscape(value) {
      const s = String(value ?? "");

      if (/[",\n\r]/.test(s)) {
        return '"' + s.replaceAll('"', '""') + '"';
      }

      return s;
    }

    function kczDatasetCsv(records) {
      const headers = [
        "id",
        "player_name",
        "opponent_name",
        "starting_price",
        "ending_price",
        "price_move",
        "abs_price_move",
        "favorite_starting_price",
        "favorite_ending_price",
        "favorite_price_move",
        "underdog_starting_price",
        "underdog_ending_price",
        "underdog_price_move",
        "price_expansion",
        "price_contraction",
        "volatility_score",
        "range_points",
        "direction_flips",
        "row_count",
        "final_score",
        "source_workbook",
        "tags"
      ];

      const lines = [headers.join(",")];

      for (const record of records) {
        const row = headers.map((header) => {
          if (header === "tags") {
            return kczCsvEscape(allRecordTags(record).join("|"));
          }

          if (typeof kcvFieldValue === "function") {
            const v = kcvFieldValue(record, header);
            if (v !== 0) {
              return kczCsvEscape(v);
            }
          }

          const m = metric(record, header);
          const value = m !== "" && m != null ? m : record[header];

          return kczCsvEscape(value ?? "");
        });

        lines.push(row.join(","));
      }

      return lines.join("\n");
    }

    function kczCurrentFilterSummary() {
      const lines = [];

      lines.push("# KChart filtered export");
      lines.push("");
      lines.push("Created: " + new Date().toISOString());
      lines.push("Matching datasets: " + filtered.length.toLocaleString());
      lines.push("");

      lines.push("## Search");
      lines.push("");
      lines.push("- Search text: " + (document.getElementById("q")?.value || ""));
      lines.push("- Player filter: " + (document.getElementById("playerFilter")?.value || ""));
      lines.push("- Opponent filter: " + (document.getElementById("opponentFilter")?.value || ""));
      lines.push("- First set margin: " + (document.getElementById("firstSetMargin")?.value || ""));
      lines.push("");

      lines.push("## Active tags");
      lines.push("");

      if (activeTags && activeTags.size) {
        [...activeTags].sort().forEach((tag) => lines.push("- " + tag));
      } else {
        lines.push("- none");
      }

      lines.push("");
      lines.push("## Numeric filters");
      lines.push("");

      const numeric = [
        ["Start min", "startMin"],
        ["Start max", "startMax"],
        ["End min", "endMin"],
        ["End max", "endMax"],
        ["Vol min", "volMin"],
        ["Vol max", "volMax"],
        ["Range min", "rangeMin"],
        ["Range max", "rangeMax"],
        ["Flips min", "flipMin"],
        ["Flips max", "flipMax"]
      ];

      numeric.forEach(([label, id]) => {
        const value = document.getElementById(id)?.value || "";
        if (value !== "") {
          lines.push("- " + label + ": " + value);
        }
      });

      if (!numeric.some(([, id]) => (document.getElementById(id)?.value || "") !== "")) {
        lines.push("- none");
      }

      lines.push("");
      lines.push("## Compare filters");
      lines.push("");

      if (typeof kcvCompareFilters !== "undefined" && kcvCompareFilters.length) {
        kcvCompareFilters.forEach((row, i) => {
          lines.push(
            "- " +
            (i + 1) +
            ". " +
            row.lhs +
            " " +
            row.op +
            " " +
            row.rhs
          );
        });
      } else {
        lines.push("- none");
      }

      lines.push("");
      lines.push("## Sort / view");
      lines.push("");
      lines.push("- Sort: " + (document.getElementById("sort")?.value || ""));
      lines.push("- Direction: " + (document.getElementById("dir")?.value || ""));
      lines.push("- View: " + (document.getElementById("view")?.value || ""));
      lines.push("");

      lines.push("## Dataset list");
      lines.push("");

      filtered.forEach((record) => {
        lines.push(
          "- " +
          (record.id || "") +
          " | " +
          (record.player_name || "") +
          " vs " +
          (record.opponent_name || "") +
          " | start " +
          (record.starting_price ?? "") +
          " -> end " +
          (record.ending_price ?? "")
        );
      });

      lines.push("");

      return lines.join("\n");
    }

    async function kczFetchFirst(paths, kind) {
      const tried = [];

      for (const path of paths.filter(Boolean)) {
        const url = enc(path);
        tried.push(url);

        try {
          const res = await fetch(url, { cache: "no-store" });

          if (!res.ok) {
            continue;
          }

          const bytes = new Uint8Array(await res.arrayBuffer());

          if (!bytes.length) {
            continue;
          }

          return {
            ok: true,
            path,
            url,
            bytes
          };
        } catch (error) {}
      }

      return {
        ok: false,
        kind,
        tried
      };
    }

    function kczCsvCandidates(record) {
      if (typeof csvCandidates === "function") {
        return csvCandidates(record);
      }

      const id = String(record.id || record.dataset_id || "").trim();
      const files = filesOf(record) || {};

      return [
        files.csv || "",
        record.csv || "",
        record.csv_file || "",
        record.csv_path || "",
        id ? "csvprice data/" + id + ".csv" : "",
        id ? "./csvprice data/" + id + ".csv" : "",
        id ? "csvprice%20data/" + id + ".csv" : "",
        id ? id + ".csv" : ""
      ].filter(Boolean);
    }

    function kczPngCandidates(record) {
      if (typeof pngCandidates === "function") {
        return pngCandidates(record);
      }

      const id = String(record.id || record.dataset_id || "").trim();
      const files = filesOf(record) || {};

      return [
        id ? "png charts/" + id + ".png" : "",
        id ? "./png charts/" + id + ".png" : "",
        files.png || "",
        record.png || "",
        record.png_file || "",
        record.png_path || ""
      ].filter(Boolean);
    }

    function kczDownloadBlob(blob, filename) {
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");

      a.href = url;
      a.download = filename;
      document.body.appendChild(a);
      a.click();

      setTimeout(() => {
        URL.revokeObjectURL(url);
        a.remove();
      }, 5000);
    }

    async function kczExportFilteredZip() {
      if (!filtered || !filtered.length) {
        alert("No filtered datasets to export.");
        return;
      }

      const count = filtered.length;

      if (count > 500) {
        const ok = confirm(
          "You are exporting " +
          count.toLocaleString() +
          " datasets. This may be large and can take a while. Continue?"
        );

        if (!ok) {
          return;
        }
      }

      const btn = document.getElementById("kczExportZipBtn");

      if (btn) {
        btn.disabled = true;
        btn.textContent = "Preparing ZIP…";
      }

      const entries = [];
      const missing = [];

      entries.push({
        name: "filters_applied.md",
        data: kczCurrentFilterSummary()
      });

      entries.push({
        name: "filtered_datasets.csv",
        data: kczDatasetCsv(filtered)
      });

      for (let i = 0; i < filtered.length; i++) {
        const record = filtered[i];
        const id = kczSanitizeFilename(record.id || ("dataset_" + i));

        if (btn) {
          btn.textContent =
            "Exporting " +
            (i + 1).toLocaleString() +
            " / " +
            filtered.length.toLocaleString();
        }

        const csvResult = await kczFetchFirst(kczCsvCandidates(record), "csv");

        if (csvResult.ok) {
          entries.push({
            name: "csv/" + id + ".csv",
            data: csvResult.bytes
          });
        } else {
          missing.push(
            id +
            " CSV missing. Tried: " +
            csvResult.tried.join(" | ")
          );
        }

        const pngResult = await kczFetchFirst(kczPngCandidates(record), "png");

        if (pngResult.ok) {
          entries.push({
            name: "png/" + id + ".png",
            data: pngResult.bytes
          });
        } else {
          missing.push(
            id +
            " PNG missing. Tried: " +
            pngResult.tried.join(" | ")
          );
        }

        if (i % 25 === 0) {
          await new Promise((resolve) => setTimeout(resolve, 10));
        }
      }

      entries.push({
        name: "missing_files.txt",
        data: missing.length
          ? missing.join("\n")
          : "No missing CSV or PNG files."
      });

      if (btn) {
        btn.textContent = "Building ZIP…";
      }

      const zip = kczCreateZip(entries);

      const stamp = new Date()
        .toISOString()
        .slice(0, 19)
        .replaceAll(":", "")
        .replace("T", "_");

      kczDownloadBlob(zip, "kchart_filtered_export_" + stamp + ".zip");

      if (btn) {
        btn.disabled = false;
        btn.textContent = "Export ZIP";
      }
    }

    function kczInstallExportButton() {
      if (document.getElementById("kczExportZipBtn")) {
        return;
      }

      const bar = document.querySelector(".summary-bar") || document.querySelector(".controls");

      if (!bar) {
        return;
      }

      const btn = document.createElement("button");
      btn.id = "kczExportZipBtn";
      btn.className = "primary";
      btn.textContent = "Export ZIP";
      btn.onclick = kczExportFilteredZip;

      bar.appendChild(btn);
    }

    kczInstallExportButton();
'''

    marker = "    loadData();"

    if marker not in s:
        raise SystemExit("Could not find loadData marker. Patch stopped.")

    s = s.replace(marker, patch + "\n\n" + marker)

    p.write_text(s, encoding="utf-8")

    print("PATCHED: Export ZIP button added to viewer.")
    print("ZIP includes filters_applied.md, filtered_datasets.csv, missing_files.txt, CSVs, and PNGs.")
