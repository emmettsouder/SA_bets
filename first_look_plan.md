# SA_Bet — Plan

## 0. Goal (updated 2026-05-04)

**Backtest how Situational Awareness LP's 13F-HR filings moved stocks — with particular weight on the most recent filing (Q4'25), since it's the cleanest comp for what filing #6 will look like. If the historical edge is real and survives costs, deploy a live system that trades within ~10 minutes of each new filing release on EDGAR.**

Order of operations:
1. Backtest the announcement effect on the 5 historical filings (calibration sample).
2. Decide based on results whether there's an edge worth trading.
3. If yes, paper-trade the next filing (~2026-05-15); live capital only after a green paper run.

**Hard deadline:** the next filing (period 2026-03-31) is due ~2026-05-15 — about 10 days from today. To preserve optionality, the live infrastructure should be paper-ready by then even if the calibration is borderline.

**Verified context (from EDGAR, 2026-05-04):**
- Filer: **Situational Awareness LP**, CIK **0002045724**, San Francisco / Delaware LP
- 5 historical 13F-HRs (Q4'24 through Q4'25). Two had zero new common positions (Q4'24 was an initial filing; Q2'25 had no new names), so the usable calibration sample is N=3 filings × ~10 names = 29 firm-events.
- ~$5.5B reported portfolio at 2025-Q4, 29 unique issuers, AI-power/data-center thesis
- Acceptance timestamps confirmed (see [data/filings/KNOWN_ISSUES.md](data/filings/KNOWN_ISSUES.md)): 4 of 5 historical filings hit during regular session, 1 was pre-market.

**Calibration result (see [results/calibration_summary.md](results/calibration_summary.md)):** mean SPY-adjusted 1-day return on the new-positions basket is +0.41% (t = 0.52, 15/29 positive). Not statistically distinguishable from zero. Decision: paper-trade the 2026-05-15 filing; no live capital until at least one more clean paper event.

---

## 1. Pivot summary — what changes from a backtest to a live system

| Concern | Backtest framing | Live framing |
|---|---|---|
| Sample horizon | "Use all 5 historical filings" | "Calibrate on 5, deploy on filing #6" |
| Latency | Doesn't matter | <10 min from EDGAR acceptance to filled order; budget below |
| Slippage | Optional sensitivity | First-class — modeled and capped |
| Failure modes | Re-run the script | Paged on miss; kill switch; daily PnL caps |
| Universe | Anything in any 13F | Pre-vetted ticker whitelist mapped from CUSIPs |
| Decision rule | Many variants compared post-hoc | **One** committed rule, decided before deployment |

The single most important consequence: **we must commit to a trading rule before the next filing**, and we cannot pick the rule that looks best on N=5 — that's overfitting on a sample too small to overfit on. Rule selection must be theory-driven (which variant from §2 has the strongest a priori case), informed by but not selected by the historical sample.

---

## 2. What "moves stock prices" actually means — disambiguate the thesis

Before writing any code, lock down which version of the claim we're testing. They have different data needs and different odds of being true.

| # | Variant | What it predicts | Why it might be true | Why it might not |
|---|---------|------------------|----------------------|------------------|
| A | **Announcement effect** | Disclosed names show abnormal returns in a tight window around the 13F filing timestamp ([−1, +3] days) | Aschenbrenner has unusual public profile; "smart-money copy" trades happen on filing | 45-day lag means info is stale; effect (if any) is dwarfed by ambient noise on AI names |
| B | **New-position premium** | *Newly initiated* positions outperform existing/trimmed positions in the post-filing window | New positions are the only true signal; rolls and trims are noise | Sample of new positions per quarter is tiny (likely <10) |
| C | **Persistence** | A portfolio that copies SA's disclosed holdings (T+1 after filing) outperforms the market over the subsequent quarter | If thesis is real, copy-trading is the practical play | Concentrated AI book — may just be a long-AI-beta bet, not alpha |
| D | **Volume/attention** | Even absent return effects, disclosed names see abnormal *volume* and option IV around filing | Lower bar than return effects; tests whether the market notices at all | Many names already have enormous baseline AI-driven volume |

**Recommendation:** test A, B, D as event studies and C as a backtest. They share infrastructure. Don't try to test only A — too easy to get a noisy null and conclude nothing.

---

## 3. Data acquisition

