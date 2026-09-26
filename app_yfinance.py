"""
AlphaPulse - free Yahoo Finance market-data backend using yfinance.

Run:
    py -m pip install yfinance
    py app.py

Then open AlphaPulse_yfinance.html in your browser.

The browser does NOT call Yahoo Finance directly. This local Python service
uses yfinance and exposes only JSON to the HTML dashboard.
"""

from urllib.parse import urlparse, parse_qs
import math

import yfinance as yf




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


# Streamlit entry point. Streamlit Cloud provides the web server.
def run_streamlit_app():
    import json
    from pathlib import Path
    import streamlit as st
    import streamlit.components.v1 as components

    st.set_page_config(
        page_title="AlphaPulse AI Swing & Momentum Analytics",
        page_icon="📈",
        layout="wide",
    )

    st.markdown("### AlphaPulse — Yahoo Finance / yfinance")
    st.caption("Real Yahoo Finance market data via yfinance. No FMP API key and no mock/fallback market data.")

    ticker = st.text_input(
        "Ticker symbol",
        value="NVDA",
        max_chars=15,
        help="Enter a US stock ticker, for example NVDA, AMD, PLTR or AAPL.",
    ).strip().upper()

    presets = ["NVDA", "AAPL", "TSLA", "MSFT", "AMD", "AMZN", "META", "PLTR"]
    selected = st.selectbox("Quick ticker", ["--"] + presets, index=0)
    if selected != "--":
        ticker = selected

    if not ticker:
        st.warning("Enter a ticker symbol.")
        st.stop()

    try:
        with st.spinner(f"Loading Yahoo Finance data for {ticker}..."):
            data = build_stock(ticker)
    except Exception as exc:
        st.error(f"Yahoo Finance error for {ticker}: {exc}")
        st.info("Check the ticker symbol and try again.")
        st.stop()

    # Reuse the existing AlphaPulse HTML dashboard. The HTML no longer calls
    # a local HTTP endpoint: its data-fetch function is replaced below with
    # the data that Streamlit fetched server-side using yfinance.
    html_path = Path(__file__).with_name("AlphaPulse_yfinance.html")
    if not html_path.exists():
        st.error("AlphaPulse_yfinance.html is missing from the repository.")
        st.stop()

    html = html_path.read_text(encoding="utf-8")
    data_json = json.dumps(data, separators=(",", ":"), allow_nan=False)
    ticker_json = json.dumps(ticker)

    override = f"""
<script>
window.__ALPHAPULSE_STOCK_DATA__ = {data_json};

window.fetchAndRenderData = async function(symbol) {{
    const requested = String(symbol || '').toUpperCase();
    const data = window.__ALPHAPULSE_STOCK_DATA__;

    if (!data || !data.quote || data.quote.symbol !== requested) {{
        showError('This Streamlit page is currently loaded for ' + data.symbol + '. Use the ticker field above to load another symbol.');
        return;
    }}

    try {{
        const quote = data.quote;
        const profile = data.profile || {{}};
        const historyData = data.history || [];
        const keyMetrics = data.keyMetrics || null;

        if (!quote || historyData.length < 30) {{
            throw new Error('Insufficient Yahoo Finance historical data.');
        }}

        historyData.sort((a, b) => new Date(a.date) - new Date(b.date));
        const analysis = runQuantitativeAnalysis(quote, profile, historyData, keyMetrics);

        renderOverview(quote, profile);
        renderScores(analysis, quote.price);
        renderTechnicalIndicators(analysis);
        renderChart(historyData, analysis);
        renderSummary(requested, analysis);
        showLoading(false);
    }} catch (error) {{
        console.error(error);
        showError('Yahoo Finance analysis error: ' + error.message);
        showLoading(false);
    }}
}};

window.addEventListener('load', function() {{
    window.fetchAndRenderData({ticker_json});
}});
</script>
"""

    html = html.replace("</body>", override + "\n</body>")
    components.html(html, height=1550, scrolling=True)


if __name__ == "__main__":
    run_streamlit_app()
