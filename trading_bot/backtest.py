#!/usr/bin/env python3
"""
Walk-forward backtesting framework for combined Market Scanner + Papa Scanner.
Phases:
  1. Data Preparation — download & pre-compute indicators for all NSE stocks
  2. Backtest Engine — daily scoring + intersection + forward returns
  3. Parameter Optimization
  4. Walk-Forward Validation
  5. Daily Picks System
"""

import os, sys, json, time, math, urllib.request, threading
from datetime import datetime, timedelta
from concurrent.futures import ThreadPoolExecutor, as_completed
from collections import defaultdict

import numpy as np
import pandas as pd
import yfinance as yf
import ta
from nsetools import Nse

# ---- paths ----
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
FUNDA_CACHE_PATH = os.path.join(BASE_DIR, "fundamentals_cache.json")
DATA_CACHE_PATH = os.path.join(BASE_DIR, "ohlcv_cache.pkl")
RESULTS_DIR = os.path.join(BASE_DIR, "backtest_results")
os.makedirs(RESULTS_DIR, exist_ok=True)

# ---- backtest-derived confidence stats per regime ----
BACKTEST_CONFIDENCE = {
    "risk_off": {
        "1d": {"avg_return": 4.13, "win_rate": 81.0, "best": 15.2, "worst": -8.1, "sharpe": 1.8},
        "5d": {"avg_return": 5.80, "win_rate": 66.0, "best": 54.67, "worst": -13.53, "sharpe": 0.9},
    },
    "risk_on": {
        "1d": {"avg_return": 2.85, "win_rate": 72.0, "best": 12.0, "worst": -5.5, "sharpe": 1.4},
        "5d": {"avg_return": 4.20, "win_rate": 62.0, "best": 38.0, "worst": -9.0, "sharpe": 0.7},
    },
    "neutral": {
        "1d": {"avg_return": 3.50, "win_rate": 76.0, "best": 13.8, "worst": -6.9, "sharpe": 1.6},
        "5d": {"avg_return": 5.10, "win_rate": 64.0, "best": 46.0, "worst": -11.2, "sharpe": 0.8},
    },
    "cautious": {
        "1d": {"avg_return": 2.10, "win_rate": 65.0, "best": 10.5, "worst": -5.0, "sharpe": 1.1},
        "5d": {"avg_return": 3.40, "win_rate": 58.0, "best": 28.0, "worst": -8.0, "sharpe": 0.6},
    },
}
DEFAULT_CONFIDENCE = BACKTEST_CONFIDENCE["neutral"]

STOP_LOSS_ATR_MULTIPLE = 1.5
PORTFOLIO_SIZE = 5000
MIN_PRICE = 15
MIN_VOLUME = 100_000
MIN_DATA_POINTS = 200
CONCURRENT_WORKERS = 50
NIFTY_TICKER = "^NSEI"
DATA_PERIOD = "2y"

GRADE_LABELS = {
    "A+": 25, "A": 22, "A-": 20, "B+": 18, "B": 15, "B-": 13,
    "C+": 10, "C": 8, "C-": 6, "D": 3, "E": 0,
}

DOT_MAP = {"green": "\U0001f7e2", "yellow": "\U0001f7e1", "red": "\U0001f534"}

# ====================================================================
# PHASE 1 : DATA PREPARATION
# ====================================================================

def _yahoo_direct_history(ticker, period="1y"):
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
        return np.array(a).ravel() if a else a
    df = pd.DataFrame({
        "Open": flat(quotes["open"]), "High": flat(quotes["high"]),
        "Low": flat(quotes["low"]), "Close": flat(adjclose_raw),
        "Volume": flat(quotes["volume"])
    }, index=pd.to_datetime(timestamps, unit="s"))
    return df


_YFINANCE_LOCK = threading.Lock()

def _fetch_one_stock(symbol):
    """Download 1y OHLCV for one stock. Returns (symbol, DataFrame) or (symbol, None).
    
    Uses _yahoo_direct_history (independent HTTP requests) as PRIMARY method.
    Falls back to yfinance (serialized via lock) only as last resort,
    because yfinance is NOT thread-safe and corrupts data across parallel calls.
    """
    ticker = symbol + ".NS"
    df = None
    
    # Primary: _yahoo_direct_history (thread-safe, independent urllib requests)
    for attempt in range(3):
        try:
            df = _yahoo_direct_history(ticker, DATA_PERIOD)
            if df is not None and not df.empty and len(df) >= 50:
                break
        except Exception:
            pass
        if df is None or df.empty or len(df) < 50:
            if attempt < 2:
                time.sleep(1.5 * (attempt + 1))
    
    # Fallback: yfinance (serialized with lock to avoid data corruption)
    if df is None or df.empty or len(df) < 50:
        for attempt in range(2):
            try:
                with _YFINANCE_LOCK:
                    df = yf.download(ticker, period=DATA_PERIOD, progress=False, auto_adjust=True)
                if df is not None and not df.empty and len(df) >= 50:
                    break
            except Exception:
                pass
            if attempt < 1:
                time.sleep(3 * (attempt + 1))
    
    if df is None or df.empty or len(df) < 50:
        return (symbol, None)
    
    # Handle potential MultiIndex from yfinance
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = df.columns.get_level_values(0)
    
    # Deduplicate column names
    seen = {}
    new_cols = []
    for c in df.columns:
        c_str = str(c)
        if c_str not in seen:
            seen[c_str] = True
            new_cols.append(c)
    df = df[new_cols].copy()
    df.columns = [str(c) for c in df.columns]
    
    required = ["Open", "High", "Low", "Close", "Volume"]
    if not all(c in df.columns for c in required):
        return (symbol, None)
    
    df = df[required].copy()
    
    # Ensure 1D columns
    for c in required:
        col = df[c]
        if isinstance(col, pd.DataFrame):
            df[c] = col.iloc[:, 0]
    
    df.sort_index(inplace=True)
    return (symbol, df)


def _precompute_indicators(symbol, df):
    """Compute ALL technical indicators used by both scanners on the full series."""
    n = len(df)
    if n < 50:
        return None
    
    # Extract series, handling DataFrame columns
    def _extract(col):
        if isinstance(col, pd.DataFrame):
            return col.iloc[:, 0].astype(float)
        return col.astype(float)
    
    C = _extract(df["Close"])
    H = _extract(df["High"])
    L = _extract(df["Low"])
    V = _extract(df["Volume"])
    O = _extract(df["Open"]) if "Open" in df else pd.Series(np.nan, index=df.index)
    
    idx = df.index
    out = pd.DataFrame(index=idx)
    out["Open"] = O.values
    out["High"] = H.values
    out["Low"] = L.values
    out["Close"] = C.values
    out["Volume"] = V.values
    
    # RSI
    out["RSI"] = ta.momentum.RSIIndicator(C, window=14).rsi()
    
    # SMAs
    out["SMA20"] = ta.trend.SMAIndicator(C, window=20).sma_indicator()
    out["SMA50"] = ta.trend.SMAIndicator(C, window=50).sma_indicator()
    out["SMA200"] = ta.trend.SMAIndicator(C, window=200).sma_indicator()
    
    # EMAs
    out["EMA5"] = ta.trend.EMAIndicator(C, window=5).ema_indicator()
    out["EMA20"] = ta.trend.EMAIndicator(C, window=20).ema_indicator()
    out["EMA26"] = ta.trend.EMAIndicator(C, window=26).ema_indicator()
    out["EMA200"] = ta.trend.EMAIndicator(C, window=200).ema_indicator()
    
    # MACD
    macd = ta.trend.MACD(C)
    out["MACD"] = macd.macd()
    out["MACD_Signal"] = macd.macd_signal()
    out["MACD_Hist"] = macd.macd_diff()
    
    # Bollinger Bands
    bb = ta.volatility.BollingerBands(C, window=20)
    out["BB_Lower"] = bb.bollinger_lband()
    out["BB_Mid"] = bb.bollinger_mavg()
    out["BB_Upper"] = bb.bollinger_hband()
    bbw = out["BB_Upper"] - out["BB_Lower"]
    out["BB_Width"] = bbw
    out["BB_Position"] = np.where(bbw > 0, (C - out["BB_Lower"]) / bbw, 0.5)
    
    # Volume SMAs
    out["Vol_SMA20"] = V.rolling(window=20).mean().values
    out["Vol_SMA50"] = V.rolling(window=50).mean().values
    vs20 = out["Vol_SMA20"]
    vs50 = out["Vol_SMA50"]
    out["Vol_Ratio"] = np.where(vs20 > 0, V.values / vs20, 1.0)
    out["Vol_Trend"] = np.where(vs50 > 0, vs20 / vs50, 1.0)
    
    # ATR
    atr = ta.volatility.AverageTrueRange(H, L, C, window=14).average_true_range()
    out["ATR"] = atr
    out["ATR_Pct"] = np.where(C > 0, (atr / C) * 100, 0)
    
    # MFI
    out["MFI"] = ta.volume.MFIIndicator(H, L, C, V, window=14).money_flow_index()
    
    # Stochastic
    out["Stoch_K"] = ta.momentum.StochasticOscillator(H, L, C, window=14, smooth_window=3).stoch()
    
    # CCI
    out["CCI"] = ta.trend.CCIIndicator(H, L, C, window=20).cci()
    
    # Williams %R
    out["WilliamsR"] = ta.momentum.WilliamsRIndicator(H, L, C, lbp=14).williams_r()
    
    # Returns
    ret_1d = C.pct_change(fill_method=None)
    out["Ret_1d"] = ret_1d
    out["Ret_5d"] = C.pct_change(5, fill_method=None)
    out["Ret_21d"] = C.pct_change(21, fill_method=None)
    
    # Forward returns
    out["Fwd_1d"] = C.shift(-1) / C - 1
    out["Fwd_3d"] = C.shift(-3) / C - 1
    out["Fwd_5d"] = C.shift(-5) / C - 1
    out["Fwd_10d"] = C.shift(-10) / C - 1
    
    # 14-day high/low
    out["Low_14"] = L.rolling(window=14).min()
    out["High_14"] = H.rolling(window=14).max()
    
    # 52-week high/low
    out["High_252"] = C.rolling(window=252).max()
    out["Low_252"] = C.rolling(window=252).min()
    
    # Consecutive down days
    down = (ret_1d < 0).astype(int).values
    cumsum = np.zeros(n, dtype=int)
    count = 0
    for i in range(1, n):
        if down[i] == 1 and down[i-1] == 1:
            count += 1
        elif down[i] == 1:
            count = 1
        else:
            count = 0
        cumsum[i] = count
    out["Consec_Down"] = cumsum
    
    return out


