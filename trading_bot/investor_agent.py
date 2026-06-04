#!/usr/bin/env python3
"""
Disciplined Investor Agent — questions picks daily until it would invest its own money.

Criteria (hardened from 4 rounds of investor rejection):
  1. Expected 1d ≥ 3% (high conviction, not noise)
  2. Fwd_5d must be cached (not backtest estimate)
  3. Net expected return > 0 after transaction costs
  4. Reward/risk ratio ≥ 1:1 on some horizon
  5. Fundamentals: P/E < 30, ROE > 10%, D/E < 1.5
  6. Can buy ≥ 1 full share per pick
  7. Max 60% of portfolio in any single position
  8. At least 2 qualifying picks (diversification)
  9. Respect regime: risk_off requires higher conviction
"""
import os, sys, json, time, urllib.request
from datetime import datetime

BASE_URL = "http://127.0.0.1:5000"
PORTFOLIO = 5000

# Minimum criteria per pick
MIN_EXPECTED_1D = 3.0        # 3% minimum 1d expected return
MIN_NET_1D = 2.5             # 2.5% net after costs
MIN_RR_5D = 1.0              # reward/risk >= 1:1 on 5d
MAX_PE = 30
MIN_ROE = 10.0               # percent
MAX_DE = 1.5
MAX_SINGLE_POSITION_PCT = 60  # max % of portfolio in one stock
MIN_QUALIFYING_PICKS = 2

# Risk_off is stricter
RISK_OFF_MULTIPLIER = 1.5    # need 1.5x the expected return in risk_off

# Track whether we've done algorithm critique
_algorithm_critique_cache = None


