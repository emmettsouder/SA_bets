"""Focused analysis of the most recent SA filing only (2025-Q4, accepted 2026-02-11 03:31 ET).

Computes returns of the SA-position-size-weighted basket of new common-stock
positions over multiple horizons (intraday hours and multi-day), each
benchmark-adjusted vs SPY (and SMH for sector).

Entry assumption: 9:30 ET open on 2026-02-11 (acceptance was pre-market at
03:31, so we'd be queued at the open with ~6 hours to spare). The 10-min SLA
target is comfortably met if the filing comes pre-market.
"""

import csv
import statistics as st
from datetime import datetime, timedelta, timezone
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prices

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

EVENT_DATE = "2026-02-11"
EVENT_NEXT = "2026-02-12"
RANGE_END = "2026-04-30"  # for multi-day exits up to ~50 trading days post-event
INTRADAY_START = "2026-02-09"
INTRADAY_END = "2026-02-13"
MIN_VALUE_USD = 1_000_000


def load_basket():
    """Load Q4'25 new common positions with size weights."""
    rows = list(csv.DictReader(open(DATA / "filings" / "tradeable_new_positions.csv")))
    rows = [r for r in rows if r["period"] == "2025-12-31" and int(r["common_value_usd"]) >= MIN_VALUE_USD]
    total = sum(int(r["common_value_usd"]) for r in rows)
    for r in rows:
        r["weight"] = int(r["common_value_usd"]) / total
        r["common_value_usd"] = int(r["common_value_usd"])
    rows.sort(key=lambda r: -r["common_value_usd"])
    return rows, total


def load_ticker_map():
    rows = list(csv.DictReader(open(DATA / "cusip_ticker_map.csv")))
    return {r["issuer"].upper().strip(): r["ticker"] for r in rows}


def et_hour(bar: dict) -> str:
    """Convert UTC timestamp to America/New_York wall time HH:MM."""
    # Eastern Standard Time in February: UTC-5
    ts = datetime.fromisoformat(bar["ts_utc"].replace("Z", "+00:00"))
    et = ts - timedelta(hours=5)
    return et.strftime("%H:%M")


def find_intraday_bar(bars: list[dict], target_date: str, target_et_hhmm: str):
    """Find first bar on target_date at or after target_et_hhmm (ET)."""
    for b in bars:
        if b["ts_utc"][:10] != target_date:
            continue
        if et_hour(b) >= target_et_hhmm:
            return b
    return None


def find_daily_bar(bars: list[dict], target_date: str):
    for b in bars:
        if b["date"] == target_date:
            return b
    # next available
    for b in bars:
        if b["date"] > target_date:
            return b
    return None


def daily_at_offset(bars: list[dict], from_date: str, n: int):
    """Return bar n trading days after the bar at from_date."""
    idx = next((i for i, b in enumerate(bars) if b["date"] >= from_date), None)
    if idx is None or idx + n >= len(bars):
        return None
    return bars[idx + n]


