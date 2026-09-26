"""
AlphaPulse - Yahoo Finance / yfinance + Streamlit

Gebruik:
    pip install -r requirements.txt
    streamlit run app_yfinance.py

Benodigd in dezelfde GitHub repository:
    app_yfinance.py
    AlphaPulse_yfinance.html
    requirements.txt

De browser haalt GEEN data rechtstreeks uit Yahoo Finance.
Streamlit/yfinance haalt de data server-side op en geeft deze door
aan het AlphaPulse HTML-dashboard.

Er wordt geen mock/demo marktdata gegenereerd.
"""

from pathlib import Path
import math

import yfinance as yf


# ============================================================
# HULPFUNCTIES
# ============================================================

def clean_number(value):
    """Zet een waarde veilig om naar float."""
    try:
        value = float(value)
        if math.isfinite(value):
            return value
    except (TypeError, ValueError):
        pass

    return None


def safe_text(value, default=""):
    """Zet een waarde veilig om naar tekst."""
    if value is None:
        return default

    return str(value)


# ============================================================
# YAHOO FINANCE DATA
# ============================================================

def build_stock(symbol):
    """
    Haalt echte Yahoo Finance data op via yfinance.

    Ondersteunt bijvoorbeeld:
        NVDA
        AMD
        PLTR
        AAPL
        TSLA
        JBL
        ASML.AS
        SAP.DE
        BMW.DE
        enz.
    """

    symbol = symbol.strip().upper()

    if not symbol:
        raise ValueError("Please enter a ticker symbol.")

    if len(symbol) > 15:
        raise ValueError("Ticker symbol is too long.")

    # Yahoo Finance ticker
    ticker = yf.Ticker(symbol)

    # --------------------------------------------------------
    # HISTORICAL DATA
    # --------------------------------------------------------

    hist = ticker.history(
        period="1y",
        interval="1d",
        auto_adjust=False,
        actions=False,
    )

    if hist is None or hist.empty:
        raise ValueError(
            f"No Yahoo Finance data found for {symbol}."
        )

    # Alleen rijen met een geldige Close
    hist = hist.dropna(subset=["Close"])

    if len(hist) < 30:
        raise ValueError(
            f"Yahoo Finance returned too little historical data for {symbol}."
        )

    # --------------------------------------------------------
    # HISTORY OMZETTEN NAAR JSON
    # --------------------------------------------------------

    rows = []

    for idx, row in hist.iterrows():

        date_value = idx.strftime("%Y-%m-%d")

        volume_value = clean_number(
            row.get("Volume")
        )

        if volume_value is None:
            volume_value = 0

        rows.append(
            {
                "date": date_value,
                "open": clean_number(row.get("Open")),
                "high": clean_number(row.get("High")),
                "low": clean_number(row.get("Low")),
                "close": clean_number(row.get("Close")),
                "adjClose": clean_number(row.get("Adj Close")),
                "volume": int(volume_value),
            }
        )

    # --------------------------------------------------------
    # LAATSTE DATA
    # --------------------------------------------------------

    latest = rows[-1]

    if len(rows) >= 2:
        previous = rows[-2]
    else:
        previous = latest

    # --------------------------------------------------------
    # LAATSTE PRIJS VIA FAST_INFO
    # --------------------------------------------------------

    live_price = None
    previous_close = None

    try:
        fast = ticker.fast_info

        live_price = clean_number(
            fast.get("last_price")
        )

        previous_close = clean_number(
            fast.get("previous_close")
        )

    except Exception:
        live_price = None
        previous_close = None

    # Als fast_info geen waarde geeft,
    # gebruiken we de laatste historische candle.
    price = (
        live_price
        if live_price is not None
        else latest["close"]
    )

    prev_close = (
        previous_close
        if previous_close is not None
        else previous["close"]
    )

    # --------------------------------------------------------
    # DAGVERANDERING
    # --------------------------------------------------------

    if (
        price is not None
        and prev_close is not None
    ):
        change = price - prev_close

        if prev_close != 0:
            change_pct = (
                change / prev_close
            ) * 100
        else:
            change_pct = 0

    else:
        change = 0
        change_pct = 0

    # --------------------------------------------------------
    # COMPANY INFORMATION
    # --------------------------------------------------------

    try:
        info = ticker.info or {}

    except Exception:
        info = {}

    # --------------------------------------------------------
    # CLOSES / VOLUME
    # --------------------------------------------------------

    closes = [
        r["close"]
        for r in rows
        if r["close"] is not None
    ]

    volumes = [
        r["volume"]
        for r in rows
        if r["volume"] is not None
    ]

    # Gemiddeld volume laatste 20 handelsdagen
    recent_volumes = volumes[-20:]

    if recent_volumes:
        avg_volume = (
            sum(recent_volumes)
            / len(recent_volumes)
        )
    else:
        avg_volume = None

    # 1-year low / high
    year_low = min(closes)

    year_high = max(closes)

    # --------------------------------------------------------
    # COMPANY PROFILE
    # --------------------------------------------------------

    company_name = (
        info.get("longName")
        or info.get("shortName")
        or symbol
    )

    profile = {
        "companyName": safe_text(
            company_name,
            symbol
        ),

        "sector": safe_text(
            info.get("sector"),
            "Equities"
        ),

        "industry": safe_text(
            info.get("industry"),
            ""
        ),

        "website": safe_text(
            info.get("website"),
            ""
        ),

        "mktCap": clean_number(
            info.get("marketCap")
        ),
    }

    # --------------------------------------------------------
    # QUOTE
    # --------------------------------------------------------

    if closes:

        last_200 = closes[-200:]

        price_avg_200 = (
            sum(last_200)
            / len(last_200)
        )

    else:
        price_avg_200 = None

    quote = {
        "symbol": symbol,

        "name": profile["companyName"],

        "price": clean_number(
            price
        ),

        "previousClose": clean_number(
            prev_close
        ),

        "change": clean_number(
            change
        ),

        "changesPercentage": clean_number(
            change_pct
        ),

        "marketCap": profile["mktCap"],

        "pe": clean_number(
            info.get("trailingPE")
            or info.get("forwardPE")
        ),

        "volume": latest["volume"],

        "avgVolume": clean_number(
            avg_volume
        ),

        "yearLow": clean_number(
            year_low
        ),

        "yearHigh": clean_number(
            year_high
        ),

        "priceAvg200": clean_number(
            price_avg_200
        ),

        "exchange": safe_text(
            info.get("exchange")
        ),

        "currency": safe_text(
            info.get("currency"),
            "USD"
        ),

        "marketState": safe_text(
            info.get("marketState")
        ),
    }

    # --------------------------------------------------------
    # FUNDAMENTAL METRICS
    # --------------------------------------------------------

    key_metrics = {
        "roeTTM": clean_number(
            info.get("returnOnEquity")
        ),

        "profitMargins": clean_number(
            info.get("profitMargins")
        ),

        "revenueGrowth": clean_number(
            info.get("revenueGrowth")
        ),

        "debtToEquity": clean_number(
            info.get("debtToEquity")
        ),

        "trailingEps": clean_number(
            info.get("trailingEps")
        ),
    }

    # --------------------------------------------------------
    # COMPLETE DATASET
    # --------------------------------------------------------

    return {
        "source": "Yahoo Finance via yfinance",

        "symbol": symbol,

        "quote": quote,

        "profile": profile,

        "keyMetrics": key_metrics,

        "history": rows,
    }


