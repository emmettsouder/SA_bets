"""Download and parse all Situational Awareness LP Schedule 13D / 13G filings.

Outputs:
  data/filings/<accession>/primary_doc.xml + exhibits
  data/filings/13d_filings.csv     (one row per 13D/13G filing)
  data/filings/13d_transactions.csv (one row per individual buy/sell from the 60-day exhibit)
"""

import csv
import json
import re
import time
import urllib.request
import xml.etree.ElementTree as ET
from pathlib import Path

CIK = "0002045724"
CIK_NUM = int(CIK)
UA = "SA_Bet Research emmettsouder@gmail.com"
ROOT = Path(__file__).resolve().parent.parent
FILINGS_DIR = ROOT / "data" / "filings"
NS = {"e": "http://www.sec.gov/edgar/schedule13D"}


def fetch(url: str) -> str:
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        return r.read().decode("utf-8", errors="replace")


def list_13d_filings() -> list[dict]:
    payload = json.loads(fetch(f"https://data.sec.gov/submissions/CIK{CIK}.json"))
    recent = payload["filings"]["recent"]
    rows = []
    for i, form in enumerate(recent["form"]):
        if "13D" not in form and "13G" not in form:
            continue
        rows.append({
            "form": form,
            "accession": recent["accessionNumber"][i],
            "filing_date": recent["filingDate"][i],
            "acceptance_datetime": recent["acceptanceDateTime"][i],
            "primary_document": recent["primaryDocument"][i],
        })
    rows.sort(key=lambda r: r["filing_date"])
    return rows


def filing_dir_url(accession: str) -> str:
    return f"https://www.sec.gov/Archives/edgar/data/{CIK_NUM}/{accession.replace('-', '')}/"


def download_filing(accession: str) -> Path:
    out_dir = FILINGS_DIR / accession
    out_dir.mkdir(parents=True, exist_ok=True)
    base = filing_dir_url(accession)
    j = json.loads(fetch(base + "index.json"))
    for item in j["directory"]["item"]:
        name = item["name"]
        if name.startswith(accession):
            continue
        local = out_dir / name
        if local.exists():
            continue
        local.write_text(fetch(base + name))
        time.sleep(0.2)
    return out_dir


def parse_13d_xml(xml_path: Path) -> dict:
    root = ET.fromstring(xml_path.read_text())

    def text(elem, path):
        e = elem.find(path, NS)
        return e.text.strip() if e is not None and e.text else ""

    cover = root.find(".//e:coverPageHeader", NS)
    sub = text(root, ".//e:submissionType")
    issuer = root.find(".//e:issuerInfo", NS)
    primary_filer = root.find(".//e:reportingPersonInfo", NS)

    return {
        "submission_type": sub,
        "amendment_no": text(cover, "e:amendmentNo") or "0",
        "date_of_event": text(cover, "e:dateOfEvent"),
        "previous_accession": text(root, ".//e:previousAccessionNumber"),
        "issuer_cik": text(issuer, "e:issuerCIK"),
        "issuer_cusip": text(issuer, "e:issuerCUSIP"),
        "issuer_name": text(issuer, "e:issuerName"),
        "shares_owned": int(float(text(primary_filer, "e:aggregateAmountOwned") or 0)),
        "percent_of_class": float(text(primary_filer, "e:percentOfClass") or 0),
        "shared_voting": int(float(text(primary_filer, "e:sharedVotingPower") or 0)),
        "transaction_desc": text(root, ".//e:transactionDesc"),
        "funds_source": text(root, ".//e:fundsSource"),
    }


# --- 60-day transaction exhibit parsing ---
DATE_RE = r"(\d{1,2}/\d{1,2}/\d{4})"
TXN_LINE_RE = re.compile(
    rf"{DATE_RE}\s+(Purchase|Sale)\s+\(?([\d,]+)\)?\s+\$?([\d.]+)",
    re.IGNORECASE,
)


