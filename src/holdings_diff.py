"""Compute quarter-over-quarter holdings diffs for SA LP filings.

Critical normalization:
- Issuer names appear in mixed case across filings — uppercase before keying.
- Options use a different CUSIP than the underlying common stock. We track
  common-stock and option positions separately per (normalized_issuer).
- The trading rule cares about NEW common-stock positions only — that's the
  output `tradeable_new_positions.csv`.
"""

import csv
import re
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FILINGS_DIR = ROOT / "data" / "filings"

# Common corporate suffixes to strip when normalizing issuer names.
SUFFIXES = [
    "INC", "INC.", "CORP", "CORP.", "CORPORATION", "LTD", "LTD.", "LIMITED",
    "PLC", "CO", "CO.", "COMPANY", "HLDGS", "HLDG", "HOLDINGS", "HOLDING",
    "GROUP", "ENTERPRISES", "TRUST", "ETF", "L P", "LP", "LLC", "PL",
    "MFG", "TECHNOLOGIES", "TECHNOLOGY", "TECH", "NEW", "CL A",
]


def norm_issuer(name: str) -> str:
    """Normalize issuer name for cross-quarter matching."""
    s = name.upper().strip()
    s = re.sub(r"[&]", " AND ", s)
    s = re.sub(r"[^A-Z0-9 ]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    # Repeatedly strip trailing suffixes
    changed = True
    while changed:
        changed = False
        for suf in SUFFIXES:
            if s.endswith(" " + suf):
                s = s[: -(len(suf) + 1)].strip()
                changed = True
    return s


def load_long():
    rows = list(csv.DictReader(open(FILINGS_DIR / "holdings_long.csv")))
    by_period = defaultdict(list)
    for r in rows:
        by_period[r["period_of_report"]].append(r)
    return by_period


def book_state(rows):
    """Aggregate per (norm_issuer): common shares, option presence, total value, raw issuer name, cusips."""
    s = {}
    for r in rows:
        key = norm_issuer(r["issuer"])
        if key not in s:
            s[key] = {
                "issuer_raw": r["issuer"],
                "cusips_common": set(),
                "cusips_option": set(),
                "common_shares": 0,
                "common_value": 0,
                "option_value": 0,
                "has_common": False,
                "has_option": False,
            }
        if r["put_call"]:
            s[key]["cusips_option"].add(r["cusip"])
            s[key]["option_value"] += int(r["value_usd"])
            s[key]["has_option"] = True
        else:
            s[key]["cusips_common"].add(r["cusip"])
            s[key]["common_shares"] += int(r["shares"])
            s[key]["common_value"] += int(r["value_usd"])
            s[key]["has_common"] = True
    return s


def main():
    by_period = load_long()
    periods = sorted(by_period)

    diff_rows = []  # all transitions
    tradeable_new_rows = []  # the calibration sample for rule v1

    prior = None
    prior_period = None
    for p in periods:
        cur = book_state(by_period[p])
        if prior is None:
            classification = "INIT"
            for k, v in cur.items():
                diff_rows.append({
                    "period": p, "prior_period": "", "issuer_norm": k,
                    "issuer_raw": v["issuer_raw"], "classification": classification,
                    "common_shares_prev": 0, "common_shares_cur": v["common_shares"],
                    "common_value_cur": v["common_value"], "option_value_cur": v["option_value"],
                    "has_common_prev": False, "has_common_cur": v["has_common"],
                    "has_option_prev": False, "has_option_cur": v["has_option"],
                })
            prior = cur
            prior_period = p
            continue

        all_keys = set(prior) | set(cur)
        for k in all_keys:
            in_prior = k in prior
            in_cur = k in cur
            pv = prior.get(k, {})
            cv = cur.get(k, {})

            had_common = pv.get("has_common", False)
            has_common = cv.get("has_common", False)
            ds = cv.get("common_shares", 0) - pv.get("common_shares", 0)

            # Classification for trading rule purposes
            if not in_prior and in_cur:
                cls = "NEW_ALL"  # issuer fully new
            elif in_prior and not in_cur:
                cls = "EXIT_ALL"
            elif has_common and not had_common:
                cls = "NEW_COMMON"  # newly took common-stock exposure (was absent or option-only)
            elif had_common and not has_common:
                cls = "EXIT_COMMON"
            elif ds > 0:
                cls = "INC"
            elif ds < 0:
                cls = "DEC"
            else:
                cls = "HOLD"

            diff_rows.append({
                "period": p, "prior_period": prior_period, "issuer_norm": k,
                "issuer_raw": cv.get("issuer_raw", pv.get("issuer_raw", "")),
                "classification": cls,
                "common_shares_prev": pv.get("common_shares", 0),
                "common_shares_cur": cv.get("common_shares", 0),
                "common_value_cur": cv.get("common_value", 0),
                "option_value_cur": cv.get("option_value", 0),
                "has_common_prev": pv.get("has_common", False),
                "has_common_cur": cv.get("has_common", False),
                "has_option_prev": pv.get("has_option", False),
                "has_option_cur": cv.get("has_option", False),
            })

            # Tradeable: new common-stock exposure on this filing
            if cls in ("NEW_ALL", "NEW_COMMON") and has_common:
                tradeable_new_rows.append({
                    "period": p, "issuer_norm": k, "issuer_raw": cv["issuer_raw"],
                    "cusips_common": ";".join(sorted(cv["cusips_common"])),
                    "common_shares": cv["common_shares"],
                    "common_value_usd": cv["common_value"],
                    "had_option_prior": pv.get("has_option", False),
                    "classification": cls,
                })

        prior = cur
        prior_period = p

    out_diff = FILINGS_DIR / "diff_long.csv"
    out_new = FILINGS_DIR / "tradeable_new_positions.csv"
    with out_diff.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(diff_rows[0].keys()))
        w.writeheader(); w.writerows(diff_rows)
    with out_new.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(tradeable_new_rows[0].keys()))
        w.writeheader(); w.writerows(tradeable_new_rows)

    # Summary print
    by_p = defaultdict(lambda: defaultdict(int))
    for r in diff_rows:
        by_p[r["period"]][r["classification"]] += 1
    print(f"{'period':<12} " + " ".join(f"{c:>11}" for c in ["NEW_ALL", "NEW_COMMON", "EXIT_ALL", "EXIT_COMMON", "INC", "DEC", "HOLD", "INIT"]))
    for p in periods:
        line = f"{p:<12} " + " ".join(f"{by_p[p].get(c, 0):>11}" for c in ["NEW_ALL", "NEW_COMMON", "EXIT_ALL", "EXIT_COMMON", "INC", "DEC", "HOLD", "INIT"])
        print(line)

    print(f"\nTradeable NEW common-stock positions per filing:")
    by_p_trade = defaultdict(list)
    for r in tradeable_new_rows:
        by_p_trade[r["period"]].append(r)
    for p in periods:
        names = by_p_trade.get(p, [])
        if names:
            print(f"\n  {p}: {len(names)} names")
            for r in sorted(names, key=lambda x: -x["common_value_usd"]):
                flag = " (was option-only)" if r["had_option_prior"] else ""
                print(f"    {r['issuer_raw']:35s} ${r['common_value_usd']:>13,.0f}{flag}")
        else:
            print(f"\n  {p}: 0 names — rule would skip this filing")

    print(f"\nWrote {out_diff}")
    print(f"Wrote {out_new}")


if __name__ == "__main__":
    main()
