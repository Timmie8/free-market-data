"""
AlphaPulse - free Yahoo Finance market-data backend using yfinance.

Run:
    py -m pip install yfinance
    py app.py

Then open AlphaPulse_yfinance.html in your browser.

The browser does NOT call Yahoo Finance directly. This local Python service
uses yfinance and exposes only JSON to the HTML dashboard.
"""

from http.server import BaseHTTPRequestHandler, HTTPServer
from urllib.parse import urlparse, parse_qs
import json
import math
import traceback

import yfinance as yf


HOST = "127.0.0.1"
PORT = 5000


def clean_number(value):
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except (TypeError, ValueError):
        pass
    return None


def safe_text(value, default=""):
    if value is None:
        return default
    return str(value)


def build_stock(symbol):
    symbol = symbol.strip().upper()
    if not symbol or len(symbol) > 15:
        raise ValueError("Invalid ticker symbol.")

    ticker = yf.Ticker(symbol)

    # One year gives enough observations for SMA200.
    hist = ticker.history(
        period="1y",
        interval="1d",
        auto_adjust=False,
        actions=False,
    )

    if hist is None or hist.empty:
        raise ValueError(f"No Yahoo Finance data found for {symbol}.")

    hist = hist.dropna(subset=["Close"])
    if len(hist) < 30:
        raise ValueError(f"Yahoo Finance returned too little history for {symbol}.")

    rows = []
    for idx, row in hist.iterrows():
        date_value = idx.strftime("%Y-%m-%d")
        rows.append({
            "date": date_value,
            "open": clean_number(row.get("Open")),
            "high": clean_number(row.get("High")),
            "low": clean_number(row.get("Low")),
            "close": clean_number(row.get("Close")),
            "adjClose": clean_number(row.get("Adj Close")),
            "volume": int(row["Volume"]) if clean_number(row.get("Volume")) is not None else 0,
        })

    latest = rows[-1]
    previous = rows[-2] if len(rows) >= 2 else latest

    # fast_info is useful for the latest available price when Yahoo provides it.
    try:
        fast = ticker.fast_info
        live_price = clean_number(fast.get("last_price"))
        previous_close = clean_number(fast.get("previous_close"))
    except Exception:
        live_price = None
        previous_close = None

    price = live_price or latest["close"]
    prev_close = previous_close or previous["close"]
    change = price - prev_close if price is not None and prev_close is not None else 0
    change_pct = (change / prev_close * 100) if prev_close else 0

    # Company metadata. Yahoo can occasionally omit individual fields, so each
    # value is optional rather than fabricated.
    try:
        info = ticker.info or {}
    except Exception:
        info = {}

    closes = [r["close"] for r in rows if r["close"] is not None]
    volumes = [r["volume"] for r in rows if r["volume"] is not None]

    avg_volume = sum(volumes[-20:]) / len(volumes[-20:]) if volumes[-20:] else None
    year_low = min(closes)
    year_high = max(closes)

    profile = {
        "companyName": safe_text(
            info.get("longName") or info.get("shortName"), symbol
        ),
        "sector": safe_text(info.get("sector"), "Equities"),
        "industry": safe_text(info.get("industry"), ""),
        "website": safe_text(info.get("website"), ""),
        "mktCap": clean_number(info.get("marketCap")),
    }

    quote = {
        "symbol": symbol,
        "name": profile["companyName"],
        "price": clean_number(price),
        "previousClose": clean_number(prev_close),
        "change": clean_number(change),
        "changesPercentage": clean_number(change_pct),
        "marketCap": profile["mktCap"],
        "pe": clean_number(info.get("trailingPE") or info.get("forwardPE")),
        "volume": latest["volume"],
        "avgVolume": clean_number(avg_volume),
        "yearLow": clean_number(year_low),
        "yearHigh": clean_number(year_high),
        "priceAvg200": clean_number(
            sum(closes[-200:]) / min(200, len(closes))
        ) if closes else None,
        "exchange": safe_text(info.get("exchange")),
        "currency": safe_text(info.get("currency"), "USD"),
        "marketState": safe_text(info.get("marketState")),
    }

    key_metrics = {
        "roeTTM": clean_number(info.get("returnOnEquity")),
        "profitMargins": clean_number(info.get("profitMargins")),
        "revenueGrowth": clean_number(info.get("revenueGrowth")),
        "debtToEquity": clean_number(info.get("debtToEquity")),
        "trailingEps": clean_number(info.get("trailingEps")),
    }

    return {
        "source": "Yahoo Finance via yfinance",
        "symbol": symbol,
        "quote": quote,
        "profile": profile,
        "keyMetrics": key_metrics,
        "history": rows,
    }


class Handler(BaseHTTPRequestHandler):
    def send_json(self, payload, status=200):
        body = json.dumps(payload, separators=(",", ":"), allow_nan=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Cache-Control", "no-store")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_OPTIONS(self):
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self):
        try:
            parsed = urlparse(self.path)

            if parsed.path == "/api/health":
                return self.send_json({"ok": True, "source": "yfinance"})

            if parsed.path != "/api/stock":
                return self.send_json({"error": "Use /api/stock?symbol=NVDA"}, 404)

            params = parse_qs(parsed.query)
            symbol = params.get("symbol", [""])[0]
            if not symbol:
                return self.send_json({"error": "Missing symbol parameter."}, 400)

            data = build_stock(symbol)
            self.send_json(data)

        except Exception as exc:
            traceback.print_exc()
            self.send_json({
                "error": f"Yahoo Finance/yfinance error: {type(exc).__name__}: {exc}"
            }, 500)

    def log_message(self, fmt, *args):
        print(f"[yfinance] {self.address_string()} - {fmt % args}")


if __name__ == "__main__":
    print(f"AlphaPulse yfinance backend running at http://{HOST}:{PORT}")
    print("Open AlphaPulse_yfinance.html in your browser.")
    print("Press Ctrl+C to stop.")
    HTTPServer((HOST, PORT), Handler).serve_forever()
