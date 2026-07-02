#!/usr/bin/env python3
from __future__ import annotations

import csv
import json
import shutil
import subprocess
import sys
from pathlib import Path

BASE = Path(r"C:\Users\alexm\Downloads\kbot\my-kalshi-app\csv data\match_price_history")
REPO = "kchart"
BRANCH = "main"

REQUIRED = [
    "csvprice data",
    "json data",
    "npy data",
    "master_player_manifest.csv",
    "master_player_index.json",
    "KCHART_DATA_INSTRUCTIONS.md",
]

def run(cmd, cwd=BASE):
    print("+ " + " ".join(cmd))
    subprocess.run(cmd, cwd=str(cwd), check=True, text=True)

def capture(cmd, cwd=BASE):
    print("+ " + " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(cwd), check=True, text=True, stdout=subprocess.PIPE)
    return result.stdout.strip()

def require_tool(name):
    if shutil.which(name) is None:
        print(f"Missing tool: {name}")
        sys.exit(1)

def validate():
    missing = []
    for item in REQUIRED:
        if not (BASE / item).exists():
            missing.append(item)
    if missing:
        print("Missing required files/folders:")
        for x in missing:
            print(" -", x)
        sys.exit(1)

def gh_owner():
    return capture(["gh", "api", "user", "-q", ".login"])

def repo_exists(owner):
    result = subprocess.run(
        ["gh", "repo", "view", f"{owner}/{REPO}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        text=True,
    )
    return result.returncode == 0

def create_repo(owner):
    if repo_exists(owner):
        print(f"Repo exists: {owner}/{REPO}")
    else:
        run(["gh", "repo", "create", f"{owner}/{REPO}", "--public"])

def write_gallery():
    manifest = BASE / "master_player_manifest.csv"
    rows = []
    with manifest.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for r in reader:
            rows.append(r)

    tag_set = set()
    for r in rows:
        for t in str(r.get("tags", "")).split("|"):
            if t:
                tag_set.add(t)

    (BASE / "gallery_data.json").write_text(json.dumps(rows), encoding="utf-8")
    (BASE / "gallery_tags.json").write_text(json.dumps(sorted(tag_set)), encoding="utf-8")

    html = r'''<!doctype html>
<html>
<head>
  <meta charset="utf-8">
  <title>KChart Player Dataset Gallery</title>
  <style>
    body { margin:0; background:#0d1117; color:#e5e7eb; font-family:Arial, sans-serif; }
    header { position:sticky; top:0; z-index:10; background:#111827; border-bottom:1px solid #374151; padding:12px; }
    input, select, button { background:#0d1117; color:#e5e7eb; border:1px solid #374151; border-radius:6px; padding:7px; margin:3px; }
    button { cursor:pointer; }
    .stats { color:#9ca3af; font-size:13px; margin-top:6px; }
    .wrap { display:grid; grid-template-columns: 330px 1fr; min-height:100vh; }
    aside { border-right:1px solid #374151; padding:12px; overflow:auto; max-height:calc(100vh - 70px); position:sticky; top:70px; }
    main { padding:12px; }
    .tag { display:inline-block; padding:4px 7px; margin:3px; border:1px solid #374151; border-radius:999px; font-size:12px; color:#cbd5e1; cursor:pointer; }
    .tag.active { background:#2563eb; color:white; }
    table { width:100%; border-collapse:collapse; font-size:13px; }
    th, td { border-bottom:1px solid #1f2937; padding:6px; text-align:left; vertical-align:top; }
    th { position:sticky; top:70px; background:#111827; cursor:pointer; }
    tr:hover { background:#111827; }
    a { color:#93c5fd; text-decoration:none; }
    .tags-cell { max-width:450px; color:#9ca3af; }
  </style>
</head>
<body>
<header>
  <strong>KChart Player Dataset Gallery</strong>
  <input id="q" placeholder="Search player, id, workbook, tag..." oninput="applyFilters()">
  <select id="winnerFilter" onchange="applyFilters()">
    <option value="">winner/loser</option>
    <option value="winner">winner</option>
    <option value="loser">loser</option>
  </select>
  <select id="sideFilter" onchange="applyFilters()">
    <option value="">favorite/underdog</option>
    <option value="heavy_favorite">heavy favorite</option>
    <option value="favorite">favorite</option>
    <option value="slight_favorite">slight favorite</option>
    <option value="slight_underdog">slight underdog</option>
    <option value="underdog">underdog</option>
    <option value="heavy_underdog">heavy underdog</option>
  </select>
  <select id="setsFilter" onchange="applyFilters()">
    <option value="">sets</option>
    <option value="2_sets">2 sets</option>
    <option value="3_sets">3 sets</option>
  </select>
  <button onclick="clearFilters()">Clear</button>
  <a href="master_player_manifest.csv">manifest.csv</a>
  <a href="master_player_index.json">index.json</a>
  <a href="KCHART_DATA_INSTRUCTIONS.md">instructions</a>
  <div class="stats" id="stats"></div>
</header>

<div class="wrap">
  <aside>
    <h3>Tags</h3>
    <div id="tagBox"></div>
  </aside>
  <main>
    <table id="tbl">
      <thead>
        <tr>
          <th onclick="sortBy('id')">id</th>
          <th onclick="sortBy('player_name')">player</th>
          <th onclick="sortBy('opponent_name')">opponent</th>
          <th onclick="sortByNum('starting_price')">start</th>
          <th onclick="sortByNum('ending_price')">end</th>
          <th onclick="sortByNum('volatility_score')">vol</th>
          <th onclick="sortByNum('range_points')">range</th>
          <th>files</th>
          <th>tags</th>
        </tr>
      </thead>
      <tbody></tbody>
    </table>
  </main>
</div>

<script>
let data = [];
let tags = [];
let activeTags = new Set();
let filtered = [];
let sortKey = "id";
let sortAsc = true;

async function load() {
  data = await (await fetch("gallery_data.json")).json();
  tags = await (await fetch("gallery_tags.json")).json();
  renderTags();
  applyFilters();
}

function renderTags() {
  const box = document.getElementById("tagBox");
  box.innerHTML = "";
  for (const t of tags) {
    const span = document.createElement("span");
    span.className = "tag";
    span.textContent = t;
    span.onclick = () => {
      if (activeTags.has(t)) activeTags.delete(t);
      else activeTags.add(t);
      span.classList.toggle("active");
      applyFilters();
    };
    box.appendChild(span);
  }
}

function rowTags(r) {
  return String(r.tags || "").split("|").filter(Boolean);
}

function hasTag(r, t) {
  return rowTags(r).includes(t);
}

function applyFilters() {
  const q = document.getElementById("q").value.toLowerCase().trim();
  const wf = document.getElementById("winnerFilter").value;
  const sf = document.getElementById("sideFilter").value;
  const setf = document.getElementById("setsFilter").value;

  filtered = data.filter(r => {
    const all = JSON.stringify(r).toLowerCase();
    if (q && !all.includes(q)) return false;
    if (wf && !hasTag(r, wf)) return false;
    if (sf && !hasTag(r, sf)) return false;
    if (setf && !hasTag(r, setf)) return false;
    for (const t of activeTags) {
      if (!hasTag(r, t)) return false;
    }
    return true;
  });

  doSort();
  renderTable();
}

function clearFilters() {
  document.getElementById("q").value = "";
  document.getElementById("winnerFilter").value = "";
  document.getElementById("sideFilter").value = "";
  document.getElementById("setsFilter").value = "";
  activeTags.clear();
  for (const e of document.querySelectorAll(".tag")) e.classList.remove("active");
  applyFilters();
}

function sortBy(k) {
  sortKey = k;
  sortAsc = !sortAsc;
  doSort();
  renderTable();
}

function sortByNum(k) {
  sortKey = k;
  sortAsc = !sortAsc;
  filtered.sort((a,b) => (Number(a[k]) || 0) - (Number(b[k]) || 0));
  if (!sortAsc) filtered.reverse();
  renderTable();
}

function doSort() {
  filtered.sort((a,b) => String(a[sortKey] || "").localeCompare(String(b[sortKey] || "")));
  if (!sortAsc) filtered.reverse();
}

function renderTable() {
  document.getElementById("stats").textContent = `${filtered.length.toLocaleString()} of ${data.length.toLocaleString()} player datasets`;
  const tbody = document.querySelector("#tbl tbody");
  tbody.innerHTML = "";

  for (const r of filtered.slice(0, 1000)) {
    const tr = document.createElement("tr");
    tr.innerHTML = `
      <td>${r.id || ""}</td>
      <td>${r.player_name || ""}</td>
      <td>${r.opponent_name || ""}</td>
      <td>${r.starting_price || ""}</td>
      <td>${r.ending_price || ""}</td>
      <td>${r.volatility_score || ""}</td>
      <td>${r.range_points || ""}</td>
      <td>
        <a href="${r.csv_file || "#"}">csv</a>
        <a href="${r.json_file || "#"}">json</a>
        <a href="${r.npy_file || "#"}">npy</a>
        ${r.png_file ? `<a href="${r.png_file}">png</a>` : ""}
      </td>
      <td class="tags-cell">${r.tags || ""}</td>
    `;
    tbody.appendChild(tr);
  }

  if (filtered.length > 1000) {
    const tr = document.createElement("tr");
    tr.innerHTML = `<td colspan="9">Showing first 1,000 rows. Narrow filters to see more.</td>`;
    tbody.appendChild(tr);
  }
}

load();
</script>
</body>
</html>
'''
    (BASE / "index.html").write_text(html, encoding="utf-8")
    print("Gallery files written.")

def git_push(owner):
    if not (BASE / ".git").exists():
        run(["git", "init"])

    remote = f"https://github.com/{owner}/{REPO}.git"

    result = subprocess.run(["git", "remote", "get-url", "origin"], cwd=str(BASE), text=True, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
    if result.returncode == 0:
        run(["git", "remote", "set-url", "origin", remote])
    else:
        run(["git", "remote", "add", "origin", remote])

    run(["git", "checkout", "-B", BRANCH])
    run(["git", "add", "."])
    status = capture(["git", "status", "--porcelain"])
    if status:
        run(["git", "commit", "-m", "Refresh tagged KChart dataset and searchable gallery"])
    else:
        print("No changes to commit.")
    run(["git", "push", "-u", "origin", BRANCH])

def main():
    require_tool("git")
    require_tool("gh")
    validate()
    owner = gh_owner()
    create_repo(owner)
    write_gallery()
    git_push(owner)
    print()
    print("DONE")
    print(f"Repo: https://github.com/{owner}/{REPO}")
    print(f"Gallery: https://{owner}.github.io/{REPO}/")

if __name__ == "__main__":
    main()
