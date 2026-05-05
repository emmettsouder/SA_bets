"""Placebo test: were short-basket names already declining before the filing?

Plus visualizations of cumulative SPY-adjusted returns through the event window
for both Q3 2025 and Q4 2025 filings.
"""

import csv
import sys
from datetime import datetime, timedelta
from pathlib import Path

import matplotlib.pyplot as plt
import matplotlib.dates as mdates

sys.path.insert(0, str(Path(__file__).resolve().parent))
import prices
from filing_analysis import load_long_short_baskets, load_ticker_map, FILINGS

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results"
FIGS = RESULTS / "figures"
FIGS.mkdir(parents=True, exist_ok=True)

PRE_DAYS = 30
POST_DAYS = 45


def daily_index_for_date(bars, target_date):
    for i, b in enumerate(bars):
        if b["date"] >= target_date:
            return i
    return None


def cumulative_returns_around_event(bars, event_date, pre=PRE_DAYS, post=POST_DAYS):
    """Return list of (offset, cum_return) where cum_return is cumulative
    log-style return relative to close at offset = -1 (last close before event).
    Offsets range over actual trading days in [-pre, +post]."""
    idx0 = daily_index_for_date(bars, event_date)
    if idx0 is None:
        return []
    # Reference: close of bar immediately before event_date
    if idx0 - 1 < 0:
        return []
    ref = bars[idx0 - 1]["close"]
    if not ref:
        return []
    out = []
    for j in range(max(0, idx0 - pre), min(len(bars), idx0 + post + 1)):
        offset = j - idx0  # 0 = event day's close, -1 = day before event
        c = bars[j]["close"]
        if c is None:
            continue
        out.append((offset, c / ref - 1, bars[j]["date"]))
    return out


def basket_curve(rows, prices_by_ticker, event_date, pre=PRE_DAYS, post=POST_DAYS):
    """Weighted-mean cumulative return curve for a basket."""
    per_ticker_curves = []
    weights = []
    for r in rows:
        bars = prices_by_ticker.get(r["ticker"], [])
        if not bars:
            continue
        curve = cumulative_returns_around_event(bars, event_date, pre, post)
        if not curve:
            continue
        per_ticker_curves.append({(o): v for o, v, _ in curve})
        weights.append(r["weight"])
    if not per_ticker_curves:
        return []
    # Aggregate weighted average per offset
    all_offsets = sorted(set().union(*[set(c.keys()) for c in per_ticker_curves]))
    out = []
    for o in all_offsets:
        vals = [(c[o], w) for c, w in zip(per_ticker_curves, weights) if o in c]
        if not vals: continue
        tw = sum(w for _, w in vals)
        if tw == 0: continue
        out.append((o, sum(v * w for v, w in vals) / tw))
    return out


def placebo_window(curve, start_off, end_off):
    """Return cumulative return between start_off and end_off (inclusive)."""
    pts = dict(curve)
    if start_off not in pts or end_off not in pts:
        # Find nearest available
        offs = sorted(pts.keys())
        start_off = max((o for o in offs if o <= start_off), default=None)
        end_off = min((o for o in offs if o >= end_off), default=None)
        if start_off is None or end_off is None:
            return None
    return (1 + pts[end_off]) / (1 + pts[start_off]) - 1


