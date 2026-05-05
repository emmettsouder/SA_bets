# Data quirks discovered during parsing

## 1. Issuer name casing is inconsistent across filings
Same issuer appears as e.g. "Intel Corp" in 2025-Q1 and "INTEL CORP" in 2025-Q2. **Diff must normalize issuer names** (uppercase + suffix-strip) — see `src/holdings_diff.py::norm_issuer`.

## 2. CUSIPs not stable across filings for the same security
Bloom Energy common stock used CUSIP `093712AH0` in 2025-Q3 (option-format) and `093712107` in 2025-Q4 (standard CUSIP). Both rows have `put_call=""` and `titleOfClass="COM CL A"`, so they are unambiguously the same security. This was a data-entry quirk in the fund's filings.

**Implication:** never use raw CUSIP as the cross-quarter join key. Use normalized issuer name.

## 3. Token positions — 1 share, ~$37
2025-Q4 13F lists Intel common with `shares=1, value=$37, put_call=""`. The fund's real Intel exposure is 20.2M call options (~$747M). The 1-share common is a procedural artifact.

**Implication:** trading rule must apply a min-position-size filter. Suggested: `common_value_usd >= $1,000,000` or weight ≥ 0.05% of total book.

## 4. Two filings had zero new common-stock positions
2024-Q4 (initial filing, all positions are INIT not NEW) and 2025-Q2. The "long-new-positions" rule produces no trades on those filings — by design, but worth knowing the rule sometimes does nothing.

## 5. Acceptance datetimes — most are during market hours

| Period | Acceptance (UTC) | ET | Market state |
|---|---|---|---|
| 2024-Q4 | 2025-02-11 17:58 | 12:58 | regular |
| 2025-Q1 | 2025-05-14 15:14 | 11:14 | regular |
| 2025-Q2 | 2025-08-14 13:54 | 09:54 | regular (just after open) |
| 2025-Q3 | 2025-11-14 17:10 | 12:10 | regular |
| 2025-Q4 | 2026-02-11 08:31 | 03:31 | pre-market |

4 of 5 historical filings hit during regular session. Live system needs both regular-session and pre-market code paths.

## 6. Options signals deliberately not traded in Rule v1
The fund's largest exposures by notional value are often option positions (Intel calls, CoreWeave calls, VanEck ETF calls, Bloom Energy calls). Rule v1 only trades NEW common-stock positions. Possible Rule v2: also trade common stock when the fund newly takes a long-call position on the same issuer. Not in scope for the May 15 deployment.
