"""Placebo test for the put-short thesis.

Question: were SA's put-target names (NVDA, MU, TSMC, AVGO, CRWV, SMH, INFY)
already declining vs SPY *before* the disclosure date? If so, our post-event
short PnL is largely trend continuation we couldn't have captured cheaply,
not a true disclosure-driven effect.

For each put-event firm, compute SPY-adjusted cumulative return over:
  Pre-event:    [t-30, t-1], [t-20, t-1], [t-5, t-1]
  Post-event:   [t-1, t+1], [t-1, t+2]   (re-anchored at t-1 close for clean comparison)

Then apply the trend-exhaustion filter from Rule v2:
  Skip shorts where 20d SPY-adj return is NOT < -15%
  (i.e. only take the trade if the name was NOT already collapsing)

Re-compute thesis Sharpe both with and without that filter.
"""

import csv
import math
import statistics as st
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prices
from theses import load_holdings, issuer_state, basket_for_thesis, load_ticker_map, PRIOR_FOR
from filing_analysis import FILINGS

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
PERIODS = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]


def daily_index(bars, target_date):
    for i, b in enumerate(bars):
        if b["date"] >= target_date:
            return i
    return None


def cum_ret(bars, idx_start, idx_end):
    """Cumulative close-to-close return between bar indices [idx_start, idx_end]."""
    if idx_start is None or idx_end is None or idx_start >= len(bars) or idx_end >= len(bars):
        return None
    if idx_start < 0:
        return None
    a = bars[idx_start]["close"]
    b = bars[idx_end]["close"]
    if a is None or b is None: return None
    return b / a - 1


