#!/usr/bin/env python3
"""Extend OHLCV cache to 2+ years of data. Uses existing cache's symbol list."""
import os, sys, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from backtest import _fetch_one_stock, _precompute_indicators, DATA_CACHE_PATH, CONCURRENT_WORKERS
from concurrent.futures import ThreadPoolExecutor, as_completed
import pandas as pd

def main():
    old_cache = pd.read_pickle(DATA_CACHE_PATH)
    symbols = list(old_cache.keys())
    old_start = old_cache[symbols[0]].index[0]
    old_end = old_cache[symbols[0]].index[-1]
    del old_cache

    print(f"Extending {len(symbols)} stocks to 2 years...", flush=True)
    print(f"Old range: {old_start} to {old_end} ({len(pd.date_range(old_start, old_end, freq='B'))} trading days)", flush=True)

    raw_data = {}
    downloaded = 0
    errors = 0
    total = len(symbols)
    start_t = time.time()

    print(f"Downloading {total} stocks (2y period)...", flush=True)
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
                elapsed = time.time() - start_t
                rate = downloaded / elapsed
                eta = (total - downloaded) / rate if rate > 0 else 0
                print(f"  [{downloaded}/{total}] {len(raw_data)} OK, {errors} err | {rate:.0f} stk/min | ETA {eta:.1f} min", flush=True)

    print(f"Downloaded: {len(raw_data)} OK, {errors} errors in {(time.time()-start_t)/60:.1f} min", flush=True)

    print("Pre-computing indicators...", flush=True)
    all_data = {}
    done = 0
    for sym, df in raw_data.items():
        result = _precompute_indicators(sym, df)
        if result is not None:
            all_data[sym] = result
        done += 1
        if done % 500 == 0:
            print(f"  [{done}/{len(raw_data)}] indicators, {len(all_data)} valid", flush=True)

    print(f"Saving {len(all_data)} stocks to {DATA_CACHE_PATH}", flush=True)
    pd.to_pickle(all_data, DATA_CACHE_PATH)

    verify = list(all_data.keys())[0]
    print(f"New range: {all_data[verify].index[0]} to {all_data[verify].index[-1]}", flush=True)
    print(f"Trading days: {len(all_data[verify])}", flush=True)
    print(f"Total time: {(time.time()-start_t)/60:.1f} minutes", flush=True)

if __name__ == "__main__":
    main()
