"""Daily OHLCV fetcher via Yahoo Finance chart endpoint, cached to disk.

Free, no API key, ~no rate limit issues at our volume. Returns a list of dicts
with keys: date (YYYY-MM-DD), open, high, low, close, adj_close, volume.

Used for historical event-study backtesting only. The live trading system uses
Alpaca's market data, not this.
"""

import json
import time
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data" / "prices"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
UA = "Mozilla/5.0 SA_Bet"


def _to_unix(date_str: str) -> int:
    return int(datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp())


def fetch_chart(ticker: str, start: str, end: str) -> list[dict]:
    """Return daily bars between [start, end] inclusive. Dates are YYYY-MM-DD."""
    p1 = _to_unix(start)
    p2 = _to_unix(end) + 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={p1}&period2={p2}&interval=1d&events=div%2Csplit"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    err = data.get("chart", {}).get("error")
    if err:
        raise RuntimeError(f"{ticker}: {err}")
    res = data["chart"]["result"][0]
    ts = res.get("timestamp", [])
    quote = res["indicators"]["quote"][0]
    adj = res["indicators"].get("adjclose", [{}])[0].get("adjclose", [None] * len(ts))
    bars = []
    for i, t in enumerate(ts):
        d = datetime.fromtimestamp(t, tz=timezone.utc).strftime("%Y-%m-%d")
        bars.append({
            "date": d,
            "open": quote["open"][i],
            "high": quote["high"][i],
            "low": quote["low"][i],
            "close": quote["close"][i],
            "adj_close": adj[i],
            "volume": quote["volume"][i],
        })
    return bars


def get(ticker: str, start: str = "2024-10-01", end: str = "2026-05-04", refresh: bool = False) -> list[dict]:
    cache = CACHE_DIR / f"{ticker.replace('/', '_')}.json"
    if cache.exists() and not refresh:
        cached = json.loads(cache.read_text())
        if cached.get("start") <= start and cached.get("end") >= end:
            bars = [b for b in cached["bars"] if start <= b["date"] <= end]
            return bars
    bars = fetch_chart(ticker, start, end)
    cache.write_text(json.dumps({"ticker": ticker, "start": start, "end": end, "bars": bars}))
    time.sleep(0.25)
    return bars


def fetch_intraday(ticker: str, start: str, end: str, interval: str = "60m") -> list[dict]:
    """Intraday bars. Yahoo limits: 1m=7d, 5m/15m/30m=60d, 60m/90m=730d."""
    p1 = _to_unix(start)
    p2 = _to_unix(end) + 86400
    url = (
        f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
        f"?period1={p1}&period2={p2}&interval={interval}&includePrePost=false"
    )
    req = urllib.request.Request(url, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=30) as r:
        data = json.loads(r.read())
    err = data.get("chart", {}).get("error")
    if err:
        raise RuntimeError(f"{ticker}: {err}")
    res = data["chart"]["result"][0]
    ts = res.get("timestamp", [])
    quote = res["indicators"]["quote"][0]
    bars = []
    for i, t in enumerate(ts):
        dt_utc = datetime.fromtimestamp(t, tz=timezone.utc)
        bars.append({
            "ts_utc": dt_utc.isoformat(),
            "ts_unix": t,
            "open": quote["open"][i],
            "high": quote["high"][i],
            "low": quote["low"][i],
            "close": quote["close"][i],
            "volume": quote["volume"][i],
        })
    return bars


def get_intraday(ticker: str, start: str, end: str, interval: str = "60m", refresh: bool = False) -> list[dict]:
    cache = CACHE_DIR / f"{ticker.replace('/', '_')}_intraday_{interval}.json"
    if cache.exists() and not refresh:
        cached = json.loads(cache.read_text())
        if cached.get("start") <= start and cached.get("end") >= end:
            return [b for b in cached["bars"] if start <= b["ts_utc"][:10] <= end]
    bars = fetch_intraday(ticker, start, end, interval)
    cache.write_text(json.dumps({"ticker": ticker, "start": start, "end": end, "interval": interval, "bars": bars}))
    time.sleep(0.25)
    return bars


def get_many(tickers: list[str], start: str, end: str, refresh: bool = False) -> dict[str, list[dict]]:
    out = {}
    failures = []
    for t in tickers:
        try:
            out[t] = get(t, start, end, refresh)
        except Exception as e:
            failures.append((t, str(e)))
            print(f"  FAIL {t}: {e}")
    if failures:
        print(f"\n{len(failures)} ticker(s) failed: {[f[0] for f in failures]}")
    return out


if __name__ == "__main__":
    bars = get("SPY", "2024-12-01", "2025-01-15")
    print(f"SPY: {len(bars)} bars")
    for b in bars[:3] + bars[-3:]:
        print(f"  {b['date']}  C={b['close']:.2f}  V={b['volume']:,}")
