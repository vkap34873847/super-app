"""
validate_methodology.py — Agent that tests the believability of the trading methodology.

Runs statistical tests, baseline comparisons, and overfitting checks on the
backtest pipeline to determine whether the strategy has real edge or is noise.

Usage: python3 validate_methodology.py
"""
import sys, os, json, math
from datetime import datetime
import pandas as pd
import numpy as np

BASE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE)

# Supress warnings
import warnings
warnings.filterwarnings("ignore")

from backtest import load_data, run_single_day_backtest, compute_nifty_returns, get_daily_picks, rank_picks
from backtest import BACKTEST_CONFIDENCE, DEFAULT_CONFIDENCE
from nse_scanner import scan_all as scan_market
from papa_scanner import scan_all_papa


def load_cache():
    print("Loading OHLCV cache...")
    all_data = load_data()
    with open(os.path.join(BASE, "fundamentals_cache.json")) as f:
        funda_cache = json.load(f).get("data", {})
    nifty_df = _get_nifty_cached()
    nifty_returns = compute_nifty_returns(nifty_df) if nifty_df is not None else None
    return all_data, funda_cache, nifty_df, nifty_returns


def _get_nifty_cached():
    """Get Nifty data from cache."""
    from backtest import _get_nifty_df
    try:
        return _get_nifty_df()
    except Exception:
        return None


def test_random_baseline(all_data, funda_cache, nifty_df, nifty_returns, n_trials=100):
    """Compare strategy returns vs random selection from the same universe."""
    print(f"\n{'='*60}")
    print("TEST 1: Random Baseline Comparison")
    print(f"{'='*60}")

    # Find last valid date
    ref_sym = list(all_data.keys())[0]
    valid_fwd = all_data[ref_sym]["Fwd_1d"].dropna()
    as_of_date = valid_fwd.index[-1].strftime("%Y-%m-%d")
    print(f"Testing date: {as_of_date}")

    # Get strategy picks (strict scan)
    params = {"risk_off_d_filter": False, "rank_by": "blended", "top_n": 3}
    picks = get_daily_picks(as_of_date, all_data=all_data, fundamentals_cache=funda_cache,
                            nifty_df=nifty_df, nifty_returns=nifty_returns, params=params)
    strat_1d = [p.get("expected_1d") or 0 for p in picks]
    strat_avg = np.mean(strat_1d) if strat_1d else 0
    print(f"  Strategy avg expected 1d: {strat_avg:+.2f}%")

    # Random selection: pick 3 random stocks that have Fwd_1d data
    symbols_with_data = [s for s, df in all_data.items()
                         if df is not None and "Fwd_1d" in df.columns and df["Fwd_1d"].dropna().iloc[-1] is not None
                         and not pd.isna(df["Fwd_1d"].dropna().iloc[-1])]
    print(f"  Universe: {len(symbols_with_data)} stocks with data")

    random_avgs = []
    for _ in range(n_trials):
        syms = np.random.choice(symbols_with_data, size=min(3, len(symbols_with_data)), replace=False)
        returns = []
        for s in syms:
            df = all_data[s]
            f1 = df["Fwd_1d"].dropna()
            if len(f1) > 0:
                returns.append(float(f1.iloc[-1]) * 100)
        if returns:
            random_avgs.append(np.mean(returns))

    if random_avgs:
        random_mean = np.mean(random_avgs)
        random_std = np.std(random_avgs)
        random_pctile = sum(1 for r in random_avgs if r >= strat_avg) / len(random_avgs) * 100
        z_score = (strat_avg - random_mean) / random_std if random_std > 0 else 0

        print(f"\n  Random baseline ({n_trials} trials):")
        print(f"    Mean: {random_mean:+.2f}%")
        print(f"    Std:  {random_std:.2f}%")
        print(f"    Strategy rank: {random_pctile:.1f}th percentile")
        print(f"    Z-score vs random: {z_score:.2f}")
        print(f"    P-value (one-tailed): {1 - (sum(1 for r in random_avgs if r < strat_avg) / len(random_avgs)):.4f}")

        if z_score >= 2:
            print(f"  ✅ Strategy beats random with high confidence (z={z_score:.2f})")
        elif z_score >= 1:
            print(f"  ⚠️  Strategy beats random but modestly (z={z_score:.2f})")
        else:
            print(f"  ❌ Strategy NOT significantly better than random (z={z_score:.2f})")
    else:
        print("  Could not compute random baseline")

    return {"strat_avg_1d": strat_avg, "random_mean": random_mean if random_avgs else None,
            "random_std": random_std if random_avgs else None, "z_score": z_score if random_avgs else None,
            "percentile": random_pctile if random_avgs else None}


