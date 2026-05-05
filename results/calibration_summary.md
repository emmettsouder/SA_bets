# Rule v1 Calibration — Historical Event Study Results

**Date:** 2026-05-04
**Sample:** 3 filings × ~10 new common-stock positions per filing = 29 firm-events
**Rule tested:** equal-weight long basket of NEW common-stock positions, 1-day hold

## Headline numbers

Headline metric is `d1_vwap_close`: enter at day-t VWAP proxy ((O+H+L+C)/4) on disclosure day, exit at day-(t+1) close. Approximates a ~10-minute-after-acceptance fill held to the next session's close.

| Metric | N | Mean | SD | t-stat | Positive |
|---|---|---|---|---|---|
| Raw 1-day return | 29 | **−0.21%** | 4.19% | −0.27 | 13/29 (45%) |
| SPY-adjusted | 29 | **+0.41%** | 4.20% | 0.52 | 15/29 (52%) |
| SMH-adjusted | 29 | **+0.38%** | 4.01% | 0.51 | 15/29 (52%) |

**No statistically meaningful edge.** All t-stats well below 1.0; sign test essentially coin-flip. Means are positive after benchmark adjustment but inside the noise floor.

## Per-filing breakdown

| Filing | Acceptance | N | Raw 1-day | SPY-adj 1-day | SMH-adj 1-day | Wider 5-day | Placebo (t−2→t−1) |
|---|---|---|---|---|---|---|---|
| 2025-Q1 | Wed 11:14 ET | 7 | −1.86% | −2.37% | −1.64% | +14.10% | +5.67% |
| 2025-Q3 | Fri 12:10 ET | 14 | +1.81% | +2.32% | +1.94% | −7.00% | −11.25% |
| 2025-Q4 | Wed 03:31 ET (pre-mkt) | 8 | −2.30% | −0.51% | −0.57% | −0.70% | −2.42% |

## Interpretation (honest)

1. **One outperforming filing, two neutral-to-negative.** Q3 was the only event where the basket beat its benchmarks. With N=3 filings, this is consistent with a true zero-mean effect plus noise *or* a real ~+50bp edge with a wide confidence interval — we can't distinguish them.

2. **The Q3 outperformance is suspicious.** That filing announced 14 names — many small-cap crypto-miner pivots (Cipher, Riot, Hut 8, Bitdeer, CleanSpark) during a hot week for AI compute. The basket may have ridden sector momentum rather than Aschenbrenner-disclosure alpha. Sector adjustment via SMH only partially controls for this; a better control would be a custom miner-pivot benchmark, but that's circular.

3. **Pre-event placebo is large.** Placebo magnitudes (+5.7%, −11.3%, −2.4%) are bigger than event-window returns. Signal-to-noise on these names is poor — you'd need a much stronger event effect to detect it cleanly.

4. **Wider window is mean-reverting.** Q1 had a +14% 5-day window after a flat 1-day window, while Q3 reversed −7%. No persistent multi-day drift evident — *if* there's an effect, it's concentrated in the first session.

## Decision

**Paper-trade the 2026-05-15 filing. Do not deploy live capital on it.**

Rationale:
- The point estimate is positive after benchmark adjustment but is not distinguishable from zero.
- Sample size makes any "deploy or kill" call premature.
- Paper costs nothing, exercises the live system, and adds one data point.
- Live capital should follow at least one more clean paper event (and ideally two), not just the first one.

**Re-evaluation gate:** after the 2026-Q2 filing (~Aug 14, 2026), we'll have 4 filings of paper data. If the cumulative SPY-adjusted return on Rule v1 is positive in 3 of 4 events with mean > +0.5%, consider a small live deployment. Otherwise paper-only continues or strategy is killed.

## Per-name detail (top movers)

**Worst 5 (1-day SPY-adj):**
- 2025-Q1  APLD  Applied Digital  −6.52%
- 2025-Q4  KRC   Kilroy Realty    −6.36%
- 2025-Q1  IREN  IREN Limited     −4.66%
- 2025-Q1  ONTO  Onto Innovation  −4.34%
- 2025-Q4  BITF  Bitfarms         −3.80%

**Best 5 (1-day SPY-adj):**
- 2025-Q4  PSIX  Power Solutions Intl  +10.37%
- 2025-Q3  LITE  Lumentum              +8.06%
- 2025-Q3  SNDK  SanDisk               +7.32%
- 2025-Q3  WDC   Western Digital       +5.28%
- 2025-Q3  HUT   Hut 8                 +5.27%

Pattern check (post-hoc — DO NOT use for rule selection):
- Both winners and losers are dominated by miners and storage/semi names. The same kind of name produced +5% in Q3 and −6% in Q1, depending on the broader tape. This is consistent with sector-noise dominance, not disclosure alpha.
- PSIX +10.4% on Q4 is a small-cap one-name event; its own news flow likely matters more than the 13F.

## Caveats

- **Survivorship and IPO timing.** WhiteFiber IPO'd mid-2025; CoreWeave IPO'd Mar 2025; SanDisk re-listed Feb 2025. Some "new in SA's book" names had little prior trading history, making benchmark betas unreliable.
- **VWAP proxy.** Without intraday data, VWAP is approximated by (O+H+L+C)/4. For pre-market acceptance (Q4'25), real entry would be near the open, which biases the proxy. Refining requires intraday bars.
- **No transaction costs.** Real fills will pay 5–20 bps slippage on thin small-caps. At this signal magnitude, costs likely dominate any positive mean.
- **Single-rule test.** Variants (large positions only, weight-tilted, top-N) not tested — deliberately, to avoid overfitting on N=3.
