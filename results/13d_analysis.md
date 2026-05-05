# 13D / 13G Pre-Emption of 13F-HR — Analysis

**Date:** 2026-05-04
**Question:** For positions large enough to require a Schedule 13D/G filing, the 13F-HR is a stale rerun. Does this affect our trading rule?

## Universe

SA has filed exactly **2 Schedule 13D family filings**, both on the same issuer:

| Form | Acc # | Filed | Acceptance | Issuer | CUSIP | Shares | % of class | Event date |
|------|-------|-------|-----------|--------|-------|--------|-----------|------------|
| SCHEDULE 13D | 0000935836-25-000543 | 2025-08-19 | 16:55 ET | Core Scientific | 21874A106 | 17,682,918 | 5.8% | 2025-08-12 |
| SCHEDULE 13D/A | 0000935836-25-000638 | 2025-10-14 | 17:50 ET | Core Scientific | 21874A106 | 28,756,478 | 9.4% | 2025-10-09 |

**No 13G filings** (would imply passive intent — SA chose 13D, signaling they reserve the right to act).

## CORZ — full SA disclosure timeline

| Date | Time | Form | SA shares | % of book | Notes |
|------|------|------|-----------|-----------|-------|
| 2025-05-14 | 15:14 | 13F-HR (Q1) | 4,521,578 | 3.3% | First appearance |
| 2025-08-14 | 13:54 | 13F-HR (Q2) | 7,994,038 | 6.4% | Pre-13D, pre-trigger reporting |
| **2025-08-19** | **16:55** | **13D** | **17,682,918** | **5.8% of co.** | **First disclosure of >5% stake** |
| **2025-10-14** | **17:50** | **13D/A** | **28,756,478** | **9.4% of co.** | **Activist signal: stake increased ~62%** |
| 2025-11-14 | 17:10 | 13F-HR (Q3) | 20,180,534 | 8.7% | **Stale** — 13D/A already showed 28.76M one month earlier |
| 2026-02-11 | 08:31 | 13F-HR (Q4) | 28,756,478 | 7.6% | **Identical** to 13D/A from 4 months prior |

The 28,756,478-share position was **first known publicly on 2025-10-14** but not appearing in a 13F-HR until **2026-02-11 — 120 days later**.

## Did 13Ds move the price? Did the subsequent 13F-HRs?

CORZ next-session returns and event-day volume vs 30-day median:

| Event | t→t+1 raw | vs SPY | vs SMH | vs QQQ | +5d SPY-adj | Volume vs 30d median |
|-------|-----------|--------|--------|--------|-------------|----------------------|
| 13D filed (5.8%) | −1.88% | −1.62% | −1.22% | −1.29% | −3.00% | **+24%** |
| 13D/A filed (9.4%) | **+5.28%** | **+4.84%** | +2.80% | +4.57% | +0.16% | **+51%** |
| Q3 13F-HR (CORZ stale) | −0.94% | −0.01% | +0.42% | −0.08% | +0.58% | **−34%** |
| Q4 13F-HR (CORZ identical to 13D/A) | −0.22% | −0.20% | −2.70% | −0.49% | −3.90% | **−41%** |

**Volume is the cleanest signal.** 13D filings drew **above-median** volume the next session; subsequent 13F-HRs drew **below-median** volume. The market knew the news on the 13D and ignored it on the 13F.

The 13D/A's +4.8% next-day SPY-adjusted move is striking — and SA bought another 2.3M shares **on the same day they filed**, at $19.07, paying up into their own announcement.

## What this means for Rule v1

**Direct impact on the calibration: minimal.** CORZ is in every 13F-HR since Q1'25 but is not classified as a *new* position in any of the 3 calibration filings (Q1, Q3, Q4 2025), so it never entered our `tradeable_new_positions.csv`. We are not contaminating the new-positions backtest with this stale-news case.

**Indirect / meta-impact: significant.**

1. **Selection bias by stake size.** SA's single highest-conviction name (~$418M, ~7.6% of book on the latest 13F) is exactly the one that bypasses the 13F's information moment. As AUM grows, more names will cross 5% and have their disclosure shock pulled forward to a 13D — leaving the 13F-HR with the smaller, less-conviction names. Rule v1's "all new positions ≥$1M, equal-weight" basket is therefore *negatively selected* on conviction.

2. **The 13D itself is the better trade.** Two 13D events (admittedly N=2): 1 down, 1 up, mean ~+1.5% SPY-adj on day +1; both with above-median volume. The +5% pop on the 13D/A is the only clear positive event in any of the 6 SA-disclosure events on CORZ.

3. **Live system needs to monitor 13D filings too.** Currently the plan polls only 13F-HR. EDGAR's submissions JSON returns 13D/13G/A filings under SA's CIK in the same JSON — trivial extension. 13D deadline is 10 days after crossing the threshold, so a poll cadence comparable to the 13F window is enough.

4. **CORZ specifically going forward.** If SA's CORZ position changes materially, expect a 13D/A within ~10 days — not a 4-month wait for the next 13F. Conversely, the upcoming 2026-05-15 13F-HR will reveal nothing new about CORZ unless we see a 13D/A first.

## Action items

- [x] Pull all 13D/G filings, parse, save to `data/filings/13d_filings.csv` and `data/filings/13d_transactions.csv`
- [ ] Add 13D/G as additional event types in `event_study.py` (N is too small to power its own backtest, but logging is free)
- [ ] In the live poller (when built), trigger on form-types `("13F-HR", "13F-HR/A", "SCHEDULE 13D", "SCHEDULE 13D/A", "SCHEDULE 13G", "SCHEDULE 13G/A")`
- [ ] In `first_look_plan.md`, add a §2.5 distinguishing 13F-event-study (variant A) from 13D-event-study (variant E, new)

## Limitations

- N=2 13D events. Cannot statistically distinguish disclosure alpha from CORZ-specific noise.
- 8/19 13D fell during Bitcoin volatility; 10/14 13D/A fell on a strong day for AI/miner names broadly. The +5% 13D/A pop may be partly sector-driven.
- Single-issuer sample. Conclusions may not generalize once more 13Ds exist.