def test_ranking_circularity(all_data, funda_cache, nifty_df, nifty_returns):
    """Test if blended ranking creates circularity (uses forward returns in formula)."""
    print(f"\n{'='*60}")
    print("TEST 2: Ranking Circularity Check")
    print(f"{'='*60}")

    ref_sym = list(all_data.keys())[0]
    valid_fwd = all_data[ref_sym]["Fwd_1d"].dropna()
    as_of_date = valid_fwd.index[-1].strftime("%Y-%m-%d")

    # Compare blended vs composite ranking
    for rank_method in ["composite", "blended"]:
        params = {"risk_off_d_filter": False, "rank_by": rank_method, "top_n": 10}
        picks = get_daily_picks(as_of_date, all_data=all_data, fundamentals_cache=funda_cache,
                                nifty_df=nifty_df, nifty_returns=nifty_returns, params=params)
        avg_1d = np.mean([p.get("expected_1d") or 0 for p in picks]) if picks else 0
        avg_score = np.mean([p.get("_rank_score") or 0 for p in picks]) if picks else 0
        print(f"  {rank_method:>10}: avg 1d={avg_1d:+.2f}%  avg score={avg_score:.1f}  n={len(picks)}")

    # Test: correlation between rank position and forward return
    params_raw = {"risk_off_d_filter": False, "rank_by": "composite", "top_n": 100}
    picks_all = get_daily_picks(as_of_date, all_data=all_data, fundamentals_cache=funda_cache,
                                nifty_df=nifty_df, nifty_returns=nifty_returns, params=params_raw)
    if len(picks_all) >= 10:
        returns = [p.get("expected_1d") or 0 for p in picks_all[:50]]
        positions = list(range(len(returns)))
        corr = np.corrcoef(positions, returns)[0, 1] if len(set(returns)) > 1 else 0
        print(f"  Correlation rank position vs 1d return: {corr:.4f}")
        if abs(corr) > 0.3:
            print(f"  ⚠️ Strong correlation ({corr:.3f}) — ranking may be circular")
        else:
            print(f"  ✅ Weak correlation ({corr:.3f}) — ranking is picking real signal")
    else:
        corr = 0

    return {"correlation": corr}


