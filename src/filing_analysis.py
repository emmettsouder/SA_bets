"""Generalized post-filing analysis with long + short baskets.

Long basket  = NEW common-stock positions (weight = current_common_value)
Short basket = DEC + EXIT_COMMON + EXIT_ALL where prior common holding existed
               (weight = prior_common_value — size of the position being trimmed/exited)

Hypothesis: if disclosure causes attention-driven price impact:
  - LONG basket should have +ve post-disclosure returns
  - SHORT basket should have -ve post-disclosure returns
  - Net long-short should be more strongly +ve than long-only

Entry logic:
  - Pre-market acceptance (before 09:30 ET): enter at 09:30 ET open of disclosure day
  - Regular session acceptance: enter at the next 60m bar boundary after
    acceptance + 10min latency
  - After-hours / weekend: enter at next session's 09:30 ET open
"""

import csv
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prices

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
RESULTS.mkdir(exist_ok=True)

MIN_VALUE_USD = 1_000_000

FILINGS = {
    "2025-03-31": {
        "label": "Q1 2025",
        "acceptance_et": "2025-05-14 11:14",
        "trading_day": "2025-05-14",
        "entry_et": "11:30",
        "entry_label": "11:30 ET (next 60m bar after 11:14 acceptance)",
    },
    "2025-06-30": {
        "label": "Q2 2025",
        "acceptance_et": "2025-08-14 09:54",
        "trading_day": "2025-08-14",
        "entry_et": "10:30",
        "entry_label": "10:30 ET (next 60m bar after 09:54 acceptance)",
    },
    "2025-09-30": {
        "label": "Q3 2025",
        "acceptance_et": "2025-11-14 12:10",
        "trading_day": "2025-11-14",
        "entry_et": "12:30",
        "entry_label": "12:30 ET (next 60m bar after 12:10 acceptance)",
    },
    "2025-12-31": {
        "label": "Q4 2025",
        "acceptance_et": "2026-02-11 03:31",
        "trading_day": "2026-02-11",
        "entry_et": "09:30",
        "entry_label": "09:30 ET (open; filing was pre-market)",
    },
}


