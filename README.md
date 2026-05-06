# SA_bets

Backtest and live-trading framework for **Situational Awareness LP** 13F-HR disclosures (CIK 0002045724).

The thesis: Aschenbrenner's fund has unusual public profile, ~$5.5B AUM, and a focused AI-infra book. When a quarterly 13F drops, attention-driven copy-trading from retail and small funds may move disclosed names in the first hours/days post-acceptance. With <$100K capital we can enter inside that window before the slow money does.

## TL;DR

| Trade idea | Win @ D+1 | Mean D+1 SPY-adj | Per-trade Sharpe |
|---|---|---|---|
| **Short underlying of NEW puts** | **3/3** | **+4.25%** | 0.84 (filing) / 1.00 (firm-event, weighted) |
| Short EXIT-only common | 3/4 | +1.31% | — |
| Long NEW common (any flavor) | **0/3 to 0/4** | −1.6% to −2.5% | money-loser |

**Key inversion:** the original "buy what SA buys" rule loses on every variant tested. The signal in the filings is the **bearish side** — names SA puts on or fully exits. Across N=4 filings (Q1–Q4 2025), that's the only consistent edge.

**Confidence is low.** N=3–4 filings, ~7–11 firm-events. The +4.25% put-thesis mean is heavily skewed by INFY in Q4'25 (a $9M put on a single name that dropped 12%). Strip that and edge is ~+1.3% — same magnitude as the EXIT thesis. The placebo (was the move already happening pre-disclosure?) hasn't been definitively run on the put basket.

## The Strategy — Rule v2 (pre-registered before deployment)

```
TRIGGER     New 13F-HR from CIK 0002045724 (poll EDGAR submissions JSON)
ENTRY       acceptance + 10 min, at next available 60m bar
            (regular session) OR 9:30 ET open (if filed pre-market)
HOLD        to close of next trading day (~1 day)

LONG basket
  - NEW common positions (cur common value ≥ $1M)
  - INC common positions (Δshares × cur price ≥ $1M)
  - Underlying of NEW call options (call notional ≥ $1M)
  Weight: Δshares × current price

SHORT basket
  - EXIT_ALL common (prior common value ≥ $1M)
  - DEC common (shares-sold × prior price ≥ $1M)
  - Underlying of NEW put options (put notional ≥ $1M)
  Weight: shares-sold × prior price (or put notional)

PER-NAME FILTERS (applied before placing each order)
  - 20-day ADV ≥ $10M               (slippage control)
  - No earnings within ±3 days       (avoid own-news domination)
  - 20d SPY-adj return: skip longs >+15%, skip shorts <−15%
                                     (trend-exhaustion / placebo control)
  - Pre-event open gap: skip if >3% in trade direction
                                     (move already happened)

SIZING      Equal-weighted across passing names.
            $X total per side; cap per-name at $X / N_pass.
```

