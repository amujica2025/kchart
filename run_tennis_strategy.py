#!/usr/bin/env python3
"""
Simple Kalshi Tennis Both-Sides Strategy Backtester
Place this file in your "tennis matches" folder and run from PowerShell:

    python run_tennis_strategy.py

It will scan for all kalshi-price-history-*-minute.csv files in the current folder
and simulate the strategy on each side it finds.

Strategy: Buy Yes at first observed price, exit at +10% TP or 50% trailing stop,
otherwise hold to the last observed price (proxy for resolution).

This version processes each file as ONE side. For full both-sides results you will
need to pair files that belong to the same match (same date + match id).

Requirements:
    pip install pandas

Author: Grok (optimized for your workflow)
"""

import os
import glob
import pandas as pd
from dataclasses import dataclass
from typing import List, Dict, Optional

# ================== CONFIG ==================
TP_PCT = 0.10          # 10% take profit
TRAIL_PCT = 0.50       # 50% trailing stop (of the peak gain)
MIN_FILES_TO_PROCESS = 1
OUTPUT_CSV = "tennis_strategy_results.csv"
# ============================================

@dataclass
class TradeResult:
    filename: str
    entry_price: float
    exit_price: float
    exit_reason: str          # "TP", "TRAILING_STOP", "HELD_TO_END"
    pnl: float                # in dollars per $1 contract
    peak_price: float
    num_observations: int


def simulate_strategy(prices: List[float], tp_pct: float = TP_PCT, trail_pct: float = TRAIL_PCT) -> TradeResult:
    """
    Simulate the strategy on a list of prices (chronological).
    Returns the outcome for one Yes contract.
    """
    if not prices or len(prices) < 2:
        return TradeResult("", 0, 0, "INVALID", 0, 0, 0)

    entry = prices[0]
    peak = entry
    position_open = True

    for price in prices[1:]:
        if not position_open:
            break

        # Update peak
        if price > peak:
            peak = price

        # Check Take Profit first
        if price >= entry * (1 + tp_pct):
            pnl = (price - entry) / entry   # return as fraction, then * $1
            return TradeResult("", entry, price, "TP", pnl, peak, len(prices))

        # Check Trailing Stop (only if in profit)
        if peak > entry:
            drawdown_from_peak = (peak - price) / (peak - entry)
            if drawdown_from_peak >= trail_pct:
                pnl = (price - entry) / entry
                return TradeResult("", entry, price, "TRAILING_STOP", pnl, peak, len(prices))

    # Never exited early → hold to last observed price (proxy for resolution)
    final_price = prices[-1]
    pnl = (final_price - entry) / entry
    return TradeResult("", entry, final_price, "HELD_TO_END", pnl, peak, len(prices))


def process_file(filepath: str) -> Optional[TradeResult]:
    """Load one minute history file and run the strategy."""
    try:
        df = pd.read_csv(filepath)

        # Try common column names for price
        price_col = None
        for col in ["price", "yes_price", "last_price", "close", "value"]:
            if col in df.columns:
                price_col = col
                break

        if price_col is None:
            print(f"  ⚠️  Skipping {os.path.basename(filepath)} — no recognized price column")
            return None

        prices = df[price_col].dropna().astype(float).tolist()

        if len(prices) < 2:
            return None

        result = simulate_strategy(prices)
        result.filename = os.path.basename(filepath)
        return result

    except Exception as e:
        print(f"  ❌ Error processing {os.path.basename(filepath)}: {e}")
        return None


def main():
    print("=" * 70)
    print("KALSHI TENNIS STRATEGY BACKTESTER")
    print("Both-Sides 10% TP + 50% Trailing Stop (No Price Filter)")
    print("=" * 70)

    # Find all minute CSV files in current directory
    csv_files = glob.glob("kalshi-price-history-*-minute.csv")

    if not csv_files:
        print("\nNo files matching 'kalshi-price-history-*-minute.csv' found in this folder.")
        print("Make sure you are running this script from inside your 'tennis matches' folder.")
        return

    print(f"\nFound {len(csv_files)} match files. Processing...\n")

    results: List[TradeResult] = []

    for i, f in enumerate(csv_files, 1):
        if i % 500 == 0:
            print(f"  Processed {i}/{len(csv_files)} files...")

        res = process_file(f)
        if res:
            results.append(res)

    if not results:
        print("No valid results. Check that your CSV files have a 'price' column.")
        return

    # Summary statistics
    total_contracts = len(results)
    total_pnl = sum(r.pnl for r in results)
    roi = (total_pnl / total_contracts) * 100 if total_contracts > 0 else 0

    tp_count = sum(1 for r in results if r.exit_reason == "TP")
    trail_count = sum(1 for r in results if r.exit_reason == "TRAILING_STOP")
    held_count = sum(1 for r in results if r.exit_reason == "HELD_TO_END")

    avg_pnl = total_pnl / total_contracts

    print("\n" + "=" * 70)
    print("RESULTS SUMMARY")
    print("=" * 70)
    print(f"Contracts processed:     {total_contracts}")
    print(f"Total P&L (per $1):      ${total_pnl:,.2f}")
    print(f"Average P&L per contract: ${avg_pnl:,.4f}")
    print(f"ROI:                      {roi:.2f}%")
    print()
    print(f"Exited at +10% TP:        {tp_count} ({tp_count/total_contracts*100:.1f}%)")
    print(f"Stopped via 50% trail:    {trail_count} ({trail_count/total_contracts*100:.1f}%)")
    print(f"Held to end:              {held_count} ({held_count/total_contracts*100:.1f}%)")
    print("=" * 70)

    # Save detailed results
    df_out = pd.DataFrame([{
        "filename": r.filename,
        "entry_price": round(r.entry_price, 2),
        "exit_price": round(r.exit_price, 2),
        "exit_reason": r.exit_reason,
        "pnl_dollars": round(r.pnl, 4),
        "peak_price": round(r.peak_price, 2),
        "observations": r.num_observations
    } for r in results])

    df_out.to_csv(OUTPUT_CSV, index=False)
    print(f"\nDetailed trade log saved to: {OUTPUT_CSV}")

    print("\nNOTE: This script currently treats each file as ONE side of a match.")
    print("For true both-sides backtesting you need to pair files that belong to the same match.")
    print("Reply with 'pair the files' if you want me to enhance the script with automatic pairing logic.")


if __name__ == "__main__":
    main()