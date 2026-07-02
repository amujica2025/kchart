# KChart Data Instructions

This dataset converts Kalshi tennis match XLSX workbooks into player-level price datasets.

## Structure

Each original workbook = one match.

Each match creates two player datasets:

- one CSV
- one JSON
- one NPY

## Folders

csvprice data/
Player-level CSV files.

json data/
Player-level JSON metadata files.

npy data/
Player-level NumPy files.

png charts/
Optional chart images.

## Master files

master_player_manifest.csv
Flat searchable index of all player datasets.

master_player_index.json
Structured index for LLM agents and scripts.

## CSV columns

timestamp
player_price
opponent_price
tags
volatility_score
max_single_move
direction_flips
range_points
crossings_25
crossings_50
crossings_75
first_cross_50_pct

## Tags

Tags include player name, opponent name, favorite/underdog status, winner/loser, starting price, ending price, price bucket, sets, tiebreakers, volatility, shape, reversals, threshold crossings, comeback/collapse patterns, and other searchable labels.

## Important note

Winner, loser, ending price, and final score are historical labels only.

Do not use them as live-entry triggers.

Live strategy rules should only use data available at that moment:

- current price
- prior prices
- rolling volatility
- rolling slope
- crossings
- reversals
- current trend

## Goal

The goal is not to predict match winners.

The goal is to identify repeatable price behavior before large repricing events so those patterns can become automated entry and exit rules.
