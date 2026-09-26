import json
from pathlib import Path

import streamlit as st
import streamlit.components.v1 as components

from app_yfinance import build_stock

st.set_page_config(
    page_title="AlphaPulse AI Swing & Momentum Analytics",
    page_icon="📈",
    layout="wide",
)

st.markdown("### AlphaPulse — Yahoo Finance / yfinance")
st.caption("Market data is fetched server-side with yfinance. No FMP API key and no mock/fallback market data.")

ticker = st.text_input(
    "Ticker symbol",
    value="NVDA",
    max_chars=15,
    help="Enter a US stock ticker, for example NVDA, AMD, PLTR or AAPL.",
).strip().upper()

if not ticker:
    st.warning("Enter a ticker symbol.")
    st.stop()

try:
    with st.spinner(f"Loading Yahoo Finance data for {ticker}..."):
        data = build_stock(ticker)
except Exception as exc:
    st.error(f"Yahoo Finance error for {ticker}: {exc}")
    st.info("Check that the ticker exists and try again.")
    st.stop()

html_path = Path(__file__).with_name("AlphaPulse_yfinance.html")
html = html_path.read_text(encoding="utf-8")

bridge = r"""
<script>
window.__ALPHAPULSE_STOCK_DATA__ = __STOCK_DATA_PLACEHOLDER__;
</script>
"""

# Override the browser-side fetch function with the server-fetched yfinance data.
override = r"""
<script>
window.__ALPHAPULSE_STOCK_DATA__ = __STOCK_DATA_PLACEHOLDER__;

window.fetchAndRenderData = async function(symbol) {
        const requested = String(symbol || "").toUpperCase();
        const embedded = window.__ALPHAPULSE_STOCK_DATA__;

        if (!embedded || !embedded.quote || embedded.quote.symbol !== requested) {
            const banner = document.getElementById("errorBanner");
            const msg = document.getElementById("errorMessage");
            if (banner && msg) {
                msg.textContent = `Yahoo Finance data for ${requested} is not loaded. Change the Streamlit ticker field above and rerun.`;
                banner.classList.remove("hidden");
            }
            return;
        }

        try {
            showLoading(true);
            hideError();

            const quote = embedded.quote;
            const profile = embedded.profile || {};
            const keyMetrics = embedded.keyMetrics || {};
            const historyData = Array.isArray(embedded.history) ? embedded.history.slice() : [];

            historyData.sort((a, b) => new Date(a.date) - new Date(b.date));

            if (historyData.length < 30) {
                throw new Error("Insufficient Yahoo Finance history.");
            }

            const analysis = runQuantitativeAnalysis(
                quote, profile, historyData, keyMetrics
            );

            renderOverview(quote, profile);
            renderScores(analysis, quote.price);
            renderTechnicalIndicators(analysis);
            renderChart(historyData, analysis);
            renderSummary(requested, analysis);
            showLoading(false);
        } catch (error) {
            console.error(error);
            showError(`Yahoo Finance data error: ${error.message}`);
            showLoading(false);
        }
    };

// Reload the dashboard using the server-provided data.
window.fetchAndRenderData(requestedTicker);
</script>
"""
# requestedTicker is injected safely as JSON.
override = override.replace(
    "window.fetchAndRenderData(requestedTicker);",
    f"window.fetchAndRenderData({json.dumps(ticker)});"
)
data_json = json.dumps(data, separators=(",", ":"), allow_nan=False)
html = html.replace("</body>", override.replace("__STOCK_DATA_PLACEHOLDER__", data_json) + "\n</body>")

components.html(html, height=1500, scrolling=True)
