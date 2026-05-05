"""Compute Sharpe-like statistics for the 'short underlying of NEW puts' thesis.

Sharpe is fragile with N=3 filings or N=7 firm-events. Report multiple framings
so the user can see exactly how thin the sample is, and how the answer moves
when we strip the INFY outlier.
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


def find_intraday_bar(bars, target_date, target_et_hhmm):
    for b in bars:
        if b["ts_utc"][:10] != target_date: continue
        et = datetime.fromisoformat(b["ts_utc"].replace("Z", "+00:00")) - timedelta(hours=5)
        if et.strftime("%H:%M") >= target_et_hhmm:
            return b
    return None


def daily_at_offset(bars, from_date, n):
    idx = next((i for i, b in enumerate(bars) if b["date"] >= from_date), None)
    if idx is None or idx + n >= len(bars): return None
    return bars[idx + n]


def main():
    holdings = load_holdings()
    tmap = load_ticker_map()

    # Build the per-firm-event return list
    events = []  # each: {filing, ticker, weight, raw_d1, spy_d1, short_pnl_spy_adj}

    # Pull SPY price data once
    spy_intraday = prices.get_intraday("SPY", "2025-05-12", "2026-02-15", "60m")
    spy_daily = prices.get("SPY", "2025-05-10", "2026-02-20")

    for period in PERIODS:
        cfg = FILINGS[period]
        cur = issuer_state(holdings[period])
        prior = issuer_state(holdings[PRIOR_FOR[period]])
        basket = basket_for_thesis("S_NEW_puts_underlying", cur, prior)
        if not basket:
            continue
        for r in basket:
            r["ticker"] = tmap.get(r["issuer_norm"]) or tmap.get(r["issuer_raw"].upper().strip())

        # SPY return at the same D+1 horizon (intraday-entry → close day +1)
        spy_eb = find_intraday_bar(spy_intraday, cfg["trading_day"], cfg["entry_et"])
        spy_d1 = daily_at_offset(spy_daily, cfg["trading_day"], 1)
        spy_ret = (spy_d1["close"] / spy_eb["open"] - 1) if spy_eb and spy_d1 else None

        for r in basket:
            tkr = r["ticker"]
            if not tkr: continue
            ib = prices.get_intraday(tkr, "2025-05-12", "2026-02-15", "60m")
            db = prices.get(tkr, "2025-05-10", "2026-02-20")
            eb = find_intraday_bar(ib, cfg["trading_day"], cfg["entry_et"])
            xb = daily_at_offset(db, cfg["trading_day"], 1)
            if not eb or not xb or eb["open"] is None or xb["close"] is None: continue
            stock_ret = xb["close"] / eb["open"] - 1
            short_pnl = -stock_ret  # short = profit if stock falls
            short_pnl_spy_adj = short_pnl - (-spy_ret) if spy_ret is not None else None
            # Equivalently: spy_ret - stock_ret
            events.append({
                "filing": cfg["label"],
                "ticker": tkr,
                "issuer": r["issuer_raw"],
                "weight": r["weight"],
                "raw_stock_d1": stock_ret,
                "spy_d1": spy_ret,
                "short_pnl_d1": short_pnl,
                "short_pnl_spy_adj": short_pnl_spy_adj,
            })

    print(f"\n=== Per-firm-event detail (D+1 SPY-adjusted short PnL) ===\n")
    print(f"{'Filing':<10s} {'Ticker':<7s} {'Issuer':<32s} {'Weight $':>15s} {'Stock D+1':>10s} {'SPY D+1':>10s} {'Short PnL':>11s} {'PnL−SPY':>10s}")
    for e in events:
        print(f"{e['filing']:<10s} {e['ticker']:<7s} {e['issuer'][:32]:<32s} ${e['weight']:>14,.0f} "
              f"{100*e['raw_stock_d1']:+9.2f}% {100*e['spy_d1']:+9.2f}% "
              f"{100*e['short_pnl_d1']:+10.2f}% {100*e['short_pnl_spy_adj']:+9.2f}%")

    # --- Statistics ---
    spy_adj_returns = [e["short_pnl_spy_adj"] for e in events]
    weights = [e["weight"] for e in events]

    def sharpe_stats(vals, label):
        if len(vals) < 2:
            print(f"  {label}: N={len(vals)} (insufficient for Sharpe)")
            return
        m = st.mean(vals)
        s = st.stdev(vals)
        sr = m / s if s else float("inf")
        print(f"  {label}: N={len(vals)}  mean={100*m:+.2f}%  sd={100*s:.2f}%  per-trade Sharpe={sr:.2f}")
        return m, s, sr

    print(f"\n=== Sharpe — per firm-event (each name = one trade) ===\n")
    print("All events:")
    sharpe_stats(spy_adj_returns, "Equal-weight per-event")

    # Weighted
    tw = sum(weights)
    wmean = sum(w * r for w, r in zip(weights, spy_adj_returns)) / tw
    # Weighted SD
    wvar = sum(w * (r - wmean) ** 2 for w, r in zip(weights, spy_adj_returns)) / tw
    wsd = math.sqrt(wvar)
    wsr = wmean / wsd if wsd else 0
    print(f"  Weighted by SA put notional: mean={100*wmean:+.2f}%  sd={100*wsd:.2f}%  per-trade Sharpe={wsr:.2f}")

    # Strip INFY outlier
    no_infy = [e["short_pnl_spy_adj"] for e in events if e["ticker"] != "INFY"]
    print("\nExcluding INFY (Q4 outlier, single-name idiosyncratic):")
    sharpe_stats(no_infy, "Equal-weight per-event ex-INFY")

    # --- Per-filing basket Sharpe ---
    print(f"\n=== Sharpe — per filing (each filing = one trade event for the basket) ===\n")
    by_filing = defaultdict(list)
    by_filing_w = defaultdict(list)
    for e in events:
        by_filing[e["filing"]].append(e["short_pnl_spy_adj"])
        by_filing_w[e["filing"]].append((e["weight"], e["short_pnl_spy_adj"]))

    filing_basket_returns = []
    for f, vals_w in by_filing_w.items():
        tw_f = sum(w for w, _ in vals_w)
        bret = sum(w * r for w, r in vals_w) / tw_f
        filing_basket_returns.append((f, bret))
        print(f"  {f}: basket return (weighted) = {100*bret:+.2f}%  (N_names={len(vals_w)})")
    vals = [r for _, r in filing_basket_returns]
    if len(vals) >= 2:
        m = st.mean(vals); s = st.stdev(vals); sr = m/s if s else float("inf")
        print(f"\n  Across {len(vals)} filings: mean={100*m:+.2f}%  sd={100*s:.2f}%  per-filing Sharpe={sr:.2f}")
        # Annualize: filings come 4/year, but only some have new puts (3 of 4 historical)
        events_per_year = 4 * (3/4)  # ~3 deployments per year based on history
        ann_sr = sr * math.sqrt(events_per_year)
        print(f"  Annualized Sharpe (assuming {events_per_year:.1f} deployments/year): {ann_sr:.2f}")
        # Stripping Q4 outlier
        vals_no_q4 = [r for f, r in filing_basket_returns if f != "Q4 2025"]
        if len(vals_no_q4) >= 2:
            m2 = st.mean(vals_no_q4); s2 = st.stdev(vals_no_q4); sr2 = m2/s2 if s2 else float("inf")
            print(f"\n  Excluding Q4 (INFY-driven): N=2 mean={100*m2:+.2f}%  sd={100*s2:.2f}%  Sharpe={sr2:.2f}")
            print(f"  (N=2 Sharpe is unstable but informative — strip the outlier and the mean drops to ~1.3% with very low SD)")

    # --- Win rate at firm-event level ---
    wins = sum(1 for r in spy_adj_returns if r > 0)
    print(f"\n=== Win rate ===")
    print(f"  Positive D+1 SPY-adj firm-events: {wins}/{len(spy_adj_returns)} = {100*wins/len(spy_adj_returns):.0f}%")

    # CSV out
    out = RESULTS / "puts_short_per_event.csv"
    with out.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(events[0].keys()))
        w.writeheader(); w.writerows(events)
    print(f"\nWrote {out}")


if __name__ == "__main__":
    main()