def parse_transactions_from_text(text: str, source: str) -> list[dict]:
    """Pull 60-day txns out of either a primary_doc.xml's `transactionDesc` or an HTML exhibit."""
    clean = re.sub(r"<[^>]+>", " ", text)
    clean = re.sub(r"\s+", " ", clean)
    rows = []
    for m in TXN_LINE_RE.finditer(clean):
        date, side, shares, price = m.groups()
        rows.append({
            "source": source,
            "date": date,
            "side": side.title(),
            "shares": int(shares.replace(",", "")),
            "price_per_share": float(price),
        })
    # Also support narrative form: "On 7/18/2025, the Fund purchased 203,578 shares ... $13.189"
    narrative = re.compile(
        rf"On\s+{DATE_RE},\s+the\s+Fund\s+(purchased|sold)\s+([\d,]+)\s+shares.*?\$([\d.]+)",
        re.IGNORECASE | re.DOTALL,
    )
    for m in narrative.finditer(clean):
        date, side, shares, price = m.groups()
        rows.append({
            "source": source,
            "date": date,
            "side": "Purchase" if side.lower() == "purchased" else "Sale",
            "shares": int(shares.replace(",", "")),
            "price_per_share": float(price),
        })
    # Dedupe (in case both regexes hit the same row)
    seen = set()
    out = []
    for r in rows:
        key = (r["date"], r["side"], r["shares"], r["price_per_share"])
        if key in seen:
            continue
        seen.add(key)
        out.append(r)
    return out


def main():
    filings = list_13d_filings()
    print(f"Found {len(filings)} 13D/13G filings\n")

    filing_rows = []
    txn_rows = []

    for f in filings:
        acc = f["accession"]
        out_dir = download_filing(acc)
        xml_path = out_dir / "primary_doc.xml"
        parsed = parse_13d_xml(xml_path)

        # Parse transactions from primary_doc (initial 13Ds list them inline)
        # OR from ex99* exhibit (amendments use that)
        txn_sources = []
        if parsed["transaction_desc"] and "On" in parsed["transaction_desc"]:
            txn_sources.append(("primary_doc.xml", parsed["transaction_desc"]))
        for exhibit in out_dir.glob("ex99*.htm"):
            txn_sources.append((exhibit.name, exhibit.read_text()))

        all_txns = []
        for source, text in txn_sources:
            all_txns.extend(parse_transactions_from_text(text, f"{acc}/{source}"))

        for t in all_txns:
            t["accession"] = acc
            t["form"] = f["form"]
            t["issuer"] = parsed["issuer_name"]
            t["cusip"] = parsed["issuer_cusip"]
            txn_rows.append(t)

        filing_rows.append({
            "accession": acc,
            "form": f["form"],
            "filing_date": f["filing_date"],
            "acceptance_datetime": f["acceptance_datetime"],
            "amendment_no": parsed["amendment_no"],
            "previous_accession": parsed["previous_accession"],
            "date_of_event": parsed["date_of_event"],
            "issuer_name": parsed["issuer_name"],
            "issuer_cik": parsed["issuer_cik"],
            "issuer_cusip": parsed["issuer_cusip"],
            "shares_owned": parsed["shares_owned"],
            "percent_of_class": parsed["percent_of_class"],
            "n_transactions_disclosed": len(all_txns),
        })

        print(f"  {f['form']:15s} {acc}  filed={f['filing_date']}  accept={f['acceptance_datetime']}  "
              f"issuer={parsed['issuer_name']}  shares={parsed['shares_owned']:,}  pct={parsed['percent_of_class']}%  "
              f"txns={len(all_txns)}")

    filings_csv = FILINGS_DIR / "13d_filings.csv"
    txn_csv = FILINGS_DIR / "13d_transactions.csv"

    with filings_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(filing_rows[0].keys()))
        w.writeheader()
        w.writerows(filing_rows)

    with txn_csv.open("w", newline="") as fh:
        cols = ["accession", "form", "issuer", "cusip", "date", "side", "shares", "price_per_share", "source"]
        w = csv.DictWriter(fh, fieldnames=cols)
        w.writeheader()
        for r in txn_rows:
            w.writerow({k: r.get(k, "") for k in cols})

    print(f"\nWrote {filings_csv}  ({len(filing_rows)} rows)")
    print(f"Wrote {txn_csv}     ({len(txn_rows)} rows)")


if __name__ == "__main__":
    main()
