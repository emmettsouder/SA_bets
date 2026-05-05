"""Historical event study for Rule v1: long basket of NEW common-stock positions.

For each tradeable_new_position, compute:
  - Same-day return: open(t)/close(t) - 1
  - 1-day hold (buy close t, sell close t+1): close(t+1)/close(t) - 1
  - Realistic ~10-min-entry proxy: vwap(t)/close(t+1) where vwap ~ (O+H+L+C)/4
  - Pre-event placebo: close(t-1)/close(t-2) - 1
  - Wider window: close(t+5)/close(t-1) - 1

All returns also benchmark-adjusted vs SPY (broad) and SMH (AI-infra proxy).
"""

import csv
import json
import statistics as st
from collections import defaultdict
from datetime import datetime
from pathlib import Path

import sys
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prices

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

MIN_VALUE_USD = 1_000_000  # filter out token positions like $37 Intel

# Map filing period → acceptance datetime → event date (trading day t)
# Pre-market or weekend acceptance pushes to next trading day; otherwise same day.
# All historical filings happened on weekdays during/before regular session, so
# event_date == acceptance calendar date for our sample.
EVENT_DATES = {
    "2025-03-31": "2025-05-14",  # accepted 11:14 ET Wed
    "2025-09-30": "2025-11-14",  # accepted 12:10 ET Fri
    "2025-12-31": "2026-02-11",  # accepted 03:31 ET Wed pre-market → same-day
}

BENCHMARKS = ["SPY", "SMH", "QQQ"]


def load_ticker_map() -> dict[str, str]:
    rows = list(csv.DictReader(open(DATA / "cusip_ticker_map.csv")))
    # Use issuer (uppercase) as key — same normalization the diff used
    out = {}
    for r in rows:
        out[r["issuer"].upper().strip()] = r["ticker"]
    return out


def trading_day_offset(bars: list[dict], target_date: str, offset: int) -> dict | None:
    """Return the bar `offset` trading days from target_date. offset=0 means the bar at target_date.
    If target_date itself is not a trading day, snap to the next trading day for offset=0,
    but for non-zero offsets count actual trading days from there."""
    dates = [b["date"] for b in bars]
    # Find index of target_date or first trading day >= target_date
    idx = None
    for i, d in enumerate(dates):
        if d >= target_date:
            idx = i
            break
    if idx is None:
        return None
    j = idx + offset
    if j < 0 or j >= len(bars):
        return None
    return bars[j]


def rtn(num, den):
    if num is None or den is None or den == 0:
        return None
    return num / den - 1