# ============================================================
# STREAMLIT APP
# ============================================================

def run_streamlit_app():

    import json

    import streamlit as st

    import streamlit.components.v1 as components

    # --------------------------------------------------------
    # PAGE CONFIG
    # --------------------------------------------------------

    st.set_page_config(
        page_title=(
            "AlphaPulse AI Swing & "
            "Momentum Analytics"
        ),
        page_icon="📈",
        layout="wide",
    )

    # --------------------------------------------------------
    # HEADER
    # --------------------------------------------------------

    st.markdown(
        "# AlphaPulse — AI Swing & Momentum Analytics"
    )

    st.caption(
        "Yahoo Finance / yfinance market data. "
        "Enter any valid Yahoo Finance ticker. "
        "No FMP API key and no mock/fallback market data."
    )

    # --------------------------------------------------------
    # TICKER INPUT
    # --------------------------------------------------------

    with st.form(
        "ticker_form",
        clear_on_submit=False
    ):

        col1, col2 = st.columns(
            [5, 1]
        )

        with col1:

            ticker_input = st.text_input(
                "Ticker symbol",

                value=st.session_state.get(
                    "alpha_ticker",
                    "NVDA"
                ),

                max_chars=15,

                placeholder=(
                    "e.g. NVDA, AMD, PLTR, "
                    "AAPL, ASML.AS"
                ),

                help=(
                    "Enter any valid Yahoo Finance "
                    "symbol. Examples: NVDA, AMD, "
                    "PLTR, AAPL, ASML.AS, SAP.DE."
                ),
            )

        with col2:

            st.write("")
            st.write("")

            analyze = st.form_submit_button(
                "🔎 Analyze",
                use_container_width=True
            )

    # --------------------------------------------------------
    # NIEUWE TICKER OPSLAAN
    # --------------------------------------------------------

    if analyze:

        clean_ticker = (
            ticker_input
            .strip()
            .upper()
        )

        if not clean_ticker:

            st.error(
                "Please enter a ticker symbol."
            )

            st.stop()

        st.session_state[
            "alpha_ticker"
        ] = clean_ticker

    # --------------------------------------------------------
    # HUIDIGE TICKER
    # --------------------------------------------------------

    ticker = (
        st.session_state
        .get(
            "alpha_ticker",
            "NVDA"
        )
        .strip()
        .upper()
    )

    # --------------------------------------------------------
    # YAHOO FINANCE OPHALEN
    # --------------------------------------------------------

    try:

        with st.spinner(
            f"Loading Yahoo Finance data for {ticker}..."
        ):

            data = build_stock(
                ticker
            )

    except Exception as exc:

        st.error(
            f"Yahoo Finance error for {ticker}: {exc}"
        )

        st.info(
            "Check the Yahoo Finance ticker symbol. "
            "Examples: NVDA, AMD, PLTR, AAPL, "
            "ASML.AS or SAP.DE."
        )

        st.stop()

    # --------------------------------------------------------
    # HTML DASHBOARD CONTROLEREN
    # --------------------------------------------------------

    html_path = (
        Path(__file__).with_name(
            "AlphaPulse_yfinance.html"
        )
    )

    if not html_path.exists():

        st.error(
            "AlphaPulse_yfinance.html "
            "is missing from the repository."
        )

        st.stop()

    # --------------------------------------------------------
    # HTML INLEZEN
    # --------------------------------------------------------

    html = html_path.read_text(
        encoding="utf-8"
    )

    # --------------------------------------------------------
    # DATA VEILIG NAAR JAVASCRIPT
    # --------------------------------------------------------

    data_json = json.dumps(
        data,
        separators=(",", ":"),
        allow_nan=False
    )

    ticker_json = json.dumps(
        ticker
    )

    # --------------------------------------------------------
    # JAVASCRIPT BRIDGE
    # --------------------------------------------------------

    override = f"""
<script>

window.__ALPHAPULSE_STOCK_DATA__ = {data_json};

window.__ALPHAPULSE_STREAMLIT_TICKER__ = {ticker_json};


/*
 * Streamlit heeft de ticker server-side
 * opgehaald via yfinance.
 *
 * Het HTML-dashboard gebruikt uitsluitend
 * deze echte data.
 *
 * Er wordt GEEN localhost API aangeroepen.
 * Er wordt GEEN fake/demo data gebruikt.
 */


window.fetchAndRenderData = async function(symbol) {{

    const requested =
        String(symbol || '').toUpperCase();

    const data =
        window.__ALPHAPULSE_STOCK_DATA__;

    const loaded =
        window.__ALPHAPULSE_STREAMLIT_TICKER__;


    /*
     * Controleer of de gevraagde ticker
     * overeenkomt met de door Streamlit
     * geladen ticker.
     */

    if (
        !data ||
        !data.quote ||
        data.quote.symbol !== requested
    ) {{

        showError(
            'Ticker ' +
            requested +
            ' is not loaded. ' +
            'Use the Ticker symbol field above ' +
            'and click Analyze.'
        );

        return;
    }}


    try {{

        const quote =
            data.quote;

        const profile =
            data.profile || {{}};

        const historyData =
            Array.isArray(data.history)
                ? data.history.slice()
                : [];

        const keyMetrics =
            data.keyMetrics || {{}};


        /*
         * Controle historische data
         */

        if (
            !quote ||
            historyData.length < 30
        ) {{

            throw new Error(
                'Insufficient Yahoo Finance '
                + 'historical data.'
            );
        }}


        /*
         * Chronologisch sorteren
         */

        historyData.sort(
            (a, b) =>
                new Date(a.date)
                -
                new Date(b.date)
        );


        /*
         * Bestaande AlphaPulse
         * technische analyse uitvoeren.
         */

        const analysis =
            runQuantitativeAnalysis(
                quote,
                profile,
                historyData,
                keyMetrics
            );


        /*
         * Dashboard renderen
         */

        renderOverview(
            quote,
            profile
        );

        renderScores(
            analysis,
            quote.price
        );

        renderTechnicalIndicators(
            analysis
        );

        renderChart(
            historyData,
            analysis
        );

        renderSummary(
            loaded,
            analysis
        );


        showLoading(false);

        hideError();

    }}

    catch (error) {{

        console.error(error);

        showError(
            'Yahoo Finance analysis error: '
            +
            error.message
        );

        showLoading(false);
    }}

}};


/*
 * Dashboard automatisch laden
 * voor de ticker die Streamlit
 * heeft opgehaald.
 */

window.addEventListener(
    'load',
    function() {{

        window.fetchAndRenderData(
            {ticker_json}
        );

    }}
);

</script>
"""

    # --------------------------------------------------------
    # JAVASCRIPT TOEVOEGEN
    # --------------------------------------------------------

    html = html.replace(
        "</body>",
        override +
        "\n</body>"
    )

    # --------------------------------------------------------
    # DASHBOARD TONEN
    # --------------------------------------------------------

    components.html(
        html,
        height=1550,
        scrolling=True
    )


# ============================================================
# START STREAMLIT
# ============================================================

if __name__ == "__main__":
    run_streamlit_app()