def test_forward_return_consistency(all_data):
    """Test if forward returns are consistent across time."""
    print(f"\n{'='*60}")
    print("TEST 3: Forward Return Consistency")
    print(f"{'='*60}")

    # Sample 50 random stocks and check their forward return distributions
    symbols = list(all_data.keys())
    np.random.seed(42)
    sample = np.random.choice(symbols, size=min(50, len(symbols)), replace=False)

    all_f1, all_f5 = [], []
    for s in sample:
        df = all_data[s]
        f1 = df["Fwd_1d"].dropna().values
        f5 = df["Fwd_5d"].dropna().values
        all_f1.extend(f1)
        all_f5.extend(f5)

    if all_f1:
        f1_arr = np.array(all_f1) * 100
        print(f"  Fwd_1d distribution across {len(sample)} stocks:")
        print(f"    Mean: {np.mean(f1_arr):+.2f}%")
        print(f"    Median: {np.median(f1_arr):+.2f}%")
        print(f"    Std: {np.std(f1_arr):.2f}%")
        print(f"    Skew: {pd.Series(f1_arr).skew():.2f}")
        print(f"    % positive: {np.mean(f1_arr > 0) * 100:.1f}%")
        # Test if mean is significantly different from 0
        t_stat = np.mean(f1_arr) / (np.std(f1_arr) / np.sqrt(len(f1_arr)))
        print(f"    T-stat (mean != 0): {t_stat:.2f}")
        print(f"    {'✅ Significantly non-zero' if abs(t_stat) > 2 else '❌ Could be noise'}")

    if all_f5:
        f5_arr = np.array(all_f5) * 100
        print(f"  Fwd_5d distribution:")
        print(f"    Mean: {np.mean(f5_arr):+.2f}%")
        print(f"    Median: {np.median(f5_arr):+.2f}%")
        print(f"    Std: {np.std(f5_arr):.2f}%")
        print(f"    % positive: {np.mean(f5_arr > 0) * 100:.1f}%")

    return {"mean_f1": float(np.mean(f1_arr)) if all_f1 else 0,
            "t_stat": float(t_stat) if all_f1 and len(f1_arr) > 1 else 0,
            "pct_positive": float(np.mean(f1_arr > 0) * 100) if all_f1 else 0,
            "std_f1": float(np.std(f1_arr)) if all_f1 else 0}


def test_regime_stability(all_data, funda_cache, nifty_df, nifty_returns):
    """Test if strategy works across different market regimes."""
    print(f"\n{'='*60}")
    print("TEST 4: Regime Stability")
    print(f"{'='*60}")

    regimes = ["risk_on", "neutral", "cautious", "risk_off"]
    results = {}

    for regime in regimes:
        params = {"regime": regime, "risk_off_d_filter": True if regime == "risk_off" else False,
                  "rank_by": "blended", "top_n": 5}
        ref_sym = list(all_data.keys())[0]
        valid_fwd = all_data[ref_sym]["Fwd_1d"].dropna()
        # Use a mid-point date
        mid_idx = len(valid_fwd) // 2
        as_of_date = valid_fwd.index[mid_idx].strftime("%Y-%m-%d")

        picks = get_daily_picks(as_of_date, all_data=all_data, fundamentals_cache=funda_cache,
                                nifty_df=nifty_df, nifty_returns=nifty_returns, params=params)
        if picks:
            avg = np.mean([p.get("expected_1d") or 0 for p in picks])
            n = len(picks)
            results[regime] = {"avg_1d": avg, "n": n}
            print(f"  {regime:>10}: avg 1d={avg:+.2f}%  n={n}")
        else:
            results[regime] = {"avg_1d": 0, "n": 0}
            print(f"  {regime:>10}: NO PICKS")

    if results:
        avgs = [r["avg_1d"] for r in results.values() if r["n"] > 0]
        if len(avgs) >= 2:
            regime_std = np.std(avgs)
            print(f"  Cross-regime std: {regime_std:.2f}%")
            if regime_std > 3:
                print(f"  ⚠️ High regime sensitivity (std={regime_std:.2f}) — overfitting likely")
            else:
                print(f"  ✅ Reasonably stable across regimes (std={regime_std:.2f})")

    return results