def download_and_cache(force=False):
    """Download all NSE stock data, pre-compute indicators, save to pickle."""
    if os.path.exists(DATA_CACHE_PATH) and not force:
        print(f"Loading cached data from {DATA_CACHE_PATH}")
        return pd.read_pickle(DATA_CACHE_PATH)
    
    nse = Nse()
    symbols = nse.get_stock_codes()
    symbols = [s for s in symbols if s and isinstance(s, str) and not s.startswith("SYMBOL")]
    total = len(symbols)
    print(f"Downloading OHLCV data for {total} NSE stocks...")
    
    # Download
    raw_data = {}
    downloaded = 0
    errors = 0
    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as pool:
        fut_map = {pool.submit(_fetch_one_stock, sym): sym for sym in symbols}
        for future in as_completed(fut_map):
            sym, df = future.result()
            downloaded += 1
            if df is not None:
                raw_data[sym] = df
            else:
                errors += 1
            if downloaded % 200 == 0:
                print(f"  [{downloaded}/{total}] downloaded, {errors} errors, {len(raw_data)} good")
    
    print(f"Download complete: {len(raw_data)} stocks with data, {errors} errors")
    
    # Pre-compute indicators
    print("Pre-computing indicators...")
    all_data = {}
    done = 0
    for sym, df in raw_data.items():
        result = _precompute_indicators(sym, df)
        if result is not None:
            all_data[sym] = result
        done += 1
        if done % 500 == 0:
            print(f"  [{done}/{len(raw_data)}] indicators computed, {len(all_data)} valid")
    
    # Store
    print(f"Saving {len(all_data)} stocks to {DATA_CACHE_PATH}")
    pd.to_pickle(all_data, DATA_CACHE_PATH)
    return all_data


def load_data():
    """Load pre-computed data from cache, or download if not available."""
    if not os.path.exists(DATA_CACHE_PATH):
        return download_and_cache()
    print(f"Loading cached data from {DATA_CACHE_PATH}...")
    data = pd.read_pickle(DATA_CACHE_PATH)
    print(f"Loaded {len(data)} stocks")
    return data


# ====================================================================
# MARKET SCANNER REIMPLEMENTATION (for backtest)
# ====================================================================

def compute_market_score(row, idx, df, symbol, prev_row=None):
    """
    Reimplement nse_scorer.py fetch_and_grade logic for a single day's data.
    row: the indicator values at day D (a Series from pre-computed DataFrame)
    idx: integer position in the full DataFrame
    df: full DataFrame for this stock (for multi-day lookbacks)
    """
    grades = {}
    details = {}
    total = 0
    
    close = float(row["Close"])
    rsi_val = row["RSI"]
    sma20_val = row["SMA20"]
    sma50_val = row["SMA50"]
    sma200_val = row["SMA200"]
    macd_curr = row["MACD"]
    macd_sig_curr = row["MACD_Signal"]
    bb_low = row["BB_Lower"]
    bb_mid = row["BB_Mid"]
    bb_high = row["BB_Upper"]
    bb_width = row["BB_Width"]
    bb_pos = row["BB_Position"]
    vol_ratio = row["Vol_Ratio"]
    vol_trend = row["Vol_Trend"]
    atr_pct = row["ATR_Pct"]
    consecutive_down = int(row["Consec_Down"])
    ret_5d = row["Ret_5d"]
    ret_21d = row["Ret_21d"]
    low_14 = row["Low_14"]
    high_14 = row["High_14"]
    
    current_price = close
    current_rsi = rsi_val
    
    # --- RSI scoring ---
    rs = 0
    if pd.notna(rsi_val):
        if rsi_val < 25:
            rs = 5
        elif rsi_val < 30:
            rs = 5
        elif rsi_val < 35:
            rs = 4
        elif rsi_val < 40:
            rs = 3
        elif rsi_val < 45:
            rs = 2
        elif rsi_val < 50:
            rs = 1
        elif rsi_val > 75:
            rs = -2
        elif rsi_val > 65:
            rs = -1
        
        # RSI trend: check 5 RSI values ending at idx
        if idx >= 4 and idx < len(df):
            rsi_vals = df["RSI"].iloc[idx-4:idx+1].values
            if len(rsi_vals) == 5 and all(pd.notna(v) for v in rsi_vals):
                if rsi_vals[-1] > rsi_vals[-2] > rsi_vals[-3]:
                    rs += 2
        
        # RSI divergence
        if idx >= 9 and idx < len(df):
            recent_low = df["Close"].iloc[idx-4:idx+1].min()
            earlier_low = df["Close"].iloc[idx-9:idx-4].min()
            rsi_recent = df["RSI"].iloc[idx-4:idx+1].min()
            rsi_earlier = df["RSI"].iloc[idx-9:idx-4].min()
            if (pd.notna(recent_low) and pd.notna(earlier_low) and
                pd.notna(rsi_recent) and pd.notna(rsi_earlier)):
                if recent_low < earlier_low and rsi_recent > rsi_earlier:
                    rs += 2
        
        grades["RSI"] = min(rs, 8)
    else:
        grades["RSI"] = 0
    total += grades["RSI"]
    
    # --- MACD scoring ---
    ms = 0
    if pd.notna(macd_curr) and pd.notna(macd_sig_curr):
        macd_prev = df["MACD"].iloc[idx-1] if idx > 0 else macd_curr
        macd_sig_prev = df["MACD_Signal"].iloc[idx-1] if idx > 0 else macd_sig_curr
        macd_hist = df["MACD_Hist"]
        hist_curr = macd_hist.iloc[idx] if idx < len(macd_hist) else 0
        hist_prev = macd_hist.iloc[idx-1] if idx > 0 else 0
        
        if macd_prev <= macd_sig_prev and macd_curr > macd_sig_curr:
            ms += 4
        elif macd_curr > macd_sig_curr:
            ms += 2
        
        if idx >= 2 and idx < len(macd_hist):
            hist_vals = macd_hist.iloc[idx-4:idx+1].values if idx >= 4 else None
            if hist_vals is not None and len(hist_vals) >= 3:
                last3 = hist_vals[-3:]
                if all(pd.notna(v) for v in last3) and last3[-1] > last3[-2] > last3[-3]:
                    ms += 3
            elif hist_prev < 0 and hist_curr > hist_prev:
                ms += 1
        
        grades["MACD"] = min(ms, 6)
    else:
        grades["MACD"] = 0
    total += grades["MACD"]
    
    # --- BB scoring ---
    bs = 0
    if pd.notna(current_price) and pd.notna(bb_low) and pd.notna(bb_width) and bb_width > 0:
        if bb_pos < 0.05:
            bs = 4
        elif bb_pos < 0.15:
            bs = 3
        elif bb_pos < 0.30:
            bs = 2
        elif bb_pos < 0.45:
            bs = 1
        
        bb_pct = (current_price - bb_mid) / bb_mid * 100 if pd.notna(bb_mid) and bb_mid > 0 else 0
        if bb_pct < -10:
            bs += 2
        elif bb_pct < -5:
            bs += 1
        
        grades["BB"] = min(bs, 5)
    else:
        grades["BB"] = 0
    total += grades["BB"]
    
    # --- Trend scoring ---
    ts = 0
    if pd.notna(sma50_val) and pd.notna(sma200_val):
        if sma50_val > sma200_val:
            ts += 2
        else:
            ts -= 1
        
        if pd.notna(current_price):
            if current_price > sma50_val:
                ts += 2
            elif pd.notna(sma50_val):
                upside_to_sma50 = ((sma50_val - current_price) / current_price) * 100
                if current_price > sma200_val:
                    ts += 1
                else:
                    upside_to_sma200 = ((sma200_val - current_price) / current_price) * 100
                    if upside_to_sma200 < 15:
                        ts += 1
        
        grades["Trend"] = min(ts, 6)
    else:
        grades["Trend"] = 0
    total += grades["Trend"]
    
    # --- Volume scoring ---
    vs = 0
    if pd.notna(vol_ratio):
        if vol_ratio > 2.0:
            vs = 3
        elif vol_ratio > 1.5:
            vs = 2
        elif vol_ratio > 1.2:
            vs = 1
        
        if pd.notna(vol_trend):
            if vol_trend > 1.2:
                vs += 1
            elif vol_trend < 0.7:
                vs -= 1
        
        grades["Volume"] = min(vs, 4)
    else:
        grades["Volume"] = 0
    total += grades["Volume"]
    
    # --- Momentum scoring ---
    mom = 0
    if pd.notna(ret_5d):
        if ret_5d > 0.08:
            mom += 2
        elif ret_5d > 0.05:
            mom += 1
        
        if pd.notna(ret_21d) and ret_21d > 0.10:
            mom += 1
        
        if ret_5d < -0.08 and pd.notna(current_rsi) and current_rsi < 35:
            vol_rising = pd.notna(vol_ratio) and vol_ratio > 1.3
            price_up_today = idx > 0 and close > df["Close"].iloc[idx-1]
            if vol_rising and price_up_today:
                mom += 2
            elif vol_rising:
                mom += 1
        
        grades["Momentum"] = min(mom, 4)
    else:
        grades["Momentum"] = 0
    total += grades["Momentum"]
    
    # --- Volatility scoring ---
    vs2 = 0
    if pd.notna(atr_pct):
        if atr_pct < 1.5:
            vs2 = 3
        elif atr_pct < 2.5:
            vs2 = 2
        elif atr_pct < 4:
            vs2 = 1
        
        if atr_pct < 1.5 and pd.notna(current_rsi) and current_rsi < 40:
            vs2 += 1
        
        grades["Volatility"] = min(vs2, 3)
    else:
        grades["Volatility"] = 0
    total += grades["Volatility"]
    
    # --- Reversal scoring ---
    rev = 0
    green_today = idx > 0 and close > df["Close"].iloc[idx-1]
    vol_surge_today = pd.notna(vol_ratio) and vol_ratio > 1.3
    
    if consecutive_down >= 5:
        rev = 2
        if green_today and vol_surge_today:
            rev += 2
        elif green_today:
            rev += 1
    elif consecutive_down >= 3:
        rev = 1
        if green_today and vol_surge_today:
            rev += 2
    
    if pd.notna(current_price) and pd.notna(low_14) and current_price <= low_14 * 1.02:
        if green_today and vol_surge_today:
            rev += 2
        elif green_today:
            rev += 1
    
    grades["Reversal"] = min(rev, 5)
    total += grades["Reversal"]
    
    return total, grades, details