def main():
    holdings = load_holdings()
    tmap = load_ticker_map()

    # Build the universe of put-event firms across filings
    events = []
    for period in PERIODS:
        cfg = FILINGS[period]
        cur = issuer_state(holdings[period])
        prior = issuer_state(holdings[PRIOR_FOR[period]])
        basket = basket_for_thesis("S_NEW_puts_underlying", cur, prior)
        for r in basket:
            r["ticker"] = tmap.get(r["issuer_norm"]) or tmap.get(r["issuer_raw"].upper().strip())
        for r in basket:
            events.append({
                "filing": cfg["label"],
                "period": period,
                "trading_day": cfg["trading_day"],
                "ticker": r["ticker"],
                "issuer": r["issuer_raw"],
                "weight": r["weight"],
            })

    # Pull SPY daily for the whole horizon
    spy_daily = prices.get("SPY", "2025-04-01", "2026-04-30")

    # For each event firm, pull bars and compute pre/post windows
    fmt = lambda x: f"{100*x:+7.2f}%" if x is not None else "    n/a"
    print(f"\n{'Filing':<8s} {'Tkr':<6s} {'SA $':>10s} | "
          f"{'pre30':>8s} {'pre20':>8s} {'pre5':>8s} | "
          f"{'post1':>8s} {'post2':>8s} | "
          f"{'pre30 SPY-adj':>14s} {'pre20 SPY-adj':>14s} {'pre5 SPY-adj':>13s} | "
          f"{'post1 SPY-adj':>14s} {'post2 SPY-adj':>14s} | "
          f"{'filter':>8s}")

    for e in events:
        bars = prices.get(e["ticker"], "2025-04-01", "2026-04-30")
        i0 = daily_index(bars, e["trading_day"])
        i_spy = daily_index(spy_daily, e["trading_day"])
        if i0 is None or i_spy is None:
            print(f"{e['filing']:<8s} {e['ticker']:<6s}  no bars")
            continue
        # Reference is close at t-1 (last close before disclosure)
        # Pre windows look back from t-1
        # Post windows look forward from t-1 close
        # i0 is the index at trading_day (or first bar >=). i0-1 is t-1.
        idx_pre30 = i0 - 30
        idx_pre20 = i0 - 20
        idx_pre5 = i0 - 5
        idx_t_minus_1 = i0 - 1
        # Post-event close points
        idx_post1 = i0 + 1   # close of t+1 (NB i0 is close of t)
        idx_post2 = i0 + 2

        def s(a, b): return cum_ret(bars, a, b)
        def sp(a, b): return cum_ret(spy_daily, daily_index(spy_daily, e["trading_day"]) + a - i0,
                                                 daily_index(spy_daily, e["trading_day"]) + b - i0)
        # Stock returns (close-to-close)
        r_pre30 = s(idx_pre30, idx_t_minus_1)
        r_pre20 = s(idx_pre20, idx_t_minus_1)
        r_pre5  = s(idx_pre5,  idx_t_minus_1)
        r_post1 = s(idx_t_minus_1, idx_post1)
        r_post2 = s(idx_t_minus_1, idx_post2)

        # SPY returns at same windows
        sp_pre30 = sp(i0 - 30, i0 - 1)
        sp_pre20 = sp(i0 - 20, i0 - 1)
        sp_pre5  = sp(i0 - 5,  i0 - 1)
        sp_post1 = sp(i0 - 1, i0 + 1)
        sp_post2 = sp(i0 - 1, i0 + 2)

        adj = lambda r, m: (r - m) if (r is not None and m is not None) else None
        pre30_adj = adj(r_pre30, sp_pre30)
        pre20_adj = adj(r_pre20, sp_pre20)
        pre5_adj  = adj(r_pre5,  sp_pre5)
        post1_adj = adj(r_post1, sp_post1)
        post2_adj = adj(r_post2, sp_post2)

        # Trend-exhaustion filter (Rule v2): take the SHORT only if 20d SPY-adj is NOT below -15%
        # i.e. skip when stock has already collapsed
        passes = (pre20_adj is not None) and (pre20_adj > -0.15)

        e["pre30_adj"]  = pre30_adj
        e["pre20_adj"]  = pre20_adj
        e["pre5_adj"]   = pre5_adj
        e["post1_adj"]  = post1_adj
        e["post2_adj"]  = post2_adj
        e["passes_filter"] = passes
        # Short PnL = -stock return; SPY-adj short PnL = SPY - stock = -(stock-SPY) = -post1_adj
        e["short_pnl_post1_spy_adj"] = -post1_adj if post1_adj is not None else None
        e["short_pnl_post2_spy_adj"] = -post2_adj if post2_adj is not None else None

        print(f"{e['filing']:<8s} {e['ticker']:<6s} ${e['weight']/1e6:>8.0f}M | "
              f"{fmt(r_pre30):>8} {fmt(r_pre20):>8} {fmt(r_pre5):>8} | "
              f"{fmt(r_post1):>8} {fmt(r_post2):>8} | "
              f"{fmt(pre30_adj):>14} {fmt(pre20_adj):>14} {fmt(pre5_adj):>13} | "
              f"{fmt(post1_adj):>14} {fmt(post2_adj):>14} | "
              f"{'PASS' if passes else 'SKIP':>8s}")

    # Aggregate stats
    print(f"\n=== Trend-exhaustion filter result ===")
    pass_events = [e for e in events if e.get("passes_filter")]
    skip_events = [e for e in events if not e.get("passes_filter")]
    print(f"PASS (would trade):  {len(pass_events)}/{len(events)}")
    for e in pass_events:
        print(f"   {e['filing']} {e['ticker']}: pre20 SPY-adj = {fmt(e['pre20_adj'])}, post1 short PnL = {fmt(e['short_pnl_post1_spy_adj'])}")
    print(f"SKIP (filter rejects): {len(skip_events)}/{len(events)}")
    for e in skip_events:
        print(f"   {e['filing']} {e['ticker']}: pre20 SPY-adj = {fmt(e['pre20_adj'])}, post1 short PnL would have been {fmt(e['short_pnl_post1_spy_adj'])}")

    # Compare unfiltered vs filtered Sharpe
    def sharpe(vals):
        vals = [v for v in vals if v is not None]
        if len(vals) < 2: return None, None, None, len(vals)
        m = st.mean(vals); s = st.stdev(vals)
        return m, s, (m / s if s else None), len(vals)

    print(f"\n=== Pre-event vs post-event SPY-adjusted return magnitudes ===")
    pre20_pnl = [-e["pre20_adj"] for e in events if e["pre20_adj"] is not None]  # short PnL = -stock_adj
    pre5_pnl  = [-e["pre5_adj"]  for e in events if e["pre5_adj"]  is not None]
    post1_pnl = [e["short_pnl_post1_spy_adj"] for e in events if e["short_pnl_post1_spy_adj"] is not None]
    post2_pnl = [e["short_pnl_post2_spy_adj"] for e in events if e["short_pnl_post2_spy_adj"] is not None]

    for label, vals in [("pre [t-20, t-1] short PnL", pre20_pnl),
                        ("pre [t-5, t-1] short PnL ", pre5_pnl),
                        ("post [t-1, t+1] short PnL", post1_pnl),
                        ("post [t-1, t+2] short PnL", post2_pnl)]:
        if vals:
            m = st.mean(vals); s = st.stdev(vals) if len(vals) > 1 else 0
            print(f"  {label}: N={len(vals)}  mean={100*m:+6.2f}%  sd={100*s:5.2f}%")

    print(f"\n=== Sharpe estimates (per firm-event) ===")
    print(f"{'Configuration':<40s} {'N':>4s} {'Mean':>8s} {'SD':>8s} {'Sharpe':>8s}")
    for label, vals in [
        ("Unfiltered, post1 short PnL",    post1_pnl),
        ("Unfiltered, post2 short PnL",    post2_pnl),
        ("Filter PASS only, post1",        [e["short_pnl_post1_spy_adj"] for e in pass_events if e["short_pnl_post1_spy_adj"] is not None]),
        ("Filter PASS only, post2",        [e["short_pnl_post2_spy_adj"] for e in pass_events if e["short_pnl_post2_spy_adj"] is not None]),
        ("Filter SKIP only, post1 (counterfactual)", [e["short_pnl_post1_spy_adj"] for e in skip_events if e["short_pnl_post1_spy_adj"] is not None]),
    ]:
        m, s, sr, n = sharpe(vals)
        if n < 2:
            print(f"  {label:<40s} {n:>4d} {'n/a':>8s} {'n/a':>8s} {'n/a':>8s}")
        else:
            print(f"  {label:<40s} {n:>4d} {100*m:+7.2f}% {100*s:>7.2f}% {sr:>+7.2f}")

    # Save CSV
    out = RESULTS / "placebo_puts.csv"
    cols = ["filing", "ticker", "issuer", "weight",
            "pre30_adj", "pre20_adj", "pre5_adj",
            "post1_adj", "post2_adj",
            "short_pnl_post1_spy_adj", "short_pnl_post2_spy_adj",
            "passes_filter"]
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for e in events:
            w.writerow({k: e.get(k) for k in cols})
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
