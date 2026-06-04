import logging
import time
import random
import os
import httpx
logging.getLogger("yfinance").setLevel(logging.CRITICAL)

import yfinance as yf
import pandas as pd
import ta
import numpy as np
import time
import re
from concurrent.futures import ThreadPoolExecutor, as_completed
import threading
from nsetools import Nse

_FUNDA_CACHE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "fundamentals_cache.json")
_FUNDA_CACHE = {}
_FUNDA_SCAN_COUNT = 0
_FUNDA_CACHE_WORKERS = 20

_TAPETIDE_TOKEN = "tpt_rt_83f5266cf3e768180e77ee6fe1cd6ef1f4b36a34d07143a46244c77f"
_TAPETIDE_URL = "https://mcp.tapetide.com/mcp"
_TAPETIDE_WORKERS = 5

def _load_funda_cache():
    global _FUNDA_CACHE, _FUNDA_SCAN_COUNT
    try:
        import json
        with open(_FUNDA_CACHE_PATH) as f:
            data = json.load(f)
        _FUNDA_CACHE = data.get("data", {})
        _FUNDA_SCAN_COUNT = data.get("scan_count", 0)
        return data
    except Exception:
        _FUNDA_CACHE = {}
        _FUNDA_SCAN_COUNT = 0
        return {"data": {}, "scan_count": 0}

def _save_funda_cache():
    import json
    data = {
        "version": 1,
        "last_updated": time.strftime("%Y-%m-%d %H:%M:%S"),
        "scan_count": _FUNDA_SCAN_COUNT,
        "data": _FUNDA_CACHE,
    }
    try:
        with open(_FUNDA_CACHE_PATH, "w") as f:
            json.dump(data, f, indent=1)
    except Exception:
        pass

def _fetch_funda_google(symbol):
    """Fetch fundamentals via Google Finance scraping."""
    from bs4 import BeautifulSoup
    try:
        url = f"https://www.google.com/finance/quote/{symbol}:NSE"
        r = httpx.get(url, timeout=10, follow_redirects=True)
        if r.status_code != 200:
            return None
        soup = BeautifulSoup(r.text, 'html.parser')
        f = {}
        rows = soup.find_all('div', class_='gyFHrc')
        for row in rows:
            label_el = row.find('div', class_='mfs7Fc')
            value_el = row.find('div', class_='P6K39c')
            if not label_el or not value_el:
                continue
            label = label_el.get_text(strip=True)
            value = value_el.get_text(strip=True)

            if label == "P/E ratio":
                try:
                    f["trailingPE"] = float(value)
                except:
                    pass
            elif label == "Market cap":
                mcap_str = value.replace("T INR", "e12").replace("B INR", "e9").replace("M INR", "e6").replace("K INR", "e3").replace("INR", "").strip()
                try:
                    f["marketCap"] = float(mcap_str)
                except:
                    pass
            elif label == "Dividend yield":
                try:
                    f["dividendYield"] = float(value.replace("%", "").strip()) / 100
                except:
                    pass
            elif label == "Year range":
                parts = value.replace("₹", "").replace(",", "").split(" - ")
                if len(parts) == 2:
                    try:
                        f["fiftyTwoWeekHigh"] = float(parts[1])
                        f["fiftyTwoWeekLow"] = float(parts[0])
                    except:
                        pass
        return f if len(f) > 0 else None
    except Exception as e:
        return None