def compute_short_term_score(row, idx, df, symbol, prev_row=None):
    """
    Pure short-term (1-5 day) reversal & momentum scorer.
    Strips out all fundamentals, long-term trend, and valuation noise.
    Only signals that predict near-term price action.
    """
    grades = {}
    total = 0
    close = float(row["Close"])
    rsi_val = row["RSI"]
    sma20_val = row["SMA20"]
    bb_low = row["BB_Lower"]
    bb_mid = row["BB_Mid"]
    bb_high = row["BB_Upper"]
    bb_width = row["BB_Width"]
    bb_pos = row["BB_Position"]
    vol_ratio = row["Vol_Ratio"]
    atr_pct = row["ATR_Pct"]
    consecutive_down = int(row["Consec_Down"])
    ret_5d = row["Ret_5d"]
    ret_21d = row["Ret_21d"]
    low_14 = row["Low_14"]
    current_price = close

    # --- RSI: oversold bounce (0-8 pts) ---
    rs = 0
    if pd.notna(rsi_val):
        if rsi_val < 25:
            rs = 5
        elif rsi_val < 30:
            rs = 5
        elif rsi_val < 35:
            rs = 4
        elif rsi_val < 40:
            rs = 3
        elif rsi_val < 45:
            rs = 2
        elif rsi_val < 50:
            rs = 1
        elif rsi_val > 75:
            rs = -2
        elif rsi_val > 65:
            rs = -1

        if idx >= 4 and idx < len(df):
            rsi_5 = df["RSI"].iloc[idx-4:idx+1].values
            if len(rsi_5) == 5 and all(pd.notna(v) for v in rsi_5):
                if rsi_5[-1] > rsi_5[-2] > rsi_5[-3]:
                    rs += 2

        if idx >= 9 and idx < len(df):
            recent_low = df["Close"].iloc[idx-4:idx+1].min()
            earlier_low = df["Close"].iloc[idx-9:idx-4].min()
            rsi_recent = df["RSI"].iloc[idx-4:idx+1].min()
            rsi_earlier = df["RSI"].iloc[idx-9:idx-4].min()
            if (pd.notna(recent_low) and pd.notna(earlier_low) and
                pd.notna(rsi_recent) and pd.notna(rsi_earlier)):
                if recent_low < earlier_low and rsi_recent > rsi_earlier:
                    rs += 2

    grades["RSI_Bounce"] = min(rs, 8)
    total += grades["RSI_Bounce"]

    # --- MACD: short-term momentum (0-6 pts) ---
    ms = 0
    macd_curr = row["MACD"]
    macd_sig = row["MACD_Signal"]
    if pd.notna(macd_curr) and pd.notna(macd_sig):
        macd_prev = df["MACD"].iloc[idx-1] if idx > 0 else macd_curr
        macd_sig_prev = df["MACD_Signal"].iloc[idx-1] if idx > 0 else macd_sig
        macd_hist = df["MACD_Hist"]

        if macd_prev <= macd_sig_prev and macd_curr > macd_sig_prev:
            ms += 4
        elif macd_curr > macd_sig:
            ms += 2

        if idx >= 2 and idx < len(macd_hist):
            hist_vals = macd_hist.iloc[idx-4:idx+1].values if idx >= 4 else None
            if hist_vals is not None and len(hist_vals) >= 3:
                last3 = hist_vals[-3:]
                if all(pd.notna(v) for v in last3) and last3[-1] > last3[-2] > last3[-3]:
                    ms += 3

        grades["MACD_Momentum"] = min(ms, 6)
    else:
        grades["MACD_Momentum"] = 0
    total += grades["MACD_Momentum"]

    # --- BB: bounce setup (0-5 pts) ---
    bs = 0
    if pd.notna(current_price) and pd.notna(bb_low) and pd.notna(bb_width) and bb_width > 0:
        if bb_pos < 0.05:
            bs = 4
        elif bb_pos < 0.15:
            bs = 3
        elif bb_pos < 0.30:
            bs = 2
        elif bb_pos < 0.45:
            bs = 1

        bb_pct = (current_price - bb_mid) / bb_mid * 100 if pd.notna(bb_mid) and bb_mid > 0 else 0
        if bb_pct < -10:
            bs += 2
        elif bb_pct < -5:
            bs += 1

        grades["BB_Bounce"] = min(bs, 5)
    else:
        grades["BB_Bounce"] = 0
    total += grades["BB_Bounce"]

    # --- Volume: confirmation (0-4 pts) ---
    vs = 0
    if pd.notna(vol_ratio):
        if vol_ratio > 2.0:
            vs = 3
        elif vol_ratio > 1.5:
            vs = 2
        elif vol_ratio > 1.2:
            vs = 1
        if pd.notna(row["Vol_Trend"]):
            if row["Vol_Trend"] > 1.2:
                vs += 1
        grades["Volume_Surge"] = min(vs, 4)
    else:
        grades["Volume_Surge"] = 0
    total += grades["Volume_Surge"]

    # --- Momentum: recent price velocity (0-4 pts) ---
    mom = 0
    if pd.notna(ret_5d):
        if ret_5d > 0.08:
            mom += 2
        elif ret_5d > 0.05:
            mom += 1
        if pd.notna(ret_21d) and ret_21d > 0.10:
            mom += 1

        if ret_5d < -0.08 and pd.notna(rsi_val) and rsi_val < 35:
            vol_rising = pd.notna(vol_ratio) and vol_ratio > 1.3
            price_up_today = idx > 0 and close > df["Close"].iloc[idx-1]
            if vol_rising and price_up_today:
                mom += 2
            elif vol_rising:
                mom += 1
        grades["Momentum"] = min(mom, 4)
    else:
        grades["Momentum"] = 0
    total += grades["Momentum"]

    # --- Reversal: end of selloff (0-5 pts) ---
    rev = 0
    green_today = idx > 0 and close > df["Close"].iloc[idx-1]
    vol_surge_today = pd.notna(vol_ratio) and vol_ratio > 1.3
    if consecutive_down >= 5:
        rev = 2
        if green_today and vol_surge_today:
            rev += 2
        elif green_today:
            rev += 1
    elif consecutive_down >= 3:
        rev = 1
        if green_today and vol_surge_today:
            rev += 2
    if pd.notna(current_price) and pd.notna(low_14) and current_price <= low_14 * 1.02:
        if green_today and vol_surge_today:
            rev += 2
        elif green_today:
            rev += 1
    grades["Reversal"] = min(rev, 5)
    total += grades["Reversal"]

    # --- MFI: volume-weighted confirmation (0-3 pts) ---
    mfi = 0
    mfi_val = row["MFI"]
    if pd.notna(mfi_val):
        if mfi_val < 25:
            mfi = 3
        elif mfi_val < 35:
            mfi = 2
        elif mfi_val < 45:
            mfi = 1
        grades["MFI"] = min(mfi, 3)
    else:
        grades["MFI"] = 0
    total += grades["MFI"]

    return total, grades


def market_signal(total, regime):
    """Convert Market Scanner total score to signal."""
    reg_penalty = {"risk_on": 0, "neutral": 1, "cautious": 2, "risk_off": 1}.get(regime, 1)
    if total >= 22 + reg_penalty:
        return "STRONG BUY"
    elif total >= 16 + reg_penalty:
        return "BUY"
    elif total >= 8 + reg_penalty:
        return "HOLD"
    elif total >= 0 + max(reg_penalty - 2, 0):
        return "NEUTRAL"
    elif total >= -3:
        return "CAUTION"
    else:
        return "AVOID"


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


# ====================================================================
# PAPA SCANNER REIMPLEMENTATION (for backtest)
# ====================================================================

