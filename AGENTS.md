# Super App — Complete Context

## Project Structure
```
super-app/
├── AGENTS.md              ← You are here
├── README.md              ← Public docs
├── .gitignore
├── tiktok_downloader_web/  ← TikTok downloader (older project, separate)
│   ├── app.py              Flask backend for TikTok
│   ├── download_manager.py Parallel downloader
│   └── dubber.py           Hindi dubbing pipeline
└── trading_bot/            ← ACTIVE PROJECT — NSE Trading Bot
    ├── app.py               Flask web server (4 tabs + portfolio)
    ├── backtest.py          Walk-forward backtest + daily picks engine
    ├── nse_scanner.py       9-parameter market scanner
    ├── papa_scanner.py      Papa D·V·M 3-dot methodology scanner
    ├── investor_agent.py    Disciplined investor agent (watch mode)
    ├── validate_methodology.py Statistical methodology validation
    ├── extend_data.py       OHLCV cache refresh script
    ├── stock_bot.py         Legacy runner (may be unused)
    ├── ohlcv_cache.pkl      ~2,254 stocks, 498 trading days of OHLCV + indicators
    ├── fundamentals_cache.json Static fundamentals for ~2,375 stocks
    ├── portfolio.json       Server-side portfolio holdings (created on use)
    └── backtest_results/    Walk-forward backtest output
```

## Trading Bot — Architecture

### Data Flow
1. **OHLCV Cache** (`ohlcv_cache.pkl`): Pre-computed DataFrame per stock with ~40 technical indicators (RSI, MACD, BB, ATR, MFI, Stoch, CCI, Williams %R, forward returns Fwd_1d/3d/5d/10d). Created by `_precompute_indicators()` in `backtest.py`. Updated manually via `extend_data.py`.
2. **Fundamentals Cache** (`fundamentals_cache.json`): P/E, ROE, D/E, market cap, etc. Fetched from Google Finance + Tapetide API via `papa_scanner.py`. Auto-refreshes during Papa scans.
3. **Live Scanners** (Market + Papa tabs): Fetch fresh OHLCV data per stock on every scan. Do NOT use the pickle cache.
4. **Daily Picks + Portfolio tabs**: Use the pickle cache (static until manually refreshed).

### Key Components

#### `app.py` — Flask Web Server
- Routes: `/` (Market Scanner), `/papa` (Papa Approach), `/both` (Combined), `/picks` (Daily Picks), `/portfolio` (Portfolio)
- All HTML/JS inline as Python strings (no Jinja templates)
- API endpoints: `/api/market/*`, `/api/papa/*`, `/api/both/*`, `/api/picks/*`, `/api/portfolio/*`
- Background threads for scans (market/papa take ~30s each)

#### `backtest.py` (~2126 lines) — Core Engine
- **`load_data()`**: Loads pickle cache, downloads if missing
- **`_precompute_indicators()`**: 40+ technical indicators + forward returns per stock
- **`run_single_day_backtest()`**: Runs both scanners for a single date
- **`compare_ranking_strategies()`**: Tests 8 ranking methods (blended, composite, eigen, momentum, quality, value, DVM, short_term)
- **`get_daily_picks()`**: Main entry for Daily Picks. Takes params dict with regime-aware defaults. Returns ranked picks with fundamentals, confidence, sizing, stop loss, transaction costs.
- **`compute_short_term_score()`**: Short-term momentum scoring
- **`apply_transaction_costs()`**: STT (0.1%), brokerage (0.02%), slippage (0.3-0.5%)
- **Regime detection**: risk_on/neutral/cautious/risk_off based on Nifty 200SMA + distance from high
- **Dynamic stop loss**: `-max(2.5%, expected_return × 2)`
- 498 trading days of OHLCV data (Jun 2024 - Jun 2026)

#### `nse_scanner.py` — Market Scanner
- 9 parameters: RSI, MACD, Bollinger Bands, Trend, Volume, Momentum, Volatility, Reversal, Upside
- Scans all NSE stocks concurrently (50 workers)
- Returns grade (A+ to E), score (0-30), signal (STRONG BUY to CAUTION)
- Regime-aware scoring

#### `papa_scanner.py` — Papa D·V·M Scanner
- Based on Surendra Pal Rana's methodology (fuziwaiinvesting.com)
- D (Durability) 🟢>55/🟡35-55/🔴<35, V (Valuation) 🟢≥50/🟡30-50/🔴<30, M (Momentum) 🟢>60/🟡35-60/🔴<35
- 11-point checklist: Chart, P/E low, Mom 30→35, RSI 30→35, MFI 30→35, MACD ↑, Price/Vol/EMA, Stoch, CCI red, Will -100:-21, Beta ok
- 27 dot patterns classified into lifecycle stages: ICU → Conscious → Recovery Watch → Pre-Entry Ready → Gear 1 → Gear 2 → Top Gear → SELL → Free Fall
- Computes gear level (1-7+), overall score (0-100)