def load_long_short_baskets(period: str, include_inc: bool = True):
    """Build long and short baskets keyed on MARGINAL commitment this quarter.

    Long basket weights:  Δshares_added × current_price  (= "new dollars committed")
                          Includes NEW_ALL, NEW_COMMON, and (if include_inc) INC.
    Short basket weights: Δshares_sold × prior_price     (= "dollars liquidated")
                          Includes DEC, EXIT_COMMON, EXIT_ALL.
    """
    diff = list(csv.DictReader(open(DATA / "filings" / "diff_long.csv")))
    longs, shorts = [], []
    for r in diff:
        if r["period"] != period:
            continue
        cls = r["classification"]
        cur_val = int(r["common_value_cur"]) if r["common_value_cur"] else 0
        cur_sh = int(r["common_shares_cur"]) if r["common_shares_cur"] else 0
        prev_sh = int(r["common_shares_prev"]) if r["common_shares_prev"] else 0
        cur_price = (cur_val / cur_sh) if cur_sh else 0
        delta_shares = cur_sh - prev_sh

        # ---- Long basket ----
        if cls in ("NEW_ALL", "NEW_COMMON") and cur_val >= MIN_VALUE_USD and cur_sh > 0:
            # weight basis = cur_val for NEW (since prev_sh=0)
            longs.append({
                "issuer_norm": r["issuer_norm"], "issuer_raw": r["issuer_raw"],
                "weight_basis": delta_shares * cur_price,  # equals cur_val for NEW
                "side": "LONG", "classification": cls,
                "prev_shares": prev_sh, "cur_shares": cur_sh, "delta_shares": delta_shares,
                "cur_value": cur_val,
            })
        elif cls == "INC" and include_inc and delta_shares > 0 and cur_price > 0:
            marginal = delta_shares * cur_price
            if marginal >= MIN_VALUE_USD:
                longs.append({
                    "issuer_norm": r["issuer_norm"], "issuer_raw": r["issuer_raw"],
                    "weight_basis": marginal,
                    "side": "LONG", "classification": cls,
                    "prev_shares": prev_sh, "cur_shares": cur_sh, "delta_shares": delta_shares,
                    "cur_value": cur_val,
                })
        # ---- Short basket ----
        elif cls in ("DEC", "EXIT_COMMON", "EXIT_ALL") and prev_sh > 0:
            shorts.append({
                "issuer_norm": r["issuer_norm"], "issuer_raw": r["issuer_raw"],
                "side": "SHORT", "classification": cls,
                "prior_period": r["prior_period"],
                "prev_shares": prev_sh, "cur_shares": cur_sh,
                "delta_shares": delta_shares,
            })

    # Look up prior common values for shorts; weight = (prev_sh - cur_sh) × prior_price
    holdings = list(csv.DictReader(open(DATA / "filings" / "holdings_long.csv")))
    for s in shorts:
        prior_value = 0
        prior_shares = 0
        for h in holdings:
            if h["period_of_report"] != s["prior_period"]:
                continue
            if h["put_call"]:
                continue
            if _norm(h["issuer"]) != s["issuer_norm"]:
                continue
            prior_value += int(h["value_usd"])
            prior_shares += int(h["shares"])
        prior_price = (prior_value / prior_shares) if prior_shares else 0
        shares_sold = s["prev_shares"] - s["cur_shares"]
        s["weight_basis"] = shares_sold * prior_price  # marginal liquidation value
        s["prior_value"] = prior_value

    shorts = [s for s in shorts if s["weight_basis"] >= MIN_VALUE_USD]
    return longs, shorts