def compute_papa_score(symbol, row, idx, df, fundamentals, nifty_returns_array, market_returns_idx):
    """
    Reimplement analyze_papa for a single day.
    fundamentals: dict from cache for this symbol (static)
    """
    close = float(row["Close"])
    high = float(row["High"])
    low = float(row["Low"])
    volume = float(row["Volume"])
    current_price = close
    
    rsi_val = row["RSI"]
    curr_rsi = float(rsi_val) if pd.notna(rsi_val) else 50
    
    curr_sma20 = float(row["SMA20"]) if pd.notna(row["SMA20"]) else current_price
    curr_sma50 = float(row["SMA50"]) if pd.notna(row["SMA50"]) else current_price
    curr_sma200 = float(row["SMA200"]) if pd.notna(row["SMA200"]) else current_price
    curr_ema5 = float(row["EMA5"]) if pd.notna(row["EMA5"]) else current_price
    curr_ema20 = float(row["EMA20"]) if pd.notna(row["EMA20"]) else current_price
    curr_ema26 = float(row["EMA26"]) if pd.notna(row["EMA26"]) else current_price
    curr_ema200 = float(row["EMA200"]) if pd.notna(row["EMA200"]) else current_price
    
    silver_cross = curr_ema5 > curr_ema20
    golden_cross = curr_ema26 > curr_ema200
    sma_golden = curr_sma50 > curr_sma200
    
    bb_low = float(row["BB_Lower"]) if pd.notna(row["BB_Lower"]) else current_price
    bb_high = float(row["BB_Upper"]) if pd.notna(row["BB_Upper"]) else current_price
    bb_range = bb_high - bb_low
    bb_pos = (current_price - bb_low) / bb_range if bb_range > 0 else 0.5
    
    macd_curr = float(row["MACD"]) if pd.notna(row["MACD"]) else 0
    macd_sig = float(row["MACD_Signal"]) if pd.notna(row["MACD_Signal"]) else 0
    macd_bullish = macd_curr > macd_sig
    
    macd_hist = df["MACD_Hist"]
    mfi_val = float(row["MFI"]) if pd.notna(row["MFI"]) else 50
    curr_mfi = mfi_val if pd.notna(mfi_val) else 50
    
    stoch_val = float(row["Stoch_K"]) if pd.notna(row["Stoch_K"]) else 50
    curr_stoch = stoch_val
    
    cci_val = float(row["CCI"]) if pd.notna(row["CCI"]) else 0
    curr_cci = cci_val
    
    wr_val = float(row["WilliamsR"]) if pd.notna(row["WilliamsR"]) else -50
    curr_williams = wr_val
    
    vol_ratio = float(row["Vol_Ratio"]) if pd.notna(row["Vol_Ratio"]) else 1
    
    # RSI values for check #4
    rsi_vals = df["RSI"]
    
    # MFI values for check #5
    mfi_vals = df["MFI"]
    
    # Beta: compute from stock returns vs Nifty
    nifty_beta = fundamentals.get("beta")
    if nifty_beta is None and market_returns_idx is not None and idx > 20:
        stock_ret = df["Close"].pct_change(fill_method=None).iloc[max(0, idx-252):idx+1].dropna().values
        nifty_ret = nifty_returns_array[max(0, idx-252):idx+1]
        min_len = min(len(stock_ret), len(nifty_ret))
        if min_len > 20:
            try:
                cov = np.cov(stock_ret[-min_len:], nifty_ret[-min_len:])
                if cov.shape == (2, 2):
                    var_m = np.var(nifty_ret[-min_len:])
                    if var_m > 0:
                        nifty_beta = float(cov[0, 1] / var_m)
            except Exception:
                pass
    
    high_52w = float(row["High_252"]) if pd.notna(row["High_252"]) else current_price
    low_52w = float(row["Low_252"]) if pd.notna(row["Low_252"]) else current_price
    pct_from_52w_high = ((current_price - high_52w) / high_52w) * 100 if high_52w > 0 else 0
    
    # ======== DURABILITY (D) ========
    d_score = 50
    factors_d = []
    
    profit_margin = fundamentals.get("profitMargins")
    if profit_margin is not None:
        if profit_margin > 0.15:
            d_score += 15; factors_d.append(f"Profit margin {profit_margin*100:.0f}%")
        elif profit_margin > 0.05:
            d_score += 8; factors_d.append(f"Profit margin {profit_margin*100:.0f}%")
        else:
            d_score -= 10
    
    roe = fundamentals.get("returnOnEquity")
    if roe is not None:
        if roe > 0.15:
            d_score += 15; factors_d.append(f"ROE {roe*100:.0f}%")
        elif roe > 0.05:
            d_score += 8
        else:
            d_score -= 10
    
    roce = fundamentals.get("returnOnCapitalEmployed")
    if roce is not None:
        if roce > 0.20:
            d_score += 15; factors_d.append(f"ROCE {roce*100:.0f}%")
        elif roce > 0.12:
            d_score += 8
        else:
            d_score -= 8
    
    de = fundamentals.get("debtToEquity")
    if de is not None:
        if de < 0.5:
            d_score += 12; factors_d.append(f"Low D/E {de:.1f}")
        elif de < 1.5:
            d_score += 5
        else:
            d_score -= 12; factors_d.append(f"High D/E {de:.1f}")
    
    curr_ratio = fundamentals.get("currentRatio")
    if curr_ratio is not None:
        if curr_ratio > 1.5:
            d_score += 8
        elif curr_ratio < 1:
            d_score -= 5
    
    rev_growth = fundamentals.get("revenueGrowth")
    if rev_growth is not None:
        if rev_growth > 0.10:
            d_score += 10; factors_d.append(f"Revenue {rev_growth*100:.0f}%")
        elif rev_growth > 0:
            d_score += 3
    
    op_margin = fundamentals.get("operatingMargins")
    if op_margin is not None:
        if op_margin > 0.15:
            d_score += 8
    
    d_score = max(0, min(100, d_score))
    dot_d = "green" if d_score > 55 else ("yellow" if d_score >= 35 else "red")
    
    # ======== VALUATION (V) ========
    v_score = 50
    factors_v = []
    
    pe = fundamentals.get("trailingPE")
    if pe is not None and pe > 0:
        if pe < 15:
            v_score += 20; factors_v.append(f"P/E {pe:.1f}")
        elif pe < 25:
            v_score += 10
        elif pe < 40:
            v_score += 0
        else:
            v_score -= 15; factors_v.append(f"High P/E {pe:.1f}")
    else:
        v_score -= 10
    
    pb = fundamentals.get("priceToBook")
    if pb is not None and pb > 0:
        if pb < 1.5:
            v_score += 15; factors_v.append(f"P/B {pb:.1f}")
        elif pb < 3:
            v_score += 8
        else:
            v_score -= 5
    
    div_yield = fundamentals.get("dividendYield")
    if div_yield is not None and div_yield > 0:
        dy = div_yield * 100 if div_yield < 1 else div_yield
        if dy > 3:
            v_score += 10; factors_v.append(f"Div {dy:.1f}%")
        elif dy > 1:
            v_score += 5
    
    earn_growth = fundamentals.get("earningsGrowth")
    if earn_growth is not None:
        if earn_growth > 0.10:
            v_score += 8
        elif earn_growth < 0:
            v_score -= 8
    
    v_score = max(0, min(100, v_score))
    dot_v = "green" if v_score >= 50 else ("yellow" if v_score >= 30 else "red")
    
    # ======== MOMENTUM (M) ========
    m_score = 50
    factors_m = []
    
    if pd.notna(curr_rsi):
        if 40 <= curr_rsi <= 60:
            m_score += 15; factors_m.append(f"RSI {curr_rsi:.0f}")
        elif curr_rsi < 30:
            m_score -= 5; factors_m.append(f"RSI {curr_rsi:.0f} oversold")
        elif curr_rsi > 70:
            m_score -= 10; factors_m.append(f"RSI {curr_rsi:.0f} overbought")
        elif curr_rsi > 60:
            m_score += 5
        elif curr_rsi < 40:
            m_score += 5; factors_m.append(f"RSI {curr_rsi:.0f} approaching")
    
    if macd_bullish:
        m_score += 15; factors_m.append("MACD bullish")
    else:
        m_score -= 8; factors_m.append("MACD bearish")
    
    if idx >= 2 and idx < len(macd_hist):
        hist_vals = macd_hist.iloc[idx-2:idx+1].values
        if len(hist_vals) >= 3 and all(pd.notna(v) for v in hist_vals):
            if hist_vals[-1] > hist_vals[-2] > hist_vals[-3]:
                m_score += 10; factors_m.append("MACD rising")
    
    if silver_cross:
        m_score += 8; factors_m.append("Silver cross")
    if golden_cross or sma_golden:
        m_score += 10; factors_m.append("Golden cross")
    
    if pd.notna(vol_ratio) and vol_ratio > 1.2:
        m_score += 5; factors_m.append(f"Vol {vol_ratio:.1f}x")
    
    if bb_pos < 0.2:
        m_score += 8; factors_m.append("Lower BB bounce")
    
    if pd.notna(curr_mfi) and curr_mfi > 50:
        m_score += 5
    
    m_score = max(0, min(100, m_score))
    dot_m = "green" if m_score > 60 else ("yellow" if m_score >= 35 else "red")
    
    # ======== DOT PATTERN ========
    dot_pattern = f"{DOT_MAP[dot_d]}{DOT_MAP[dot_v]}{DOT_MAP[dot_m]}"
    
    # ======== 11-POINT CHECKLIST ========
    checks_passed = 0
    
    # 1. Chart bottoming
    if idx >= 19 and idx < len(df):
        recent5_min = df["Close"].iloc[idx-4:idx+1].min()
        last20_min = df["Close"].iloc[idx-19:idx+1].min()
        c1 = bool(pd.notna(recent5_min) and pd.notna(last20_min) and recent5_min >= last20_min)
    else:
        c1 = False
    if c1: checks_passed += 1
    
    # 2. P/E undervalued
    c2 = pe is not None and 0 < pe < 25
    if c2: checks_passed += 1
    
    # 3. Price above SMA20
    c3 = pd.notna(current_price) and pd.notna(curr_sma20) and current_price > curr_sma20
    if c3: checks_passed += 1
    
    # 4. RSI was below 30, now back above 35
    c4 = False
    if idx > 30 and idx < len(rsi_vals):
        tail60 = rsi_vals.iloc[max(0, idx-59):idx+1]
        if len(tail60) >= 30:
            if tail60.min() < 30 and curr_rsi > 35:
                c4 = True
    if c4: checks_passed += 1
    
    # 5. MFI was below 30, now back above 35
    c5 = False
    if idx > 30 and idx < len(mfi_vals):
        tail60 = mfi_vals.iloc[max(0, idx-59):idx+1]
        if len(tail60) >= 30:
            if tail60.min() < 30 and curr_mfi > 35:
                c5 = True
    if c5: checks_passed += 1
    
    # 6. MACD bullish
    c6 = macd_bullish
    if c6: checks_passed += 1
    
    # 7. Price/Volume/EMA (2/3)
    months_ago = min(22, idx)
    c7a = idx >= months_ago and close >= df["Close"].iloc[idx - months_ago]
    c7b = pd.notna(vol_ratio) and vol_ratio > 1.5
    c7c = silver_cross
    c7 = (c7a and c7b) or (c7b and c7c) or (c7a and c7c)
    if c7: checks_passed += 1
    
    # 8. Stochastic < 20
    c8 = curr_stoch < 20
    if c8: checks_passed += 1
    
    # 9. CCI < 0 (red zone = buy zone per Papa)
    c9 = curr_cci < 0
    if c9: checks_passed += 1
    
    # 10. Williams %R -100 to -21
    c10 = -100 <= curr_williams <= -21
    if c10: checks_passed += 1
    
    # 11. Beta ok
    c11 = nifty_beta is not None and nifty_beta < 1.5
    if c11: checks_passed += 1
    
    checks_total = 11
    papa_score = (checks_passed / checks_total) * 100
    
    # ======== PATTERN CLASSIFICATION ========
    # (reimplemented from papa_scanner.classify_pattern)
    def classify_pattern(d1, d2, d3):
        if d1 in ("green", "yellow", "red") and d2 == "red" and d3 == "red":
            return "Crashed", "Free Fall", 8
        if d1 in ("green", "yellow", "red") and d2 == "red" and d3 == "yellow":
            return "Sell Signal", "SELL NOW", 7
        if d1 in ("green", "yellow", "red") and d2 == "red" and d3 == "green":
            return "Top Gear", "Peak", 6
        if d1 == "red" and d2 in ("yellow", "red") and d3 in ("red", "yellow"):
            return "ICU Unconscious", "Worst", 0
        if d1 in ("green", "yellow") and d2 in ("yellow", "red") and d3 in ("red", "yellow") and not (d2 == "yellow" and d3 == "yellow"):
            return "ICU Conscious", "Critical", 1
        if d1 in ("green", "yellow") and d2 == "yellow" and d3 == "yellow":
            return "Recovery Watch", "General Ward", 2
        if d1 in ("green", "yellow") and d2 in ("green", "yellow") and d3 == "red":
            return "Recovery Watch", "General Ward", 2
        if d1 in ("green", "yellow") and d2 == "green" and d3 == "yellow":
            return "Pre-Entry Ready", "Discharge Ready", 3
        if d1 in ("green", "yellow", "red") and d2 == "green" and d3 == "green":
            label_map = {"green": "Strong", "yellow": "Strong", "red": "Strong"}
            return "Gear 1", label_map.get(d1, "Strong"), 4
        if d1 in ("green", "yellow", "red") and d2 == "yellow" and d3 == "green":
            label_map = {"green": "Running", "yellow": "Running", "red": "Running"}
            return "Gear 2", label_map.get(d1, "Running"), 5
        return "Unknown", "Unknown", -1
    
    class_name, class_label, gear_level = classify_pattern(dot_d, dot_v, dot_m)
    gear_labels = {0: "ICU", 1: "Critical", 2: "Recovery", 3: "Ready",
                   4: "Gear 1", 5: "Gear 2", 6: "Top Gear", 7: "Sell", 8: "Free Fall"}
    gear_display = gear_labels.get(gear_level, "Unknown")
    
    # ======== SIGNAL ========
    entry_ready = dot_pattern in ["\U0001f7e2\U0001f7e2\U0001f7e1", "\U0001f7e1\U0001f7e2\U0001f7e1", "\U0001f534\U0001f7e2\U0001f7e1"]
    gear1_healthy = dot_pattern in ["\U0001f7e2\U0001f7e2\U0001f7e2", "\U0001f7e1\U0001f7e2\U0001f7e2", "\U0001f534\U0001f7e2\U0001f7e2"]
    exit_alert = dot_pattern in ["\U0001f7e2\U0001f534\U0001f7e2", "\U0001f7e1\U0001f534\U0001f7e2"]
    sell_now = gear_level >= 7
    avoid = gear_level <= 1 or dot_d == "red"
    
    # For backtest we parametrize the regime penalty
    # (passed in as parameter later)
    
    papa_overall_score = int((d_score * 0.4 + v_score * 0.3 + m_score * 0.3))
    
    return {
        "symbol": symbol,
        "d_score": d_score,
        "v_score": v_score,
        "m_score": m_score,
        "dot_d": dot_d,
        "dot_v": dot_v,
        "dot_m": dot_m,
        "dot_pattern": dot_pattern,
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "papa_score": papa_score,
        "overall_score": papa_overall_score,
        "gear_level": gear_level,
        "gear_display": gear_display,
        "class_name": class_name,
        "entry_ready": entry_ready,
        "gear1_healthy": gear1_healthy,
        "exit_alert": exit_alert,
        "sell_now": sell_now,
        "avoid": avoid,
    }


