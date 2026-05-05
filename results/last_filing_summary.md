# Last Filing (2026-02-11) — Position-Size-Weighted Analysis

**Filing:** Situational Awareness LP, 2025-Q4 13F-HR
**Acceptance:** 2026-02-11 03:31 ET (pre-market, Wednesday)
**Entry assumption:** 9:30 ET open of 2026-02-11 (acceptance was ~6 hours pre-open, well within 10-min SLA)
**Basket:** 8 NEW common-stock positions (≥$1M), position-size-weighted by SA's reported value

## Basket composition

| Ticker | Issuer | SA value | Weight |
|---|---|---|---|
| KRC | Kilroy Realty | $49.6M | **30.51%** |
| WYFI | WhiteFiber | $27.8M | 17.08% |
| PSIX | Power Solutions Intl | $24.7M | 15.19% |
| CLSK | CleanSpark | $16.6M | 10.21% |
| BITF | Bitfarms | $16.2M | 9.97% |
| LBRT | Liberty Energy | $10.5M | 6.44% |
| PUMP | ProPetro | $8.7M | 5.32% |
| BW | Babcock & Wilcox | $8.6M | 5.28% |
| **Total** | | **$162.6M** | 100% |

## Returns (position-size-weighted)

| Horizon | Basket (wtd) | SPY | SMH | QQQ | vs SPY | vs SMH | vs QQQ |
|---|---|---|---|---|---|---|---|
| **Intraday** (entry 9:30 ET → exit at:) | | | | | | | |
| 10:30 ET (1h) | −1.00% | −0.65% | −0.32% | −0.88% | **−0.35%** | −0.68% | −0.12% |
| 11:30 ET (2h) | −1.30% | −0.40% | +0.39% | −0.51% | **−0.90%** | −1.69% | −0.79% |
| 12:30 ET (3h) | −2.64% | −0.52% | +0.14% | −0.56% | **−2.12%** | −2.78% | −2.09% |
| 13:30 ET (4h) | −2.19% | −0.38% | +0.49% | −0.28% | −1.81% | −2.68% | −1.91% |
| 14:30 ET (5h) | −3.12% | −0.59% | +0.46% | −0.53% | −2.53% | −3.59% | −2.60% |
| 15:30 ET (~EOD) | −2.55% | −0.64% | +0.26% | −0.55% | **−1.91%** | −2.81% | −1.99% |
| **Multi-day** (entry day-0 open → close day +n) | | | | | | | |
| Day +1 | −4.43% | −2.17% | −1.87% | −2.55% | **−2.26%** | −2.56% | −1.88% |
| Day +2 | +0.61% | −2.10% | −1.48% | −2.35% | +2.72% | +2.09% | +2.96% |
| Day +3 | −1.78% | −1.94% | −1.53% | −2.45% | +0.16% | −0.25% | +0.67% |
| Day +5 | −3.09% | −1.71% | −0.88% | −2.09% | −1.38% | −2.21% | −1.00% |
| Day +10 | +0.49% | −1.02% | −0.44% | −1.16% | +1.51% | +0.93% | +1.65% |
| Day +20 | −6.66% | −4.36% | −6.21% | −3.10% | −2.30% | −0.45% | −3.56% |
| Day +40 | −5.15% | −2.43% | +5.57% | −0.86% | −2.72% | **−10.72%** | −4.29% |

## Per-name detail

| Ticker | Weight | Entry | 1h | Day +1 | Day +5 | Day +20 |
|---|---|---|---|---|---|---|
| KRC | 30.5% | $33.54 | +0.78% | **−9.63%** | −3.13% | −12.58% |
| WYFI | 17.1% | $19.35 | −1.99% | −5.99% | −7.80% | −13.33% |
| PSIX | 15.2% | $85.68 | −0.87% | +8.22% | −1.05% | −29.31% |
| CLSK | 10.2% | $10.06 | −2.14% | −7.46% | −2.39% | −5.07% |
| BITF | 10.0% | $2.23 | −2.47% | −7.17% | −6.73% | −0.45% |
| LBRT | 6.4% | $24.81 | −0.85% | −0.16% | +8.38% | +22.13% |
| PUMP | 5.3% | $11.33 | +2.29% | −0.53% | +1.50% | +27.01% |
| BW | 5.3% | $10.00 | −6.96% | −3.80% | −6.60% | +30.50% |

## Honest interpretation

**Was Rule v1, position-size-weighted, +EV after the last filing?** No. At every short horizon (1h–EOD–day+1) the basket was negative both raw and SPY-adjusted. 7 of 8 names were down on day +1. The 30%-weight name (KRC) was the worst on day +1 at −9.6%, dragging the whole basket.

**Statistical caveat: N=1.** Single-event observations don't generalize. The pooled N=29 (equal-weight, 3 filings) showed +0.4% mean SPY-adjusted with t=0.5 — also not significant. The most recent filing being the worst of the three is suggestive but not conclusive.

**Why this matters more than it should given N=1:** the most recent filing is the most relevant predictor of how the next filing (~2026-05-15) will behave, since fund composition, AUM, and market regime are closest to current. Two months ago looks much more like next week than 14 months ago does.

**Position-size weighting was *worse* than equal-weight here.** The pool's worst day-1 names happened to be the heavily-weighted ones. Going forward, equal-weight is the safer default for v1 — size-weighting concentrates risk in whatever name SA happened to make biggest, and SA's portfolio construction is not optimized for a 1-day post-disclosure trade.

**KRC the puzzle.** Kilroy Realty is a coastal-CA office REIT — odd in a book otherwise dominated by AI-power/data-center names. Plausibly held as a real-estate proxy for AI campus demand, but it's the kind of position-type-mismatch that suggests "new positions" alone is too crude a signal. Filtering by sector congruence with the rest of the book might improve the rule, but that's a refinement we cannot calibrate at this sample size without overfitting.

## Implications for the 2026-05-15 filing

1. **Paper-only is the right call** — confirmed, not just by the pooled N=29 result but by the most recent N=1 datum being clearly negative.
2. **If/when we deploy live, prefer equal-weight over size-weight** for v1. SA's position sizing is built for a multi-quarter hold, not a 1-day post-disclosure trade.
3. **Consider a sector filter for v2.** Drop names that don't share the dominant book theme (AI infra). Would have excluded KRC. *Do not* implement this for v1 — it's a post-hoc fix and risks fitting noise.
4. **Day-0 intraday underperformance is the cleanest observation** in this dataset. The basket dropped 1.9% vs SPY in a 6-hour window with no overnight or macro confound. If a real "anti-edge" exists (i.e., disclosure causes selling pressure on already-running names), this is what it would look like. One observation, not enough to act on, but worth tracking on the next filing.

## Files

- `data/filings/tradeable_new_positions.csv` — basket source
- `data/cusip_ticker_map.csv` — ticker resolution
- `results/last_filing_analysis.csv` — per-name returns at every horizon
- `data/prices/*_intraday_60m.json` — cached hourly bars used in this analysis