def critique_algorithm():
    """
    Meta-critique of the algorithm itself — not market data, but methodology.
    Runs once, caches the result. Returns list of methodological concerns.
    Each concern: { "issue": str, "severity": str, "explanation": str }
    """
    global _algorithm_critique_cache
    if _algorithm_critique_cache is not None:
        return _algorithm_critique_cache

    concerns = []
    try:
        import sys
        sys.path.insert(0, os.path.join(os.path.dirname(__file__)))
        from backtest import load_data
        
        all_data = load_data()
        ref_sym = list(all_data.keys())[0]
        ref_df = all_data[ref_sym]
        fwd = ref_df["Fwd_1d"].dropna()
        n_days = len(fwd)
        n_stocks = len(all_data)

        # 1. Look-ahead bias
        last_fwd = fwd.index[-1]
        last_close = ref_df["Close"].dropna().index[-1]
        concerns.append({
            "issue": "Forward returns assume same-day fill at close",
            "severity": "medium",
            "explanation": f"Fwd_1d = shift(-1) of Close. Last trade: {str(last_close.date())}, last Fwd: {str(last_fwd.date())}. Assumes buying at today's close and selling at tomorrow's close. In reality, fills happen at next open with gap risk. 0.5-1% overnight gap can eat the entire expected edge."
        })

        # 2. Ranking circularity
        concerns.append({
            "issue": "Blended ranking uses forward returns in its formula",
            "severity": "high",
            "explanation": "The blended score is: composite - max(0, -fwd_1d × 150) + max(0, fwd_1d × 50). This penalizes stocks with negative Fwd_1d and boosts those with positive Fwd_1d. By construction, the TOP-ranked picks will have POSITIVE forward returns. The ranking already knows the answer — this inflates backtest vs any strategy that ranks on independent signals."
        })

        # 3. Sample size
        concerns.append({
            "issue": "Statistical significance of 81% win rate",
            "severity": "medium",
            "explanation": f"Top-3 picks over {n_days} trading days = {n_days*3} events. At 81% win rate: ~{int(n_days*3*0.81)} winners, ~{int(n_days*3*0.19)} losers. The 95% binomial confidence interval spans roughly 75-87%. That's a 12% range — not precise enough for confident capital allocation."
        })

        # 4. Regime overfitting
        concerns.append({
            "issue": "Regime parameters were tuned in-sample",
            "severity": "high",
            "explanation": "D=green filter in risk_off, papa_reg_penalty=3, market_reg_penalty=1, SMA200 threshold for regime detection — all tuned on the same 498-day data. The walk-forward test period (Jan-May 2026) is only 5 months of 1 regime (bear market). Needs true out-of-sample testing on unseen market cycles."
        })

        # 5. Survivorship bias
        concerns.append({
            "issue": "Dead stocks are missing from the cache",
            "severity": "high",
            "explanation": f"OHLCV cache has {n_stocks} stocks that exist TODAY. Stocks delisted, bankrupt, or merged during 2024-2026 are excluded. These would be WORST performers. Backtest misses the left tail of the distribution — the stocks that went to zero."
        })

        # 6. D=green filter concentration
        concerns.append({
            "issue": "D=green filter creates untenable concentration",
            "severity": "medium",
            "explanation": f"In risk_off, only ~3 stocks pass both scanners + D=green filter out of {n_stocks} — that's 0.13% of the market. A single stock can wipe out days of gains. No position sizing can fix a portfolio of 3 stocks where 1 goes -10%."
        })

        # 7. Backtest improvement is suspiciously large
        concerns.append({
            "issue": "Blended ranking's 2.4x improvement over composite is suspicious",
            "severity": "high",
            "explanation": "Changing ONLY the ranking method (not what stocks you pick, just HOW you order them) improved 5d returns from +1.52% to +3.64%. That's a 2.4x improvement from re-ranking the SAME candidates. This is possible IF the ranking uses information correlated with future returns — which blended does (it uses forward returns). This is effectively data leakage."
        })

        # 8. Forward return computation
        concerns.append({
            "issue": "Fwd_returns use raw Close, not adjusted close",
            "severity": "medium",
            "explanation": "If Fwd_1d is computed from Close (not Adjusted Close), corporate actions (dividends, stock splits, rights issues) will distort returns. A 5% stock dividend appears as a -4.76% drop, not an economic loss. The yahoo_direct_history uses adjclose for the DataFrame Close, but verify: yfinance's auto_adjust=True is used in fallback."
        })

        _algorithm_critique_cache = sorted(concerns, key=lambda x: {"high": 0, "medium": 1, "low": 2}[x["severity"]])
    except Exception as e:
        import traceback
        _algorithm_critique_cache = [{
            "issue": f"Algorithm critique error: {e}",
            "severity": "low",
            "explanation": traceback.format_exc()
        }]
    
    return _algorithm_critique_cache


def fetch_picks():
    """Get today's picks from the running server."""
    try:
        req = urllib.request.Request(f"{BASE_URL}/api/picks/start", method="POST")
        resp = urllib.request.urlopen(req, timeout=30)
        scan_id = json.loads(resp.read())["scan_id"]
        # Poll for completion
        for _ in range(60):
            time.sleep(1)
            req = urllib.request.Request(f"{BASE_URL}/api/picks/progress/{scan_id}")
            resp = urllib.request.urlopen(req, timeout=10)
            status = json.loads(resp.read())
            if status.get("status") == "done":
                break
            if status.get("status") == "error":
                return None, f"Scan error: {status.get('error', 'unknown')}"
        else:
            return None, "Scan timed out after 60s"
        # Get results
        req = urllib.request.Request(f"{BASE_URL}/api/picks/results/{scan_id}")
        resp = urllib.request.urlopen(req, timeout=10)
        result = json.loads(resp.read())
        return result, None
    except Exception as e:
        return None, str(e)


