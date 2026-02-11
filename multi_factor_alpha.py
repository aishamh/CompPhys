"""
Multi-Factor Alpha Model
Combines multiple free data sources for enhanced signal quality

Data Sources:
1. ETF Flows (synthetic/Farside)
2. Gold prices (Yahoo Finance)
3. Funding rates (Coinalyze - FREE)
4. Liquidations (Coinalyze - FREE)
5. Open Interest (Coinalyze - FREE)
"""

import requests
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime, timedelta
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# FREE DATA FETCHERS
# ============================================================================

class CoinalyzeAPI:
    """
    Free crypto derivatives data API
    Docs: https://api.coinalyze.net/v1/doc/
    """
    BASE_URL = "https://api.coinalyze.net/v1"

    @staticmethod
    def get_funding_rate_history(symbol: str = "BTCUSD_PERP.A", days: int = 365) -> pd.DataFrame:
        """Fetch historical funding rates"""
        print(f"Fetching funding rate history for {symbol}...")

        # Calculate timestamps
        end_time = int(datetime.now().timestamp())
        start_time = end_time - (days * 24 * 60 * 60)

        url = f"{CoinalyzeAPI.BASE_URL}/funding-rate-history"
        params = {
            "symbols": symbol,
            "interval": "daily",
            "from": start_time,
            "to": end_time
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                records = data[0].get('history', [])
                df = pd.DataFrame(records)
                if len(df) > 0:
                    df['date'] = pd.to_datetime(df['t'], unit='s')
                    df['funding_rate'] = df['c'].astype(float)  # 'c' is the funding rate
                    df = df[['date', 'funding_rate']].sort_values('date')
                    print(f"  Retrieved {len(df)} days of funding data")
                    return df
        except Exception as e:
            print(f"  Error: {e}")

        return None

    @staticmethod
    def get_open_interest_history(symbol: str = "BTCUSD_PERP.A", days: int = 365) -> pd.DataFrame:
        """Fetch historical open interest"""
        print(f"Fetching open interest history for {symbol}...")

        end_time = int(datetime.now().timestamp())
        start_time = end_time - (days * 24 * 60 * 60)

        url = f"{CoinalyzeAPI.BASE_URL}/open-interest-history"
        params = {
            "symbols": symbol,
            "interval": "daily",
            "from": start_time,
            "to": end_time
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                records = data[0].get('history', [])
                df = pd.DataFrame(records)
                if len(df) > 0:
                    df['date'] = pd.to_datetime(df['t'], unit='s')
                    df['open_interest'] = df['c'].astype(float)
                    df = df[['date', 'open_interest']].sort_values('date')
                    print(f"  Retrieved {len(df)} days of OI data")
                    return df
        except Exception as e:
            print(f"  Error: {e}")

        return None

    @staticmethod
    def get_liquidation_history(symbol: str = "BTCUSD_PERP.A", days: int = 365) -> pd.DataFrame:
        """Fetch historical liquidations"""
        print(f"Fetching liquidation history for {symbol}...")

        end_time = int(datetime.now().timestamp())
        start_time = end_time - (days * 24 * 60 * 60)

        url = f"{CoinalyzeAPI.BASE_URL}/liquidation-history"
        params = {
            "symbols": symbol,
            "interval": "daily",
            "from": start_time,
            "to": end_time
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                records = data[0].get('history', [])
                df = pd.DataFrame(records)
                if len(df) > 0:
                    df['date'] = pd.to_datetime(df['t'], unit='s')
                    # 'l' = long liquidations, 's' = short liquidations
                    df['liq_long'] = df['l'].astype(float) if 'l' in df.columns else 0
                    df['liq_short'] = df['s'].astype(float) if 's' in df.columns else 0
                    df['liq_total'] = df['liq_long'] + df['liq_short']
                    df = df[['date', 'liq_long', 'liq_short', 'liq_total']].sort_values('date')
                    print(f"  Retrieved {len(df)} days of liquidation data")
                    return df
        except Exception as e:
            print(f"  Error: {e}")

        return None


def fetch_fear_greed_index() -> pd.DataFrame:
    """Fetch Fear & Greed Index (free)"""
    print("Fetching Fear & Greed Index...")

    url = "https://api.alternative.me/fng/?limit=1000&format=json"

    try:
        response = requests.get(url, timeout=30)
        data = response.json()

        if 'data' in data:
            df = pd.DataFrame(data['data'])
            df['date'] = pd.to_datetime(df['timestamp'].astype(int), unit='s')
            df['fear_greed'] = df['value'].astype(int)
            df['fg_classification'] = df['value_classification']
            df = df[['date', 'fear_greed', 'fg_classification']].sort_values('date')
            print(f"  Retrieved {len(df)} days of Fear & Greed data")
            return df
    except Exception as e:
        print(f"  Error: {e}")

    return None


# ============================================================================
# LOAD EXISTING DATA
# ============================================================================

def load_existing_data():
    """Load our previously fetched data"""
    print("\nLoading existing data...")

    # ETF + BTC + Gold merged data
    merged_file = "twelvedata_export/btc_gold_etf_merged.csv"
    try:
        merged = pd.read_csv(merged_file)
        merged['date'] = pd.to_datetime(merged['date'])
        print(f"  Loaded merged data: {len(merged)} rows")
        return merged
    except Exception as e:
        print(f"  Error loading merged data: {e}")
        return None


# ============================================================================
# MULTI-FACTOR ANALYSIS
# ============================================================================

def build_multi_factor_model(merged: pd.DataFrame, funding: pd.DataFrame,
                              oi: pd.DataFrame, liqs: pd.DataFrame,
                              fear_greed: pd.DataFrame) -> pd.DataFrame:
    """
    Build multi-factor model combining all signals
    """
    print("\n" + "="*60)
    print("BUILDING MULTI-FACTOR MODEL")
    print("="*60)

    # Start with merged data
    df = merged.copy()
    df['date'] = pd.to_datetime(df['date']).dt.normalize()

    # Merge funding rates
    if funding is not None:
        funding['date'] = pd.to_datetime(funding['date']).dt.normalize()
        df = df.merge(funding, on='date', how='left')
        print(f"  Added funding rates")

    # Merge open interest
    if oi is not None:
        oi['date'] = pd.to_datetime(oi['date']).dt.normalize()
        df = df.merge(oi, on='date', how='left')
        print(f"  Added open interest")

    # Merge liquidations
    if liqs is not None:
        liqs['date'] = pd.to_datetime(liqs['date']).dt.normalize()
        df = df.merge(liqs, on='date', how='left')
        print(f"  Added liquidations")

    # Merge fear & greed
    if fear_greed is not None:
        fear_greed['date'] = pd.to_datetime(fear_greed['date']).dt.normalize()
        df = df.merge(fear_greed[['date', 'fear_greed']], on='date', how='left')
        print(f"  Added Fear & Greed Index")

    print(f"\n  Final dataset: {len(df)} rows, {len(df.columns)} columns")

    return df


def create_signals(df: pd.DataFrame) -> pd.DataFrame:
    """Create trading signals from multi-factor data"""
    print("\n" + "-"*60)
    print("CREATING TRADING SIGNALS")
    print("-"*60)

    df = df.copy()

    # === ETF Flow Signals ===
    if 'total_flow_usd_millions' in df.columns:
        flow_10 = df['total_flow_usd_millions'].quantile(0.1)
        flow_90 = df['total_flow_usd_millions'].quantile(0.9)
        df['etf_outflow'] = (df['total_flow_usd_millions'] <= flow_10).astype(int)
        df['etf_inflow'] = (df['total_flow_usd_millions'] >= flow_90).astype(int)
        print(f"  ETF signals: outflow threshold ${flow_10:.1f}M, inflow ${flow_90:.1f}M")

    # === Gold Signals ===
    if 'gold_close' in df.columns:
        df['gold_5d_ret'] = df['gold_close'].pct_change(5) * 100
        df['gold_rising'] = (df['gold_5d_ret'] > 0).astype(int)
        df['gold_falling'] = (df['gold_5d_ret'] < 0).astype(int)
        print(f"  Gold momentum signals created")

    # === Funding Rate Signals ===
    if 'funding_rate' in df.columns:
        df['funding_high'] = (df['funding_rate'] > 0.0005).astype(int)  # > 0.05%
        df['funding_low'] = (df['funding_rate'] < -0.0001).astype(int)  # < -0.01%
        df['funding_extreme_high'] = (df['funding_rate'] > 0.001).astype(int)  # > 0.1%
        print(f"  Funding rate signals created")

    # === Open Interest Signals ===
    if 'open_interest' in df.columns:
        df['oi_change'] = df['open_interest'].pct_change() * 100
        df['oi_spike'] = (df['oi_change'] > df['oi_change'].quantile(0.9)).astype(int)
        df['oi_drop'] = (df['oi_change'] < df['oi_change'].quantile(0.1)).astype(int)
        print(f"  Open interest signals created")

    # === Liquidation Signals ===
    if 'liq_total' in df.columns:
        liq_90 = df['liq_total'].quantile(0.9)
        df['liq_cascade'] = (df['liq_total'] >= liq_90).astype(int)
        df['liq_ratio'] = df['liq_long'] / (df['liq_short'] + 1)  # Long/Short ratio
        df['liq_long_dominant'] = (df['liq_ratio'] > 1.5).astype(int)  # More longs liquidated
        df['liq_short_dominant'] = (df['liq_ratio'] < 0.67).astype(int)  # More shorts liquidated
        print(f"  Liquidation signals created")

    # === Fear & Greed Signals ===
    if 'fear_greed' in df.columns:
        df['extreme_fear'] = (df['fear_greed'] <= 20).astype(int)
        df['extreme_greed'] = (df['fear_greed'] >= 80).astype(int)
        print(f"  Fear & Greed signals created")

    # === Forward Returns (target) ===
    if 'close' in df.columns:
        df['fwd_ret_1d'] = df['close'].pct_change().shift(-1) * 100
        df['fwd_ret_5d'] = df['close'].pct_change(5).shift(-5) * 100
        df['fwd_ret_10d'] = df['close'].pct_change(10).shift(-10) * 100

    return df


def backtest_multi_factor_strategies(df: pd.DataFrame) -> dict:
    """Backtest various multi-factor combinations"""
    print("\n" + "="*60)
    print("MULTI-FACTOR STRATEGY BACKTEST")
    print("="*60)

    results = {}
    baseline_ret = df['fwd_ret_5d'].mean()
    print(f"\n  Baseline (all days) 5-day return: {baseline_ret:.2f}%")

    # Define strategies
    strategies = {}

    # Strategy 1: Original (ETF outflows + Gold rising)
    if 'etf_outflow' in df.columns and 'gold_rising' in df.columns:
        strategies['A: ETF_Out + Gold_Up'] = (df['etf_outflow'] == 1) & (df['gold_rising'] == 1)

    # Strategy 2: Add funding rate filter
    if 'funding_low' in df.columns:
        strategies['B: A + Funding_Low'] = (
            (df.get('etf_outflow', 0) == 1) &
            (df.get('gold_rising', 0) == 1) &
            (df['funding_low'] == 1)
        )

    # Strategy 3: Add liquidation cascade
    if 'liq_long_dominant' in df.columns:
        strategies['C: A + Long_Liqs'] = (
            (df.get('etf_outflow', 0) == 1) &
            (df.get('gold_rising', 0) == 1) &
            (df['liq_long_dominant'] == 1)
        )

    # Strategy 4: Extreme fear + ETF outflows
    if 'extreme_fear' in df.columns:
        strategies['D: ETF_Out + Extreme_Fear'] = (
            (df.get('etf_outflow', 0) == 1) &
            (df['extreme_fear'] == 1)
        )

    # Strategy 5: Maximum confluence
    strategies['E: Max_Confluence'] = (
        (df.get('etf_outflow', 0) == 1) &
        (df.get('gold_rising', 0) == 1) &
        (df.get('funding_low', 0) == 1) &
        (df.get('extreme_fear', 0) == 1)
    )

    # Strategy 6: Contrarian inverse (SELL signals)
    strategies['F: SELL (Inflow + Gold_Down)'] = (
        (df.get('etf_inflow', 0) == 1) &
        (df.get('gold_falling', 0) == 1)
    )

    # Strategy 7: Funding extreme contrarian
    if 'funding_extreme_high' in df.columns:
        strategies['G: Funding_Extreme_Short'] = df['funding_extreme_high'] == 1

    # Backtest each strategy
    print(f"\n{'Strategy':<35} {'N':>5} {'Avg Ret':>10} {'Edge':>10} {'Win%':>8}")
    print("-"*70)

    for name, mask in strategies.items():
        subset = df[mask]
        n = len(subset)

        if n > 0:
            avg_ret = subset['fwd_ret_5d'].mean()
            edge = avg_ret - baseline_ret
            win_rate = (subset['fwd_ret_5d'] > 0).mean() * 100

            results[name] = {
                'n': n,
                'avg_return': avg_ret,
                'edge': edge,
                'win_rate': win_rate
            }

            print(f"{name:<35} {n:>5} {avg_ret:>+9.2f}% {edge:>+9.2f}% {win_rate:>7.1f}%")
        else:
            print(f"{name:<35} {'N/A':>5} {'--':>10} {'--':>10} {'--':>8}")

    return results


def main():
    print("="*60)
    print("MULTI-FACTOR CRYPTO ALPHA MODEL")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}\n")

    # Load existing data
    merged = load_existing_data()
    if merged is None:
        print("Failed to load existing data")
        return

    # Fetch additional free data
    print("\nFetching additional free data sources...")

    funding = CoinalyzeAPI.get_funding_rate_history(days=730)
    time.sleep(1)

    oi = CoinalyzeAPI.get_open_interest_history(days=730)
    time.sleep(1)

    liqs = CoinalyzeAPI.get_liquidation_history(days=730)
    time.sleep(1)

    fear_greed = fetch_fear_greed_index()

    # Build multi-factor model
    df = build_multi_factor_model(merged, funding, oi, liqs, fear_greed)

    # Create signals
    df = create_signals(df)

    # Run backtests
    results = backtest_multi_factor_strategies(df)

    # Save results
    df.to_csv("twelvedata_export/multi_factor_data.csv", index=False)

    with open("twelvedata_export/multi_factor_results.json", 'w') as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "="*60)
    print("FILES SAVED")
    print("="*60)
    print("  - twelvedata_export/multi_factor_data.csv")
    print("  - twelvedata_export/multi_factor_results.json")

    # Summary
    print("\n" + "="*60)
    print("BEST STRATEGIES BY EDGE")
    print("="*60)

    if results:
        sorted_results = sorted(results.items(), key=lambda x: x[1]['edge'], reverse=True)
        for i, (name, data) in enumerate(sorted_results[:5], 1):
            print(f"  {i}. {name}")
            print(f"     Edge: {data['edge']:+.2f}%, Win Rate: {data['win_rate']:.1f}%, N={data['n']}")

    return df, results


if __name__ == "__main__":
    df, results = main()