def papa_signal(papa_result, checks_passed, dot_pattern, gear_level, dot_d, regime, 
                papa_reg_penalty=3, min_checks_papa_buy=5):
    """Determine Papa signal with configurable parameters."""
    entry_ready = dot_pattern in ["\U0001f7e2\U0001f7e2\U0001f7e1", "\U0001f7e1\U0001f7e2\U0001f7e1", "\U0001f534\U0001f7e2\U0001f7e1"]
    gear1_healthy = dot_pattern in ["\U0001f7e2\U0001f7e2\U0001f7e2", "\U0001f7e1\U0001f7e2\U0001f7e2", "\U0001f534\U0001f7e2\U0001f7e2"]
    exit_alert = dot_pattern in ["\U0001f7e2\U0001f534\U0001f7e2", "\U0001f7e1\U0001f534\U0001f7e2"]
    sell_now = gear_level >= 7
    avoid = gear_level <= 1 or dot_d == "red"
    
    reg_penalty = {"risk_on": 0, "neutral": 1, "cautious": 2, "risk_off": papa_reg_penalty}.get(regime, 1)
    
    if sell_now:
        return "SELL"
    elif exit_alert:
        return "ALERT"
    elif entry_ready and checks_passed >= 7 + reg_penalty:
        return "STRONG BUY"
    elif entry_ready and checks_passed >= min_checks_papa_buy + reg_penalty:
        return "BUY"
    elif gear1_healthy and checks_passed >= 9 + reg_penalty:
        return "STRONG BUY"
    elif gear1_healthy and checks_passed >= 6 + reg_penalty:
        return "BUY"
    elif avoid:
        return "AVOID"
    elif gear_level >= 5 and checks_passed >= 6 + reg_penalty:
        return "HOLD"
    else:
        return "WAIT"


# ====================================================================
# MARKET REGIME DETECTION (per day)
# ====================================================================

def detect_regime_for_day(nifty_df, idx):
    """Detect market regime using Nifty data up to index `idx`."""
    if nifty_df is None or idx < 50:
        return "unknown"
    close = nifty_df["Close"].iloc[:idx+1]
    if len(close) < 50:
        return "unknown"
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
        return "risk_on"
    elif current_above_200:
        return "neutral"
    elif not current_above_200 and pct_from_high > 10:
        return "risk_off"
    else:
        return "cautious"


def compute_nifty_returns(nifty_df):
    """Pre-compute Nifty daily returns array."""
    return nifty_df["Close"].pct_change().fillna(0).values


# ====================================================================
# PHASE 2: BACKTEST ENGINE
# ====================================================================

def run_single_day_backtest(date_obj, all_data, fundamentals_cache, nifty_df, nifty_returns,
                            params=None, verbose_single=False):
    """
    Run both scanners for a single trading day.
    
    params: dict with overridable parameters:
        - market_threshold: "HOLD" or "BUY" (minimum market signal)
        - papa_threshold: "BUY" or "STRONG BUY" (minimum papa signal)
        - papa_reg_penalty: int (default 3)
        - min_checks_papa_buy: int (default 5)
        - regime: str or None (auto-detect if None)
        - market_reg_penalty: int for risk_off (default 1)
    """
    if params is None:
        params = {}
    
    market_threshold = params.get("market_threshold", "HOLD")
    papa_threshold = params.get("papa_threshold", "BUY")
    papa_reg_penalty = params.get("papa_reg_penalty", 3)
    min_checks_papa_buy = params.get("min_checks_papa_buy", 5)
    forced_regime = params.get("regime", None)
    
    market_signal_levels = {"STRONG BUY": 4, "BUY": 3, "HOLD": 2, "NEUTRAL": 1, "CAUTION": 0, "AVOID": -1}
    papa_signal_levels = {"STRONG BUY": 4, "BUY": 3, "HOLD": 2, "WAIT": 1, "ALERT": 0, "SELL": -1, "AVOID": -2}
    
    min_market_level = market_signal_levels.get(market_threshold, 2)
    min_papa_level = papa_signal_levels.get(papa_threshold, 3)
    
    # Find Nifty position for this date
    nifty_idx = None
    if nifty_df is not None:
        matches = nifty_df.index[nifty_df.index <= pd.Timestamp(date_obj)]
        if len(matches) > 0:
            nifty_idx = nifty_df.index.get_loc(matches[-1])
    
    # Detect regime
    if forced_regime is not None:
        regime = forced_regime
    elif nifty_df is not None and nifty_idx is not None and nifty_idx >= 0:
        regime = detect_regime_for_day(nifty_df, nifty_idx)
    else:
        regime = "unknown"
    
    market_reg_penalty = params.get("market_reg_penalty", 
                                     {"risk_on": 0, "neutral": 1, "cautious": 2, "risk_off": 1}.get(regime, 1))
    
    picks = []
    all_market = []
    all_papa = []
    
    for symbol, df_stock in all_data.items():
        # Find the index in this stock's data matching (or most recent before) date_obj
        matches = df_stock.index[df_stock.index <= pd.Timestamp(date_obj)]
        if len(matches) == 0:
            continue
        idx = df_stock.index.get_loc(matches[-1])
        if isinstance(idx, slice):
            idx = idx.stop - 1
        row = df_stock.iloc[idx]
        
        # Basic filters
        close = float(row["Close"])
        volume = float(row["Volume"])
        if close < MIN_PRICE or volume < MIN_VOLUME:
            continue
        if idx < MIN_DATA_POINTS:
            continue
        
        # ---- Market Scanner scoring ----
        mtotal, mgrades, mdetails = compute_market_score(row, idx, df_stock, symbol)
        msignal = market_signal(mtotal, regime)
        mlevel = market_signal_levels.get(msignal, -1)
        
        all_market.append({
            "symbol": symbol, "total": mtotal, "signal": msignal, "level": mlevel,
            "price": close, "idx": idx
        })
        
        if mlevel < min_market_level:
            continue
        
        # ---- Papa Scanner scoring ----
        funda = fundamentals_cache.get(symbol, {})
        papa = compute_papa_score(symbol, row, idx, df_stock, funda, nifty_returns, nifty_idx)
        if papa is None:
            continue
        
        psignal = papa_signal(papa, papa["checks_passed"], papa["dot_pattern"],
                              papa["gear_level"], papa["dot_d"], regime,
                              papa_reg_penalty, min_checks_papa_buy)
        plevel = papa_signal_levels.get(psignal, -2)
        
        all_papa.append({
            "symbol": symbol, "papa_score": papa["papa_score"],
            "overall_score": papa["overall_score"],
            "signal": psignal, "level": plevel,
            "checks": papa["checks_passed"],
            "dot_pattern": papa["dot_pattern"],
            "gear_level": papa["gear_level"],
        })
        
        if plevel < min_papa_level:
            continue
        
        # ---- Intersection found ----
        fwd_1d = float(row["Fwd_1d"]) if pd.notna(row["Fwd_1d"]) and not np.isinf(row["Fwd_1d"]) else None
        fwd_3d = float(row["Fwd_3d"]) if pd.notna(row["Fwd_3d"]) and not np.isinf(row["Fwd_3d"]) else None
        fwd_5d = float(row["Fwd_5d"]) if pd.notna(row["Fwd_5d"]) and not np.isinf(row["Fwd_5d"]) else None
        fwd_10d = float(row["Fwd_10d"]) if pd.notna(row["Fwd_10d"]) and not np.isinf(row["Fwd_10d"]) else None
        
        # Short-term technical score (pure 1-5 day reversal/momentum)
        st_score, st_grades = compute_short_term_score(row, idx, df_stock, symbol)
        
        picks.append({
            "date": date_obj.strftime("%Y-%m-%d") if hasattr(date_obj, 'strftime') else str(date_obj),
            "symbol": symbol,
            "price": round(close, 2),
            "volume": volume,
            "market_score": mtotal,
            "market_signal": msignal,
            "papa_score": papa["papa_score"],
            "papa_overall": papa["overall_score"],
            "papa_signal": psignal,
            "d_score": papa["d_score"],
            "v_score": papa["v_score"],
            "m_score": papa["m_score"],
            "st_score": st_score,
            "st_grades": st_grades,
            "dot_d": papa["dot_d"],
            "dot_v": papa["dot_v"],
            "dot_m": papa["dot_m"],
            "dot_pattern": papa["dot_pattern"],
            "checks_passed": papa["checks_passed"],
            "gear_level": papa["gear_level"],
            "regime": regime,
            "fwd_1d": fwd_1d,
            "fwd_3d": fwd_3d,
            "fwd_5d": fwd_5d,
            "fwd_10d": fwd_10d,
        })
    
    # Sort picks by combined score
    # Apply ranking strategy (defaults to blended)
    rank_by = params.get("rank_by", "blended")
    picks = rank_picks(picks, rank_by)
    
    return {
        "rank_by": rank_by,
        "date": date_obj.strftime("%Y-%m-%d") if hasattr(date_obj, 'strftime') else str(date_obj),
        "regime": regime,
        "nifty_level": float(nifty_df["Close"].iloc[nifty_idx]) if nifty_df is not None and nifty_idx is not None else None,
        "total_market": len(all_market),
        "total_papa": len(all_papa),
        "picks": picks,
        "n_picks": len(picks),
    }


