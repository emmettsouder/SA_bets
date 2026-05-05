"""Backtest a grid of simple trading theses on Q3'25 and Q4'25 filings.

Each thesis defines a basket and a side (long/short). For each, compute
size-weighted basket return at four horizons:
  - 1h post-entry
  - EOD of disclosure day (last available intraday bar)
  - Close day +1
  - Close day +2

Entry times:
  Q3'25 — 12:30 ET on 2025-11-14 (acceptance 12:10 ET, ~10min latency rounds to next 60m bar)
  Q4'25 — 09:30 ET on 2026-02-11 (acceptance 03:31 ET pre-market, enter at the open)
"""

import csv
import sys
from collections import defaultdict
from datetime import datetime, timedelta
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import prices
from filing_analysis import _norm, FILINGS

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
RESULTS = ROOT / "results"
MIN_USD = 1_000_000

PERIODS = ["2025-03-31", "2025-06-30", "2025-09-30", "2025-12-31"]
PRIOR_FOR = {
    "2025-03-31": "2024-12-31",
    "2025-06-30": "2025-03-31",
    "2025-09-30": "2025-06-30",
    "2025-12-31": "2025-09-30",
}
MIN_USD_PUT = 1_000_000  # threshold for new put positions


def load_holdings():
    rows = list(csv.DictReader(open(DATA / "filings" / "holdings_long.csv")))
    by_period = defaultdict(list)
    for r in rows:
        r["norm"] = _norm(r["issuer"])
        r["shares"] = int(r["shares"]) if r["shares"] else 0
        r["value"] = int(r["value_usd"]) if r["value_usd"] else 0
        by_period[r["period_of_report"]].append(r)
    return by_period


def issuer_state(rows):
    """For a single filing's rows, aggregate per (norm_issuer)."""
    s = defaultdict(lambda: {
        "issuer_raw": "", "common_shares": 0, "common_value": 0,
        "call_shares": 0, "call_value": 0, "put_shares": 0, "put_value": 0,
    })  # noqa
    for r in rows:
        k = r["norm"]
        s[k]["issuer_raw"] = r["issuer"]
        if r["put_call"] == "Call":
            s[k]["call_shares"] += r["shares"]
            s[k]["call_value"] += r["value"]
        elif r["put_call"] == "Put":
            s[k]["put_shares"] += r["shares"]
            s[k]["put_value"] += r["value"]
        else:
            s[k]["common_shares"] += r["shares"]
            s[k]["common_value"] += r["value"]
    return dict(s)


