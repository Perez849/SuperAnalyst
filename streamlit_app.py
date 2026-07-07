"""Interactive valuation app.

    streamlit run streamlit_app.py

Type a ticker, tweak the cost-of-capital and growth levers in the sidebar, and
the research note regenerates live. Uses FMP if FMP_API_KEY is set, else yfinance.
"""
import os
import streamlit as st
import streamlit.components.v1 as components

from equityval.engine import ValuationConfig, value_company

st.set_page_config(page_title="Equity Valuation Engine", layout="wide")
st.title("Equity valuation engine")
st.caption("Automated DCF + comps + DDM research note. Not investment advice.")

with st.sidebar:
    st.header("Inputs")
    ticker = st.text_input("Ticker", "AAPL").strip().upper()
    provider = st.selectbox("Data provider", ["auto", "fmp", "yfinance"])
    fmp_key = st.text_input("FMP API key", os.environ.get("FMP_API_KEY", ""), type="password")
    st.divider()
    st.subheader("Cost of capital")
    rf = st.slider("Risk-free rate", 0.0, 0.08, 0.043, 0.001, format="%.3f")
    erp = st.slider("Equity risk premium", 0.02, 0.09, 0.046, 0.001, format="%.3f")
    cp = st.slider("Country risk premium", 0.0, 0.08, 0.0, 0.001, format="%.3f")
    beta = st.text_input("Beta override (blank = auto)", "")
    st.subheader("Growth & terminal")
    horizon = st.slider("Explicit horizon (yrs)", 3, 10, 5)
    tg = st.slider("Terminal growth", 0.0, 0.05, 0.025, 0.001, format="%.3f")
    exit_m = st.text_input("Exit EV/EBITDA (blank = none)", "")
    cw = st.slider("Comps weight in target", 0.0, 1.0, 0.35, 0.05)
    go = st.button("Run valuation", type="primary")

if go and ticker:
    cfg = ValuationConfig(
        horizon=horizon, terminal_growth=tg, risk_free=rf, erp=erp,
        country_premium=cp, comps_weight=cw,
        beta_override=float(beta) if beta.strip() else None,
        exit_multiple=float(exit_m) if exit_m.strip() else None,
    )
    with st.spinner(f"Valuing {ticker}…"):
        try:
            res = value_company(ticker, provider, fmp_key or None, cfg)
        except Exception as e:
            st.error(f"Could not value {ticker}: {e}")
            st.stop()

    d = res["data"]
    cur = d.currency_symbol
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Fair value", f"{cur}{res['target']:.2f}")
    c2.metric("Current price", f"{cur}{d.price:.2f}")
    c3.metric("Upside", f"{res['upside']:+.1%}")
    c4.metric("WACC", f"{res['wacc'].wacc:.2%}")

    components.html(res["html"], height=1600, scrolling=True)
    st.download_button("Download HTML report", res["html"],
                       file_name=f"{ticker}_valuation.html", mime="text/html")
else:
    st.info("Enter a ticker and press **Run valuation**. "
            "Set an FMP API key for the best fundamentals (free tier at financialmodelingprep.com).")
