import yfinance as yf
import pandas as pd
import ta
import numpy as np
import time
from datetime import datetime
from concurrent.futures import ThreadPoolExecutor, as_completed
from nsetools import Nse

_NIFTY_DF_CACHE = None
_REGIME_CACHE = None

def _get_nifty_df():
    global _NIFTY_DF_CACHE
    if _NIFTY_DF_CACHE is not None and len(_NIFTY_DF_CACHE) > 20:
        return _NIFTY_DF_CACHE
    try:
        df = yf.download("^NSEI", period="1y", progress=False, auto_adjust=True)
        if df.empty:
            return None
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.get_level_values(0)
        df = df[["Open", "High", "Low", "Close", "Volume"]]
        _NIFTY_DF_CACHE = df
        return df
    except Exception:
        return None

def get_market_regime():
    global _REGIME_CACHE
    if _REGIME_CACHE is not None and time.time() - _REGIME_CACHE["ts"] < 300:
        return _REGIME_CACHE["regime"]
    df = _get_nifty_df()
    if df is None:
        return "unknown"
    close = df["Close"]
    sma200 = close.rolling(200).mean().iloc[-1]
    current = close.iloc[-1]
    sma50 = close.rolling(50).mean().iloc[-1]
    current_above_200 = current > sma200
    current_above_50 = current > sma50
    macd = ta.trend.MACD(close)
    hist = macd.macd_diff()
    hist_rising = len(hist) >= 3 and hist.iloc[-1] > hist.iloc[-2] > hist.iloc[-3]
    pct_from_high = (close.max() - current) / close.max() * 100
    if current_above_200 and current_above_50 and hist_rising:
        regime = "risk_on"
    elif current_above_200:
        regime = "neutral"
    elif not current_above_200 and pct_from_high > 10:
        regime = "risk_off"
    else:
        regime = "cautious"
    _REGIME_CACHE = {"regime": regime, "ts": time.time()}
    return regime

MIN_PRICE = 15
MIN_VOLUME = 100000
MIN_DATA_POINTS = 200
MIN_MARKET_CAP = 500_000_000
CONCURRENT_WORKERS = 50

def get_all_nse_symbols():
    nse = Nse()
    symbols = nse.get_stock_codes()
    return [s for s in symbols if s and isinstance(s, str) and not s.startswith("SYMBOL")]

def _get_market_cap(symbol):
    """Try to get market cap from fundamentals cache (built by Papa scanner)."""
    try:
        import json, os
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fundamentals_cache.json")
        if os.path.exists(path):
            data = json.load(open(path))
            entry = data.get("data", {}).get(symbol, {})
            return entry.get("marketCap") or 0
    except Exception:
        pass
    return 0

GRADE_LABELS = {
    "A+": 25, "A": 22, "A-": 20,
    "B+": 18, "B": 15, "B-": 13,
    "C+": 10, "C": 8, "C-": 6,
    "D": 3, "E": 0,
}

def assign_grade(score):
    if score >= 25: return "A+"
    elif score >= 22: return "A"
    elif score >= 20: return "A-"
    elif score >= 18: return "B+"
    elif score >= 15: return "B"
    elif score >= 13: return "B-"
    elif score >= 10: return "C+"
    elif score >= 8: return "C"
    elif score >= 6: return "C-"
    elif score >= 3: return "D"
    else: return "E"

def _yahoo_direct_history(ticker, period="1y"):
    import urllib.request, json
    interval = "1d"
    period_map = {"1mo": "1mo", "3mo": "3mo", "6mo": "6mo", "1y": "1y", "2y": "2y"}
    r = period_map.get(period, "1y")
    url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}?range={r}&interval={interval}"
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    resp = urllib.request.urlopen(req, timeout=15)
    data = json.loads(resp.read())
    result = data["chart"]["result"][0]
    timestamps = result["timestamp"]
    quotes = result["indicators"]["quote"][0]
    adjclose_raw = result["indicators"].get("adjclose", [{}])[0].get("adjclose", quotes["close"])
    def flat(a):
        import numpy as np
        return np.array(a).ravel() if a else a
    df = pd.DataFrame({
        "Open": flat(quotes["open"]), "High": flat(quotes["high"]),
        "Low": flat(quotes["low"]), "Close": flat(adjclose_raw),
        "Volume": flat(quotes["volume"])
    }, index=pd.to_datetime(timestamps, unit="s"))
    return df