def basket_for_thesis(thesis: str, cur, prior):
    """Return list of {issuer, weight} for this thesis. 'cur' and 'prior' are issuer_state dicts."""
    out = []
    issuers = set(cur) | set(prior)
    for k in issuers:
        c = cur.get(k, {})
        p = prior.get(k, {})
        c_csh, c_cval = c.get("common_shares", 0), c.get("common_value", 0)
        p_csh, p_cval = p.get("common_shares", 0), p.get("common_value", 0)
        c_callsh, c_callval = c.get("call_shares", 0), c.get("call_value", 0)
        p_callsh = p.get("call_shares", 0)
        c_price = (c_cval / c_csh) if c_csh else 0
        p_price = (p_cval / p_csh) if p_csh else 0
        delta_csh = c_csh - p_csh

        issuer_raw = c.get("issuer_raw") or p.get("issuer_raw") or k

        # Long theses
        if thesis == "L_NEW_common_size":
            if p_csh == 0 and c_csh > 0 and c_cval >= MIN_USD:
                out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": c_cval, "side": "LONG"})
        elif thesis == "L_NEW_common_eq":
            if p_csh == 0 and c_csh > 0 and c_cval >= MIN_USD:
                out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": 1.0, "side": "LONG"})
        elif thesis == "L_INC_common_only":
            if p_csh > 0 and delta_csh > 0 and delta_csh * c_price >= MIN_USD:
                out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": delta_csh * c_price, "side": "LONG"})
        elif thesis == "L_NEW_plus_INC_common":
            if c_csh > 0 and delta_csh > 0 and delta_csh * c_price >= MIN_USD:
                out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": delta_csh * c_price, "side": "LONG"})
        elif thesis == "L_NEW_calls_underlying":
            if p_callsh == 0 and c_callsh > 0 and c_callval >= MIN_USD:
                out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": c_callval, "side": "LONG"})
        elif thesis == "L_NEW_plus_INC_calls_underlying":
            d_call = c_callsh - p_callsh
            if c_callsh > 0 and d_call > 0:
                d_callval = c_callval - p.get("call_value", 0)
                if d_callval >= MIN_USD:
                    out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": d_callval, "side": "LONG"})
        elif thesis == "S_NEW_puts_underlying":
            # SA initiates put = bearish on underlying; we SHORT the underlying
            c_putsh = c.get("put_shares", 0); c_putval = c.get("put_value", 0)
            p_putsh = p.get("put_shares", 0)
            if p_putsh == 0 and c_putsh > 0 and c_putval >= MIN_USD_PUT:
                out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": c_putval, "side": "SHORT"})
        elif thesis == "S_NEW_plus_INC_puts_underlying":
            c_putsh = c.get("put_shares", 0); c_putval = c.get("put_value", 0)
            p_putsh = p.get("put_shares", 0); p_putval = p.get("put_value", 0)
            if c_putsh > 0 and (c_putsh - p_putsh) > 0:
                d_putval = c_putval - p_putval
                if d_putval >= MIN_USD_PUT:
                    out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": d_putval, "side": "SHORT"})
        # Short theses
        elif thesis == "S_EXIT_ALL_only":
            if p_csh > 0 and c_csh == 0 and c.get("call_shares", 0) == 0 and c.get("put_shares", 0) == 0 and p_cval >= MIN_USD:
                out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": p_cval, "side": "SHORT"})
        elif thesis == "S_DEC_common_only":
            if p_csh > 0 and c_csh > 0 and delta_csh < 0:
                liq = (-delta_csh) * p_price
                if liq >= MIN_USD:
                    out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": liq, "side": "SHORT"})
        elif thesis == "S_EXIT_plus_DEC_common":
            if p_csh > 0 and c_csh < p_csh:
                shares_sold = p_csh - c_csh
                liq = shares_sold * p_price
                if liq >= MIN_USD:
                    out.append({"issuer_norm": k, "issuer_raw": issuer_raw, "weight": liq, "side": "SHORT"})
        elif thesis == "L_minus_S_NEW_INC_vs_EXIT_DEC":
            # placeholder — composite computed separately
            pass

    return out


def load_ticker_map():
    rows = list(csv.DictReader(open(DATA / "cusip_ticker_map.csv")))
    return {r["issuer"].upper().strip(): r["ticker"] for r in rows}


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


def compute_basket_returns(basket, cfg, intraday_by_t, daily_by_t):
    """Return dict of horizon -> weighted basket return."""
    if not basket:
        return {h: None for h in ["1h", "EOD", "D+1", "D+2"]}
    trading_day = cfg["trading_day"]
    entry_et = cfg["entry_et"]
    # 1h target
    one_hour = {"09:30": "10:30", "10:30": "11:30", "11:30": "12:30",
                "12:30": "13:30", "13:30": "14:30", "14:30": "15:30"}.get(entry_et, "15:30")
    eod_target = "15:30"

    rets = []
    for r in basket:
        tkr = r.get("ticker")
        if not tkr: continue
        ib = intraday_by_t.get(tkr, [])
        db = daily_by_t.get(tkr, [])
        eb = find_intraday_bar(ib, trading_day, entry_et)
        if not eb or eb["open"] is None: continue
        entry = eb["open"]
        h1 = find_intraday_bar(ib, trading_day, one_hour)
        eod = find_intraday_bar(ib, trading_day, eod_target)
        d1 = daily_at_offset(db, trading_day, 1)
        d2 = daily_at_offset(db, trading_day, 2)
        rets.append({
            "weight": r["weight"],
            "1h": (h1["close"] / entry - 1) if h1 and h1["close"] else None,
            "EOD": (eod["close"] / entry - 1) if eod and eod["close"] else None,
            "D+1": (d1["close"] / entry - 1) if d1 and d1["close"] else None,
            "D+2": (d2["close"] / entry - 1) if d2 and d2["close"] else None,
        })
    out = {}
    for h in ["1h", "EOD", "D+1", "D+2"]:
        tw = sum(x["weight"] for x in rets if x[h] is not None)
        out[h] = (sum(x["weight"] * x[h] for x in rets if x[h] is not None) / tw) if tw else None
    return out


