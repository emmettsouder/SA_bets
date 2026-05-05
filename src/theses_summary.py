"""Summarize thesis_grid.csv into a clean per-thesis pooled table."""

import csv
import statistics as st
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
GRID = ROOT / "results" / "thesis_grid.csv"

rows = list(csv.DictReader(open(GRID)))


def pf(x):
    if not x: return None
    return float(x)


# Pool by thesis
by_thesis = {}
for r in rows:
    by_thesis.setdefault(r["thesis"], []).append(r)

# Compute pooled stats per thesis
def stats(vals):
    vals = [v for v in vals if v is not None]
    if not vals:
        return None, None, 0, 0
    mean = st.mean(vals)
    pos = sum(1 for v in vals if v > 0)
    return mean, vals, len(vals), pos


print(f"\n{'Thesis':<48s} {'Side':<5s} {'Filings':>8s} | {'1h SPY':>10s} {'D+1 SPY':>10s} {'D+2 SPY':>10s}  {'Win@D+1':>9s} {'Win@D+2':>9s}")
print("-" * 130)

ranked = []
for thesis, rs in by_thesis.items():
    side = rs[0]["side"]
    spy_1h_vals = [pf(r["spy_1h"]) for r in rs]
    spy_d1_vals = [pf(r["spy_D+1"]) for r in rs]
    spy_d2_vals = [pf(r["spy_D+2"]) for r in rs]
    m1, _, n1, _ = stats(spy_1h_vals)
    md1, vd1, nd1, posd1 = stats(spy_d1_vals)
    md2, vd2, nd2, posd2 = stats(spy_d2_vals)
    fmt = lambda x: f"{100*x:+7.2f}%" if x is not None else "    n/a"
    win = lambda p, n: f"{p}/{n}" if n else " 0/0"
    print(f"{thesis:<48s} {side:<5s} {nd1:>8d} | {fmt(m1):>10s} {fmt(md1):>10s} {fmt(md2):>10s}  {win(posd1, nd1):>9s} {win(posd2, nd2):>9s}")
    ranked.append((thesis, side, md1 or 0, md2 or 0, nd1, posd1, posd2))

print("\nSorted by D+1 SPY-adj mean:")
print("-" * 130)
print(f"{'Thesis':<48s} {'Side':<5s} {'N filings':>10s} | {'D+1 SPY mean':>14s} {'Win rate D+1':>14s}")
for thesis, side, md1, md2, n, p1, p2 in sorted(ranked, key=lambda x: -x[2]):
    print(f"{thesis:<48s} {side:<5s} {n:>10d} | {100*md1:+11.2f}%   {p1}/{n}")