### 3.1 Locate the filer on EDGAR
- Search EDGAR full-text for "Situational Awareness" — confirm the legal entity name (likely "Situational Awareness LP" or a GP/management entity). Record the **CIK**.
- Pull the full 13F-HR filing history. Each filing has:
  - Filing acceptance datetime (this is the event timestamp — *not* the report period end date)
  - Period-of-report (quarter end)
  - The XML information table listing holdings (CUSIP, issuer, class, value, shares, put/call flag)
- Save raw filings + parsed tables to `data/filings/`.

### 3.2 Map CUSIP → ticker
- 13F gives CUSIPs, not tickers. Need a CUSIP→ticker mapping.
- Free options: OpenFIGI API (free tier with rate limits), or scrape from a 13F aggregator (whalewisdom, fintel — but ToS).
- Cache the mapping; CUSIPs are stable enough.

### 3.3 Price data
- Daily OHLCV + adjusted close for every disclosed ticker, plus benchmarks (SPY, QQQ, an AI-themed ETF like BOTZ or ARKQ for sector control).
- Source: `yfinance` is fine for a first look. Date range: from 60 trading days before earliest filing to 60 trading days after most recent filing.
- For announcement-day intraday effects (variant A tight window), grab 1-min or 5-min bars on event days only (Polygon free tier or Alpaca).

### 3.4 Holdings deltas
For each consecutive pair of filings, compute per-ticker:
- `new`: didn't appear last quarter, appears this quarter
- `exited`: appeared last quarter, gone this quarter
- `increased` / `decreased` / `unchanged`: by share count (not dollar value — value moves with price)
- Position size as % of portfolio (for weighting)

---

## 4. Event study — variants A and B

### 4.1 Define the event
- **Event date `t=0`:** trading day on which the filing's acceptance datetime falls. If filed after 4pm ET, `t=0` is the next trading day (the first day the market could react during regular hours).
- **Event windows:** [−1, +1], [0, +3], [0, +20] trading days. Pre-window [−5, −2] as a placebo to check for leakage.

### 4.2 Abnormal returns
Two specifications, run both:
1. **Market-adjusted:** `AR_it = R_it − R_mt` where `R_mt` is SPY return. Cheap, robust, easy to defend.
2. **Market model:** estimate `α_i, β_i` for each name on a [−120, −20] pre-event window regressing daily returns on SPY (and optionally QQQ as a second factor for tech-heavy names). `AR_it = R_it − (α_i + β_i · R_mt)`.

Aggregate to **CAR** over each window. Cross-sectional t-test of CARs vs. zero. Report mean, median, % positive, and a sign test (more robust to outliers than t-test with N this small).

### 4.3 Subsamples for variant B
Split holdings by type (new / increased / unchanged / decreased / exited) and by position weight (top-quartile weight vs. rest). Compare CARs across buckets.

### 4.4 Volume / IV (variant D)
- Abnormal volume: `(Vol_it / mean(Vol_i, [−60,−10])) − 1`. Test against zero.
- Optional: ATM 30-day IV change around event (requires options data — skip for first look unless free source available).

---

## 5. Copy-trade backtest — variant C

Simple, transparent, no overfitting:
- On the trading day after each filing's acceptance timestamp, construct a portfolio matching the disclosed weights (clipped to long-only — 13F doesn't disclose shorts reliably anyway).
- Hold until the next filing's T+1, then rebalance.
- Track total return, volatility, Sharpe, max drawdown.
- Benchmarks: SPY, QQQ, an AI-themed ETF. The AI-ETF benchmark is the honest one — beating SPY tells us nothing if the book is just long-AI.

Report **gross of fees and slippage**, then with a 10 bps round-trip cost as a sanity haircut. With a tiny rebalance frequency (quarterly), costs are negligible — the benchmark is the real concern.

---

## 6. Confounders & robustness — the parts most likely to invalidate the result

These deserve real attention; a positive headline result that ignores them isn't worth much.