def main():
    holdings = load_holdings()
    tmap = load_ticker_map()

    # Pull all needed prices once
    all_tickers = set(tmap.values()) | {"SPY"}
    intraday_by_t, daily_by_t = {}, {}
    intraday_start = "2025-05-12"
    intraday_end = "2026-02-15"
    daily_start = "2025-05-10"
    daily_end = "2026-02-20"
    print(f"Pulling prices for {len(all_tickers)} tickers...")
    for t in sorted(all_tickers):
        try:
            intraday_by_t[t] = prices.get_intraday(t, intraday_start, intraday_end, "60m")
        except Exception as e:
            intraday_by_t[t] = []
        try:
            daily_by_t[t] = prices.get(t, daily_start, daily_end)
        except Exception as e:
            daily_by_t[t] = []

    prior_for = PRIOR_FOR

    THESES = [
        ("L_NEW_common_size",               "Long NEW common (size-wt by cur $)"),
        ("L_NEW_common_eq",                 "Long NEW common (equal-wt)"),
        ("L_INC_common_only",               "Long INC common only (Δ$ wt)"),
        ("L_NEW_plus_INC_common",           "Long NEW+INC common (Δ$ wt)"),
        ("L_NEW_calls_underlying",          "Long underlying of NEW call options"),
        ("L_NEW_plus_INC_calls_underlying", "Long underlying of NEW+INC calls"),
        ("S_EXIT_ALL_only",                 "Short EXIT-only common (prior $ wt)"),
        ("S_DEC_common_only",               "Short DEC-only common (Δsold × prior $)"),
        ("S_EXIT_plus_DEC_common",          "Short EXIT+DEC common"),
        ("S_NEW_puts_underlying",           "Short underlying of NEW put options"),
        ("S_NEW_plus_INC_puts_underlying",  "Short underlying of NEW+INC puts"),
    ]

    # Header
    rows = []
    for period in PERIODS:
        cfg = FILINGS[period]
        cur = issuer_state(holdings[period])
        prior = issuer_state(holdings[prior_for[period]])
        # SPY benchmark returns at each horizon
        spy_bench = compute_basket_returns(
            [{"weight": 1.0, "ticker": "SPY"}], cfg,
            {"SPY": intraday_by_t["SPY"]}, {"SPY": daily_by_t["SPY"]}
        )
        for tk, label in THESES:
            basket = basket_for_thesis(tk, cur, prior)
            for r in basket:
                r["ticker"] = tmap.get(r["issuer_norm"]) or tmap.get(r["issuer_raw"].upper().strip())
            ret = compute_basket_returns(basket, cfg, intraday_by_t, daily_by_t)

            # For SHORT theses, PnL is negated
            side = "LONG"
            if tk.startswith("S_"):
                side = "SHORT"
                ret_pnl = {h: (-v if v is not None else None) for h, v in ret.items()}
            else:
                ret_pnl = ret

            spy_adj = {h: ((ret_pnl[h] - (spy_bench[h] if side == "LONG" else -spy_bench[h])) if ret_pnl[h] is not None and spy_bench[h] is not None else None) for h in ["1h", "EOD", "D+1", "D+2"]}

            rows.append({
                "filing": cfg["label"], "thesis": label, "side": side, "n": len(basket),
                **{f"raw_{h}": ret_pnl[h] for h in ["1h", "EOD", "D+1", "D+2"]},
                **{f"spy_{h}": spy_adj[h] for h in ["1h", "EOD", "D+1", "D+2"]},
            })

    # Composite long-short row per filing
    for period in PERIODS:
        cfg = FILINGS[period]
        cur = issuer_state(holdings[period])
        prior = issuer_state(holdings[prior_for[period]])
        L = basket_for_thesis("L_NEW_plus_INC_common", cur, prior)
        S = basket_for_thesis("S_EXIT_plus_DEC_common", cur, prior)
        for r in L + S:
            r["ticker"] = tmap.get(r["issuer_norm"]) or tmap.get(r["issuer_raw"].upper().strip())
        L_ret = compute_basket_returns(L, cfg, intraday_by_t, daily_by_t)
        S_ret = compute_basket_returns(S, cfg, intraday_by_t, daily_by_t)
        spy_bench = compute_basket_returns(
            [{"weight": 1.0, "ticker": "SPY"}], cfg,
            {"SPY": intraday_by_t["SPY"]}, {"SPY": daily_by_t["SPY"]}
        )
        # Net L-S PnL: long pnl + short pnl. SPY-adjusted is dollar-neutral so SPY cancels.
        net_raw = {h: (L_ret[h] + (-S_ret[h] if S_ret[h] is not None else 0)) if L_ret[h] is not None else None for h in ["1h", "EOD", "D+1", "D+2"]}
        # SPY-adjusted of dollar-neutral L-S: just net_raw (long-spy cancels with short-(-spy)=long+spy → no, careful)
        # Properly: (L - SPY) + (-S - (-SPY)) = L - SPY - S + SPY = L - S = net_raw. Correct, SPY cancels.
        rows.append({
            "filing": cfg["label"], "thesis": "L−S: NEW+INC long, EXIT+DEC short",
            "side": "L−S", "n": f"{len(L)}+{len(S)}",
            **{f"raw_{h}": net_raw[h] for h in ["1h", "EOD", "D+1", "D+2"]},
            **{f"spy_{h}": net_raw[h] for h in ["1h", "EOD", "D+1", "D+2"]},
        })

    # Print as table
    fmt = lambda x: f"{100*x:+6.2f}%" if x is not None else "  n/a "
    print(f"\n{'Filing':<8} {'Thesis':<48} {'Side':<5} {'N':>6} | {'1h':>8} {'EOD':>8} {'D+1':>8} {'D+2':>8} | {'1h_SPY':>8} {'EOD_SPY':>8} {'D+1_SPY':>8} {'D+2_SPY':>8}")
    print("-" * 152)
    for r in rows:
        print(f"{r['filing']:<8} {r['thesis']:<48} {r['side']:<5} {str(r['n']):>6} | "
              f"{fmt(r['raw_1h'])} {fmt(r['raw_EOD'])} {fmt(r['raw_D+1'])} {fmt(r['raw_D+2'])} | "
              f"{fmt(r['spy_1h'])} {fmt(r['spy_EOD'])} {fmt(r['spy_D+1'])} {fmt(r['spy_D+2'])}")

    # Save CSV
    out_csv = RESULTS / "thesis_grid.csv"
    cols = ["filing", "thesis", "side", "n",
            "raw_1h", "raw_EOD", "raw_D+1", "raw_D+2",
            "spy_1h", "spy_EOD", "spy_D+1", "spy_D+2"]
    with out_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        w.writerows(rows)
    print(f"\nWrote {out_csv}")


if __name__ == "__main__":
    main()
