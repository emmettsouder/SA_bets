# Situational Awareness LP — Filings Index

**CIK:** 0002045724
**Location:** San Francisco, CA (Delaware LP)
**File number:** 028-24925

## 13F-HR filings on record (as of 2026-05-04)

| # | Period ending | Filed | Accession | Primary table file |
|---|---------------|-------|-----------|--------------------|
| 1 | 2024-12-31 | 2025-02-12 | 0000935836-25-000120 | TBD |
| 2 | 2025-03-31 | 2025-05-14 | 0002045724-25-000002 | TBD |
| 3 | 2025-06-30 | 2025-08-14 | 0002045724-25-000006 | TBD |
| 4 | 2025-09-30 | 2025-11-14 | 0002045724-25-000008 | TBD |
| 5 | 2025-12-31 | 2026-02-11 | 0002045724-26-000002 | SALP_13FQ425.xml |

**Next expected filing:** Q1 2026, due ~2026-05-15 (within ~10 days of today). Worth waiting for it before locking event-study results — N=6 vs N=5 is a 20% bump in sample size.

## Filing acceptance timestamps

The table above shows file dates only. For event-study `t=0` we need acceptance datetime (after-4pm filings push the event day forward). To get this: hit `https://www.sec.gov/cgi-bin/browse-edgar?action=getcompany&CIK=0002045724&type=13F&dateb=&owner=include&count=40&output=atom` and parse `<updated>` per entry, or read the `-index-headers.html` per filing.

## Snapshot — 2025-Q4 holdings (parsed)

- **Total reported value:** ~$5.52B
- **Number of <infoTable> rows:** 58
- **Unique issuers:** 29 (some issuers appear twice, indicating options positions alongside common — Bloom Energy, CoreWeave, Intel, EQT)
- **Top theme:** AI power & data centers
  - Power/infra: Bloom Energy ($875M), EQT, Solaris Energy Infra, Kilroy Realty, Babcock & Wilcox
  - Compute: CoreWeave, Applied Digital, WhiteFiber
  - Crypto-miner → AI-compute pivots: Cipher Mining, CleanSpark, Core Scientific, Hut 8, Iren, Riot Platforms, Bitfarms, Bitdeer, Hut 8
  - Semis/optical: Intel, Coherent, Lumentum, SanDisk, Tower Semiconductor
  - Oilfield services (data-center power adjacent?): Liberty Energy, ProPetro, Power Solutions Intl
  - Other: Infosys

## Implications for the study

1. **Sample size** — 5 quarters now, 6 by mid-May. Still tiny. Pre-register that we expect wide CIs and treat any p-value with skepticism.
2. **Concentration** — 29 names is small; ~5–10 names dominate by weight. The "average treatment effect" is heavily driven by the top 5 positions. Plan to report results both equal-weighted and value-weighted.
3. **Sector benchmark choice matters a lot** — the book is essentially "long AI infrastructure". SPY is the wrong benchmark; QQQ is closer; an AI-infra ETF (e.g., XLE for energy, SMH for semis, or a mix) is more honest. Consider a custom benchmark = blended XLE + SMH + QQQ that matches sector weights.
4. **Options handling** — duplicates in issuer list mean we have call/put positions. 13F discloses notional value of options, not delta-adjusted exposure. Decide: (a) ignore options in the equity backtest, or (b) treat them as additional long/short exposure in the position with appropriate notional. (a) is cleaner for first look.
5. **Aschenbrenner-as-influencer hypothesis is more credible at $5.5B** than at the $200M I'd guessed. A $5.5B book disclosing positions is a non-trivial signal.

## Files saved locally

- `data/filings/_index.html` — EDGAR company filings index (HTML, raw)
- `data/filings/2025Q4_holdings.xml` — parsed Q4 2025 information table
