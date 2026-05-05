# SA_Bet — Thesis Grid Report

**Date:** 2026-05-04
**Sample:** 4 filings (Q1, Q2, Q3, Q4 of 2025), entry within 10 minutes of acceptance, exit at close of day 0 / day +1 / day +2.
**Benchmark:** SPY return over the same window.

## Pooled results — ranked by D+1 SPY-adjusted mean

| Thesis | Side | Filings | 1h SPY | **D+1 SPY** | D+2 SPY | Win @ D+1 | Win @ D+2 |
|---|---|---|---|---|---|---|---|
| **Short underlying of NEW put options** | SHORT | 3 | +0.45% | **+4.25%** | +3.46% | **3/3** | 3/3 |
| Short underlying of NEW+INC puts | SHORT | 3 | +0.45% | +4.25% | +3.46% | 3/3 | 3/3 |
| **Short EXIT-only common** | SHORT | 4 | +1.16% | **+1.31%** | +0.24% | **3/4** | 3/4 |
| Short EXIT+DEC common | SHORT | 4 | +0.97% | +0.95% | +0.03% | 2/4 | 2/4 |
| Short DEC-only common | SHORT | 1 | −0.76% | +0.09% | −0.27% | 1/1 | 0/1 |
| Long underlying of NEW call options | LONG | 3 | +0.45% | −0.00% | +0.92% | 1/3 | 1/3 |
| L−S net (NEW+INC long, EXIT+DEC short) | L−S | 4 | −0.02% | −0.67% | −0.03% | 2/4 | 2/4 |
| Long underlying of NEW+INC calls | LONG | 3 | −1.05% | −0.84% | −0.65% | 1/3 | 1/3 |
| Long NEW+INC common (Δ$ wt) | LONG | 4 | −1.00% | −1.62% | −0.06% | **0/4** | 2/4 |
| Long INC common only (Δ$ wt) | LONG | 4 | −1.04% | −1.79% | +0.06% | **0/4** | 2/4 |
| Long NEW common (equal-wt) | LONG | 3 | −1.10% | −2.00% | +1.80% | **0/3** | 2/3 |
| Long NEW common (size-wt) | LONG | 3 | −0.68% | −2.47% | +0.61% | **0/3** | 2/3 |

## Key findings

**1. Every long thesis loses money at the disclosure window.** Buying what SA buys — whether NEW common, INC common, NEW+INC, or new-call underlyings — averages between −0.0% and −2.5% D+1 SPY-adjusted. Win rates are 0/3 or 0/4. The original Rule v1 ("buy new positions") was directionally wrong for a short-window trade.

**2. Shorting SA's PUT initiations is the strongest signal.** SA's put positions are explicit bearish bets, and the underlying stocks fell post-disclosure in 3/3 filings: Q2 (VanEck SMH puts), Q3 (NVDA + AVGO + MU + TSMC + CRWV puts, $810M notional), Q4 (Infosys puts).

**3. Shorting fully-exited common is the second-best signal** with +1.31% mean D+1 SPY-adj across all 4 filings, 3/4 win rate. Simpler and cleaner than DEC-only or EXIT+DEC combined.

**4. The L−S net thesis is essentially a wash** because the long side cancels the short side's edge. Long-only or short-only is more legible than long-short combined.

## Per-filing put-thesis detail (the headline result)

| Filing | New put names | Notional | D+1 SPY-adj |
|---|---|---|---|
| Q2 2025 | VanEck Semis ETF | $570M | +1.39% |
| Q3 2025 | NVDA, AVGO, MU, TSMC, CRWV | $691M | +1.25% |
| Q4 2025 | Infosys | $9M | +10.11% |

The Q4 result is a single small-cap idiosyncratic event (INFY −10%) and inflates the mean. Excluding Q4, the put-thesis edge is ~+1.3% — same order as the EXIT thesis.

## Caveats

- **N is small.** 4 filings, 7 firm-events for the put thesis, 11 for the EXIT thesis. Confidence intervals are wide; mean estimates are unstable.
- **Placebo not yet run on puts.** SA may have initiated puts after the underlying had already weakened (e.g., NVDA was likely declining before Aug 2025). If so, post-disclosure decline is trend continuation, not a disclosure effect. Need to test.
- **Q4 INFY drives the put-thesis mean.** Without it, edge is ~+1.3% across N=2 filings.
- **No transaction costs modeled.** Real shorts pay borrow costs; intraday entry slips. At a +1–2% gross edge, costs likely halve it.
- **Sector regime dependence.** Q3'25 was a weak window for AI semis. Put-thesis may not generalize to a strong-tape regime.

## Updated rule for the live system

> **Rule v2 candidate:** on filing detection, short the underlying of any name SA newly initiated a put position on (≥$1M notional), plus optionally short fully-exited common positions (prior value ≥$1M). Hold ~1 day to ~2 days. Skip the long side entirely.

This uses the same poller / parser / executor infrastructure as v1, with two changes:
- Trade direction (short, not long)
- Basket definition (puts + exits, not new commons)

## Recommended next steps

1. **Placebo on puts** — for each NEW put name, what was its [t−20, t−1] and [t−5, t−1] SPY-adjusted return? If it had already fallen sharply pre-event, the +1–4% post-event move is trend continuation, not disclosure causation.
2. **Borrow availability check** — confirm NVDA / AVGO / MU / TSMC / SMH and major exits are easily shortable on Alpaca (they should be — these are mega-caps).
3. **If placebo passes:** rebuild Rule v1 → Rule v2 in the executor and paper-trade the 2026-05-15 filing.

## Files

- `src/theses.py` — basket definitions and per-filing returns
- `src/theses_summary.py` — pooled summary
- `results/thesis_grid.csv` — full per-(filing, thesis) results
- `results/figures/event_window_q3_q4.png` — cumulative return curves
