"""Download and parse all Situational Awareness LP 13F-HR filings.

Outputs:
  data/filings/<accession>/primary_doc.xml
  data/filings/<accession>/holdings.xml
  data/filings/holdings_long.csv   (one row per (filing, position))
  data/filings/filings_meta.csv    (one row per filing with acceptance time)
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
NS = {"n": "http://www.sec.gov/edgar/document/thirteenf/informationtable"}
PRIMARY_NS = {"p": "http://www.sec.gov/edgar/thirteenffiler"}


def fetch(url: str, *, binary: bool = False):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept-Encoding": "gzip, deflate"})
    with urllib.request.urlopen(req, timeout=30) as resp:
        data = resp.read()
        if resp.headers.get("Content-Encoding") == "gzip":
            import gzip
            data = gzip.decompress(data)
    return data if binary else data.decode("utf-8")


def list_13f_filings():
    """Use EDGAR submissions JSON to get all 13F-HR filings for the CIK."""
    url = f"https://data.sec.gov/submissions/CIK{CIK}.json"
    payload = json.loads(fetch(url))
    recent = payload["filings"]["recent"]
    rows = []
    for i, form in enumerate(recent["form"]):
        if form not in ("13F-HR", "13F-HR/A"):
            continue
        rows.append({
            "form": form,
            "accession": recent["accessionNumber"][i],
            "filing_date": recent["filingDate"][i],
            "period_of_report": recent["reportDate"][i],
            "acceptance_datetime": recent["acceptanceDateTime"][i],
            "primary_document": recent["primaryDocument"][i],
        })
    rows.sort(key=lambda r: r["period_of_report"])
    return rows


def filing_dir_url(accession: str) -> str:
    acc_nodash = accession.replace("-", "")
    return f"https://www.sec.gov/Archives/edgar/data/{CIK_NUM}/{acc_nodash}/"


def list_filing_files(accession: str) -> list[str]:
    """Return basenames of XML files in the filing's archive directory."""
    base = filing_dir_url(accession)
    html = fetch(base)
    paths = {m.group(1) for m in re.finditer(r'href="([^"]+\.xml)"', html)}
    return [p.rsplit("/", 1)[-1] for p in paths]


def find_holdings_xml(accession: str) -> str:
    """The information-table XML is the one that is NOT primary_doc.xml."""
    files = list_filing_files(accession)
    files = [f for f in files if f.lower() != "primary_doc.xml"]
    if len(files) != 1:
        raise RuntimeError(f"Expected 1 holdings XML, got {files} for {accession}")
    return files[0]


def parse_holdings(xml_text: str) -> list[dict]:
    root = ET.fromstring(xml_text)
    out = []
    for it in root.findall("n:infoTable", NS):
        def t(tag):
            el = it.find(f"n:{tag}", NS)
            return el.text.strip() if el is not None and el.text else ""
        shrs = it.find("n:shrsOrPrnAmt", NS)
        out.append({
            "issuer": t("nameOfIssuer"),
            "title_of_class": t("titleOfClass"),
            "cusip": t("cusip"),
            "value_usd": int(t("value") or 0),
            "shares": int(shrs.find("n:sshPrnamt", NS).text) if shrs is not None else 0,
            "shares_type": shrs.find("n:sshPrnamtType", NS).text if shrs is not None else "",
            "put_call": t("putCall"),  # empty if common stock
        })
    return out


def main():
    FILINGS_DIR.mkdir(parents=True, exist_ok=True)
    filings = list_13f_filings()
    print(f"Found {len(filings)} 13F filings")

    meta_rows = []
    long_rows = []

    for f in filings:
        acc = f["accession"]
        d = FILINGS_DIR / acc
        d.mkdir(exist_ok=True)
        time.sleep(0.2)  # be nice to SEC

        primary_url = filing_dir_url(acc) + f["primary_document"]
        primary_path = d / "primary_doc.xml"
        if not primary_path.exists():
            primary_path.write_text(fetch(primary_url))
            time.sleep(0.2)

        holdings_name = find_holdings_xml(acc)
        holdings_url = filing_dir_url(acc) + holdings_name
        holdings_path = d / "holdings.xml"
        if not holdings_path.exists():
            holdings_path.write_text(fetch(holdings_url))
            time.sleep(0.2)

        holdings = parse_holdings(holdings_path.read_text())
        total_value = sum(h["value_usd"] for h in holdings)

        meta_rows.append({
            "accession": acc,
            "form": f["form"],
            "period_of_report": f["period_of_report"],
            "filing_date": f["filing_date"],
            "acceptance_datetime": f["acceptance_datetime"],
            "n_positions": len(holdings),
            "n_unique_cusips": len({h["cusip"] for h in holdings}),
            "total_value_usd": total_value,
        })

        for h in holdings:
            long_rows.append({
                "accession": acc,
                "period_of_report": f["period_of_report"],
                "filing_date": f["filing_date"],
                "acceptance_datetime": f["acceptance_datetime"],
                **h,
                "weight": h["value_usd"] / total_value if total_value else 0.0,
            })

        print(f"  {f['period_of_report']}  {acc}  filed={f['filing_date']}  accept={f['acceptance_datetime']}  N={len(holdings)}  $={total_value:,.0f}")

    meta_csv = FILINGS_DIR / "filings_meta.csv"
    long_csv = FILINGS_DIR / "holdings_long.csv"
    with meta_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(meta_rows[0].keys()))
        w.writeheader()
        w.writerows(meta_rows)
    with long_csv.open("w", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(long_rows[0].keys()))
        w.writeheader()
        w.writerows(long_rows)
    print(f"\nWrote {meta_csv}")
    print(f"Wrote {long_csv}  ({len(long_rows)} rows)")


if __name__ == "__main__":
    main()