def test_data_snooping(all_data, funda_cache, nifty_df, nifty_returns):
    """Test if top N performance is just selection bias."""
    print(f"\n{'='*60}")
    print("TEST 5: Selection Bias / Data Snooping")
    print(f"{'='*60}")

    ref_sym = list(all_data.keys())[0]
    valid_fwd = all_data[ref_sym]["Fwd_1d"].dropna()
    as_of_date = valid_fwd.index[-1].strftime("%Y-%m-%d")

    for top_n in [1, 3, 5, 10, 20]:
        params = {"risk_off_d_filter": False, "rank_by": "blended", "top_n": top_n}
        picks = get_daily_picks(as_of_date, all_data=all_data, fundamentals_cache=funda_cache,
                                nifty_df=nifty_df, nifty_returns=nifty_returns, params=params)
        if picks:
            avg = np.mean([p.get("expected_1d") or 0 for p in picks])
            # Also check win rate
            wins = sum(1 for p in picks if (p.get("expected_1d") or 0) > 0)
            wr = wins / len(picks) * 100 if picks else 0
            print(f"  Top {top_n:2d}: avg 1d={avg:+.2f}%  win rate={wr:.0f}%")
        else:
            print(f"  Top {top_n:2d}: no picks")

    # Key test: does the edge persist beyond top 3?
    params3 = {"risk_off_d_filter": False, "rank_by": "blended", "top_n": 3}
    picks3 = get_daily_picks(as_of_date, all_data=all_data, fundamentals_cache=funda_cache,
                             nifty_df=nifty_df, nifty_returns=nifty_returns, params=params3)
    params20 = {"risk_off_d_filter": False, "rank_by": "blended", "top_n": 20}
    picks20 = get_daily_picks(as_of_date, all_data=all_data, fundamentals_cache=funda_cache,
                              nifty_df=nifty_df, nifty_returns=nifty_returns, params=params20)
    if picks3 and picks20:
        avg3 = np.mean([p.get("expected_1d") or 0 for p in picks3])
        avg20 = np.mean([p.get("expected_1d") or 0 for p in picks20])
        ratio = avg3 / avg20 if avg20 != 0 else 0
        print(f"\n  Top 3 vs Top 20 ratio: {ratio:.2f}x")
        if ratio > 3:
            print(f"  ⚠️ Large gap ({ratio:.1f}x) — edge is concentrated in top picks, noise likely in tail")
        elif ratio > 1.5:
            print(f"  ✅ Edge degrades gracefully ({ratio:.1f}x) — consistent ranking")
        else:
            print(f"  ❌ Top picks similar to broader set — ranking adds little value")
    else:
        ratio = 0

    return {"top3_top20_ratio": ratio}


def test_feature_robustness(all_data, funda_cache, nifty_df, nifty_returns):
    """Test if small parameter changes drastically change results."""
    print(f"\n{'='*60}")
    print("TEST 6: Parameter Robustness")
    print(f"{'='*60}")

    ref_sym = list(all_data.keys())[0]
    valid_fwd = all_data[ref_sym]["Fwd_1d"].dropna()
    as_of_date = valid_fwd.index[-1].strftime("%Y-%m-%d")

    configs = [
        ("Default (blended)", {"rank_by": "blended", "top_n": 3}),
        ("Composite only", {"rank_by": "composite", "top_n": 3}),
        ("Eigen only", {"rank_by": "eigen", "top_n": 3}),
        ("No D filter", {"risk_off_d_filter": False, "rank_by": "blended", "top_n": 3}),
        ("Top 5", {"risk_off_d_filter": False, "rank_by": "blended", "top_n": 5}),
        ("Relaxed market", {"market_threshold": "NEUTRAL", "rank_by": "blended", "top_n": 3}),
    ]

    results = []
    for name, params in configs:
        picks = get_daily_picks(as_of_date, all_data=all_data, fundamentals_cache=funda_cache,
                                nifty_df=nifty_df, nifty_returns=nifty_returns, params=params)
        if picks:
            avg = np.mean([p.get("expected_1d") or 0 for p in picks])
            n = len(picks)
            overlap = sum(1 for p in picks if p.get("symbol") in {x.get("symbol") for x in
                          get_daily_picks(as_of_date, all_data=all_data, fundamentals_cache=funda_cache,
                                          nifty_df=nifty_df, nifty_returns=nifty_returns,
                                          params={"rank_by": "blended", "top_n": 3})})
            results.append({"config": name, "avg_1d": avg, "n": n, "overlap": overlap})
            print(f"  {name:<20}: avg 1d={avg:+.2f}%  n={n}  overlap={overlap}")

    if results:
        avgs = [r["avg_1d"] for r in results if r["n"] > 0]
        if len(avgs) >= 2:
            param_std = np.std(avgs)
            print(f"  Cross-config std: {param_std:.2f}%")
            if param_std > 2:
                print(f"  ⚠️ High parameter sensitivity (std={param_std:.2f}%) — results fragile")
            else:
                print(f"  ✅ Robust to parameter changes (std={param_std:.2f}%)")
    else:
        param_std = 0

    return {"param_std": param_std}