**Why these filters are defensible (won't overfit on N=4):** every choice is theory-motivated and pre-specified. Liquidity floors and earnings blackouts are standard quant hygiene; the trend-exhaustion filter directly addresses the placebo finding (most pre-disclosure declines were already in motion).

## Findings in detail

See [`results/thesis_grid_report.md`](results/thesis_grid_report.md) for the full thesis grid across all 4 filings, [`results/calibration_summary.md`](results/calibration_summary.md) for the original equal-weight pooled study, and [`results/last_filing_summary.md`](results/last_filing_summary.md) for the focused size-weighted Q4 2025 analysis.

Plots:
- [`results/figures/event_window_q3_q4.png`](results/figures/event_window_q3_q4.png) — cumulative SPY-adjusted basket trajectories for Q3 and Q4, showing the dramatic pre-event moves on both long and short baskets.
- [`results/figures/per_name_d1.png`](results/figures/per_name_d1.png) — per-name Day +1 contributions in each filing, showing huge cross-name dispersion.

### Top per-firm-event short-PnL results (D+1 SPY-adj)

| Filing | Ticker | SA put $ | Stock D+1 | Short PnL − SPY |
|---|---|---|---|---|
| Q2 2025 | SMH (VanEck Semis) | $570M | −1.37% | **+1.39%** |
| Q3 2025 | NVDA | $298M | −1.81% | +0.42% |
| Q3 2025 | CRWV | $192M | −4.66% | **+3.27%** |
| Q3 2025 | MU | $50M | −4.96% | **+3.57%** |
| Q3 2025 | AVGO | $76M | −0.58% | −0.81% |
| Q3 2025 | TSM | $75M | −1.35% | −0.04% |
| Q4 2025 | INFY | $9M | −12.28% | **+10.11%** |

5 of 7 firm-events were positive. Cross-name dispersion within Q3 alone runs from −0.81% to +3.57%.

## Caveats — what we don't know

- **Sample size.** 4 filings, 7 put-events, 11 exit-events. Confidence intervals on every estimate are very wide. The "true" Sharpe could plausibly be zero or negative.
- **Trend continuation confound.** SA exits names whose theses broke; those names had often already been falling. Pre-event placebo windows showed −5% to −9% SPY-adjusted basket moves in the 20 days *before* disclosure — bigger than the post-event moves we're trying to capture.
- **Aschenbrenner-specificity.** The growing-fame argument is hypothesis, not data. The strategy might be picking up generic 13F effects, not anything specific to SA.
- **Single-name outliers.** Q4 INFY drove most of the put-thesis mean. Without it the edge is half. Names like CRWV (recent IPO, thin borrow) may be hard to short cheaply in size.
- **No transaction costs modeled.** Real shorts pay 5–40 bps borrow + slippage on entry. At a +1–2% gross edge, costs probably eat 25–50% of the alpha.
- **No live execution validation.** All numbers are paper backtests on Yahoo daily/hourly data. Real fills will differ.

## What's expected at $100K capital

- **Annual SPY-adj alpha:** ~2–4% if the historical edge holds; could be 0% or negative
- **Per-filing dollar PnL:** $300–$1,500 expected, $2–4K realistic SD
- **Events per year:** 3–4 (some quarters had no put initiations or exits)
- **Total annual:** $1–4K alpha; modest in absolute terms

The strategic value is the **system**, not the alpha on $100K. The pipeline is reusable for any 13F filer or 8-K event monitoring.

## Repo structure

```
SA_bets/
  README.md                       # this file
  first_look_plan.md              # full strategy document (v1 → v2 evolution)

  src/
    edgar_pull.py                 # download/parse 13Fs from EDGAR
    holdings_diff.py              # quarter-over-quarter classification
    prices.py                     # Yahoo daily + intraday prices, cached
    filing_analysis.py            # long-short basket builder for any filing
    event_study.py                # original equal-weight study
    last_filing_analysis.py       # focused Q4 2025 analysis
    placebo_plots.py              # pre/post event placebo + visualization
    theses.py                     # grid of trade thesis backtests
    theses_summary.py             # pooled per-thesis ranking
    sharpe_puts.py                # Sharpe statistics for put-short thesis

  data/
    cusip_ticker_map.csv          # 44 securities → tickers, exchange, notes
    filings/                      # raw EDGAR XML + parsed CSVs
    prices/                       # cached Yahoo OHLCV (daily + 60m)

  results/
    thesis_grid.csv               # full per-(filing, thesis) returns
    thesis_grid_report.md         # ranked thesis summary
    calibration_summary.md        # original event study writeup
    last_filing_summary.md        # focused Q4'25 analysis writeup
    event_study_v1.csv            # firm-event detail
    last_filing_analysis.csv      # Q4'25 firm-event detail
    puts_short_per_event.csv      # put-thesis Sharpe inputs
    figures/
      event_window_q3_q4.png
      per_name_d1.png
```

## How to reproduce

Requires Python 3.10+ with `matplotlib`. No paid data feeds.

```bash
# 1. Pull all 13F filings from EDGAR
python3 src/edgar_pull.py

# 2. Compute quarter-over-quarter holdings deltas
python3 src/holdings_diff.py

# 3. Original equal-weight event study
python3 src/event_study.py

# 4. Focused Q4 2025 size-weighted analysis
python3 src/last_filing_analysis.py

# 5. Long-short with INC included
python3 src/filing_analysis.py

# 6. Full thesis grid (the headline numbers)
python3 src/theses.py
python3 src/theses_summary.py

# 7. Placebo + plots
python3 src/placebo_plots.py

# 8. Sharpe statistics for put-short thesis
python3 src/sharpe_puts.py
```

## Roadmap

### Before 2026-05-15 (next filing)

- [ ] Placebo on put basket — were NVDA/MU/TSMC/AVGO/CRWV already declining 10%+ pre-disclosure?
- [ ] Backtest Rule v2 *with filters* on Q1–Q4 2025 — confirm filters don't exclude all trades
- [ ] Build EDGAR poller (submissions-JSON, persisted `last_seen_accession`, SMS/email on detect)
- [ ] Build Alpaca paper executor (orders, fill tracking, kill switch)
- [ ] End-to-end paper rehearsal with mock filing

### At 2026-05-15 deadline

- [ ] Paper-trade the actual filing release. **No live capital.**

### After 2026-Q2 (Aug 2026 filing)

- [ ] Re-evaluate Sharpe with N=5 paper events
- [ ] If win rate ≥ 60% at D+1 with positive mean over 2+ paper events, consider small live capital ($1K–$5K) for Q3 2026

### v3+ — options expansion (deferred)

Higher-leverage variants of the same direction signals:
- **Buy short-dated OTM puts** on names SA newly puts on, instead of shorting underlying
- **Sell calls** as a defined-risk variant
- Trade-offs: liquid mega-caps (NVDA, AVGO) have tight option spreads but high baseline IV — directional move has to clear priced-in vol. Smaller names (CRWV, INFY) have wider spreads but bigger realized moves; leverage helps if signal hits
- IV crush can produce zero PnL even on a "right direction, small magnitude" trade. Sizing small is mandatory
- Defer until v2 (equity) shows live edge

## Status

**Pre-deployment.** All numbers are historical backtests. No live capital deployed. No paper trading executed yet. The 2026-05-15 filing is the planned first paper trade.

## License

Personal research project. No license — no warranties, no advice, not for distribution.