#### `investor_agent.py` — Disciplined Investor
- Questions the algorithm until it would invest its own ₹5,000
- `critique_algorithm()`: 8 methodological concerns printed on each scan
- `evaluate()`: Per-pick scoring against strict criteria
- `watch()`: Loop checking every 10s, re-scanning hourly
- Acceptance: expected 1d ≥ 4.5% (risk_off) or ≥ 3% (normal), P/E < 30, ROE > 10%, D/E < 1.5, 2+ qualifying picks, R/R ≥ 1:1
- Currently running at PID (check `ps aux | grep investor`)

#### `validate_methodology.py` — Statistical Validation
- 6 tests: Random baseline (z-score), ranking circularity, forward return consistency, regime stability, selection bias, parameter robustness
- Believability score 0-100
- Run: `python3 validate_methodology.py`

### Web UI Tabs
| Tab | Route | Scanner | Data Source | Speed |
|-----|-------|---------|------------|-------|
| Market Scanner | `/` | `nse_scanner.py` | Live fetch per stock | ~30s |
| Papa Approach | `/papa` | `papa_scanner.py` | Live fetch per stock | ~30s |
| Both | `/both` | Both sequentially | Live fetch | ~60s |
| Daily Picks | `/picks` | `backtest.py get_daily_picks()` | Pickle cache | ~5s |
| Portfolio | `/portfolio` | `api/portfolio/analyze` | Pickle cache | ~3s |

### Daily Picks Methodology
1. Detect market regime (risk_on/off/neutral/cautious from Nifty)
2. Dual scan: strict (D=green filter, top 3) + relaxed (15+ candidates)
3. Strict picks get ★ gold star + highlighted row
4. Each pick shows: market score, papa overall, DVM dots, gear, 11-point checklist, expected 1d/5d, net returns after costs, fundamentals (P/E, ROE, D/E, market cap), position sizing, dynamic stop loss
5. Transaction costs: STT 0.1% + brokerage 0.02% + slippage 0.3-0.5%
6. Blended ranking: `composite_score + max(0, fwd_1d × 50) - max(0, -fwd_1d × 150)`
7. ALGORITHM CRITIQUE: 8 methodological concerns printed per scan (circular ranking, regime overfitting, survivorship bias, etc.)

### Portfolio Tab
- Server-side persistence via `portfolio.json`
- Add holdings: symbol, qty, buy price, note
- Table: current price, P&L, market signal, papa signal, DVM dots, expected 1d, advice (BUY/HOLD/SELL/WATCH)
- Summary: invested, value, P&L, best/worst, advice breakdown
- Auto-refreshes analysis every 60s from cache

### Known Issues
1. **Data staleness**: `ohlcv_cache.pkl` is static — use `extend_data.py` to refresh. Live scanner tabs (Market/Papa) always fetch fresh data.
2. **Circular ranking**: Blended ranking formula uses forward returns, creating data leakage. Top picks guaranteed to have positive forward returns by construction.
3. **Network**: TikTok blocked → tikwm.com proxy. NSE/BSE APIs blocked → yfinance fallback.
4. **yfinance threading**: Concurrent downloads corrupt ~52% of data — use `_yahoo_direct_history` as primary.
5. **Flask debug**: Threading issues with `debug=True` — use `debug=False`.
6. **5d estimates**: On last cached date, Fwd_5d is NaN (5 days ahead doesn't exist). Falls back to per-stock historical average.
7. **OHLCV cache missing DVM scores**: DVM scores computed live by `papa_scanner.py`, not stored in cache. Portfolio analyzer uses simplified heuristic.

### Running
```bash
# Start Flask server (port 5000)
cd trading_bot && python3 app.py 5000

# Start investor agent watch mode
cd trading_bot && python3 investor_agent.py

# Refresh OHLCV cache (takes ~30 min)
cd trading_bot && python3 extend_data.py

# Validate methodology
cd trading_bot && python3 validate_methodology.py
```

### Network Constraints
- TikTok blocked → tikwm.com API proxy
- yt-dlp/TikTok direct → use `download_video_tikwm()`
- NSE/BSE APIs → 403/Cloudflare blocked, yfinance/#_yahoo_direct_history fallback
- Flask `send_file()` → resolves relative to `app.root_path`, not CWD. Use `.resolve()`.
- Network speed ~3-4 MB/s for downloads

### Key Backtest Results (498 trading days, blended top 3)
- 1d avg: +4.13% (81% win rate)
- 5d avg: +5.80% (66% win rate)
- WARNING: Inflation suspected due to circular ranking (uses forward returns in formula)
- 474 events in backtest, 75-87% confidence interval

### Deployment
- Flask server, NOT static — cannot deploy to surge.sh
- Recommended: Render.com (free tier, auto-deploys from GitHub)
- Config: `runtime.txt` (Python 3.9.6), `requirements.txt`, `render.yaml` or `Dockerfile`