1. **Tiny N.** ~4–7 filings × ~10–30 holdings each ≈ 50–200 firm-events total. Some of those overlap (same name held across quarters), so independent observations are fewer. Power to detect anything below ~3% CAR is weak. Be transparent: report confidence intervals, not just point estimates.
2. **Cross-correlation.** AI names are highly correlated. CARs across positions are not independent → naive t-stats overstate significance. Use cluster-robust SEs (cluster by event date) or bootstrap the test statistic.
3. **Sector beta, not alpha.** If holdings are 90% Mag-7-plus-AI-infra, "outperformance vs. SPY" is just AI exposure. The AI-ETF benchmark is essential.
4. **Reporting lag.** 13F is filed up to 45 days after quarter end. By filing date, the positions could be months old. If we find an announcement effect, it's about *attention to the disclosure*, not about Aschenbrenner's stock-picking skill.
5. **Confidential treatment / amendments.** Funds can request confidential treatment for some positions; amendments (13F-HR/A) restate prior filings. Treat amendments as a separate event or fold them in carefully.
5b. **13D/13G pre-emption.** Names where SA crosses 5% of the issuer's float require a Schedule 13D within 10 days, *before* the 13F-HR. The 13F-HR is then a stale rerun for that name. Currently affects only Core Scientific (1 of 29 names) — but as AUM grows, more names will pre-empt. See [results/13d_analysis.md](results/13d_analysis.md). Implication: Rule v1 is negatively selected on conviction (its biggest names disappear into 13D channel).
6. **Survivorship in the analysis itself.** We have every filing because the fund still files. Not really a survivorship issue here, but: don't drop names that delisted/got acquired — handle them properly with their last available return.
7. **Concurrent news.** A position appearing as "new" might also have its own earnings call, M&A rumor, etc. on the same day. For top-CAR names, manually inspect the news on event day to see if the move is plausibly attributable to the 13F at all.
8. **Multiple hypothesis testing.** We're running 4 variants × 3 windows × 2 AR specs = 24 tests. Apply at least a Bonferroni-style sanity check before claiming any single result.

---

## 7. Live system architecture

```
┌────────────────┐    ┌──────────────┐    ┌─────────────┐    ┌──────────────┐    ┌────────────┐
│  EDGAR Poller  │───▶│ XML Fetcher  │───▶│   Differ    │───▶│   Decider    │───▶│  Executor  │
│  (loop, 5–10s) │    │  + Parser    │    │ vs prior Q  │    │ (rule + risk)│    │ (Alpaca)   │
└────────────────┘    └──────────────┘    └─────────────┘    └──────────────┘    └────────────┘
        │                                                            │                  │
        ▼                                                            ▼                  ▼
   Notifier (SMS/email on detect)                              Order log        Fill confirms
                                                                                       │
                                                                                       ▼
                                                                              Position monitor
                                                                              (exit rules, stops)
```

### 7.1 EDGAR Poller
- Poll the filer's submissions JSON every 5–10s during the deadline window. Endpoint: `https://data.sec.gov/submissions/CIK0002045724.json` — returns the 1000 most recent filings as JSON. Compare top accession to last seen; new entry = trigger.
- The Atom feed (`browse-edgar?...&output=atom`) is also viable but the JSON endpoint is lower-latency.
- **Important:** SEC requires a UA header with contact info. Set `User-Agent: SA_Bet emmettsouder@gmail.com`. Rate limit: 10 req/s — well within bounds.
- Polling window: only run aggressive polling on/around deadline days. For Q1 2026 the deadline is 2026-05-15; expand window to 2026-05-01 through 2026-05-20 just in case of early/late filing. Outside that window, poll every 5 min.
- Robustness: persist `last_seen_accession` across restarts (file or sqlite). Trigger forms: `13F-HR`, `13F-HR/A`, `SCHEDULE 13D`, `SCHEDULE 13D/A`, `SCHEDULE 13G`, `SCHEDULE 13G/A`. 13Ds can hit any time (10-day deadline after material change), so polling cadence must stay continuous outside 13F windows too — not just during the quarterly deadline.

### 7.2 XML Fetcher + Parser
- On trigger: fetch filing-index, identify the information-table XML (filename varies — e.g., `SALP_13FQ425.xml`), download, parse `infoTable` rows.
- Output: list of `(cusip, issuer, class, value_usd, shares, putCall_or_None)`.
- Strip duplicates from options legs; keep options-aware view separately for analysis but do not trade options on first version.

### 7.3 Differ
- Load prior filing's parsed holdings; classify each current row as `new | increased | decreased | unchanged | exited` by share count (not value). Compute new-position weight % of portfolio.