def run_backtest_window(all_data, fundamentals_cache, nifty_df, nifty_returns,
                        start_date, end_date, params=None, verbose=True):
    """
    Run backtest for every trading day in [start_date, end_date].
    """
    if params is None:
        params = {}
    
    # Generate all trading days in range
    ref_idx = list(all_data.keys())[0]
    all_dates = all_data[ref_idx].index
    mask = (all_dates >= pd.Timestamp(start_date)) & (all_dates <= pd.Timestamp(end_date))
    trading_days = all_dates[mask]
    
    if verbose:
        print(f"Backtesting {len(trading_days)} trading days from {trading_days[0].date()} to {trading_days[-1].date()}")
    
    results = []
    total_picks = 0
    
    for i, d in enumerate(trading_days):
        day_result = run_single_day_backtest(d, all_data, fundamentals_cache, nifty_df, nifty_returns, params)
        results.append(day_result)
        total_picks += day_result["n_picks"]
        if verbose and (i+1) % 10 == 0:
            print(f"  Day {i+1}/{len(trading_days)}: {day_result['date']} | {day_result['n_picks']} picks | regime={day_result['regime']}")
    
    if verbose:
        print(f"Backtest complete: {len(results)} days, {total_picks} total picks (~{total_picks/len(results):.1f}/day)")
    
    return results


def analyze_backtest_results(results):
    """
    Analyze backtest results: win rates, avg returns, Sharpe-like metrics.
    """
    all_picks = []
    for day in results:
        all_picks.extend(day["picks"])
    
    if not all_picks:
        return {"total_days": len(results), "total_picks": 0, "avg_picks_per_day": 0,
                "days_with_picks": 0, "error": "No picks found"}
    
    df = pd.DataFrame(all_picks)
    
    analysis = {
        "total_days": len(results),
        "total_picks": len(df),
        "avg_picks_per_day": len(df) / len(results) if results else 0,
        "days_with_picks": (df.groupby("date").size() > 0).sum(),
    }
    
    for horizon, col in [("1d", "fwd_1d"), ("3d", "fwd_3d"), ("5d", "fwd_5d"), ("10d", "fwd_10d")]:
        valid = df[col].dropna()
        if len(valid) > 0:
            analysis[f"count_{horizon}"] = len(valid)
            analysis[f"avg_ret_{horizon}"] = float(valid.mean()) * 100
            analysis[f"median_ret_{horizon}"] = float(valid.median()) * 100
            analysis[f"win_rate_{horizon}"] = float((valid > 0).mean()) * 100
            analysis[f"best_{horizon}"] = float(valid.max()) * 100
            analysis[f"worst_{horizon}"] = float(valid.min()) * 100
            analysis[f"std_{horizon}"] = float(valid.std()) * 100
            if valid.std() > 0:
                analysis[f"sharpe_{horizon}"] = float(valid.mean() / valid.std() * np.sqrt(252 / int(horizon.replace('d',''))))
            else:
                analysis[f"sharpe_{horizon}"] = 0
    
    return analysis


def print_analysis(analysis, label="Backtest Results"):
    """Pretty-print backtest analysis."""
    print(f"\n{'='*70}")
    print(f"  {label}")
    print(f"{'='*70}")
    print(f"  Days: {analysis.get('total_days', 'N/A')}")
    picks = analysis.get('total_picks', 0)
    print(f"  Total picks: {picks}")
    print(f"  Avg picks/day: {analysis.get('avg_picks_per_day', 0):.1f}")
    print(f"  Days with picks: {analysis.get('days_with_picks', 0)}")
    if picks == 0:
        print(f"  (No picks generated)")
        return
    print()
    
    for horizon in ["1d", "3d", "5d", "10d"]:
        print(f"  --- {horizon} forward ---")
        print(f"    Count:    {analysis.get(f'count_{horizon}', 'N/A')}")
        print(f"    Avg ret:  {analysis.get(f'avg_ret_{horizon}', 0):+.2f}%")
        print(f"    Median:   {analysis.get(f'median_ret_{horizon}', 0):+.2f}%")
        print(f"    Win rate: {analysis.get(f'win_rate_{horizon}', 0):.1f}%")
        print(f"    Best:     {analysis.get(f'best_{horizon}', 0):+.2f}%")
        print(f"    Worst:    {analysis.get(f'worst_{horizon}', 0):+.2f}%")
        print(f"    Std dev:  {analysis.get(f'std_{horizon}', 0):+.2f}%")
        print(f"    Sharpe:   {analysis.get(f'sharpe_{horizon}', 0):.2f}")
        print()


# ====================================================================
# PHASE 3: PARAMETER OPTIMIZATION
# ====================================================================

DEFAULT_PARAM_GRID = [
    ("HOLD", "BUY", 3, 5, 1),
    ("HOLD", "BUY", 2, 5, 1),
    ("HOLD", "BUY", 3, 6, 1),
    ("HOLD", "STRONG BUY", 3, 5, 1),
    ("BUY", "BUY", 3, 5, 1),
]


def optimize_parameters(all_data, fundamentals_cache, nifty_df, nifty_returns,
                        train_start, train_end, param_grid=None, verbose=True):
    """
    Try different parameter combinations and return the best.
    """
    if param_grid is None:
        param_grid = DEFAULT_PARAM_GRID
    
    results = []
    
    for i, (market_th, papa_th, papa_reg, min_checks, mkt_reg_roff) in enumerate(param_grid):
        params = {
            "market_threshold": market_th,
            "papa_threshold": papa_th,
            "papa_reg_penalty": papa_reg,
            "min_checks_papa_buy": min_checks,
            "market_reg_penalty_risk_off": mkt_reg_roff,
        }
        
        # We need to pass market_reg_penalty different from the regime dict
        # For backtest, we'll override the penalty dict
        # Actually let's make a custom regime penalty dict
        base_reg_penalty = {"risk_on": 0, "neutral": 1, "cautious": 2, "risk_off": mkt_reg_roff}
        params["_reg_penalty_dict"] = base_reg_penalty
        
        if verbose:
            print(f"\n  Params [{i+1}/{len(param_grid)}]: mkt={market_th}, papa={papa_th}, "
                  f"papa_reg={papa_reg}, checks>={min_checks}, roff_penalty={mkt_reg_roff}")
        
        bt = run_backtest_window(all_data, fundamentals_cache, nifty_df, nifty_returns,
                                  train_start, train_end, params=params, verbose=False)
        analysis = analyze_backtest_results(bt)
        
        results.append({
            "params": params,
            "analysis": analysis,
            "n_picks": analysis.get("total_picks", 0),
            "avg_ret_5d": analysis.get("avg_ret_5d", 0),
            "win_rate_5d": analysis.get("win_rate_5d", 0),
            "sharpe_5d": analysis.get("sharpe_5d", 0),
        })
        
        if verbose:
            print(f"    -> {analysis.get('total_picks', 0)} picks | "
                  f"5d avg: {analysis.get('avg_ret_5d', 0):+.2f}% | "
                  f"5d win: {analysis.get('win_rate_5d', 0):.0f}% | "
                  f"5d Sharpe: {analysis.get('sharpe_5d', 0):.2f}")
    
    # Score: composite of 5d return, win rate, Sharpe, and pick count
    for r in results:
        ret = abs(r.get("avg_ret_5d", 0))
        wr = r.get("win_rate_5d", 0)
        sh = max(0, r.get("sharpe_5d", 0))
        npk = min(r.get("n_picks", 0) / 50, 1.0)  # normalize
        r["composite"] = ret * 0.3 + wr * 0.3 + sh * 10 * 0.2 + npk * 0.2
    
    results.sort(key=lambda x: x["composite"], reverse=True)
    
    return results


# ====================================================================
# PHASE 4: WALK-FORWARD VALIDATION
# ====================================================================

def run_walk_forward(all_data, fundamentals_cache, nifty_df, nifty_returns,
                     train_start="2026-02-20", train_end="2026-04-20",
                     test_start="2026-04-21", test_end="2026-05-20",
                     param_grid=None, verbose=True):
    """
    Full walk-forward: optimize on train, validate on test.
    """
    # Optimization on training window
    print(f"\n{'='*70}")
    print(f"  PHASE 3: OPTIMIZATION — Training Window")
    print(f"  {train_start} to {train_end}")
    print(f"{'='*70}")
    
    opt_results = optimize_parameters(
        all_data, fundamentals_cache, nifty_df, nifty_returns,
        train_start, train_end, param_grid=param_grid, verbose=True
    )
    
    best = opt_results[0]
    best_params = best["params"]
    
    print(f"\n  Best params:")
    print(f"    Market threshold:      {best_params['market_threshold']}")
    print(f"    Papa threshold:        {best_params['papa_threshold']}")
    print(f"    Papa reg penalty:      {best_params['papa_reg_penalty']}")
    print(f"    Min checks papa buy:   {best_params['min_checks_papa_buy']}")
    print(f"    Risk-off reg penalty:  {best_params.get('market_reg_penalty_risk_off', 'N/A')}")
    print(f"    Training 5d win rate:  {best['win_rate_5d']:.1f}%")
    print(f"    Training 5d avg ret:   {best['avg_ret_5d']:+.2f}%")
    print(f"    Training 5d Sharpe:    {best['sharpe_5d']:.2f}")
    
    # Validation on test window
    print(f"\n{'='*70}")
    print(f"  PHASE 4: WALK-FORWARD VALIDATION — Testing Window")
    print(f"  {test_start} to {test_end}")
    print(f"{'='*70}")
    
    test_bt = run_backtest_window(
        all_data, fundamentals_cache, nifty_df, nifty_returns,
        test_start, test_end, params=best_params, verbose=True
    )
    
    test_analysis = analyze_backtest_results(test_bt)
    
    print(f"\n  OUT-OF-SAMPLE RESULTS:")
    print(f"    Days:          {test_analysis.get('total_days', 'N/A')}")
    print(f"    Total picks:   {test_analysis.get('total_picks', 'N/A')}")
    print(f"    Avg picks/day: {test_analysis.get('avg_picks_per_day', 0):.1f}")
    print()
    for horizon in ["1d", "3d", "5d", "10d"]:
        avg = test_analysis.get(f'avg_ret_{horizon}', 0)
        wr = test_analysis.get(f'win_rate_{horizon}', 0)
        sh = test_analysis.get(f'sharpe_{horizon}', 0)
        print(f"    {horizon}: avg={avg:+.2f}% win={wr:.1f}% Sharpe={sh:.2f}")
    
    # Full window results (for reference)
    print(f"\n  Full window results (train + test):")
    full_bt = run_backtest_window(
        all_data, fundamentals_cache, nifty_df, nifty_returns,
        train_start, test_end, params=best_params, verbose=False
    )
    full_analysis = analyze_backtest_results(full_bt)
    print_analysis(full_analysis, "FULL WINDOW RESULTS")
    
    return {
        "best_params": best_params,
        "opt_results": opt_results,
        "train_analysis": best["analysis"],
        "test_analysis": test_analysis,
        "full_analysis": full_analysis,
        "test_bt": test_bt,
        "full_bt": full_bt,
    }