def _fetch_funda_tapetide(symbol):
    """Fetch fundamentals from Tapetide MCP API (ROE, ROCE, D/E, PB, etc.)."""
    import json
    try:
        headers = {
            "Authorization": f"Bearer {_TAPETIDE_TOKEN}",
            "Content-Type": "application/json",
            "Accept": "text/event-stream, application/json",
        }
        payload = {
            "jsonrpc": "2.0", "id": 1,
            "method": "tools/call",
            "params": {"name": "get_company_profile", "arguments": {"symbol": symbol}},
        }
        r = httpx.post(_TAPETIDE_URL, json=payload, headers=headers, timeout=15)
        if r.status_code != 200:
            return None
        resp = r.json()
        content = resp.get("result", {}).get("content", [])
        if not content:
            return None
        text = content[0].get("text", "{}")
        data = json.loads(text).get("data", {})
        funda = data.get("fundamentals", {})
        if not funda:
            return None

        result = {}
        roe = funda.get("roe")
        if roe is not None:
            result["returnOnEquity"] = roe / 100.0
        roce = funda.get("roce")
        if roce is not None:
            result["returnOnCapitalEmployed"] = roce / 100.0
        de = funda.get("debt_to_equity")
        if de is not None:
            result["debtToEquity"] = de
        pb = funda.get("price_to_book")
        if pb is not None:
            result["priceToBook"] = pb
        bv = funda.get("book_value")
        if bv is not None:
            result["bookValue"] = bv
        pe = funda.get("stock_pe")
        if pe is not None:
            result["trailingPE"] = pe
        rg = funda.get("revenue_growth_1y")
        if rg is not None:
            result["revenueGrowth"] = rg / 100.0
        eg = funda.get("yoy_quarterly_profit_growth")
        if eg is not None:
            result["earningsGrowth"] = eg / 100.0

        # Fallback: extract growth rates from unified_growth_rates
        ugr = data.get("unified_growth_rates", {})
        if "revenueGrowth" not in result:
            rg_ugr = ugr.get("revenue_growth", {})
            rg_1y = rg_ugr.get("1Y")
            if rg_1y is not None:
                result["revenueGrowth"] = rg_1y / 100.0
        if "earningsGrowth" not in result:
            neg_ugr = ugr.get("net_income_growth", {})
            neg_1y = neg_ugr.get("1Y")
            if neg_1y is not None:
                result["earningsGrowth"] = neg_1y / 100.0

        net_income = funda.get("net_income")
        yearly_revenue = funda.get("yearly_revenue")
        if net_income is not None and yearly_revenue is not None and yearly_revenue > 0:
            result["profitMargins"] = net_income / yearly_revenue

        return result if len(result) > 0 else None
    except Exception:
        return None


def _fetch_one_funda(symbol):
    funda = _fetch_funda_google(symbol)
    return symbol, funda if funda and len(funda) > 0 else None


def _run_tapetide_batch(symbols, progress_callback=None):
    """Fetch Tapetide fundamentals for all symbols — merges into _FUNDA_CACHE."""
    global _FUNDA_CACHE
    done = 0
    total = len(symbols)
    futures = []
    with ThreadPoolExecutor(max_workers=_TAPETIDE_WORKERS) as pool:
        for sym in symbols:
            fut = pool.submit(_fetch_funda_tapetide, sym)
            futures.append((sym, fut))
        for sym, fut in futures:
            done += 1
            try:
                tap_data = fut.result()
                if tap_data:
                    existing = _FUNDA_CACHE.get(sym)
                    if existing:
                        existing.update(tap_data)
                    else:
                        _FUNDA_CACHE[sym] = tap_data
            except Exception:
                pass
            if progress_callback and done % 50 == 0:
                progress_callback(done, total)


def _download_funda_cache(symbols, progress_callback=None):
    global _FUNDA_CACHE
    total = len(symbols)
    # Phase 1: Google Finance
    done = 0
    with ThreadPoolExecutor(max_workers=_FUNDA_CACHE_WORKERS) as pool:
        fut_map = {pool.submit(_fetch_one_funda, sym): sym for sym in symbols}
        for future in as_completed(fut_map):
            sym, funda = future.result()
            done += 1
            if funda:
                _FUNDA_CACHE[sym] = funda
            if progress_callback and done % 50 == 0:
                progress_callback(done, total)
    # Phase 2: Tapetide — merge D·V·M fields (ROE, ROCE, D/E, etc.)
    _run_tapetide_batch(symbols, progress_callback)
    _FUNDA_SCAN_COUNT = 0
    _save_funda_cache()