def _norm(name: str) -> str:
    """Reuse the diff's normalization. Hand-inlined to avoid import cycle."""
    import re
    SUFFIXES = ["INC", "INC.", "CORP", "CORP.", "CORPORATION", "LTD", "LTD.", "LIMITED",
                "PLC", "CO", "CO.", "COMPANY", "HLDGS", "HLDG", "HOLDINGS", "HOLDING",
                "GROUP", "ENTERPRISES", "TRUST", "ETF", "L P", "LP", "LLC", "PL",
                "MFG", "TECHNOLOGIES", "TECHNOLOGY", "TECH", "NEW", "CL A"]
    s = name.upper().strip()
    s = re.sub(r"[&]", " AND ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    changed = True
    while changed:
        changed = False
        for suf in SUFFIXES:
            if s.endswith(" " + suf):
                s = s[: -(len(suf) + 1)].strip()
                changed = True
    return s


def load_ticker_map():
    rows = list(csv.DictReader(open(DATA / "cusip_ticker_map.csv")))
    return {r["issuer"].upper().strip(): r["ticker"] for r in rows}


def find_intraday_bar(bars, target_date, target_et_hhmm):
    for b in bars:
        if b["ts_utc"][:10] != target_date:
            continue
        et = datetime.fromisoformat(b["ts_utc"].replace("Z", "+00:00")) - timedelta(hours=5)
        if et.strftime("%H:%M") >= target_et_hhmm:
            return b
    return None


def daily_at_offset(bars, from_date, n):
    idx = next((i for i, b in enumerate(bars) if b["date"] >= from_date), None)
    if idx is None or idx + n >= len(bars):
        return None
    return bars[idx + n]


def analyze(period: str, intraday_window_days: int = 3, daily_horizons=(1, 2, 3, 5, 10, 20, 40)):
    cfg = FILINGS[period]
    longs, shorts = load_long_short_baskets(period)
    tmap = load_ticker_map()

    # Resolve tickers
    for r in longs + shorts:
        r["ticker"] = tmap.get(r["issuer_norm"]) or tmap.get(r["issuer_raw"].upper().strip())

    print(f"\n=== {cfg['label']} filing — long-short analysis ===")
    print(f"Acceptance: {cfg['acceptance_et']} ET")
    print(f"Entry: {cfg['entry_label']}")

    print(f"\nLONG basket ({len(longs)} new common positions, weight by current common value)")
    long_total = sum(r["weight_basis"] for r in longs)
    for r in sorted(longs, key=lambda x: -x["weight_basis"]):
        r["weight"] = r["weight_basis"] / long_total
        print(f"  {r['ticker']:<6s} {r['issuer_raw'][:32]:<32s} ${r['weight_basis']:>13,.0f}  {r['weight']*100:>5.2f}%  ({r['classification']})")

    print(f"\nSHORT basket ({len(shorts)} downsized/exited common positions, weight by PRIOR common value)")
    short_total = sum(r["weight_basis"] for r in shorts)
    for r in sorted(shorts, key=lambda x: -x["weight_basis"]):
        r["weight"] = r["weight_basis"] / short_total
        sold_frac = (r["prev_shares"] - r["cur_shares"]) / r["prev_shares"] if r["prev_shares"] else 0
        print(f"  {r['ticker']:<6s} {r['issuer_raw'][:32]:<32s} prior=${r['weight_basis']:>13,.0f}  {r['weight']*100:>5.2f}%  ({r['classification']}, sold {sold_frac*100:.0f}%)")

    # Fetch prices
    trading_day = cfg["trading_day"]
    intraday_start = (datetime.fromisoformat(trading_day) - timedelta(days=2)).strftime("%Y-%m-%d")
    intraday_end = (datetime.fromisoformat(trading_day) + timedelta(days=intraday_window_days)).strftime("%Y-%m-%d")
    daily_end = (datetime.fromisoformat(trading_day) + timedelta(days=80)).strftime("%Y-%m-%d")
    tickers = list({r["ticker"] for r in longs + shorts if r.get("ticker")}) + ["SPY", "SMH", "QQQ"]
    print(f"\nFetching prices...")
    intraday = {}
    daily = {}
    for t in tickers:
        try:
            intraday[t] = prices.get_intraday(t, intraday_start, intraday_end, "60m")
        except Exception as e:
            intraday[t] = []
        try:
            daily[t] = prices.get(t, trading_day, daily_end)
        except Exception as e:
            daily[t] = []

    # Compute returns per ticker
    entry_et = cfg["entry_et"]
    intraday_horizons = ["10:30", "11:30", "12:30", "13:30", "14:30", "15:30"]
    intraday_horizons = [h for h in intraday_horizons if h > entry_et]

    def ticker_returns(rec):
        tkr = rec["ticker"]
        ib = intraday.get(tkr, [])
        db = daily.get(tkr, [])
        entry_bar = find_intraday_bar(ib, trading_day, entry_et)
        if not entry_bar or entry_bar["open"] is None:
            return None
        entry = entry_bar["open"]
        rec["entry_price"] = entry
        for hh in intraday_horizons:
            xb = find_intraday_bar(ib, trading_day, hh)
            rec[f"r_{hh}"] = (xb["close"] / entry - 1) if (xb and xb["close"]) else None
        for n in daily_horizons:
            xb = daily_at_offset(db, trading_day, n)
            rec[f"d_{n}"] = (xb["close"] / entry - 1) if (xb and xb["close"]) else None
        return rec

    longs = [r for r in (ticker_returns(r) for r in longs) if r is not None]
    shorts = [r for r in (ticker_returns(r) for r in shorts) if r is not None]

    def basket_ret(rows, key):
        total_w = sum(r["weight"] for r in rows if r.get(key) is not None)
        if total_w == 0: return None
        return sum(r["weight"] * r[key] for r in rows if r.get(key) is not None) / total_w

    def bench_ret(tkr, key, is_intraday):
        if is_intraday:
            ib = intraday.get(tkr, [])
            eb = find_intraday_bar(ib, trading_day, entry_et)
            xb = find_intraday_bar(ib, trading_day, key)
            if not eb or not xb or eb["open"] is None or xb["close"] is None: return None
            return xb["close"] / eb["open"] - 1
        else:
            db = daily.get(tkr, [])
            eb_intra = find_intraday_bar(intraday.get(tkr, []), trading_day, entry_et)
            entry_px = eb_intra["open"] if eb_intra and eb_intra["open"] else (db[0]["open"] if db else None)
            xb = daily_at_offset(db, trading_day, key)
            if entry_px is None or not xb or xb["close"] is None: return None
            return xb["close"] / entry_px - 1

    fmt = lambda x: f"{100*x:+6.2f}%" if x is not None else "  n/a "
    print(f"\n{'Horizon':<14s} {'Long':>9s} {'Short(stock)':>13s} {'L−S':>9s} {'SPY':>8s} {'SMH':>8s} {'L−SPY':>9s} {'(−S)−SPY':>10s} {'(L−S)−SPY':>11s}")
    print("-" * 110)

    print("Intraday (entry → exit at):")
    for hh in intraday_horizons:
        L = basket_ret(longs, f"r_{hh}")
        S = basket_ret(shorts, f"r_{hh}")  # raw stock return — short PnL = -S
        spy = bench_ret("SPY", hh, True)
        smh = bench_ret("SMH", hh, True)
        LS = (L + (-S if S is not None else 0)) if L is not None else None
        L_spy = (L - spy) if L is not None and spy is not None else None
        negS_spy = ((-S) - spy) if S is not None and spy is not None else None
        LS_spy = (LS - 0) if LS is not None else None  # net is dollar-neutral, no benchmark needed
        # but SPY-adjusting both sides: (L-spy) - (S-spy) = L - S, same as raw L-S
        print(f"  {hh+' ET':<12s}  {fmt(L):>9} {fmt(S):>13} {fmt(LS):>9} {fmt(spy):>8} {fmt(smh):>8} {fmt(L_spy):>9} {fmt(negS_spy):>10} {fmt(LS):>11}")

    print("\nMulti-day (entry → close day +n):")
    for n in daily_horizons:
        L = basket_ret(longs, f"d_{n}")
        S = basket_ret(shorts, f"d_{n}")
        spy = bench_ret("SPY", n, False)
        smh = bench_ret("SMH", n, False)
        LS = (L + (-S if S is not None else 0)) if L is not None else None
        L_spy = (L - spy) if L is not None and spy is not None else None
        negS_spy = ((-S) - spy) if S is not None and spy is not None else None
        print(f"  day +{n:<8d} {fmt(L):>9} {fmt(S):>13} {fmt(LS):>9} {fmt(spy):>8} {fmt(smh):>8} {fmt(L_spy):>9} {fmt(negS_spy):>10} {fmt(LS):>11}")

    # Per-name day-1 detail
    print(f"\n--- Per-name day-1 detail ---")
    for side, rows in [("LONG", longs), ("SHORT", shorts)]:
        print(f"\n{side}:")
        for r in sorted(rows, key=lambda x: -x["weight"]):
            d1 = r.get("d_1")
            print(f"  {r['ticker']:<6s} {r['issuer_raw'][:32]:<32s} wt={r['weight']*100:5.1f}%  entry=${r.get('entry_price', 0):>8.2f}  D+1: {fmt(d1)}")

    return longs, shorts


def main():
    print("\n" + "="*100)
    print("Q3 2025 FILING (second-most-recent)")
    print("="*100)
    analyze("2025-09-30")

    print("\n\n" + "="*100)
    print("Q4 2025 FILING (most recent) — re-run with shorts for comparison")
    print("="*100)
    analyze("2025-12-31")


if __name__ == "__main__":
    main()