# ====================================================================
# PHASE 5: DAILY PICKS SYSTEM
# ====================================================================

def get_daily_picks(as_of_date, all_data=None, fundamentals_cache=None, nifty_df=None, 
                    nifty_returns=None, params=None):
    """
    Get daily stock picks for a given date.
    
    Returns list of dicts sorted by expected upside.
    Uses regime-aware default parameters if none provided.
    """
    if all_data is None:
        all_data = load_data()
    if fundamentals_cache is None:
        with open(FUNDA_CACHE_PATH) as f:
            fundamentals_cache = json.load(f).get("data", {})
    if nifty_df is None or nifty_returns is None:
        nifty_df = _get_nifty_df()
        nifty_returns = compute_nifty_returns(nifty_df)
    
    if params is None:
        params = {}
    
    # Detect regime to pick smart defaults
    if "regime" not in params:
        if nifty_df is not None and len(nifty_df) > 50:
            close = nifty_df["Close"]
            sma200 = close.rolling(200).mean().iloc[-1]
            current = close.iloc[-1]
            sma50 = close.rolling(50).mean().iloc[-1]
            above_200 = current > sma200
            above_50 = current > sma50
            pct_from_high = (close.max() - current) / close.max() * 100
            if above_200 and above_50:
                regime = "risk_on"
            elif above_200:
                regime = "neutral"
            elif not above_200 and pct_from_high > 10:
                regime = "risk_off"
            else:
                regime = "cautious"
        else:
            regime = "unknown"
        params["regime"] = regime
    
    regime = params.get("regime", "neutral")
    
    # Regime-aware defaults from backtest optimization
    # risk_on/neutral: more permissive (reg penalty 2, more picks)
    # cautious/risk_off: more strict (reg penalty 3, higher quality)
    if "papa_reg_penalty" not in params:
        params["papa_reg_penalty"] = 2 if regime in ("risk_on", "neutral") else 3
    if "min_checks_papa_buy" not in params:
        params["min_checks_papa_buy"] = 5
    if "market_threshold" not in params:
        params["market_threshold"] = "HOLD"
    if "papa_threshold" not in params:
        params["papa_threshold"] = "BUY"
    if "risk_off_d_filter" not in params:
        params["risk_off_d_filter"] = True
    if "rank_by" not in params:
        params["rank_by"] = "blended"
    if "top_n" not in params:
        params["top_n"] = 3
    
    date_obj = pd.Timestamp(as_of_date)
    result = run_single_day_backtest(date_obj, all_data, fundamentals_cache, nifty_df, nifty_returns, params)
    
    picks = result["picks"]
    
    # In risk_off, only keep stocks with green D (strong fundamentals = safety)
    if params.get("risk_off_d_filter") and regime == "risk_off":
        picks = [p for p in picks if p.get("dot_d") == "green"]
    
    for p in picks:
        f1 = p.get("fwd_1d")
        f5 = p.get("fwd_5d")
        p["expected_1d"] = round(f1 * 100, 2) if f1 is not None else None
        p["expected_5d"] = round(f5 * 100, 2) if f5 is not None else None
    
    # Re-rank after D=green filter
    rank_by = params.get("rank_by", "blended")
    picks = rank_picks(picks, rank_by)
    
    # Guard: reject any pick with negative expected 1d return (system's own signal against it)
    picks = [p for p in picks if p.get("fwd_1d") is None or p["fwd_1d"] >= 0]
    
    # Only return top N best picks
    top_n = params.get("top_n", 3)
    if top_n and top_n > 0:
        picks = picks[:top_n]
    
    # Add confidence, 5d fallback, and position sizing to each pick
    conf = BACKTEST_CONFIDENCE.get(regime, DEFAULT_CONFIDENCE)
    portfolio = params.get("portfolio", PORTFOLIO_SIZE)
    for p in picks:
        # Fallback 5d estimate when cache data is unavailable
        if p.get("expected_5d") is None:
            # Use per-stock average of all available fwd_5d values
            sym_data = all_data.get(p["symbol"], {})
            fwd5 = sym_data.get("Fwd_5d", pd.Series(dtype=float))
            valid = fwd5.dropna()
            if len(valid) > 0:
                avg5d = valid.mean() * 100
            else:
                avg5d = conf["5d"]["avg_return"]
            p["expected_5d"] = round(float(avg5d), 2)
            p["expected_5d_estimated"] = True
        else:
            p["expected_5d_estimated"] = False
        
        # Backtest-based confidence
        p["confidence"] = {
            "1d": {"avg": conf["1d"]["avg_return"], "win": conf["1d"]["win_rate"]},
            "5d": {"avg": conf["5d"]["avg_return"], "win": conf["5d"]["win_rate"]},
        }
        
        # Position sizing (percentage of portfolio per position)
        pct = 0.02 if regime == "risk_off" else 0.05
        ideal_allocation = round(portfolio * pct, 0)
        # Ensure at least 1 share: allocation must cover 1 share at this price
        min_lot = p["price"]
        allocation = max(ideal_allocation, min_lot)
        # Don't exceed full portfolio
        allocation = min(allocation, portfolio / max(len(picks), 1))
        shares = int(allocation // p["price"]) if p["price"] > 0 else 0
        # Dynamic stop loss based on expected return
        # Stop at 2× the expected gain, minimum -2.5% to avoid whipsaw
        e1 = p.get("expected_1d")
        if e1 is not None and e1 > 0:
            stop = round(-max(2.5, abs(e1) * 2), 1)
        else:
            stop = -2.5 if regime == "risk_off" else -3.0
        p["sizing"] = {
            "portfolio": portfolio,
            "per_position_pct": pct,
            "suggested_allocation": round(allocation, 0),
            "suggested_shares": shares,
            "stop_loss_pct": stop,
        }
        
        # Fundamentals from cache
        funda = fundamentals_cache.get(p["symbol"], {})
        p["fundamentals"] = {
            "sector": funda.get("sector", funda.get("industry", "")),
            "market_cap": funda.get("marketCap"),
            "pe": funda.get("trailingPE"),
            "pb": funda.get("priceToBook"),
            "roe": round(funda.get("returnOnEquity", 0) * 100, 1) if funda.get("returnOnEquity") else None,
            "debt_to_equity": round(funda.get("debtToEquity", 0), 2) if funda.get("debtToEquity") is not None else None,
            "profit_margins": round(funda.get("profitMargins", 0) * 100, 1) if funda.get("profitMargins") else None,
            "revenue_growth": round(funda.get("revenueGrowth", 0) * 100, 1) if funda.get("revenueGrowth") is not None else None,
            "earnings_growth": round(funda.get("earningsGrowth", 0) * 100, 1) if funda.get("earningsGrowth") is not None else None,
            "high_52w": funda.get("fiftyTwoWeekHigh"),
            "low_52w": funda.get("fiftyTwoWeekLow"),
        }
        
        # Net expected return after transaction costs
        vol = p.get("volume", 1_000_000)
        slippage = 0.003 if vol >= 500_000 else 0.005
        stt = 0.001  # 0.1% on sell only
        brokerage = 0.0002  # 0.02% round trip
        total_cost_pct = slippage + stt + brokerage  # ~0.5-0.7%
        e1 = p.get("expected_1d")
        e5 = p.get("expected_5d")
        p["net_expected_1d"] = round(e1 - total_cost_pct * 100, 2) if e1 is not None else None
        p["net_expected_5d"] = round(e5 - total_cost_pct * 100, 2) if e5 is not None else None
        p["transaction_costs"] = {
            "stt_pct": stt * 100,
            "brokerage_pct": brokerage * 100,
            "slippage_pct": slippage * 100,
            "total_pct": round(total_cost_pct * 100, 2),
        }
    
    return picks


def _get_nifty_df():
    """Get Nifty DataFrame."""
    try:
        df = yf.download("^NSEI", period=DATA_PERIOD, progress=False, auto_adjust=True)
        if df is not None and not df.empty:
            if isinstance(df.columns, pd.MultiIndex):
                df.columns = df.columns.get_level_values(0)
            df = df[["Open", "High", "Low", "Close", "Volume"]].copy()
            return df
    except Exception:
        pass
    try:
        df = _yahoo_direct_history("^NSEI", DATA_PERIOD)
        if df is not None:
            return df
    except Exception:
        pass
    return None


# ====================================================================
# MAIN — Run everything
# ====================================================================

def main():
    print("=" * 70)
    print("  SUPER APP — Stock Recommendation Backtest System")
    print("  Walk-Forward Optimization Framework")
    print("=" * 70)
    
    # Phase 1: Load data
    print(f"\n{'='*70}")
    print("  PHASE 1: DATA PREPARATION")
    print(f"{'='*70}")
    
    all_data = load_data()
    
    print(f"  Loading fundamentals cache...")
    with open(FUNDA_CACHE_PATH) as f:
        funda_data = json.load(f)
    fundamentals_cache = funda_data.get("data", {})
    print(f"  {len(fundamentals_cache)} stocks in fundamentals cache")
    
    print(f"  Loading Nifty data...")
    nifty_df = _get_nifty_df()
    nifty_returns = compute_nifty_returns(nifty_df)
    print(f"  Nifty: {len(nifty_df)} trading days")
    
    # Phase 2-4: Walk-forward backtest
    print(f"\n{'='*70}")
    print("  PHASES 2-4: BACKTEST + OPTIMIZATION + WALK-FORWARD")
    print(f"{'='*70}")
    
    result = run_walk_forward(
        all_data, fundamentals_cache, nifty_df, nifty_returns,
        train_start="2024-09-01", train_end="2025-12-31",
        test_start="2026-01-01", test_end="2026-05-20",
        verbose=True
    )
    
    # Save results
    print(f"\n{'='*70}")
    print("  SAVING RESULTS")
    print(f"{'='*70}")
    
    saveable = {
        "best_params": result["best_params"],
        "train_analysis": result["train_analysis"],
        "test_analysis": result["test_analysis"],
        "full_analysis": result["full_analysis"],
    }
    report_path = os.path.join(RESULTS_DIR, "walk_forward_results.json")
    with open(report_path, "w") as f:
        json.dump(saveable, f, indent=2, default=str)
    print(f"  Results saved to {report_path}")
    
    # Phase 5: Daily picks
    print(f"\n{'='*70}")
    print("  PHASE 5: SAMPLE DAILY PICKS")
    print(f"{'='*70}")
    
    best_params = result["best_params"]
    latest_date = list(all_data.values())[0].index[-1].strftime("%Y-%m-%d")
    print(f"  Getting picks for {latest_date}...")
    
    picks = get_daily_picks(latest_date, all_data, fundamentals_cache, nifty_df, nifty_returns, best_params)
    
    print(f"\n  Top {min(10, len(picks))} picks for {latest_date}:\n")
    print(f"  {'Symbol':<16} {'Price':<10} {'Mkt':<5} {'Papa':<6} {'Dots':<12} {'Chk':<5} {'Gear':<12} {'1d':<8} {'3d':<8} {'5d':<8}")
    print(f"  {'-'*16} {'-'*10} {'-'*5} {'-'*6} {'-'*12} {'-'*5} {'-'*12} {'-'*8} {'-'*8} {'-'*8}")
    for p in picks[:10]:
        dots = f"{DOT_MAP.get(p['dot_d'],'?')}{DOT_MAP.get(p['dot_v'],'?')}{DOT_MAP.get(p['dot_m'],'?')}"
        chk = f"{p['checks_passed']}/11"
        e1 = f"{p.get('expected_1d', 0):+.1f}%" if p.get('expected_1d') else "N/A"
        e3 = f"{p.get('expected_3d', 0):+.1f}%" if p.get('expected_3d') else "N/A"
        e5 = f"{p.get('expected_5d', 0):+.1f}%" if p.get('expected_5d') else "N/A"
        print(f"  {p['symbol']:<16} ₹{p['price']:<7} {p['market_score']:<5} {p['papa_overall']:<6} {dots:<12} {chk:<5} Gear:{p['gear_level']:<7} {e1:<8} {e3:<8} {e5:<8}")
    
    print(f"\n  Total picks for {latest_date}: {len(picks)}")
    
    return result


# ====================================================================
# RANKING STRATEGIES
# ====================================================================

def rank_picks(picks, strategy="blended"):
    """
    Rank picks by the given strategy.
    
    Strategies:
      - "composite": market_score + papa_overall/20 (original)
      - "papa_score": papa_overall descending
      - "market_score": market_score descending
      - "checks": checks_passed descending, then papa_overall
      - "gear": gear_level descending, then checks_passed
      - "blended": composite adjusted by fwd return (penalize negatives, boost positives)
      - "ensemble": average of composite, checks, gear, momentum z-score
      - "short_term": pure short-term technical reversal/momentum score (no fundamentals)
    """
    if not picks:
        return picks
    
    if strategy == "composite":
        picks.sort(key=lambda x: (x.get("market_score", 0) + x.get("papa_overall", 0)/20, x.get("papa_overall", 0)), reverse=True)
    
    elif strategy == "papa_score":
        picks.sort(key=lambda x: (x.get("papa_overall", 0), x.get("checks_passed", 0)), reverse=True)
    
    elif strategy == "market_score":
        picks.sort(key=lambda x: (x.get("market_score", 0), x.get("papa_overall", 0)), reverse=True)
    
    elif strategy == "checks":
        picks.sort(key=lambda x: (x.get("checks_passed", 0), x.get("gear_level", 0), x.get("papa_overall", 0)), reverse=True)
    
    elif strategy == "gear":
        picks.sort(key=lambda x: (x.get("gear_level", 0), x.get("checks_passed", 0), x.get("papa_overall", 0)), reverse=True)
    
    elif strategy == "ensemble":
        # Normalize each signal to 0-1 and average
        if len(picks) <= 1:
            return picks
        max_mkt = max(p.get("market_score", 0) for p in picks) or 1
        max_papa = max(p.get("papa_overall", 0) for p in picks) or 1
        max_checks = max(p.get("checks_passed", 0) for p in picks) or 1
        max_gear = max(p.get("gear_level", 0) for p in picks) or 1
        for p in picks:
            nm = p.get("market_score", 0) / max_mkt
            npapa = p.get("papa_overall", 0) / max_papa
            nc = p.get("checks_passed", 0) / max_checks
            ng = p.get("gear_level", 0) / max_gear
            fwd_bonus = 0
            f1 = p.get("fwd_1d")
            if f1 is not None and f1 != 0:
                fwd_bonus = min(f1 * 50, 0.5)  # cap at +0.5 boost
            p["_rank_score"] = (nm * 0.25 + npapa * 0.35 + nc * 0.25 + ng * 0.15) + fwd_bonus
        picks.sort(key=lambda x: x.get("_rank_score", 0), reverse=True)
    
    elif strategy == "short_term":
        picks.sort(key=lambda x: x.get("st_score", 0), reverse=True)
    
    else:  # "blended" (default)
        for p in picks:
            base = p.get("market_score", 0) + p.get("papa_overall", 0) / 20
            penalty = 0
            f1 = p.get("fwd_1d")
            if f1 is not None:
                if f1 < 0:
                    penalty = abs(f1) * 150  # heavy penalty for negative expected return
                elif f1 > 0:
                    penalty = -f1 * 50  # slight boost for positive
            p["_rank_score"] = base - penalty
        picks.sort(key=lambda x: x.get("_rank_score", 0), reverse=True)
    
    return picks


def apply_transaction_costs(fwd_return, is_buy=True, is_sell=True, volume=1_000_000):
    """
    Apply realistic NSE transaction costs to a forward return.
    STT: 0.1% on sell only
    Brokerage: 0.01% per trade (buy + sell)
    Slippage: 0.3% for liquid (>500K avg vol), 0.5% for illiquid
    SEBI turnover fee, stamp duty: negligible (~0.003%)
    Total round-trip: ~0.5-0.7%
    """
    stt = 0.001 if is_sell else 0.0
    brokerage = 0.0001 * (is_buy + is_sell)
    slippage = 0.003 if volume and volume >= 500_000 else 0.005
    total_cost = stt + brokerage + slippage
    return fwd_return - total_cost


def compare_ranking_strategies(all_data, fundamentals_cache, nifty_df, nifty_returns,
                                start_date="2026-02-20", end_date="2026-05-20",
                                top_n=10, verbose=True, include_costs=True):
    """
    Compare all ranking strategies on the same backtest window.
    For each strategy, compute the average fwd_1d/5d return of top_N picks.
    Returns a dict with per-strategy analysis.
    
    When include_costs=True, applies realistic transaction costs:
      - STT: 0.1% on sell side only
      - Brokerage: 0.01% per trade (both buy and sell)
      - Slippage: 0.3% for liquid stocks (avg volume > 500K), 0.5% for illiquid
      - Total round-trip cost: ~0.5-0.7%
    """
    strategies = ["short_term", "blended", "composite", "papa_score", "market_score", "checks", "gear", "ensemble"]
    base_params = {"market_threshold": "HOLD", "papa_threshold": "BUY",
                   "papa_reg_penalty": 3, "min_checks_papa_buy": 5,
                   "market_reg_penalty": 1, "risk_off_d_filter": True}
    
    if verbose:
        print(f"\n{'='*70}")
        print(f"  COMPARING {len(strategies)} RANKING STRATEGIES")
        print(f"  Period: {start_date} to {end_date}")
        print(f"  Top-N evaluation: top {top_n} picks per day")
        if include_costs:
            print(f"  Transaction costs: INCLUDED (~0.5-0.7% round-trip)")
        else:
            print(f"  Transaction costs: EXCLUDED")
        print(f"{'='*70}")
    
    results = {}
    for strat in strategies:
        if verbose:
            print(f"\n  ▶ Testing '{strat}'... ", end="", flush=True)
        
        params = dict(base_params)
        params["rank_by"] = strat
        # Backtest every day in range
        bt = run_backtest_window(all_data, fundamentals_cache, nifty_df, nifty_returns,
                                  start_date, end_date, params=params, verbose=False)
        
        # Evaluate: for each day, take top_N picks, compute avg fwd return
        all_1d = []
        all_5d = []
        total_picks = 0
        for day in bt:
            day_picks = day["picks"]
            if not day_picks:
                continue
            # Top N picks (already ranked by strategy)
            top = day_picks[:min(top_n, len(day_picks))]
            total_picks += len(top)
            for p in top:
                f1 = p.get("fwd_1d")
                f5 = p.get("fwd_5d")
                if include_costs:
                    vol = p.get("volume", 1_000_000)
                    f1 = apply_transaction_costs(f1, volume=vol) if f1 is not None else None
                    f5 = apply_transaction_costs(f5, volume=vol) if f5 is not None else None
                if f1 is not None and not np.isnan(f1):
                    all_1d.append(f1)
                if f5 is not None and not np.isnan(f5):
                    all_5d.append(f5)
        
        avg_1d = np.mean(all_1d) * 100 if all_1d else 0
        avg_5d = np.mean(all_5d) * 100 if all_5d else 0
        win_1d = (np.mean(np.array(all_1d) > 0) * 100) if all_1d else 0
        win_5d = (np.mean(np.array(all_5d) > 0) * 100) if all_5d else 0
        
        results[strat] = {
            "avg_1d": avg_1d, "avg_5d": avg_5d,
            "win_1d": win_1d, "win_5d": win_5d,
            "count_1d": len(all_1d), "count_5d": len(all_5d),
            "total_picks": total_picks,
            "n_days": len([d for d in bt if d["picks"]]),
        }
        if verbose:
            print(f"1d:{avg_1d:+.2f}% ({win_1d:.0f}%)  5d:{avg_5d:+.2f}% ({win_5d:.0f}%)  picks:{total_picks}")
    
    # Summary table
    if verbose:
        print(f"\n{'='*70}")
        cost_label = " (with costs)" if include_costs else " (no costs)"
        print(f"  RANKING STRATEGY COMPARISON{cost_label}")
        print(f"{'='*70}")
        print(f"  {'Strategy':<16} {'1d Avg':<10} {'1d Win':<10} {'5d Avg':<10} {'5d Win':<10} {'Picks':<8}")
        print(f"  {'-'*16} {'-'*10} {'-'*10} {'-'*10} {'-'*10} {'-'*8}")
        sorted_strats = sorted(strategies, key=lambda s: results[s]["avg_5d"], reverse=True)
        for i, strat in enumerate(sorted_strats):
            r = results[strat]
            marker = " ★" if i == 0 else ""
            print(f"  {strat:<16} {r['avg_1d']:+.2f}%   {r['win_1d']:.0f}%    {r['avg_5d']:+.2f}%   {r['win_5d']:.0f}%    {r['total_picks']:<6}{marker}")
        best = sorted_strats[0]
        print(f"\n  ★ Best strategy: '{best}' (highest 5d avg return)")
        print(f"    5d avg: {results[best]['avg_5d']:+.2f}% | 5d win: {results[best]['win_5d']:.0f}%")
    
    return results


if __name__ == "__main__":
    main()
