# Placebo: Was the Put-Short Thesis Just Trend Continuation?

**Question:** for each name SA newly put on (NVDA, MU, TSMC, AVGO, CRWV, SMH, INFY), had the underlying already been declining vs SPY *before* the disclosure date? If so, the post-event short PnL is largely trend continuation — alpha that was already in the price by filing time.

## Per-name detail (close-to-close, SPY-adjusted)

| Ticker | SA $ | Pre-30d | Pre-20d | Pre-5d | Post +1 | Post +2 | −15% filter |
|---|---|---|---|---|---|---|---|
| SMH (Q2) | $570M | +3.2% | +0.6% | +1.5% | **−1.6%** | −1.2% | PASS |
| NVDA (Q3) | $299M | −0.8% | +0.8% | −0.9% | +0.8% | −1.2% | PASS |
| **CRWV (Q3)** | $192M | **−42.3%** | **−43.9%** | −24.8% | −2.9% | −2.6% | **SKIP** |
| TSM (Q3) | $75M | −3.8% | −5.5% | −1.7% | +0.9% | +0.3% | PASS |
| **MU (Q3)** | $50M | **+25.7%** | **+15.9%** | −0.6% | **+3.1%** | −1.8% | PASS |
| AVGO (Q3) | $76M | +0.1% | −3.8% | −2.9% | +1.7% | +1.9% | PASS |
| INFY (Q4) | $9M | −10.5% | −5.0% | −1.6% | **−12.9%** | −9.9% | PASS |

Numbers are **stock returns** vs SPY. Flip sign for short PnL: a negative pre-20d means short PnL was *positive* pre-event.

## Pre vs Post (pooled)

| Window | Mean short PnL (SPY-adj) | SD |
|---|---|---|
| Pre [t−20, t−1] | **+5.84%** | 18.32% |
| Pre [t−5, t−1] | +4.42% | 9.10% |
| Post [t−1, t+1] | +1.56% | 5.38% |
| Post [t−1, t+2] | +2.07% | 3.75% |

**The pre-event 20-day move is 3.7× the post-event 1-day move.** Most of the trend was already in the price by filing date — this is the trend-continuation confound the README warned about.

## Sharpe estimates (per firm-event)

| Config | N | Mean | SD | Sharpe |
|---|---|---|---|---|
| Unfiltered, post +1 | 7 | +1.56% | 5.38% | **0.29** |
| Unfiltered, post +2 | 7 | +2.07% | 3.75% | **0.55** |
| Filter PASS only, post +1 | 6 | +1.34% | 5.86% | 0.23 |
| Filter PASS only, post +2 | 6 | +1.98% | 4.10% | 0.48 |

These numbers are lower than the 0.69–1.00 reported in `sharpe_puts.py` because that script used intraday entry (12:30 ET or 9:30 ET) rather than close-to-close. Different windows, different signals; the honest Sharpe band is **0.3 (conservative) to 0.7 (favorable entry)**.

## Three findings worth carrying forward

**1. The trend-exhaustion filter at −15% only catches CRWV.** That's the right call — CRWV had collapsed −44% in 20 days; no honest trade is going to capture much of that residue. But the filter doesn't help with the rest of the basket because most names had pre-event moves inside the −15% threshold.

**2. The single most legitimate-looking signal is MU.** Up +16% vs SPY in the 20d before SA's put was filed, then down −3% post. This is the only name where the put functioned as a real contrarian top-call rather than ride-the-trend. With one observation we can't conclude anything, but the pattern is the kind of signal we'd want to test if more data accumulates: "puts on names that had been rallying" might be where the actual disclosure effect lives.

**3. INFY is mostly a fresh shock, not trend continuation.** −5% pre-event, −13% post. Indian-IT had a regime shift in early Feb 2026 that hit on disclosure day. Good for the thesis, bad for generalizability (the post-event move had its own news catalyst, not driven by SA's disclosure).

## Updated take on Rule v2

The placebo doesn't kill the strategy but does temper expectations:

- **Realistic Sharpe band: 0.3–0.7 per trade**, depending on entry framework
- **Filter at −15%:** keep it (cheap insurance against CRWV-class blowups), but it's not the main lever
- **Future filter direction:** "puts on names with positive pre-event 20d SPY-adj return" — i.e., trade SA's contrarian top-calls, skip ride-the-trend puts. Premature to apply with N=7
- **Live capital decision:** unchanged. Paper-only on 2026-05-15. Re-evaluate after 2 paper events accumulate

## Files

- Source: `src/placebo_puts.py`
- Per-event detail: `results/placebo_puts.csv`
