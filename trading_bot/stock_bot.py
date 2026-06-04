import yfinance as yf
import pandas as pd
import ta
import time
import sys
from datetime import datetime

NIFTY50 = [
    ("RELIANCE", "Reliance Industries"), ("TCS", "Tata Consultancy"),
    ("HDFCBANK", "HDFC Bank"), ("INFY", "Infosys"),
    ("ICICIBANK", "ICICI Bank"), ("HINDUNILVR", "Hindustan Unilever"),
    ("ITC", "ITC"), ("SBIN", "SBI"),
    ("BHARTIARTL", "Bharti Airtel"), ("KOTAKBANK", "Kotak Mahindra Bank"),
    ("BAJFINANCE", "Bajaj Finance"), ("MARUTI", "Maruti Suzuki"),
    ("ASIANPAINT", "Asian Paints"), ("AXISBANK", "Axis Bank"),
    ("TITAN", "Titan"), ("NTPC", "NTPC"),
    ("ONGC", "ONGC"), ("POWERGRID", "Power Grid"),
    ("M&M", "Mahindra & Mahindra"), ("WIPRO", "Wipro"),
    ("HCLTECH", "HCL Technologies"), ("SUNPHARMA", "Sun Pharma"),
    ("ULTRACEMCO", "UltraTech Cement"), ("BAJAJFINSV", "Bajaj Finserv"),
    ("TECHM", "Tech Mahindra"), ("ADANIPORTS", "Adani Ports"),
    ("NESTLEIND", "Nestle India"), ("COALINDIA", "Coal India"),
    ("JSWSTEEL", "JSW Steel"), ("HINDALCO", "Hindalco"),
    ("GRASIM", "Grasim"), ("DRREDDY", "Dr. Reddy's"),
    ("BRITANNIA", "Britannia"), ("CIPLA", "Cipla"),
    ("DIVISLAB", "Divi's Laboratories"), ("APOLLOHOSP", "Apollo Hospitals"),
    ("HEROMOTOCO", "Hero MotoCorp"), ("BAJAJ-AUTO", "Bajaj Auto"),
    ("EICHERMOT", "Eicher Motors"), ("INDUSINDBK", "IndusInd Bank"),
    ("SBILIFE", "SBI Life"), ("HDFCLIFE", "HDFC Life"),
    ("TATACONSUM", "Tata Consumer"), ("TATASTEEL", "Tata Steel"),
    ("BPCL", "BPCL"), ("ADANIENT", "Adani Enterprises"),
    ("TRENT", "Trent"), ("LT", "Larsen & Toubro"),
    ("BEL", "Bharat Electronics"), ("HAL", "Hindustan Aeronautics"),
]

WATCHLIST = [t[0] + ".NS" for t in NIFTY50]
TICKER_NAMES = {t[0] + ".NS": t[1] for t in NIFTY50}
TICKER_NAMES.update({t[0]: t[1] for t in NIFTY50})

USD_TICKERS = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA", "BRK-B",
    "JPM", "V", "JNJ", "WMT", "MA", "PG", "UNH", "HD", "DIS", "BAC",
    "ADBE", "CRM", "NFLX", "CMCSA", "XOM", "CVX", "PEP", "KO", "ABT",
    "PFE", "TMO", "AVGO", "AMD", "COST", "QCOM", "INTC", "IBM", "CSCO",
    "ORCL", "ACN", "LIN", "NKE", "TXN", "HON", "UPS", "BA", "GE",
    "LMT", "MMM", "CAT", "DE", "GS", "MS", "SCHW", "SPGI", "BLK",
]

def normalize_ticker(ticker):
    t = ticker.strip().upper()
    if "." not in t and t not in USD_TICKERS:
        if t in TICKER_NAMES:
            return t + ".NS"
    return t

def get_display_name(ticker):
    clean = ticker.replace(".NS", "").replace(".BO", "")
    return TICKER_NAMES.get(ticker, TICKER_NAMES.get(clean, clean))

def get_currency(ticker):
    return "₹" if ".NS" in ticker or ".BO" in ticker else "$"

def fetch_data(ticker, period="6mo"):
    try:
        stock = yf.Ticker(ticker)
        df = stock.history(period=period)
        if df.empty or len(df) < 50:
            return None
        return df
    except Exception:
        return None