def main():
    # 1. Load calibration sample
    new_rows = list(csv.DictReader(open(DATA / "filings" / "tradeable_new_positions.csv")))
    new_rows = [r for r in new_rows if int(r["common_value_usd"]) >= MIN_VALUE_USD]
    new_rows = [r for r in new_rows if r["period"] in EVENT_DATES]

    ticker_map = load_ticker_map()
    universe = sorted({r["issuer_raw"].upper().strip() for r in new_rows})
    print(f"Calibration: {len(new_rows)} firm-events across {len(EVENT_DATES)} filings, {len(universe)} unique names")

    # 2. Pull prices
    earliest_event = min(EVENT_DATES.values())
    latest_event = max(EVENT_DATES.values())
    start = "2025-04-01"  # ~6 weeks before earliest event for placebo window
    end = "2026-04-30"
    print(f"\nFetching prices [{start} → {end}]")
    tickers_needed = [ticker_map[u] for u in universe if u in ticker_map] + BENCHMARKS
    bars_by_ticker = prices.get_many(tickers_needed, start, end)

    # 3. Compute returns per firm-event
    out_rows = []
    for r in new_rows:
        issuer = r["issuer_raw"].upper().strip()
        tkr = ticker_map.get(issuer)
        if not tkr:
            print(f"  SKIP no ticker: {issuer}")
            continue
        bars = bars_by_ticker.get(tkr, [])
        if not bars:
            print(f"  SKIP no bars: {tkr}")
            continue
        ed = EVENT_DATES[r["period"]]
        b_pre1 = trading_day_offset(bars, ed, -1)
        b_pre2 = trading_day_offset(bars, ed, -2)
        b0 = trading_day_offset(bars, ed, 0)
        b1 = trading_day_offset(bars, ed, 1)
        b5 = trading_day_offset(bars, ed, 5)
        if not all([b_pre1, b0, b1]):
            print(f"  SKIP missing bars near {ed} for {tkr}")
            continue
        # Same-day return: open(t) -> close(t)
        same_day = rtn(b0["close"], b0["open"])
        # 1-day hold from close(t) to close(t+1) — conservative entry
        d1_close_close = rtn(b1["close"], b0["close"])
        # VWAP proxy entry → close(t+1): captures partial same-day + overnight + next-day
        vwap_t = (b0["open"] + b0["high"] + b0["low"] + b0["close"]) / 4
        d1_vwap_close = rtn(b1["close"], vwap_t)
        # Wider 5-day window: close(t-1) -> close(t+5)
        wide = rtn(b5["close"], b_pre1["close"]) if b5 else None
        # Placebo pre-event: close(t-2) -> close(t-1)
        placebo = rtn(b_pre1["close"], b_pre2["close"]) if b_pre2 else None

        # Benchmark-adjusted
        bench_adj = {}
        for bm in BENCHMARKS:
            bm_bars = bars_by_ticker.get(bm, [])
            bm_b_pre1 = trading_day_offset(bm_bars, ed, -1)
            bm_b0 = trading_day_offset(bm_bars, ed, 0)
            bm_b1 = trading_day_offset(bm_bars, ed, 1)
            if all([bm_b_pre1, bm_b0, bm_b1]):
                bm_d1_cc = rtn(bm_b1["close"], bm_b0["close"])
                bm_vwap = (bm_b0["open"] + bm_b0["high"] + bm_b0["low"] + bm_b0["close"]) / 4
                bm_d1_vc = rtn(bm_b1["close"], bm_vwap)
                bench_adj[f"d1_close_close_minus_{bm}"] = (d1_close_close - bm_d1_cc) if d1_close_close is not None else None
                bench_adj[f"d1_vwap_close_minus_{bm}"] = (d1_vwap_close - bm_d1_vc) if d1_vwap_close is not None else None

        out_rows.append({
            "filing_period": r["period"],
            "event_date": ed,
            "issuer": issuer,
            "ticker": tkr,
            "common_value_usd": int(r["common_value_usd"]),
            "had_option_prior": r["had_option_prior"],
            "same_day_open_close": same_day,
            "d1_close_close": d1_close_close,
            "d1_vwap_close": d1_vwap_close,
            "wide_5d": wide,
            "placebo_t-2_t-1": placebo,
            **bench_adj,
        })

    # 4. Print per-filing summaries
    print(f"\nPer-filing summary (Rule v1 = equal-weight long basket of NEW common positions):\n")
    fmt_pct = lambda x: f"{100*x:+6.2f}%" if x is not None else "  n/a "
    metrics = ["d1_close_close", "d1_close_close_minus_SPY", "d1_close_close_minus_SMH",
               "d1_vwap_close", "d1_vwap_close_minus_SPY", "d1_vwap_close_minus_SMH",
               "wide_5d", "placebo_t-2_t-1"]

    by_filing = defaultdict(list)
    for r in out_rows:
        by_filing[r["filing_period"]].append(r)

    print(f"{'metric':<32s} " + " ".join(f"{p:>13}" for p in sorted(by_filing)) + f"  {'POOLED':>13}")
    print("-" * (32 + 14 * (len(by_filing) + 1)))
    pooled_by_metric = {m: [] for m in metrics}
    for m in metrics:
        line = f"{m:<32s} "
        for p in sorted(by_filing):
            vals = [r[m] for r in by_filing[p] if r.get(m) is not None]
            mean = st.mean(vals) if vals else None
            line += f"{fmt_pct(mean):>13} "
            pooled_by_metric[m].extend(vals)
        pooled = pooled_by_metric[m]
        line += f" {fmt_pct(st.mean(pooled) if pooled else None):>13}"
        print(line)

    # 5. Sign test + simple t-stat for the headline metric
    print(f"\nHeadline metric: d1_vwap_close (~realistic 10-min-entry, 1-day hold)")
    vals = [r["d1_vwap_close"] for r in out_rows if r["d1_vwap_close"] is not None]
    n = len(vals)
    mean = st.mean(vals)
    sd = st.stdev(vals) if n > 1 else float("nan")
    se = sd / (n ** 0.5) if n > 1 else float("nan")
    t = mean / se if se else float("nan")
    pos = sum(1 for v in vals if v > 0)
    print(f"  N={n}  mean={mean*100:+.2f}%  sd={sd*100:.2f}%  t={t:.2f}  positive={pos}/{n}")

    # SPY-adjusted
    vals_spy = [r["d1_vwap_close_minus_SPY"] for r in out_rows if r.get("d1_vwap_close_minus_SPY") is not None]
    if vals_spy:
        n = len(vals_spy); mean = st.mean(vals_spy); sd = st.stdev(vals_spy) if n>1 else 0
        se = sd / (n ** 0.5) if n > 1 else float("nan")
        pos = sum(1 for v in vals_spy if v > 0)
        print(f"  SPY-adj:  N={n}  mean={mean*100:+.2f}%  sd={sd*100:.2f}%  t={mean/se:.2f}  positive={pos}/{n}")

    vals_smh = [r["d1_vwap_close_minus_SMH"] for r in out_rows if r.get("d1_vwap_close_minus_SMH") is not None]
    if vals_smh:
        n = len(vals_smh); mean = st.mean(vals_smh); sd = st.stdev(vals_smh) if n>1 else 0
        se = sd / (n ** 0.5) if n > 1 else float("nan")
        pos = sum(1 for v in vals_smh if v > 0)
        print(f"  SMH-adj:  N={n}  mean={mean*100:+.2f}%  sd={sd*100:.2f}%  t={mean/se:.2f}  positive={pos}/{n}")

    # 6. Save firm-event detail
    out_csv = RESULTS / "event_study_v1.csv"
    fieldnames = list(out_rows[0].keys())
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fieldnames)
        w.writeheader(); w.writerows(out_rows)
    print(f"\nWrote {out_csv}")


if __name__ == "__main__":
    main()