def evaluate_pick(p, regime):
    """Score a single pick against all criteria. Returns (pass: bool, reasons: list)."""
    fails = []
    e1 = p.get("expected_1d")
    ne1 = p.get("net_expected_1d")
    e5 = p.get("expected_5d")
    e5_est = p.get("expected_5d_estimated", False)
    f = p.get("fundamentals", {})
    s = p.get("sizing", {})
    costs = p.get("transaction_costs", {})

    multiplier = RISK_OFF_MULTIPLIER if regime == "risk_off" else 1.0
    min_e1 = MIN_EXPECTED_1D * multiplier

    # 1. Expected 1d must be >= threshold
    if e1 is None:
        fails.append(f"expected_1d=null")
    elif e1 < min_e1:
        fails.append(f"expected_1d={e1}% < {min_e1}% (need {multiplier:.0f}x in {regime})")

    # 2. Net expected return must be positive
    if ne1 is None or ne1 <= 0:
        fails.append(f"net_expected_1d={ne1}% not positive after costs")

    # 3. Fwd_5d must be cached, not estimated
    if e5 is None:
        fails.append("expected_5d=null")
    elif e5_est:
        fails.append("expected_5d=estimated (need cached data)")

    # 4. Reward/risk >= 1:1 on 5d
    stop = abs(s.get("stop_loss_pct", 0))
    if e5 and stop > 0:
        rr = e5 / stop
        if rr < MIN_RR_5D:
            fails.append(f"5d R/R={rr:.2f}:1 < {MIN_RR_5D}:1")

    # 5. Fundamentals
    pe = f.get("pe")
    roe = f.get("roe")
    de = f.get("debt_to_equity")
    if pe and pe > MAX_PE:
        fails.append(f"P/E={pe}x > {MAX_PE}x")
    if roe is not None and roe < MIN_ROE:
        fails.append(f"ROE={roe}% < {MIN_ROE}%")
    if de is not None and de > MAX_DE:
        fails.append(f"D/E={de} > {MAX_DE}")

    # 6. Can buy at least 1 share
    shares = s.get("suggested_shares", 0)
    if shares < 1:
        fails.append(f"0 shares (can't afford 1 lot at ₹{p.get('price',0)})")

    return len(fails) == 0, fails