def calculate_indicators(df):
    df = df.copy()
    close = df["Close"]

    df["RSI"] = ta.momentum.RSIIndicator(close, window=14).rsi()
    df["SMA_20"] = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    df["SMA_50"] = ta.trend.SMAIndicator(close, window=50).sma_indicator()
    df["SMA_200"] = ta.trend.SMAIndicator(close, window=200).sma_indicator()

    macd = ta.trend.MACD(close)
    df["MACD"] = macd.macd()
    df["MACD_Signal"] = macd.macd_signal()
    df["MACD_Histogram"] = macd.macd_diff()

    df["BB_High"] = ta.volatility.BollingerBands(close, window=20).bollinger_hband()
    df["BB_Low"] = ta.volatility.BollingerBands(close, window=20).bollinger_lband()

    df["Volume_SMA"] = df["Volume"].rolling(window=20).mean()
    df["Volume_Ratio"] = df["Volume"] / df["Volume_SMA"]

    return df

def analyze_stock(ticker, verbose=False):
    raw_ticker = ticker
    ticker = normalize_ticker(ticker)

    if verbose:
        display = get_display_name(ticker)
        print(f"Analyzing {display} ({ticker})...", end=" ")

    raw = fetch_data(ticker)
    if raw is None:
        if verbose:
            print("NO_DATA")
        return None

    df = calculate_indicators(raw)
    if df is None or len(df) < 50:
        if verbose:
            print("INSUFFICIENT_DATA")
        return None

    latest = df.iloc[-1]
    prev = df.iloc[-2]

    price = latest["Close"]
    score = 0
    reasons = []

    current_rsi = latest["RSI"]
    if pd.notna(current_rsi):
        if current_rsi < 30:
            score += 2
            reasons.append(f"RSI={current_rsi:.1f} (oversold)")
        elif current_rsi > 70:
            score -= 2
            reasons.append(f"RSI={current_rsi:.1f} (overbought)")
        elif current_rsi < 40:
            score += 1
            reasons.append(f"RSI={current_rsi:.1f} (approaching oversold)")
        elif current_rsi > 60:
            score -= 1
            reasons.append(f"RSI={current_rsi:.1f} (approaching overbought)")
        else:
            reasons.append(f"RSI={current_rsi:.1f} (neutral)")

    if pd.notna(latest.get("MACD")) and pd.notna(latest.get("MACD_Signal")):
        macd_now = latest["MACD"]
        macd_prev = prev["MACD"]
        signal_now = latest["MACD_Signal"]
        signal_prev = prev["MACD_Signal"]

        if macd_prev <= signal_prev and macd_now > signal_now:
            score += 2
            reasons.append("MACD bullish cross")
        elif macd_prev >= signal_prev and macd_now < signal_now:
            score -= 2
            reasons.append("MACD bearish cross")

    if pd.notna(latest.get("SMA_50")) and pd.notna(latest.get("SMA_200")):
        sma50 = latest["SMA_50"]
        sma200 = latest["SMA_200"]
        if sma50 > sma200:
            score += 1
            reasons.append("Golden cross (SMA50 > SMA200)")
        else:
            score -= 1
            reasons.append("Death cross (SMA50 < SMA200)")

    if pd.notna(latest.get("SMA_20")):
        sma20 = latest["SMA_20"]
        if price > sma20:
            score += 1
            reasons.append("Price > SMA20")
        else:
            score -= 1
            reasons.append("Price < SMA20")

    vol_ratio = latest.get("Volume_Ratio", 1)
    if pd.notna(vol_ratio):
        if vol_ratio > 1.5:
            score += 1
            reasons.append(f"High volume ({vol_ratio:.1f}x avg)")
        elif vol_ratio < 0.5:
            score -= 1
            reasons.append(f"Low volume ({vol_ratio:.1f}x avg)")

    if pd.notna(latest.get("BB_Low")) and pd.notna(latest.get("BB_High")):
        bb_low = latest["BB_Low"]
        bb_high = latest["BB_High"]
        if price <= bb_low:
            score += 1
            reasons.append("Price near lower Bollinger Band")
        elif price >= bb_high:
            score -= 1
            reasons.append("Price near upper Bollinger Band")

    if score >= 3:
        signal = "STRONG BUY"
    elif score >= 1:
        signal = "BUY"
    elif score <= -3:
        signal = "STRONG SELL"
    elif score <= -1:
        signal = "SELL"
    else:
        signal = "HOLD"

    if verbose:
        print(f"{signal} (score={score})")

    clean_ticker = raw_ticker if "." not in raw_ticker else raw_ticker.split(".")[0]

    return {
        "ticker": clean_ticker,
        "display_name": get_display_name(ticker),
        "price": round(price, 2),
        "currency": get_currency(ticker),
        "score": score,
        "signal": signal,
        "rsi": round(current_rsi, 1) if pd.notna(current_rsi) else None,
        "volume_ratio": round(vol_ratio, 2) if pd.notna(vol_ratio) else None,
        "reasons": "; ".join(reasons),
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

def screen_stocks(tickers=None, max_stocks=20, verbose=False, progress_callback=None):
    if tickers is None:
        tickers = WATCHLIST

    total = min(len(tickers), max_stocks)
    results = []

    for i, ticker in enumerate(tickers[:max_stocks]):
        result = analyze_stock(ticker, verbose=verbose)
        if result:
            results.append(result)
        if progress_callback:
            progress_callback(i + 1, total, len(results))
        time.sleep(0.2)

    results.sort(key=lambda x: x["score"], reverse=True)

    return results

def get_top_picks(results, top_n=5):
    buys = [r for r in results if "BUY" in r["signal"]]
    sells = [r for r in results if "SELL" in r["signal"]]
    holds = [r for r in results if r["signal"] == "HOLD"]

    return {
        "top_buys": buys[:top_n],
        "top_sells": sells[:top_n],
        "hold": holds[:top_n],
        "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
    }

if __name__ == "__main__":
    verbose = "-v" in sys.argv or "--verbose" in sys.argv
    market = "in"
    ticker_arg = None

    for i, a in enumerate(sys.argv):
        if a == "--ticker" and i + 1 < len(sys.argv):
            ticker_arg = sys.argv[i + 1]
        if a == "--market" and i + 1 < len(sys.argv):
            market = sys.argv[i + 1].lower()

    if market == "in":
        default_watchlist = WATCHLIST
        mkt_label = "NSE India (Nifty 50)"
    else:
        default_watchlist = USD_TICKERS
        mkt_label = "US Market"

    if ticker_arg:
        tickers = [t.strip().upper() for t in ticker_arg.split(",")]
    else:
        tickers = default_watchlist[:30]

    print(f"\n=== Stock Bot — Scanning {mkt_label} ({len(tickers)} stocks) ===\n")
    results = screen_stocks(tickers, verbose=verbose)

    picks = get_top_picks(results, top_n=5)

    print("\n====== TOP BUY RECOMMENDATIONS ======")
    print(f"{'Ticker':<10} {'Name':<22} {'Price':<12} {'Score':<8} {'Signal':<15} {'RSI':<8} {'Reasons'}")
    print("-" * 110)
    for r in picks["top_buys"]:
        name = r.get("display_name", "")
        price_str = f"{r['currency']}{r['price']}"
        print(f"{r['ticker']:<10} {name:<22} {price_str:<12} {r['score']:<8} {r['signal']:<15} {r['rsi']:<8} {r['reasons'][:50]}")

    if not picks["top_buys"]:
        print("(none)")

    print("\n====== TOP SELL RECOMMENDATIONS ======")
    print(f"{'Ticker':<10} {'Name':<22} {'Price':<12} {'Score':<8} {'Signal':<15} {'RSI':<8} {'Reasons'}")
    print("-" * 110)
    for r in picks["top_sells"]:
        name = r.get("display_name", "")
        price_str = f"{r['currency']}{r['price']}"
        print(f"{r['ticker']:<10} {name:<22} {price_str:<12} {r['score']:<8} {r['signal']:<15} {r['rsi']:<8} {r['reasons'][:50]}")

    if not picks["top_sells"]:
        print("(none)")

    print(f"\nGenerated at: {picks['timestamp']}")
    print("Disclaimer: For educational purposes only. Do your own research.")