def analyze_one(period, ax_top, ax_bot):
    cfg = FILINGS[period]
    longs, shorts = load_long_short_baskets(period)
    tmap = load_ticker_map()
    for r in longs + shorts:
        r["ticker"] = tmap.get(r["issuer_norm"]) or tmap.get(r["issuer_raw"].upper().strip())

    long_total = sum(r["weight_basis"] for r in longs)
    short_total = sum(r["weight_basis"] for r in shorts)
    for r in longs: r["weight"] = r["weight_basis"] / long_total
    for r in shorts: r["weight"] = r["weight_basis"] / short_total

    event_date = cfg["trading_day"]
    # Pull daily bars wide enough for placebo + post windows
    start_pull = (datetime.fromisoformat(event_date) - timedelta(days=int(PRE_DAYS * 1.6))).strftime("%Y-%m-%d")
    end_pull = (datetime.fromisoformat(event_date) + timedelta(days=int(POST_DAYS * 1.6))).strftime("%Y-%m-%d")

    tickers = list({r["ticker"] for r in longs + shorts if r.get("ticker")}) + ["SPY"]
    daily = {}
    for t in tickers:
        try:
            daily[t] = prices.get(t, start_pull, end_pull)
        except Exception as e:
            print(f"  FAIL daily {t}: {e}")
            daily[t] = []

    # Compute basket curves
    long_curve = basket_curve(longs, daily, event_date)
    short_curve = basket_curve(shorts, daily, event_date)
    spy_bars = daily["SPY"]
    spy_curve_full = cumulative_returns_around_event(spy_bars, event_date)
    spy_curve = [(o, v) for o, v, _ in spy_curve_full]

    # SPY-adjusted = subtract SPY at same offset
    spy_dict = dict(spy_curve)
    long_adj = [(o, v - spy_dict.get(o, 0)) for o, v in long_curve if o in spy_dict]
    # Short PnL = -stock_return; SPY-adj short PnL = -stock - (-SPY) = SPY - stock
    # Equivalently: short stock return - SPY = (raw short) - SPY, and short PnL = -(that). Show both perspectives:
    short_adj_stock = [(o, v - spy_dict.get(o, 0)) for o, v in short_curve if o in spy_dict]
    short_pnl_adj = [(o, -v) for o, v in short_adj_stock]  # SPY-neutral PnL of the short

    # --- Placebo & post-event tabulation ---
    def pct(x):
        return f"{100*x:+6.2f}%" if x is not None else "  n/a "

    print(f"\n--- {cfg['label']} placebo + post-event windows ---")
    print(f"All values are SPY-adjusted cumulative basket returns.\n")
    print(f"{'Window':<22s} {'Long basket':>15s} {'Short stock':>15s} {'Short PnL':>15s}")
    long_a = dict(long_adj)
    short_stock_a = dict(short_adj_stock)
    short_pnl_a = dict(short_pnl_adj)

    for label, a, b in [
        ("[t-20, t-1] (placebo)", -20, -1),
        ("[t-5,  t-1] (placebo)", -5, -1),
        ("[t-1,  t+1] (event)",   -1, 1),
        ("[t-1,  t+5] (event)",   -1, 5),
        ("[t-1,  t+20]",          -1, 20),
    ]:
        l = placebo_window(list(long_a.items()), a, b)
        ss = placebo_window(list(short_stock_a.items()), a, b)
        sp = -ss if ss is not None else None
        print(f"  {label:<22s} {pct(l):>15} {pct(ss):>15} {pct(sp):>15}")

    # --- Plot top: cumulative basket vs SPY ---
    if long_curve:
        ox, oy = zip(*long_curve)
        ax_top.plot(ox, [100*v for v in oy], color="steelblue", lw=2, label=f"Long basket (N={len(longs)})")
    if short_curve:
        ox, oy = zip(*short_curve)
        ax_top.plot(ox, [100*v for v in oy], color="firebrick", lw=2, label=f"Short basket stocks (N={len(shorts)})")
    if spy_curve:
        ox, oy = zip(*spy_curve)
        ax_top.plot(ox, [100*v for v in oy], color="gray", lw=1.5, ls="--", label="SPY")

    ax_top.axvline(0, color="black", lw=0.7, ls=":")
    ax_top.axhline(0, color="black", lw=0.5)
    ax_top.set_xlabel("Trading days from filing event")
    ax_top.set_ylabel("Cumulative return (%)")
    ax_top.set_title(f"{cfg['label']} filing — raw cumulative returns (vs SPY)\nEvent: {cfg['acceptance_et']} ET")
    ax_top.legend(loc="upper left", fontsize=9)
    ax_top.grid(alpha=0.3)

    # --- Plot bottom: SPY-adjusted long basket and short PnL ---
    if long_adj:
        ox, oy = zip(*long_adj)
        ax_bot.plot(ox, [100*v for v in oy], color="steelblue", lw=2, label="Long basket − SPY")
    if short_pnl_adj:
        ox, oy = zip(*short_pnl_adj)
        ax_bot.plot(ox, [100*v for v in oy], color="firebrick", lw=2, label="Short PnL − SPY  (= SPY − short stocks)")
    # Also long-short net PnL adjusted: (long - SPY) + (-short - (-SPY)) = (long - SPY) + (SPY - short) = long - short
    if long_adj and short_adj_stock:
        la = dict(long_adj); sa = dict(short_adj_stock)
        common = sorted(set(la) & set(sa))
        ls_net = [(o, la[o] - sa[o]) for o in common]
        ox, oy = zip(*ls_net)
        ax_bot.plot(ox, [100*v for v in oy], color="darkgreen", lw=2, ls="-.", label="Long − Short (net)")

    ax_bot.axvline(0, color="black", lw=0.7, ls=":")
    ax_bot.axhline(0, color="black", lw=0.5)
    # Shade the placebo window
    ax_bot.axvspan(-20, -1, alpha=0.08, color="orange", label="placebo window [t−20, t−1]")
    ax_bot.set_xlabel("Trading days from filing event")
    ax_bot.set_ylabel("SPY-adjusted cum. return (%)")
    ax_bot.set_title(f"{cfg['label']} — SPY-adjusted strategy returns")
    ax_bot.legend(loc="best", fontsize=9)
    ax_bot.grid(alpha=0.3)

    return longs, shorts, daily, spy_curve_full