def build_plan(qualifying, portfolio, regime):
    """Build an investment plan from qualifying picks."""
    total_qualifying = len(qualifying)
    if total_qualifying == 0:
        return None
    plan = []
    # Equal-weight among qualifying picks, but cap at 60% each
    per_position = min(portfolio / total_qualifying, portfolio * MAX_SINGLE_POSITION_PCT / 100)
    remaining = portfolio
    for p in qualifying:
        price = p["price"]
        budget = min(per_position, remaining)
        shares = int(budget // price)
        actual = round(shares * price, 0)
        if shares < 1:
            continue
        plan.append({
            "symbol": p["symbol"],
            "price": price,
            "shares": shares,
            "allocation": actual,
            "pct": round(actual / portfolio * 100, 1),
            "expected_1d": p.get("expected_1d"),
            "expected_5d": p.get("expected_5d"),
            "net_expected_1d": p.get("net_expected_1d"),
            "stop_loss_pct": p.get("sizing", {}).get("stop_loss_pct"),
            "pe": p.get("fundamentals", {}).get("pe"),
            "roe": p.get("fundamentals", {}).get("roe"),
        })
        remaining -= actual
    return {
        "total_invested": round(portfolio - remaining, 0),
        "idle_cash": round(remaining, 0),
        "positions": plan,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "regime": regime,
    }


def evaluate(fetch_new=True, picks_data=None):
    """
    Main evaluation. Returns dict with:
      - satisfied: bool
      - reasons: list of why not
      - plan: investment plan dict or None
      - conditions: what needs to change

    If picks_data is provided, evaluates that data directly (no fetch).
    If fetch_new=True and no picks_data, fetches from server.
    """
    if picks_data is not None:
        result = picks_data
    elif fetch_new:
        result, error = fetch_picks()
        if error:
            return {"satisfied": False, "reasons": [f"Server error: {error}"], "plan": None, "conditions": ["Server must be running"]}
        if not result or not result.get("picks"):
            return {"satisfied": False, "reasons": ["No picks generated today"], "plan": None, "conditions": ["System must produce at least 1 pick"]}
    else:
        raise ValueError("fetch_new=False requires picks_data to be provided")

    picks = result["picks"]
    regime = result.get("regime", "unknown")
    as_of = result.get("as_of_date", "unknown")

    output = {
        "satisfied": False,
        "date": datetime.now().strftime("%Y-%m-%d"),
        "as_of_date": as_of,
        "regime": regime,
        "total_picks": len(picks),
        "reasons": [],
        "conditions": [],
        "plan": None,
        "pick_scores": [],
    }

    # Evaluate each pick
    qualifying = []
    for p in picks:
        passes, fails = evaluate_pick(p, regime)
        score = {
            "symbol": p["symbol"],
            "price": p["price"],
            "passes": passes,
            "fails": fails,
            "expected_1d": p.get("expected_1d"),
            "net_expected_1d": p.get("net_expected_1d"),
            "expected_5d": p.get("expected_5d"),
            "expected_5d_estimated": p.get("expected_5d_estimated", False),
            "stop_loss": p.get("sizing", {}).get("stop_loss_pct"),
            "fundamentals": p.get("fundamentals", {}),
        }
        output["pick_scores"].append(score)
        if passes:
            qualifying.append(p)

    output["qualifying_count"] = len(qualifying)

    # Check portfolio-level criteria
    portfolio_fails = []

    # Must have at least MIN_QUALIFYING_PICKS qualifying picks
    if len(qualifying) < MIN_QUALIFYING_PICKS:
        portfolio_fails.append(f"only {len(qualifying)} qualifying picks (need {MIN_QUALIFYING_PICKS})")

    # Max single position check (handled in build_plan)

    all_fails = portfolio_fails + [f for s in output["pick_scores"] for f in s["fails"]]

    if all_fails:
        output["reasons"] = all_fails
        # Build conditions for what needs to change
        conditions = set()
        for f in all_fails:
            if "expected_1d" in f:
                conditions.add("Wait for higher expected 1d (≥ 3%) — typically 1-2 days after a sharp selloff")
            if "estimated" in f:
                conditions.add("Wait for cached 5d forward data — system needs more trading days to populate")
            if "R/R" in f:
                conditions.add("Stop loss too wide relative to expected gain — reduce position or wait for higher conviction")
            if "P/E" in f or "ROE" in f or "D/E" in f:
                conditions.add("Find stocks with better fundamentals (P/E < 30, ROE > 10%, D/E < 1.5)")
            if "shares" in f:
                conditions.add("Build larger portfolio or find lower-priced stocks that pass all filters")
            if "positive" in f:
                conditions.add("Net expected return must exceed transaction costs — wait for a stronger signal day")
        output["conditions"] = sorted(conditions)
    else:
        output["satisfied"] = True
        output["reasons"] = []
        output["conditions"] = []
        output["plan"] = build_plan(qualifying, PORTFOLIO, regime)

    return output


def watch(interval_seconds=10, rescan_interval_seconds=3600, notify_callback=None):
    """
    Run the agent in a loop, re-evaluating cached result every `interval_seconds`.
    Re-scans the server every `rescan_interval_seconds` to pick up new data.
    Stops when the agent is satisfied.
    """
    print(f"\n{'='*60}")
    print(f"  INVESTOR AGENT — watching for high-conviction setup")
    print(f"  Portfolio: ₹{PORTFOLIO:,}  |  Check interval: {interval_seconds}s")
    print(f"  Re-scan interval: {rescan_interval_seconds}s")
    print(f"  Criteria: 1d ≥ {MIN_EXPECTED_1D}%  |  Net > 0  |  R/R ≥ {MIN_RR_5D}:1")
    print(f"  Fundamentals: P/E < {MAX_PE}  ROE > {MIN_ROE}%  D/E < {MAX_DE}")
    print(f"{'='*60}")

    iteration = 0
    last_scan_time = 0
    cached_result = None
    algo_critique_shown = False

    while True:
        iteration += 1
        now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # Re-scan only if enough time has passed since last scan
        if cached_result is None or time.time() - last_scan_time >= rescan_interval_seconds:
            print(f"\n[{now}] 🔄 Scanning for new picks...")
            result = evaluate(fetch_new=True)
            cached_result = result
            last_scan_time = time.time()

            # Show algorithm critique on each scan (it's cached, instant)
            if not algo_critique_shown:
                algo_critique_shown = True
            concerns = critique_algorithm()
            if concerns:
                print(f"\n  ⚠️  ALGORITHM CONCERNS ({len(concerns)} issues):")
                for c in concerns:
                    badge = {"high": "🔴", "medium": "🟡", "low": "🔵"}.get(c["severity"], "⚪")
                    print(f"  {badge} [{c['severity'].upper()}] {c['issue']}")
                    print(f"     {c['explanation']}")
        else:
            result = cached_result

        print(f"[{now}] #{iteration}  |  Picks: {result['total_picks']}  |  Qualifying: {result['qualifying_count']}  |  Regime: {result['regime']}")

        if result["satisfied"]:
            plan = result["plan"]
            print(f"\n{'='*60}")
            print(f"  ✅ AGENT IS SATISFIED — INVESTING NOW")
            print(f"{'='*60}")
            print(f"  Date: {plan['date']}  |  Regime: {plan['regime']}")
            print(f"  Total invested: ₹{plan['total_invested']:,.0f}  |  Idle cash: ₹{plan['idle_cash']:,.0f}")
            for pos in plan["positions"]:
                print(f"\n  {pos['symbol']:<14} {pos['shares']} sh × ₹{pos['price']:<8} = ₹{pos['allocation']:,.0f} ({pos['pct']}%)")
                print(f"    Expected 1d: {pos['expected_1d']}%  |  5d: {pos['expected_5d']}%  |  Stop: {pos['stop_loss_pct']}%")
                print(f"    P/E: {pos['pe']}x  ROE: {pos['roe']}%")
            print(f"\n  ✅ INVESTING ₹{plan['total_invested']:,.0f} of ₹{PORTFOLIO:,}")
            if notify_callback:
                notify_callback(plan)
            return plan

        print(f"  ❌ Not satisfied. {len(result['reasons'])} reasons:")
        for r in result["reasons"][:5]:
            print(f"     • {r}")
        if result.get("conditions"):
            for c in result["conditions"]:
                print(f"     → {c}")

        # Wait before next check
        try:
            time.sleep(interval_seconds)
        except KeyboardInterrupt:
            print("\n  Stopped by user.")
            return None


def main():
    """CLI entry point."""
    import argparse
    parser = argparse.ArgumentParser(description="Disciplined Investor Agent")
    parser.add_argument("--once", action="store_true", help="Evaluate once and exit")
    parser.add_argument("--interval", type=float, default=10, help="Check interval in seconds (default: 10)")
    parser.add_argument("--rescan", type=float, default=3600, help="Re-scan interval in seconds (default: 3600 = 1h)")
    args = parser.parse_args()

    if args.once:
        result = evaluate(fetch_new=True)
        if args.json:
            print(json.dumps(result, default=str, indent=2))
        else:
            print(f"\n{'='*60}")
            print(f"  INVESTOR AGENT — Single evaluation")
            print(f"{'='*60}")
            print(f"  Date: {result['date']}  |  Regime: {result['regime']}  |  As of: {result['as_of_date']}")
            print(f"  Picks today: {result['total_picks']}  |  Qualifying: {result['qualifying_count']}")
            if result["satisfied"]:
                plan = result["plan"]
                print(f"\n  ✅ WOULD INVEST — ₹{plan['total_invested']:,.0f} / ₹{PORTFOLIO:,}")
                for pos in plan["positions"]:
                    print(f"     {pos['shares']}× {pos['symbol']} @ ₹{pos['price']} = ₹{pos['allocation']:,.0f} ({pos['pct']}%)")
            else:
                print(f"\n  ❌ WOULD NOT INVEST")
                for r in result["reasons"]:
                    print(f"     • {r}")
                print(f"\n  Conditions needed:")
                for c in result["conditions"]:
                    print(f"     → {c}")
                print(f"\n  Re-run later: python3 {sys.argv[0]} --once")
    else:
        watch(interval_seconds=args.interval, rescan_interval_seconds=args.rescan)


if __name__ == "__main__":
    main()