def fetch_and_grade(symbol):
    ticker = symbol + ".NS"
    df = None
    stock = yf.Ticker(ticker)
    for hist_attempt in range(3):
        try:
            df = stock.history(period="1y")
            if df is not None and not df.empty and len(df) >= MIN_DATA_POINTS:
                break
        except Exception:
            pass
        if df is None or df.empty or len(df) < MIN_DATA_POINTS:
            try:
                df = _yahoo_direct_history(ticker, "1y")
                if df is not None and not df.empty and len(df) >= MIN_DATA_POINTS:
                    break
            except Exception:
                pass
        if hist_attempt < 2:
            time.sleep(2 * (hist_attempt + 1))
    if df is None or df.empty or len(df) < MIN_DATA_POINTS:
        return None

    close = df["Close"]
    high = df["High"]
    low = df["Low"]
    volume = df["Volume"]
    current_price = close.iloc[-1]
    avg_volume = volume.mean()

    if current_price < MIN_PRICE or avg_volume < MIN_VOLUME:
        return None

    mcap = _get_market_cap(symbol)
    if mcap > 0 and mcap < MIN_MARKET_CAP:
        return None

    rsi_indicator = ta.momentum.RSIIndicator(close, window=14)
    rsi_values = rsi_indicator.rsi()
    current_rsi = rsi_values.iloc[-1]

    sma20 = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    sma50 = ta.trend.SMAIndicator(close, window=50).sma_indicator()
    sma200 = ta.trend.SMAIndicator(close, window=200).sma_indicator()
    sma20_val = sma20.iloc[-1]
    sma50_val = sma50.iloc[-1]
    sma200_val = sma200.iloc[-1]

    macd = ta.trend.MACD(close)
    macd_line = macd.macd()
    macd_signal = macd.macd_signal()
    macd_hist = macd.macd_diff()
    macd_curr = macd_line.iloc[-1]
    macd_sig_curr = macd_signal.iloc[-1]
    macd_prev = macd_line.iloc[-2]
    macd_sig_prev = macd_signal.iloc[-2]

    bb = ta.volatility.BollingerBands(close, window=20)
    bb_low = bb.bollinger_lband().iloc[-1]
    bb_high = bb.bollinger_hband().iloc[-1]
    bb_mid = bb.bollinger_mavg().iloc[-1]
    bb_width = bb_high - bb_low

    vol_sma_20 = volume.rolling(window=20).mean()
    vol_ratio = volume.iloc[-1] / vol_sma_20.iloc[-1] if vol_sma_20.iloc[-1] > 0 else 1

    atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    atr_val = atr.iloc[-1] if pd.notna(atr.iloc[-1]) else 0
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0

    returns_5d = (close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100 if len(close) > 6 else 0
    returns_21d = (close.iloc[-1] - close.iloc[-22]) / close.iloc[-22] * 100 if len(close) > 22 else 0

    lows_14 = low.rolling(window=14).min()
    highs_14 = high.rolling(window=14).max()
    recent_low_14 = lows_14.iloc[-1]
    recent_high_14 = highs_14.iloc[-1]

    volume_ma_50 = volume.rolling(window=50).mean()
    vol_trend = vol_sma_20.iloc[-1] / volume_ma_50.iloc[-1] if volume_ma_50.iloc[-1] > 0 else 1

    consecutive_down = 0
    for i in range(min(10, len(close) - 1)):
        if close.iloc[-(i+2)] > close.iloc[-(i+1)]:
            consecutive_down += 1
        else:
            break

    grades = {}
    details = {}
    total = 0

    rs = 0
    if pd.notna(current_rsi):
        rs_val = current_rsi
        if rs_val < 25:
            rs = 5
            details["RSI"] = f"RSI={rs_val:.0f} deeply oversold"
        elif rs_val < 30:
            rs = 5
            details["RSI"] = f"RSI={rs_val:.0f} very oversold"
        elif rs_val < 35:
            rs = 4
            details["RSI"] = f"RSI={rs_val:.0f} oversold"
        elif rs_val < 40:
            rs = 3
            details["RSI"] = f"RSI={rs_val:.0f} approaching oversold"
        elif rs_val < 45:
            rs = 2
            details["RSI"] = f"RSI={rs_val:.0f} near oversold"
        elif rs_val < 50:
            rs = 1
            details["RSI"] = f"RSI={rs_val:.0f} below neutral"
        elif rs_val > 75:
            rs = -2
            details["RSI"] = f"RSI={rs_val:.0f} overbought (avoid)"
        elif rs_val > 65:
            rs = -1
            details["RSI"] = f"RSI={rs_val:.0f} nearing overbought"

        rsi_trend_ok = False
        rsi_vals = rsi_values.tail(5).values
        if len(rsi_vals) == 5 and all(pd.notna(v) for v in rsi_vals):
            if rsi_vals[-1] > rsi_vals[-2] > rsi_vals[-3]:
                rs += 2
                rsi_trend_ok = True
                details["RSI"] += ", rising"

        rsi_divergence = False
        recent_low = close.tail(5).min()
        earlier_low = close.tail(10).head(5).min()
        rsi_recent = rsi_values.tail(5).min()
        rsi_earlier = rsi_values.tail(10).head(5).min()
        if pd.notna(recent_low) and pd.notna(earlier_low) and pd.notna(rsi_recent) and pd.notna(rsi_earlier):
            if recent_low < earlier_low and rsi_recent > rsi_earlier:
                rs += 2
                rsi_divergence = True
                details["RSI"] += " + bullish divergence"

        grades["RSI"] = min(rs, 8)
    else:
        grades["RSI"] = 0
    total += grades["RSI"]

    ms = 0
    if pd.notna(macd_curr) and pd.notna(macd_sig_curr):
        if macd_prev <= macd_sig_prev and macd_curr > macd_sig_curr:
            ms += 4
            details["MACD"] = "MACD bullish cross"
        elif macd_curr > macd_sig_curr:
            ms += 2
            details["MACD"] = "MACD bullish"

        if not pd.isna(macd_hist.iloc[-2]) and not pd.isna(macd_hist.iloc[-1]):
            hist_prev = macd_hist.iloc[-2]
            hist_curr = macd_hist.iloc[-1]

            hist_vals = macd_hist.tail(5).values
            hist_rising = len(hist_vals) >= 3 and all(pd.notna(v) for v in hist_vals[-3:]) and hist_vals[-1] > hist_vals[-2] > hist_vals[-3]

            if hist_rising:
                ms += 3
                details["MACD"] = (details.get("MACD", "") + ", histogram rising 3 bars").strip(", ")
            elif hist_prev < 0 and hist_curr > hist_prev:
                ms += 1
                details["MACD"] = (details.get("MACD", "") + ", histogram narrowing from negative").strip(", ")

        grades["MACD"] = min(ms, 6)
    else:
        grades["MACD"] = 0
    total += grades["MACD"]

    bs = 0
    if pd.notna(current_price) and pd.notna(bb_low) and bb_width > 0:
        bb_pos = (current_price - bb_low) / bb_width
        if bb_pos < 0.05:
            bs = 4
            details["BB"] = "At lower Bollinger Band (bounce zone)"
        elif bb_pos < 0.15:
            bs = 3
            details["BB"] = "Near lower Bollinger Band"
        elif bb_pos < 0.30:
            bs = 2
            details["BB"] = "Below mid Bollinger Band"
        elif bb_pos < 0.45:
            bs = 1
            details["BB"] = "Slightly below mid Bollinger Band"

        bb_pct = (current_price - bb_mid) / bb_mid * 100
        if bb_pct < -10:
            bs += 2
            details["BB"] = (details.get("BB", "").strip(", ") + ", 10%+ below mid!").strip(", ")
        elif bb_pct < -5:
            bs += 1
            details["BB"] = (details.get("BB", "").strip(", ") + ", 5%+ below mid").strip(", ")

        grades["BB"] = min(bs, 5)
    else:
        grades["BB"] = 0
    total += grades["BB"]

    ts = 0
    if pd.notna(sma50_val) and pd.notna(sma200_val):
        if sma50_val > sma200_val:
            ts += 2
            details["Trend"] = "Golden cross (uptrend)"
        else:
            ts -= 1
            details["Trend"] = "Death cross (downtrend)"

        if pd.notna(current_price):
            if current_price > sma50_val:
                ts += 2
                details["Trend"] = details.get("Trend", "") + ", price > SMA50 (uptrend)"
            elif current_price < sma50_val:
                upside_to_sma50 = ((sma50_val - current_price) / current_price) * 100
                details["Trend"] = details.get("Trend", "") + f", price {upside_to_sma50:.0f}% below SMA50"

            if current_price > sma200_val:
                ts += 1
                details["Trend"] = details.get("Trend", "") + ", above SMA200"
            else:
                upside_to_sma200 = ((sma200_val - current_price) / current_price) * 100
                if upside_to_sma200 < 15:
                    ts += 1
                    details["Trend"] = details.get("Trend", "") + f", {upside_to_sma200:.0f}% to SMA200"

        grades["Trend"] = min(ts, 6)
    else:
        grades["Trend"] = 0
    total += grades["Trend"]

    vs = 0
    if pd.notna(vol_ratio):
        if vol_ratio > 2.0:
            vs = 3
            details["Volume"] = f"{vol_ratio:.1f}x avg volume (surge)"
        elif vol_ratio > 1.5:
            vs = 2
            details["Volume"] = f"{vol_ratio:.1f}x avg volume"
        elif vol_ratio > 1.2:
            vs = 1
            details["Volume"] = f"{vol_ratio:.1f}x avg volume"

        if pd.notna(vol_trend):
            if vol_trend > 1.2:
                vs += 1
                details["Volume"] = (details.get("Volume", "") + ", volume uptrend").strip(", ")
            elif vol_trend < 0.7:
                vs -= 1
                details["Volume"] = (details.get("Volume", "") + ", volume declining").strip(", ")

        grades["Volume"] = min(vs, 4)
    else:
        grades["Volume"] = 0
    total += grades["Volume"]

    mom = 0
    if pd.notna(returns_5d):
        if returns_5d > 8:
            mom += 2
            details["Momentum"] = "strong 5d rally"
        elif returns_5d > 5:
            mom += 1
            details["Momentum"] = "moderate 5d rally"

        if pd.notna(returns_21d) and returns_21d > 10:
            mom += 1
            details["Momentum"] = (details.get("Momentum", "") + ", strong 1m trend").strip(", ")

        if returns_5d < -8 and pd.notna(current_rsi) and current_rsi < 35:
            vol_rising = pd.notna(vol_ratio) and vol_ratio > 1.3
            price_up_today = close.iloc[-1] > close.iloc[-2]
            if vol_rising and price_up_today:
                mom += 2
                details["Momentum"] = "sharp drop + RSI low + volume surge (bounce setup)"
            elif vol_rising:
                mom += 1
                details["Momentum"] = "sharp drop + volume surge"

        grades["Momentum"] = min(mom, 4)
    else:
        grades["Momentum"] = 0
    total += grades["Momentum"]

    vs2 = 0
    if pd.notna(atr_pct):
        if atr_pct < 1.5:
            vs2 = 3
            details["Volatility"] = f"ATR {atr_pct:.1f}% (low volatility — stable)"
        elif atr_pct < 2.5:
            vs2 = 2
            details["Volatility"] = f"ATR {atr_pct:.1f}% (moderate volatility)"
        elif atr_pct < 4:
            vs2 = 1
            details["Volatility"] = f"ATR {atr_pct:.1f}% (above avg volatility)"

        if atr_pct < 1.5 and current_rsi < 40:
            vs2 += 1
            details["Volatility"] = "Low vol + oversold (stable bounce setup)"

        grades["Volatility"] = min(vs2, 3)
    else:
        grades["Volatility"] = 0
    total += grades["Volatility"]

    rev = 0
    green_today = close.iloc[-1] > close.iloc[-2]
    vol_surge_today = pd.notna(vol_ratio) and vol_ratio > 1.3

    if consecutive_down >= 5:
        rev = 2
        details["Reversal"] = f"{consecutive_down} consecutive down days"
        if green_today and vol_surge_today:
            rev += 2
            details["Reversal"] += " + green day with volume (reversal start)"
        elif green_today:
            rev += 1
            details["Reversal"] += " + green day"
    elif consecutive_down >= 3:
        rev = 1
        details["Reversal"] = f"{consecutive_down} consecutive down days"
        if green_today and vol_surge_today:
            rev += 2
            details["Reversal"] += " + green day with volume (reversal start)"

    if pd.notna(current_price) and pd.notna(recent_low_14) and current_price <= recent_low_14 * 1.02:
        if green_today and vol_surge_today:
            rev += 2
            details["Reversal"] += ", bounce from 14-day low with volume"
        elif green_today:
            rev += 1
            details["Reversal"] += ", bounce from 14-day low"
        else:
            details["Reversal"] += ", near 14-day low (no confirmation)"

    grades["Reversal"] = min(rev, 5)
    total += grades["Reversal"]

    grade = assign_grade(total)

    risk = "Low"
    if atr_pct > 3.5 or (pd.notna(sma50_val) and pd.notna(sma200_val) and sma50_val < sma200_val):
        risk = "High"
    elif atr_pct > 2 or total < 10:
        risk = "Medium"

    regime = get_market_regime()
    reg_penalty = {"risk_on": 0, "neutral": 1, "cautious": 2, "risk_off": 1}.get(regime, 1)

    if total >= 22 + reg_penalty:
        signal = "STRONG BUY"
    elif total >= 16 + reg_penalty:
        signal = "BUY"
    elif total >= 8 + reg_penalty:
        signal = "HOLD"
    elif total >= 0 + max(reg_penalty - 2, 0):
        signal = "NEUTRAL"
    elif total >= -3:
        signal = "CAUTION"
    else:
        signal = "AVOID"

    factor_list = []
    for cat in ["RSI", "MACD", "BB", "Trend", "Volume", "Momentum", "Volatility", "Reversal"]:
        if cat in details and grades.get(cat, 0) > 0:
            factor_list.append(f"{cat}: {details[cat]}")

    factor_list.sort(key=lambda x: grades.get(x.split(":")[0], 0), reverse=True)

    return {
        "symbol": symbol,
        "price": round(current_price, 2),
        "score": total,
        "grade": grade,
        "signal": signal,
        "risk": risk,
        "rsi": round(current_rsi, 1) if pd.notna(current_rsi) else None,
        "macd": round(macd_curr, 3) if pd.notna(macd_curr) else None,
        "volume_ratio": round(vol_ratio, 2) if pd.notna(vol_ratio) else None,
        "atr_pct": round(atr_pct, 1),
        "upside_pct": round(max(((sma50_val - current_price) / current_price) * 100, 0), 1) if pd.notna(sma50_val) and pd.notna(current_price) else 0,
        "grades": grades,
        "details": details,
        "factors": factor_list,
    }

def scan_all(progress_callback=None):
    symbols = get_all_nse_symbols()
    total_symbols = len(symbols)
    results = []
    scanned = 0
    errors = 0

    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        fut_map = {executor.submit(fetch_and_grade, sym): sym for sym in symbols}

        for future in as_completed(fut_map):
            scanned += 1
            try:
                result = future.result()
                if result:
                    results.append(result)
            except Exception:
                errors += 1

            if progress_callback:
                progress_callback(scanned, total_symbols, len(results), errors)

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

if __name__ == "__main__":
    import sys

    def print_progress(scanned, total, qualified, errors):
        pct = (scanned / total) * 100
        elapsed = time.time() - start
        rate = scanned / elapsed if elapsed > 0 else 0
        remaining = (total - scanned) / rate if rate > 0 else 0
        eta_m, eta_s = divmod(int(remaining), 60)
        print(f"\r  [{scanned}/{total}] {pct:.0f}% | Qualified: {qualified} | Errors: {errors} | {rate:.1f}/s | ETA: {eta_m}m{eta_s}s", end="", flush=True)

    print("=" * 90)
    print("  NSE SCANNER — Multi-Parameter Grading Engine")
    print("  Scanning all NSE equities with 9-factor analysis")
    print("=" * 90)
    print()

    start = time.time()
    results = scan_all(progress_callback=print_progress)
    elapsed = time.time() - start

    print(f"\n\n{'='*130}")
    print(f"SCAN COMPLETE — {elapsed:.0f}s | {len(results)} stocks qualified")
    print(f"{'='*130}\n")

    header = f"{'Rank':<5} {'Symbol':<14} {'Price':<11} {'Grade':<6} {'Score':<7} {'RSI':<6} {'Risk':<7} {'Upside':<8} {'Key Factors'}"
    print(header)
    print("─" * 130)
    for i, r in enumerate(results[:20]):
        factors = "; ".join(r["factors"][:4])
        grade_s = r["grade"]
        risk_s = r["risk"]
        upside_s = f"{r['upside_pct']}%" if r["upside_pct"] else "-"
        print(f"{i+1:<5} {r['symbol']:<14} ₹{r['price']:<8} {grade_s:<6} {r['score']:<7} {r['rsi']:<6} {risk_s:<7} {upside_s:<8} {factors[:65]}")

    print(f"\nBreakdown by grade:")
    for g in ["A+", "A", "A-", "B+", "B", "B-", "C+", "C", "C-", "D", "E"]:
        count = sum(1 for r in results if r["grade"] == g)
        if count:
            print(f"  {g}: {count} stocks")

    print(f"\nGenerated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("⚠ Disclaimer: Educational only. Not investment advice.")