def per_name_bars():
    """One figure: per-name day-1 returns by basket side, both filings."""
    fig, axs = plt.subplots(1, 2, figsize=(14, 6), sharey=True)
    for ax, period in zip(axs, ["2025-09-30", "2025-12-31"]):
        cfg = FILINGS[period]
        longs, shorts = load_long_short_baskets(period)
        tmap = load_ticker_map()
        for r in longs + shorts:
            r["ticker"] = tmap.get(r["issuer_norm"]) or tmap.get(r["issuer_raw"].upper().strip())

        event_date = cfg["trading_day"]
        start_pull = (datetime.fromisoformat(event_date) - timedelta(days=10)).strftime("%Y-%m-%d")
        end_pull = (datetime.fromisoformat(event_date) + timedelta(days=10)).strftime("%Y-%m-%d")
        all_t = list({r["ticker"] for r in longs + shorts if r.get("ticker")}) + ["SPY"]
        daily = {t: prices.get(t, start_pull, end_pull) for t in all_t}

        spy_bars = daily["SPY"]
        spy_curve = dict((o, v) for o, v, _ in cumulative_returns_around_event(spy_bars, event_date))
        spy_d1 = spy_curve.get(1, 0)

        items = []
        for r in longs:
            b = daily.get(r["ticker"], [])
            curve = cumulative_returns_around_event(b, event_date)
            d1_raw = next((v for o, v, _ in curve if o == 1), None)
            if d1_raw is None: continue
            items.append((r["ticker"], "LONG", d1_raw - spy_d1, r["weight_basis"]))
        l_total = sum(w for _, s, _, w in items if s == "LONG")
        items = [(t, s, r, (w / l_total if s == "LONG" else 0)) for (t, s, r, w) in items]

        s_items = []
        for r in shorts:
            b = daily.get(r["ticker"], [])
            curve = cumulative_returns_around_event(b, event_date)
            d1_raw = next((v for o, v, _ in curve if o == 1), None)
            if d1_raw is None: continue
            # Short PnL = -stock_return. SPY-adjusted PnL = -stock - (-SPY) = SPY - stock
            s_items.append((r["ticker"], "SHORT", spy_d1 - d1_raw, r["weight_basis"]))
        s_total = sum(w for _, s, _, w in s_items)
        s_items = [(t, s, r, (w / s_total if s_total else 0)) for (t, s, r, w) in s_items]

        all_items = items + s_items
        all_items.sort(key=lambda x: (x[1], -x[3]))  # group by side, then weight desc

        labels = [f"{t}\n{wt*100:.0f}%" for t, _, _, wt in all_items]
        rets = [r * 100 for _, _, r, _ in all_items]
        colors = ["steelblue" if s == "LONG" else "firebrick" for _, s, _, _ in all_items]
        x = list(range(len(all_items)))
        ax.bar(x, rets, color=colors, edgecolor="black", lw=0.5)
        ax.set_xticks(x); ax.set_xticklabels(labels, fontsize=8, rotation=45, ha="right")
        ax.axhline(0, color="black", lw=0.7)
        # Vertical line separating long/short
        n_long = sum(1 for _, s, _, _ in all_items if s == "LONG")
        if 0 < n_long < len(all_items):
            ax.axvline(n_long - 0.5, color="black", ls=":", lw=0.7)
        ax.set_ylabel("Day +1 SPY-adjusted return (%)")
        ax.set_title(f"{cfg['label']} — per-name Day +1 SPY-adj return\nblue = LONG ('we bought'), red = SHORT PnL ('we sold')")
        ax.grid(axis="y", alpha=0.3)

    fig.tight_layout()
    out = FIGS / "per_name_d1.png"
    fig.savefig(out, dpi=130)
    print(f"\nSaved {out}")


def main():
    fig, axs = plt.subplots(2, 2, figsize=(14, 9))
    print("Q3 2025 filing".center(72, "="))
    analyze_one("2025-09-30", axs[0, 0], axs[1, 0])
    print("\n" + "Q4 2025 filing".center(72, "="))
    analyze_one("2025-12-31", axs[0, 1], axs[1, 1])
    fig.tight_layout()
    out = FIGS / "event_window_q3_q4.png"
    fig.savefig(out, dpi=130)
    print(f"\nSaved {out}")
    plt.close(fig)

    per_name_bars()


if __name__ == "__main__":
    main()