def compute_believability_score(results):
    """Compute an overall believability score (0-100) from all test results."""
    score = 50  # Start neutral

    # Test 1: Z-score vs random
    z = results.get("test1", {}).get("z_score", 0) or 0
    if z >= 2: score += 20
    elif z >= 1: score += 10
    elif z < 1: score -= 10

    # Test 2: Ranking circularity
    r_corr = results.get("test2", {}).get("correlation", 0) or 0
    if abs(r_corr) < 0.2: score += 10
    elif abs(r_corr) > 0.4: score -= 15

    # Test 3: Forward return nonzero
    t_stat = results.get("test3", {}).get("t_stat", 0) or 0
    if abs(t_stat) > 3: score += 10
    elif abs(t_stat) < 1: score -= 10

    # Test 4: Regime stability
    regime_std = results.get("test4", {}).get("regime_std")
    if regime_std and regime_std < 2: score += 10
    elif regime_std and regime_std > 4: score -= 10

    # Test 5: Selection bias
    ratio = results.get("test5", {}).get("top3_top20_ratio", 0) or 0
    if 1.2 < ratio < 3: score += 10
    elif ratio > 4: score -= 10

    # Test 6: Parameter robustness
    param_std = results.get("test6", {}).get("param_std")
    if param_std and param_std < 1.5: score += 10
    elif param_std and param_std > 3: score -= 10

    score = max(0, min(100, score))
    return score


def main():
    print("=" * 60)
    print("  METHODOLOGY VALIDATION AGENT")
    print("  Testing the believability of the trading strategy")
    print(f"  {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("=" * 60)

    all_data, funda_cache, nifty_df, nifty_returns = load_cache()

    results = {}

    # Test 1: Random baseline
    r1 = test_random_baseline(all_data, funda_cache, nifty_df, nifty_returns, n_trials=100)
    results["test1"] = r1

    # Test 2: Ranking circularity
    r2 = test_ranking_circularity(all_data, funda_cache, nifty_df, nifty_returns)
    results["test2"] = r2

    # Test 3: Forward return consistency
    r3 = test_forward_return_consistency(all_data)
    results["test3"] = r3

    # Test 4: Regime stability
    r4 = test_regime_stability(all_data, funda_cache, nifty_df, nifty_returns)
    results["test4"] = r4

    # Test 5: Selection bias
    r5 = test_data_snooping(all_data, funda_cache, nifty_df, nifty_returns)
    results["test5"] = r5

    # Test 6: Parameter robustness
    r6 = test_feature_robustness(all_data, funda_cache, nifty_df, nifty_returns)
    results["test6"] = r6

    # Final believability score
    score = compute_believability_score(results)

    print(f"\n{'='*60}")
    print(f"  BELIEVABILITY SCORE: {score}/100")
    print(f"{'='*60}")
    if score >= 80:
        print("  ✅ STRONG — Methodology has statistically significant edge")
    elif score >= 60:
        print("  ⚠️ MODERATE — Some signal present but concerns remain")
    elif score >= 40:
        print("  ❌ WEAK — Limited evidence of real edge")
    else:
        print("  🔴 UNLIKELY — Results consistent with noise or overfitting")

    print(f"\n  Key concerns for score {score}/100:")
    if r1.get("z_score", 0) < 1.5:
        print(f"    - Fails to beat random selection significantly (z={r1.get('z_score', 0):.2f})")
    if results.get("test5", {}).get("top3_top20_ratio", 0) > 4:
        print(f"    - Edge concentrated only in top picks (ratio={results['test5'].get('top3_top20_ratio', 0):.1f}x)")
    if results.get("test4", {}).get("regime_std", 0) > 3:
        print(f"    - High regime sensitivity (std={results['test4'].get('regime_std', 0):.2f}%)")

    print(f"\n  See AMENDMENTS.md for recommended fixes.")


if __name__ == "__main__":
    main()