def main():
    basket, total_value = load_basket()
    tmap = load_ticker_map()

    print(f"\n=== Last filing analysis (Q4 2025, accepted 2026-02-11 03:31 ET pre-market) ===")
    print(f"Basket: {len(basket)} names, total SA value ${total_value:,.0f}\n")
    print(f"{'Ticker':<7s} {'Issuer':<32s} {'SA value':>14s} {'Weight':>8s}")
    for r in basket:
        tkr = tmap.get(r["issuer_norm"]) or tmap.get(r["issuer_raw"].upper().strip())
        if not tkr:
            print(f"  WARN no ticker for {r['issuer_norm']!r}")
        r["ticker"] = tkr
        print(f"{tkr:<7s} {r['issuer_raw']:<32s} ${r['common_value_usd']:>13,.0f} {r['weight']*100:>7.2f}%")

    tickers = [r["ticker"] for r in basket if r.get("ticker")] + ["SPY", "SMH", "QQQ"]

    # 1. Intraday (60m bars) for hour-level windows on day 0
    print(f"\nFetching 60m intraday bars [{INTRADAY_START} → {INTRADAY_END}]...")
    intraday = {}
    for t in tickers:
        try:
            intraday[t] = prices.get_intraday(t, INTRADAY_START, INTRADAY_END, "60m")
        except Exception as e:
            print(f"  FAIL intraday {t}: {e}")
            intraday[t] = []

    # 2. Daily bars for multi-day windows
    print(f"Fetching daily bars [{EVENT_DATE} → {RANGE_END}]...")
    daily = prices.get_many(tickers, EVENT_DATE, RANGE_END)

    # 3. Compute per-ticker returns at each horizon
    # Intraday horizons: entry at 9:30 ET, exit at 10:30, 11:30, 12:30, 13:30, 14:30, 15:30, 16:00 (close)
    intraday_horizons_et = ["10:30", "11:30", "12:30", "13:30", "14:30", "15:30", "15:59"]
    # Multi-day horizons: close of day +1, +2, +3, +5, +10, +20, +40
    daily_horizons = [1, 2, 3, 5, 10, 20, 40]

    per_ticker = []
    for r in basket:
        tkr = r["ticker"]
        if not tkr:
            continue
        ib = intraday.get(tkr, [])
        db = daily.get(tkr, [])

        entry_bar = find_intraday_bar(ib, EVENT_DATE, "09:30")
        if not entry_bar or entry_bar["open"] is None:
            print(f"  SKIP {tkr}: no 9:30 ET entry bar")
            continue
        entry = entry_bar["open"]

        rec = {"ticker": tkr, "issuer": r["issuer_raw"], "weight": r["weight"], "sa_value": r["common_value_usd"], "entry_price": entry}
        # Intraday returns
        for hh in intraday_horizons_et:
            exit_bar = find_intraday_bar(ib, EVENT_DATE, hh)
            # Use close of the bar AT the horizon (exit during/at end of that hour)
            ex_close = exit_bar["close"] if exit_bar else None
            rec[f"r_{hh}"] = (ex_close / entry - 1) if ex_close else None
        # Daily returns: from open of day 0 to close of day 0+n
        for n in daily_horizons:
            exit_bar = daily_at_offset(db, EVENT_DATE, n)
            ex_close = exit_bar["close"] if exit_bar else None
            rec[f"d_{n}"] = (ex_close / entry - 1) if ex_close else None
        per_ticker.append(rec)

    # 4. Compute basket-weighted returns and benchmarks
    def basket_return(per_ticker, key):
        total_w = sum(r["weight"] for r in per_ticker if r.get(key) is not None)
        if total_w == 0: return None
        return sum(r["weight"] * r[key] for r in per_ticker if r.get(key) is not None) / total_w

    def bench_return_intraday(tkr, hh):
        ib = intraday.get(tkr, [])
        eb = find_intraday_bar(ib, EVENT_DATE, "09:30")
        xb = find_intraday_bar(ib, EVENT_DATE, hh)
        if not eb or not xb or eb["open"] is None or xb["close"] is None: return None
        return xb["close"] / eb["open"] - 1

    def bench_return_daily(tkr, n):
        db = daily.get(tkr, [])
        eb = next((b for b in db if b["date"] >= EVENT_DATE), None)
        xb = daily_at_offset(db, EVENT_DATE, n)
        if not eb or not xb or eb["open"] is None or xb["close"] is None: return None
        return xb["close"] / eb["open"] - 1

    # 5. Print results
    print(f"\n=== Position-size-weighted basket vs benchmarks ===\n")
    print(f"Entry: 9:30 ET open on 2026-02-11 (filing was 03:31 ET pre-market)\n")

    fmt_pct = lambda x: f"{100*x:+6.2f}%" if x is not None else "  n/a "
    print(f"{'Horizon':<14s} {'Basket(wtd)':>12s} {'SPY':>8s} {'SMH':>8s} {'QQQ':>8s} {'vs SPY':>10s} {'vs SMH':>10s} {'vs QQQ':>10s}")
    print("-" * 90)
    print("Intraday (entry 9:30 → exit at):")
    for hh in intraday_horizons_et:
        b = basket_return(per_ticker, f"r_{hh}")
        spy = bench_return_intraday("SPY", hh)
        smh = bench_return_intraday("SMH", hh)
        qqq = bench_return_intraday("QQQ", hh)
        adj_spy = (b - spy) if (b is not None and spy is not None) else None
        adj_smh = (b - smh) if (b is not None and smh is not None) else None
        adj_qqq = (b - qqq) if (b is not None and qqq is not None) else None
        print(f"  {hh+' ET':<12s}  {fmt_pct(b):>11s} {fmt_pct(spy):>8s} {fmt_pct(smh):>8s} {fmt_pct(qqq):>8s} {fmt_pct(adj_spy):>10s} {fmt_pct(adj_smh):>10s} {fmt_pct(adj_qqq):>10s}")

    print("\nMulti-day (entry day-0 open → close of day +n):")
    for n in daily_horizons:
        b = basket_return(per_ticker, f"d_{n}")
        spy = bench_return_daily("SPY", n)
        smh = bench_return_daily("SMH", n)
        qqq = bench_return_daily("QQQ", n)
        adj_spy = (b - spy) if (b is not None and spy is not None) else None
        adj_smh = (b - smh) if (b is not None and smh is not None) else None
        adj_qqq = (b - qqq) if (b is not None and qqq is not None) else None
        print(f"  day +{n:<8d} {fmt_pct(b):>11s} {fmt_pct(spy):>8s} {fmt_pct(smh):>8s} {fmt_pct(qqq):>8s} {fmt_pct(adj_spy):>10s} {fmt_pct(adj_smh):>10s} {fmt_pct(adj_qqq):>10s}")

    # 6. Per-name day-1 contribution detail
    print(f"\n=== Per-name detail ===\n")
    print(f"{'Ticker':<7s} {'Wt':>6s} {'Entry':>9s} {'1h':>8s} {'EOD0':>8s} {'D+1':>8s} {'D+5':>8s} {'D+20':>8s}")
    for r in sorted(per_ticker, key=lambda x: -x["weight"]):
        e = r["entry_price"]
        print(f"{r['ticker']:<7s} {r['weight']*100:>5.1f}% ${e:>8,.2f} "
              f"{fmt_pct(r.get('r_10:30')):>8s} {fmt_pct(r.get('r_15:59')):>8s} "
              f"{fmt_pct(r.get('d_1')):>8s} {fmt_pct(r.get('d_5')):>8s} {fmt_pct(r.get('d_20')):>8s}")

    # 7. Save firm-event detail
    out_csv = RESULTS / "last_filing_analysis.csv"
    if per_ticker:
        cols = list(per_ticker[0].keys())
        with out_csv.open("w", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=cols)
            w.writeheader()
            w.writerows(per_ticker)
        print(f"\nWrote {out_csv}")


if __name__ == "__main__":
    main()
