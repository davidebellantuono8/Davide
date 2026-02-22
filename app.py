from flask import Flask, render_template, request, jsonify
import yfinance as yf
import pandas as pd
import numpy as np
import plotly.graph_objects as go
import plotly.utils
import json
from datetime import datetime, timedelta

app = Flask(__name__)


def fetch_stock_data(ticker: str, period: str = "1y") -> dict:
    """Fetch stock data and compute key metrics."""
    stock = yf.Ticker(ticker)
    hist = stock.history(period=period)

    if hist.empty:
        return None

    info = stock.info or {}

    # Price data
    current_price = float(hist["Close"].iloc[-1])
    prev_price = float(hist["Close"].iloc[-2]) if len(hist) > 1 else current_price
    price_change = current_price - prev_price
    price_change_pct = (price_change / prev_price) * 100 if prev_price else 0

    # Returns
    hist["Daily_Return"] = hist["Close"].pct_change()
    returns = hist["Daily_Return"].dropna()

    # Risk metrics
    volatility = float(returns.std() * np.sqrt(252) * 100)  # annualised %
    sharpe = float((returns.mean() * 252) / (returns.std() * np.sqrt(252))) if returns.std() > 0 else 0

    # Moving averages
    hist["MA50"] = hist["Close"].rolling(50).mean()
    hist["MA200"] = hist["Close"].rolling(200).mean()

    # RSI (14-period)
    delta = hist["Close"].diff()
    gain = delta.clip(lower=0).rolling(14).mean()
    loss = (-delta.clip(upper=0)).rolling(14).mean()
    rs = gain / loss
    rsi = float((100 - (100 / (1 + rs))).iloc[-1])

    # Bollinger Bands (20-period)
    hist["BB_Mid"] = hist["Close"].rolling(20).mean()
    hist["BB_Std"] = hist["Close"].rolling(20).std()
    hist["BB_Upper"] = hist["BB_Mid"] + 2 * hist["BB_Std"]
    hist["BB_Lower"] = hist["BB_Mid"] - 2 * hist["BB_Std"]

    # 52-week high/low
    w52_high = float(hist["High"].max())
    w52_low = float(hist["Low"].min())

    # Build candlestick + MA chart
    fig = go.Figure()
    fig.add_trace(go.Candlestick(
        x=hist.index,
        open=hist["Open"],
        high=hist["High"],
        low=hist["Low"],
        close=hist["Close"],
        name="Price",
        increasing_line_color="#26a69a",
        decreasing_line_color="#ef5350",
    ))
    fig.add_trace(go.Scatter(x=hist.index, y=hist["MA50"], name="MA 50",
                             line=dict(color="#f59e0b", width=1.5), opacity=0.9))
    fig.add_trace(go.Scatter(x=hist.index, y=hist["MA200"], name="MA 200",
                             line=dict(color="#6366f1", width=1.5), opacity=0.9))
    # Bollinger Bands
    fig.add_trace(go.Scatter(x=hist.index, y=hist["BB_Upper"], name="BB Upper",
                             line=dict(color="#94a3b8", width=1, dash="dot"), opacity=0.7))
    fig.add_trace(go.Scatter(x=hist.index, y=hist["BB_Lower"], name="BB Lower",
                             line=dict(color="#94a3b8", width=1, dash="dot"), opacity=0.7,
                             fill="tonexty", fillcolor="rgba(148,163,184,0.08)"))

    fig.update_layout(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#cbd5e1"),
        xaxis=dict(gridcolor="#1e293b", rangeslider=dict(visible=False)),
        yaxis=dict(gridcolor="#1e293b"),
        legend=dict(bgcolor="#1e293b", bordercolor="#334155"),
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
    )

    # Volume chart
    vol_colors = ["#26a69a" if c >= o else "#ef5350"
                  for c, o in zip(hist["Close"], hist["Open"])]
    vol_fig = go.Figure()
    vol_fig.add_trace(go.Bar(x=hist.index, y=hist["Volume"],
                             marker_color=vol_colors, name="Volume"))
    vol_fig.update_layout(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#cbd5e1"),
        xaxis=dict(gridcolor="#1e293b"),
        yaxis=dict(gridcolor="#1e293b"),
        margin=dict(l=10, r=10, t=10, b=10),
        showlegend=False,
    )

    return {
        "ticker": ticker.upper(),
        "name": info.get("longName", ticker.upper()),
        "sector": info.get("sector", "N/A"),
        "industry": info.get("industry", "N/A"),
        "current_price": round(current_price, 2),
        "price_change": round(price_change, 2),
        "price_change_pct": round(price_change_pct, 2),
        "market_cap": info.get("marketCap"),
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "pb_ratio": info.get("priceToBook"),
        "dividend_yield": round((info.get("dividendYield") or 0) * 100, 2),
        "eps": info.get("trailingEps"),
        "beta": info.get("beta"),
        "w52_high": round(w52_high, 2),
        "w52_low": round(w52_low, 2),
        "volatility": round(volatility, 2),
        "sharpe_ratio": round(sharpe, 3),
        "rsi": round(rsi, 1),
        "volume": int(hist["Volume"].iloc[-1]),
        "avg_volume": int(hist["Volume"].mean()),
        "chart_json": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder),
        "vol_chart_json": json.dumps(vol_fig, cls=plotly.utils.PlotlyJSONEncoder),
    }


def compare_stocks(tickers: list, period: str = "1y") -> dict:
    """Fetch normalised price performance for multiple tickers."""
    traces = []
    for ticker in tickers:
        try:
            hist = yf.Ticker(ticker).history(period=period)
            if hist.empty:
                continue
            norm = (hist["Close"] / hist["Close"].iloc[0] - 1) * 100
            traces.append(go.Scatter(x=hist.index, y=norm, name=ticker.upper(), mode="lines"))
        except Exception:
            continue

    fig = go.Figure(data=traces)
    fig.update_layout(
        paper_bgcolor="#0f172a",
        plot_bgcolor="#0f172a",
        font=dict(color="#cbd5e1"),
        xaxis=dict(gridcolor="#1e293b"),
        yaxis=dict(gridcolor="#1e293b", ticksuffix="%"),
        legend=dict(bgcolor="#1e293b", bordercolor="#334155"),
        margin=dict(l=10, r=10, t=30, b=10),
        hovermode="x unified",
        title=dict(text="Normalised Performance (%)", font=dict(size=14)),
    )
    return {"chart_json": json.dumps(fig, cls=plotly.utils.PlotlyJSONEncoder)}


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/analyze", methods=["POST"])
def analyze():
    data = request.get_json()
    ticker = (data.get("ticker") or "").strip().upper()
    period = data.get("period", "1y")

    if not ticker:
        return jsonify({"error": "No ticker provided"}), 400

    try:
        result = fetch_stock_data(ticker, period)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    if result is None:
        return jsonify({"error": f"No data found for '{ticker}'. Check the symbol and try again."}), 404

    return jsonify(result)


@app.route("/compare", methods=["POST"])
def compare():
    data = request.get_json()
    raw = data.get("tickers", "")
    tickers = [t.strip().upper() for t in raw.split(",") if t.strip()]
    period = data.get("period", "1y")

    if not tickers:
        return jsonify({"error": "No tickers provided"}), 400

    try:
        result = compare_stocks(tickers, period)
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    return jsonify(result)


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