MIN_PRICE = 15
MIN_VOLUME = 100000
MIN_DATA_POINTS = 150
MIN_MARKET_CAP = 500_000_000
CONCURRENT_WORKERS = 50

NIFTY_SYMBOL = "^NSEI"
_NIFTY_DF_CACHE = None
_REGIME_CACHE = None

def _get_nifty_df():
    global _NIFTY_DF_CACHE
    if _NIFTY_DF_CACHE is not None and len(_NIFTY_DF_CACHE) > 20:
        return _NIFTY_DF_CACHE
    try:
        df = _yahoo_direct_history(NIFTY_SYMBOL, "1y")
        if df is not None and not df.empty and len(df) > 20:
            _NIFTY_DF_CACHE = df
            return df
    except Exception:
        pass
    try:
        df = yf.download(NIFTY_SYMBOL, period="1y", progress=False, auto_adjust=True)
        if df is not None and not df.empty and len(df) > 20:
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

def get_all_nse_symbols():
    nse = Nse()
    symbols = nse.get_stock_codes()
    return [s for s in symbols if s and isinstance(s, str) and not s.startswith("SYMBOL")]

DOT_MAP = {"green": "🟢", "yellow": "🟡", "red": "🔴"}

def _to_native(obj):
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    if isinstance(obj, (np.bool_,)):
        return bool(obj)
    if isinstance(obj, dict):
        return {k: _to_native(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [_to_native(v) for v in obj]
    return obj

def score_d(score):
    if score > 55: return "green"
    elif score >= 35: return "yellow"
    return "red"

def score_v(score):
    if score >= 50: return "green"
    elif score >= 30: return "yellow"
    return "red"

def score_m(score):
    if score > 60: return "green"
    elif score >= 35: return "yellow"
    return "red"

def classify_pattern(dot1, dot2, dot3):
    # Most severe first: Free Fall → Sell → Top Gear → ICU → Recovery → Entry → Gear1 → Gear2
    if dot1 in ("green", "yellow", "red") and dot2 == "red" and dot3 == "red":
        return "Crashed", "💀 Free Fall", 8

    if dot1 in ("green", "yellow", "red") and dot2 == "red" and dot3 == "yellow":
        return "Sell Signal", "🚨 SELL NOW", 7

    if dot1 in ("green", "yellow", "red") and dot2 == "red" and dot3 == "green":
        return "Top Gear — Peak", "🟢🔴🟢 Peak ⚠️" if dot1 == "green" else ("🟡🔴🟢 Peak ⚠️" if dot1 == "yellow" else "🔴🔴🟢 Peak ⚠️"), 6

    if dot1 == "red" and dot2 in ("yellow", "red") and dot3 in ("red", "yellow"):
        return "ICU Unconscious", "💀 Worst", 0

    if dot1 in ("green", "yellow") and dot2 in ("yellow", "red") and dot3 in ("red", "yellow") and not (dot2 == "yellow" and dot3 == "yellow"):
        return "ICU Conscious", "🔴 Critical", 1

    if dot1 in ("green", "yellow") and dot2 == "yellow" and dot3 == "yellow":
        return "Recovery Watch", "🟡 General Ward", 2
    if dot1 in ("green", "yellow") and dot2 in ("green", "yellow") and dot3 == "red":
        return "Recovery Watch", "🟡 General Ward", 2

    if dot1 in ("green", "yellow") and dot2 == "green" and dot3 == "yellow":
        return "Pre-Entry Ready", "🟢 Discharge Ready", 3

    if dot1 in ("green", "yellow", "red") and dot2 == "green" and dot3 == "green":
        return "Gear 1 — Healthy", "🟢🟢🟢 Strong" if dot1 == "green" else ("🟡🟢🟢 Strong" if dot1 == "yellow" else "🔴🟢🟢 Strong"), 4

    if dot1 in ("green", "yellow", "red") and dot2 == "yellow" and dot3 == "green":
        return "Gear 2 — Running", "🟢🟡🟢 Running" if dot1 == "green" else ("🟡🟡🟢 Running" if dot1 == "yellow" else "🔴🟡🟢 Running"), 5

    return "Unknown", "❓ Unknown", -1

def get_gear_label(gear_level):
    labels = {
        0: "ICU 💀", 1: "Critical 🔴", 2: "Recovery 🟡",
        3: "Ready 🟢", 4: "Gear 1 🚗", 5: "Gear 2 🚗",
        6: "Top Gear 🏎️", 7: "Sell 🚨", 8: "Free Fall 💀"
    }
    return labels.get(gear_level, "Unknown")

def compute_beta(stock_returns, market_returns):
    if len(stock_returns) < 20 or len(market_returns) < 20:
        return None
    cov = np.cov(stock_returns, market_returns)
    if cov.shape != (2, 2):
        return None
    var_market = np.var(market_returns)
    if var_market == 0:
        return None
    beta = cov[0, 1] / var_market
    return beta

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

def analyze_papa(symbol):
    ticker = symbol + ".NS"
    df = None
    for hist_attempt in range(3):
        try:
            df = _yahoo_direct_history(ticker, "1y")
            if df is not None and not df.empty and len(df) >= MIN_DATA_POINTS:
                break
        except Exception:
            pass
        if df is None or df.empty or len(df) < MIN_DATA_POINTS:
            try:
                import yfinance as yf
                stock = yf.Ticker(ticker)
                df = stock.history(period="1y")
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
    returns = close.pct_change().dropna()
    avg_volume = volume.mean()

    if current_price < MIN_PRICE or avg_volume < MIN_VOLUME:
        return None

    fundamentals = _FUNDA_CACHE.get(symbol, {}).copy()
    if not fundamentals:
        try:
            fund_stock = yf.Ticker(ticker)
            info_data = fund_stock.info
            if info_data and isinstance(info_data, dict):
                for k in ["trailingPE", "priceToBook", "debtToEquity", "returnOnEquity",
                           "profitMargins", "currentRatio", "dividendYield", "marketCap",
                           "beta", "sector", "revenueGrowth", "operatingMargins",
                           "earningsGrowth", "freeCashflow"]:
                    v = info_data.get(k)
                    if v is not None:
                        fundamentals[k] = v
        except Exception:
            pass

    market_cap = fundamentals.get("marketCap") or 0
    if market_cap > 0 and market_cap < MIN_MARKET_CAP:
        return None

    rsi_ind = ta.momentum.RSIIndicator(close, window=14)
    rsi_vals = rsi_ind.rsi()
    curr_rsi = rsi_vals.iloc[-1] if pd.notna(rsi_vals.iloc[-1]) else 50

    sma20 = ta.trend.SMAIndicator(close, window=20).sma_indicator()
    sma50 = ta.trend.SMAIndicator(close, window=50).sma_indicator()
    sma200 = ta.trend.SMAIndicator(close, window=200).sma_indicator()
    ema5 = ta.trend.EMAIndicator(close, window=5).ema_indicator()
    ema20 = ta.trend.EMAIndicator(close, window=20).ema_indicator()
    ema26 = ta.trend.EMAIndicator(close, window=26).ema_indicator()
    ema200 = ta.trend.EMAIndicator(close, window=200).ema_indicator()

    macd = ta.trend.MACD(close)
    macd_line = macd.macd()
    macd_signal = macd.macd_signal()
    macd_hist = macd.macd_diff()

    bb = ta.volatility.BollingerBands(close, window=20)
    bb_low = bb.bollinger_lband()
    bb_high = bb.bollinger_hband()
    bb_mid = bb.bollinger_mavg()

    vol_sma20 = volume.rolling(window=20).mean()
    vol_ratio = volume.iloc[-1] / vol_sma20.iloc[-1] if vol_sma20.iloc[-1] > 0 else 1

    atr = ta.volatility.AverageTrueRange(high, low, close, window=14).average_true_range()
    atr_val = atr.iloc[-1] if pd.notna(atr.iloc[-1]) else 0
    atr_pct = (atr_val / current_price) * 100 if current_price > 0 else 0

    mfi_ind = ta.volume.MFIIndicator(high, low, close, volume, window=14)
    mfi_val = mfi_ind.money_flow_index()
    curr_mfi = mfi_val.iloc[-1] if pd.notna(mfi_val.iloc[-1]) else 50

    stoch = ta.momentum.StochasticOscillator(high, low, close, window=14, smooth_window=3)
    stoch_k = stoch.stoch()
    curr_stoch = stoch_k.iloc[-1] if pd.notna(stoch_k.iloc[-1]) else 50

    cci = ta.trend.CCIIndicator(high, low, close, window=20)
    cci_val = cci.cci()
    curr_cci = cci_val.iloc[-1] if pd.notna(cci_val.iloc[-1]) else 0

    williams = ta.momentum.WilliamsRIndicator(high, low, close, lbp=14)
    williams_val = williams.williams_r()
    curr_williams = williams_val.iloc[-1] if pd.notna(williams_val.iloc[-1]) else -50

    curr_sma20 = sma20.iloc[-1] if pd.notna(sma20.iloc[-1]) else current_price
    curr_sma50 = sma50.iloc[-1] if pd.notna(sma50.iloc[-1]) else current_price
    curr_sma200 = sma200.iloc[-1] if pd.notna(sma200.iloc[-1]) else current_price
    curr_ema5 = ema5.iloc[-1] if pd.notna(ema5.iloc[-1]) else current_price
    curr_ema20 = ema20.iloc[-1] if pd.notna(ema20.iloc[-1]) else current_price
    curr_ema26 = ema26.iloc[-1] if pd.notna(ema26.iloc[-1]) else current_price
    curr_ema200 = ema200.iloc[-1] if pd.notna(ema200.iloc[-1]) else current_price

    silver_cross = curr_ema5 > curr_ema20
    golden_cross = curr_ema26 > curr_ema200
    sma_golden = curr_sma50 > curr_sma200

    curr_bb_low = bb_low.iloc[-1] if pd.notna(bb_low.iloc[-1]) else current_price
    curr_bb_high = bb_high.iloc[-1] if pd.notna(bb_high.iloc[-1]) else current_price
    bb_range = curr_bb_high - curr_bb_low
    bb_pos = (current_price - curr_bb_low) / bb_range if bb_range > 0 else 0.5

    macd_curr = macd_line.iloc[-1] if pd.notna(macd_line.iloc[-1]) else 0
    macd_sig = macd_signal.iloc[-1] if pd.notna(macd_signal.iloc[-1]) else 0
    macd_bullish = macd_curr > macd_sig

    nifty_beta = fundamentals.get("beta")
    if nifty_beta is None:
        nifty_df = _get_nifty_df()
        if nifty_df is not None and len(nifty_df) > 20:
            nifty_returns = nifty_df["Close"].pct_change().dropna()
            stock_ret = close.pct_change().dropna()
            min_len = min(len(stock_ret), len(nifty_returns))
            if min_len > 20:
                try:
                    nifty_beta = compute_beta(
                        stock_ret.values[-min_len:],
                        nifty_returns.values[-min_len:]
                    )
                except Exception:
                    pass

    high_52w = close.rolling(252).max().iloc[-1] if len(close) > 1 else current_price
    low_52w = close.rolling(252).min().iloc[-1] if len(close) > 1 else current_price
    pct_from_52w_high = ((current_price - high_52w) / high_52w) * 100 if high_52w > 0 else 0

    # -------- DURABILITY SCORE (D) --------
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
    dot_d = score_d(d_score)

    # -------- VALUATION SCORE (V) --------
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
    dot_v = score_v(v_score)

    # -------- MOMENTUM SCORE (M) --------
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

    hist_vals = macd_hist.tail(3).values
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
    dot_m = score_m(m_score)

    # -------- DOT PATTERN --------
    dot_pattern = f"{DOT_MAP[dot_d]}{DOT_MAP[dot_v]}{DOT_MAP[dot_m]}"

    # -------- 11-POINT PAPA CHECKLIST --------
    checks = {}
    checks_passed = 0
    checks_total = 11

    # 1. Chart bottoming (higher lows in recent 20 days)
    c1 = pd.notna(close.tail(5).min()) and close.tail(5).min() >= close.tail(20).min()
    checks["1. Chart bottoming"] = bool(c1)
    if c1: checks_passed += 1

    # 2. P/E Valuation: Undervalued (P/E < sector avg or < 25)
    c2 = pe is not None and 0 < pe < 25
    checks["2. P/E Undervalued"] = bool(c2)
    if c2: checks_passed += 1

    # 3. Price above 20-day SMA (short-term uptrend)
    c3 = pd.notna(curr_sma20) and current_price > curr_sma20
    checks["3. Price above SMA20"] = bool(c3)
    if c3: checks_passed += 1

    # 4. RSI was below 30, now back above 35
    c4 = False
    if len(rsi_vals.tail(60)) >= 30:
        if rsi_vals.tail(60).min() < 30 and curr_rsi > 35:
            c4 = True
    checks["4. RSI 30→35"] = bool(c4)
    if c4: checks_passed += 1

    # 5. MFI was below 30, now back above 35
    c5 = False
    mfi_tail = mfi_val.tail(60)
    if len(mfi_tail) >= 30:
        if mfi_tail.min() < 30 and curr_mfi > 35:
            c5 = True
    checks["5. MFI 30→35"] = bool(c5)
    if c5: checks_passed += 1

    # 6. MACD red→yellow/green (MACD bullish)
    c6 = macd_bullish
    checks["6. MACD bullish"] = bool(c6)
    if c6: checks_passed += 1

    # 7a. Price Change 1M green
    months_ago = min(22, len(close) - 1)
    c7a = close.iloc[-1] >= close.iloc[-months_ago]
    # 7b. Volume delivery rising 50%
    c7b = pd.notna(vol_ratio) and vol_ratio > 1.5
    # 7c. EMA 5-day green
    c7c = curr_ema5 > curr_ema20
    c7 = (c7a and c7b) or (c7b and c7c) or (c7a and c7c)
    checks["7. Price/Vol/EMA (2/3)"] = bool(c7)
    if c7: checks_passed += 1

    # 8. Stochastic: deep oversold < 20
    c8 = curr_stoch < 20
    checks["8. Stoch <20"] = bool(c8)
    if c8: checks_passed += 1

    # 9. CCI 20: red (< 0 means bearish zone = buy zone per Papa)
    c9 = curr_cci < 0
    checks["9. CCI 20 red"] = bool(c9)
    if c9: checks_passed += 1

    # 10. William: -100 to -21 (buy zone)
    c10 = -100 <= curr_williams <= -21
    checks["10. William -100:-21"] = bool(c10)
    if c10: checks_passed += 1

    # 11. Beta: red → grey/blue/green (beta not red = finished correction)
    c11 = nifty_beta is not None and nifty_beta < 1.5
    checks["11. Beta ok"] = bool(c11)
    if c11: checks_passed += 1

    papa_score = (checks_passed / checks_total) * 100 if checks_total > 0 else 0

    # -------- CLASSIFICATION --------
    class_name, class_label, gear_level = classify_pattern(dot_d, dot_v, dot_m)
    gear_display = get_gear_label(gear_level)

    # -------- MARKET REGIME ADJUSTMENT --------
    regime = get_market_regime()
    reg_penalty = {"risk_on": 0, "neutral": 1, "cautious": 2, "risk_off": 3}.get(regime, 1)

    # -------- SIGNAL --------
    entry_ready = dot_pattern in ["🟢🟢🟡", "🟡🟢🟡", "🔴🟢🟡"]
    gear1_healthy = dot_pattern in ["🟢🟢🟢", "🟡🟢🟢", "🔴🟢🟢"]
    exit_alert = dot_pattern in ["🟢🔴🟢", "🟡🔴🟢"]
    sell_now = gear_level >= 7
    avoid = gear_level <= 1 or dot_d == "red"

    if sell_now:
        signal = "SELL"
    elif exit_alert:
        signal = "ALERT"
    elif entry_ready and checks_passed >= 7 + reg_penalty:
        signal = "STRONG BUY"
    elif entry_ready and checks_passed >= 5 + reg_penalty:
        signal = "BUY"
    elif gear1_healthy and checks_passed >= 9 + reg_penalty:
        signal = "STRONG BUY"
    elif gear1_healthy and checks_passed >= 6 + reg_penalty:
        signal = "BUY"
    elif avoid:
        signal = "AVOID"
    elif gear_level >= 5 and checks_passed >= 6 + reg_penalty:
        signal = "HOLD"
    else:
        signal = "WAIT"

    # -------- GRADE --------
    if checks_passed >= 10:
        grade = "A+"
    elif checks_passed >= 8:
        grade = "A"
    elif checks_passed >= 6:
        grade = "B"
    elif checks_passed >= 4:
        grade = "C"
    else:
        grade = "D"

    overall_score = int((d_score * 0.4 + v_score * 0.3 + m_score * 0.3))

    return _to_native({
        "symbol": symbol,
        "price": round(current_price, 2),
        "papa_score": int(papa_score),
        "overall_score": overall_score,
        "grade": grade,
        "signal": signal,
        "dot_d": dot_d,
        "dot_v": dot_v,
        "dot_m": dot_m,
        "dot_pattern": dot_pattern,
        "d_color": dot_d,
        "v_color": dot_v,
        "m_color": dot_m,
        "d_score": d_score,
        "v_score": v_score,
        "m_score": m_score,
        "class_name": class_name,
        "class_label": class_label,
        "gear_level": gear_level,
        "gear_display": gear_display,
        "rsi": round(curr_rsi, 1) if pd.notna(curr_rsi) else None,
        "mfi": round(curr_mfi, 1) if pd.notna(curr_mfi) else None,
        "stoch": round(curr_stoch, 1) if pd.notna(curr_stoch) else None,
        "cci": round(curr_cci, 1) if pd.notna(curr_cci) else None,
        "williams": round(curr_williams, 1) if pd.notna(curr_williams) else None,
        "volume_ratio": round(vol_ratio, 2) if pd.notna(vol_ratio) else None,
        "pe": round(pe, 1) if pe is not None and pe > 0 else None,
        "pb": round(pb, 1) if pb is not None and pb > 0 else None,
        "de": round(de, 1) if de is not None else None,
        "market_cap": fundamentals.get("marketCap"),
        "sector": fundamentals.get("sector", ""),
        "atr_pct": round(atr_pct, 1),
        "beta": round(nifty_beta, 2) if nifty_beta is not None else None,
        "silver_cross": bool(silver_cross),
        "golden_cross": bool(golden_cross or sma_golden),
        "macd_bullish": bool(macd_bullish),
        "checklist": {
            "1. Chart bottoming": bool(c1),
            "2. P/E Undervalued": bool(c2),
            "3. Price above SMA20": bool(c3),
            "4. RSI 30→35": bool(c4),
            "5. MFI 30→35": bool(c5),
            "6. MACD bullish": bool(c6),
            "7. Price/Vol/EMA": bool(c7),
            "8. Stochastic": bool(c8),
            "9. CCI 20 red": bool(c9),
            "10. William -100:-21": bool(c10),
            "11. Beta ok": bool(c11),
        },
        "checks_passed": checks_passed,
        "checks_total": checks_total,
        "factors_d": factors_d[:3],
        "factors_v": factors_v[:3],
        "factors_m": factors_m[:3],
    })


def scan_all_papa(progress_callback=None):
    global _FUNDA_SCAN_COUNT
    symbols = get_all_nse_symbols()
    total_symbols = len(symbols)
    results = []
    scanned = 0
    errors = 0

    _load_funda_cache()
    cache_size = len(_FUNDA_CACHE)
    needs_refresh = cache_size < len(symbols) * 0.5 or _FUNDA_SCAN_COUNT >= 25

    if needs_refresh:
        def cache_progress(done, total):
            if progress_callback:
                pct = done / total * 100
                progress_callback(done, total, 0, f"⏳ Fundamentals: {done}/{total} ({pct:.0f}%)")
        _download_funda_cache(symbols, progress_callback=cache_progress)

    with ThreadPoolExecutor(max_workers=CONCURRENT_WORKERS) as executor:
        fut_map = {executor.submit(analyze_papa, sym): sym for sym in symbols}

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

    _FUNDA_SCAN_COUNT += 1
    _save_funda_cache()
    results.sort(key=lambda x: x["overall_score"], reverse=True)
    return results


if __name__ == "__main__":
    start = time.time()

    def print_progress(scanned, total, qualified, errors):
        pct = (scanned / total) * 100
        elapsed = time.time() - start
        rate = scanned / elapsed if elapsed > 0 else 0
        remaining = (total - scanned) / rate if rate > 0 else 0
        eta_m, eta_s = divmod(int(remaining), 60)
        print(f"\r  [{scanned}/{total}] {pct:.0f}% | Qualified: {qualified} | Errors: {errors} | {rate:.1f}/s | ETA: {eta_m}m{eta_s}s", end="", flush=True)

    print("=" * 130)
    print("  PAPA APPROACH — D·V·M 3-Dot System + 11-Point Checklist")
    print("  By Surendra Pal Rana (fuziwaiinvesting.com)")
    print("  Scanning all NSE stocks with complete Papa methodology")
    print("=" * 130)
    print()

    results = scan_all_papa(progress_callback=print_progress)
    elapsed = time.time() - start

    print(f"\n\n{'='*150}")
    print(f"SCAN COMPLETE — {elapsed:.0f}s | {len(results)} stocks qualified")
    print(f"{'='*150}\n")

    h = f"{'Rank':<5} {'Symbol':<14} {'Price':<9} {'Grade':<5} {'Score':<6} {'Dots':<12} {'D':<5} {'V':<5} {'M':<5} {'Gear':<14} {'Checks':<7} {'Signal':<11} {'Key Factors'}"
    print(h)
    print("─" * 150)
    for i, r in enumerate(results[:20]):
        fac = []
        if r["factors_d"]: fac.append(r["factors_d"][0])
        if r["factors_m"]: fac.append(r["factors_m"][0])
        factors_str = "; ".join(fac[:2])
        checks_str = f"{r['checks_passed']}/{r['checks_total']}"
        print(f"{i+1:<5} {r['symbol']:<14} ₹{r['price']:<7} {r['grade']:<5} {r['overall_score']:<6} {r['dot_pattern']:<12} {r['d_score']:<5} {r['v_score']:<5} {r['m_score']:<5} {r['gear_display']:<14} {checks_str:<7} {r['signal']:<11} {factors_str[:60]}")

    grade_counts = {}
    for r in results:
        grade_counts[r["grade"]] = grade_counts.get(r["grade"], 0) + 1
    print(f"\nGrade distribution:")
    for g in ["A+", "A", "B", "C", "D"]:
        if grade_counts.get(g):
            print(f"  {g}: {grade_counts[g]} stocks")

    print(f"\nGenerated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
    print("⚠ Disclaimer: Educational only. Based on Surendra Pal Rana's methodology. Not investment advice.")
