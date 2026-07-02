from pathlib import Path

p = Path("index.html")

if not p.exists():
    raise SystemExit("index.html not found. Run this from the repo root.")

s = p.read_text(encoding="utf-8")

patch = r'''
    /*
      PNG preference patch:
      - Prefer generated chart files at png charts/<id>.png
      - Fall back to any existing PNG path already stored in the manifest
      - Prevent hard 404s when the manifest PNG path is stale
    */

    function patchedPngCandidates(record) {
      const id = String(record.id || record.dataset_id || "").trim();
      const files = filesOf(record) || {};

      const candidates = [
        id ? "png charts/" + id + ".png" : "",
        id ? "./png charts/" + id + ".png" : "",
        files.png || "",
        record.png || "",
        record.png_file || "",
        record.png_path || "",
        id ? "png charts/" + id + "_trimmed.png" : "",
        id ? "png charts/" + id + "_untrimmed.png" : "",
        id ? "png charts/" + id + "-trimmed.png" : "",
        id ? "png charts/" + id + "-untrimmed.png" : "",
        id ? "charts/" + id + ".png" : "",
        id ? "png/" + id + ".png" : ""
      ].filter(Boolean);

      return [...new Set(candidates)];
    }

    pngCandidates = patchedPngCandidates;

    function patchedFileLinks(record) {
      const files = filesOf(record);

      return `
        ${files.csv ? `<a href="${enc(files.csv)}">CSV</a>` : ""}
        ${files.json ? `<a href="${enc(files.json)}">JSON</a>` : ""}
        ${files.npy ? `<a href="${enc(files.npy)}">NPY</a>` : ""}
        <button class="linkbtn" onclick="openBestPng('${esc(record.id)}')">PNG</button>
      `;
    }

    fileLinks = patchedFileLinks;

    async function patchedOpenBestPng(id) {
      const record = data.find((r) => String(r.id) === String(id));

      if (!record) {
        alert("Record not found.");
        return;
      }

      for (const path of patchedPngCandidates(record)) {
        const url = enc(path);

        if (await imageExists(url)) {
          window.open(url, "_blank");
          return;
        }
      }

      alert("PNG not found for " + id + ". Generate PNG charts, commit them, and push.");
    }

    openBestPng = patchedOpenBestPng;
'''

marker = "    loadData();"

if marker not in s:
    raise SystemExit("Could not find loadData marker. Patch stopped.")

if "PNG preference patch:" not in s:
    s = s.replace(marker, patch + "\n\n" + marker)

p.write_text(s, encoding="utf-8")

print("PATCHED index.html: viewer now prefers png charts/<id>.png")