### 7.4 Decider (the rule)
- **Single committed rule for v1:** Equal-weight long basket of *new positions only*, with size cap per name. Rationale below in §8.
- Filters:
  - Skip names where CUSIP→ticker map is missing or ambiguous (warn, don't trade).
  - Skip ADRs / OTC / non-NMS names.
  - Skip names with average daily $ volume < $20M (illiquidity → bad fills in 10 min).
  - Skip names already gapping >5% on the day (the move may have already happened).
- Hold period: exit at next-day market close. (Justification: the announcement effect, if real, is concentrated in the first session post-disclosure; longer holds dilute the signal with sector beta.)

### 7.5 Executor — broker choice
**Alpaca** is the right choice for v1:
- Free paper trading API with realistic fills
- Same code path for paper → live with one config flip
- WebSocket order updates
- Supports US equities, fractional shares, market + limit orders
- Drawbacks: no options API on free tier (fine, we're equity-only), and not the lowest-latency broker — but well within our 10-min budget

Alternative if Alpaca limits bite: Tradier or IBKR. Skip for v1.

### 7.6 Risk & control plane
- **Hard caps:** $X total capital deployed per filing event (configurable, start small — e.g., $5k paper, then $1k live), max $X per name, max N names.
- **Kill switch:** environment variable `SA_BET_KILL=1` halts new orders on next loop.
- **Pre-trade sanity checks:** broker available? clock in market hours? account equity matches expectation? all tickers in whitelist?
- **Order type:** marketable limit at NBBO + 30 bps, IOC. Avoids worst-case market-order fills on thin names.
- **Audit log:** every poll, fetch, parse, decision, order, fill written to `logs/{filing_accession}/`.
- **Notifier:** SMS via Twilio + email on (i) filing detected, (ii) orders sent, (iii) all filled or any error. The point is *I always know what the bot just did*.

### 7.7 Latency budget (target ≤10 min, expected ≤2 min)

| Stage | Target | Hard cap |
|---|---|---|
| Poll detect → trigger | ≤10 s | 30 s |
| Fetch filing index + holdings XML | ≤5 s | 15 s |
| Parse + diff | ≤1 s | 5 s |
| CUSIP→ticker resolve + filters | ≤2 s | 10 s |
| Decider | ≤1 s | 5 s |
| Order placement (N orders parallel) | ≤5 s | 30 s |
| Fills (marketable limits) | ≤30 s | 5 min |
| **Total** | **~1 min** | **~6 min** |

10-min SLA has 4+ minutes of slack. The realistic risk isn't latency — it's filings dropping outside market hours.

### 7.8 After-hours handling
13F filings are often accepted after 4pm ET on the deadline day (it's a paperwork deadline, not market-driven). If acceptance is post-close:
- Enter orders at next session open via market-on-open or aggressive limits in the opening auction.
- This is when the price discovery actually happens — pre-market on thin names is dangerous, so wait for the regular session.

---

## 8. The trading rule, committed pre-deployment

**Rule v1 (long-only equity):**
> On detection of a new 13F-HR from CIK 0002045724, identify positions that are NEW vs the immediately prior filing. Buy each qualifying new position equal-weighted, capped at $X total. Hold until next trading day's market close. Exit unconditionally.

**Why this rule, not "copy the whole book":**
- Copying the whole book is mostly long-AI-beta. We can already get that via QQQ at zero effort and zero risk of being wrong. The interesting bet is on the *new information* in the filing, which is concentrated in newly initiated positions.
- Equal-weight (vs. SA's portfolio weights) reduces dependence on any single name and avoids constructing a $5B-fund-shaped portfolio with $5k.
- 1-day hold isolates the announcement effect, which is the only effect "trade within 10 minutes" actually capitalizes on. Longer holds turn this into a slow copy-trade, which is a different strategy.

**Rule v2 (held back for later):** add increased positions with weight tilt toward larger %-of-book increases. Defer until v1 has been observed live.

**What would falsify the thesis post-hoc:**
- If the basket consistently underperforms an AI-infra benchmark (XLE+SMH+QQQ blend) over the 1-day hold across 3+ live filings → kill the strategy.
- If transaction costs eat >50% of gross alpha → re-evaluate hold length and ticker filters.

---

## 9. Pre-deployment checklist (timeline to 2026-05-15)

| Date | Milestone | Status |
|---|---|---|
| 2026-05-04 | Filer confirmed; all 5 filings parsed; CUSIP→ticker map built; QoQ deltas computed | ✅ done |
| 2026-05-04 | Historical event study on usable filings (3 of 5 had new positions; N=29 firm-events) — see [results/calibration_summary.md](results/calibration_summary.md) | ✅ done — no statistically meaningful edge |
| 2026-05-05/06 | Per-filing deep-dive on Q4'25 (most recent, most representative): re-check benchmark choice, sector control, intraday entry assumption | ⏳ next |
| 2026-05-07/08 | Decision point: paper-only vs. abandon. Default = paper-only given borderline calibration. | ⏳ pending |
| 2026-05-09/10 | Build EDGAR poller; Alpaca paper account; end-to-end dry run with mocked filing | ⏳ |
| 2026-05-11/13 | Live paper run with poller active during business hours; test SMS/kill switch | ⏳ |
| 2026-05-14 | Code freeze. Final manual review of trading rule and caps. | ⏳ |
| 2026-05-15 (deadline) | Paper-trade the actual filing release end-to-end | ⏳ |
| Post-event | Post-mortem; if green over ≥2 paper events, plan a live (small-capital) run for Q2 2026 filing in August | ⏳ |

**No live capital on the 2026-05-15 filing.** Paper only. The first live run, if any, is Q2 2026 in August — and only if Rule v1 hits the re-evaluation gate in [calibration_summary.md](results/calibration_summary.md) (≥3 of 4 events positive, mean SPY-adj > +0.5%).

---

## 10. Honest priors (updated)

- **Variant A (announcement CAR) is now the only thesis that matters** for the live system. The 1-day post-disclosure window is what we're trading.
- I'd put ~30% probability on a real, tradeable announcement effect surviving costs after we look at the historical 5. The effect is plausible (Aschenbrenner is unusually visible, $5.5B is non-trivial size), but 13F's 45-day lag means the headline names are usually leaked or guessed already.
- The most likely *ex post* outcome from this project: the historical study shows a small, noisy, marginally positive new-position effect, we deploy in paper, and we see one or two filings before knowing whether there's anything there. This is fine — the infrastructure is the durable asset.

---

## 11. Repo layout

Legend: ✅ exists · ⏳ planned (not yet built)

```
SA_Bet/
  first_look_plan.md                    ✅
  data/
    filings/                             ✅ raw 13F + 13D XML + parsed CSVs (per-accession dirs)
      filings_meta.csv                   ✅
      holdings_long.csv                  ✅
      diff_long.csv                      ✅
      tradeable_new_positions.csv        ✅
      13d_filings.csv                    ✅ parsed 13D/G filings (issuer, %, shares, event date)
      13d_transactions.csv               ✅ 60-day txn lists from each 13D's exhibit
      KNOWN_ISSUES.md                    ✅
    prices/                              ✅ per-ticker yfinance JSON cache
    cusip_ticker_map.csv                 ✅
    filings_index.md                     ✅
  src/
    edgar_pull.py                        ✅ download + parse historical 13F filings
    edgar_pull_13d.py                    ✅ download + parse 13D/G filings & 60-day txn exhibits
    holdings_diff.py                     ✅ new/inc/dec/exit deltas
    prices.py                            ✅ yfinance wrapper
    event_study.py                       ✅ backtest of variant A
    poller.py                            ⏳ live: monitor EDGAR
    decider.py                           ⏳ live: apply rule v1
    executor.py                          ⏳ live: Alpaca client
    notifier.py                          ⏳ SMS/email
    config.py                            ⏳ caps, ticker whitelist, env flags
  logs/                                  ⏳ per-event audit trail
  results/
    event_study_v1.csv                   ✅
    calibration_summary.md               ✅
    last_filing_summary.md               ✅
    last_filing_analysis.csv             ✅
    13d_analysis.md                      ✅
```

---

## 12. Open questions to resolve before 2026-05-15

1. **CUSIP→ticker source:** manual map is in place for the ~30-name historical universe. For new names in filing #6, decide on OpenFIGI fallback vs. halt-and-page-the-human.
2. **What if the next filing is after-hours?** Acceptance times confirmed (see [data/filings/KNOWN_ISSUES.md](data/filings/KNOWN_ISSUES.md)): 4 of 5 in regular session, 1 pre-market. Live system needs both code paths.
3. **Q4'25-specific re-analysis:** the calibration ran Q4'25 alongside Q1'25 and Q3'25, but the user has flagged Q4'25 as the most representative comp for filing #6. Worth a per-filing deep-dive (sector control, intraday timing, name-by-name news scan) before locking the rule.
4. **Capital size for first live run (post-paper):** TBD with user. Recommend ≤$1k notional for first live filing — and only after the re-evaluation gate is hit.
5. **Tax wrapper:** day-trading these in a taxable account creates short-term gains on every event. Acknowledge — first runs are paper anyway.
