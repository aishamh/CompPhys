"""
Gold Price Validation for ETF Contrarian Signals
Tests whether gold prices can enhance confidence in ETF flow trading signals

Hypothesis: When ETF outflows coincide with gold strength (risk-off),
the contrarian BTC buy signal may be more reliable.
"""

import requests
import pandas as pd
import numpy as np
import os
import time
import json
from datetime import datetime
from scipy import stats
import warnings
warnings.filterwarnings('ignore')

# TwelveData API config
API_KEY = "ee002dce1abd4500b1a2209735df56a4"
BASE_URL = "https://api.twelvedata.com"


def fetch_gold_data(outputsize: int = 5000) -> pd.DataFrame:
    """Fetch gold (XAU/USD) price data from multiple sources"""
    print("Fetching gold (XAU/USD) data...")

    # Try Yahoo Finance first (free, no API key needed)
    try:
        print("  Trying Yahoo Finance (GLD ETF as gold proxy)...")
        # GLD is the SPDR Gold Trust ETF - tracks gold price
        url = "https://query1.finance.yahoo.com/v8/finance/chart/GLD"
        params = {
            "period1": "1104537600",  # Jan 1, 2005
            "period2": str(int(datetime.now().timestamp())),
            "interval": "1d"
        }
        headers = {"User-Agent": "Mozilla/5.0"}
        response = requests.get(url, params=params, headers=headers, timeout=30)
        data = response.json()

        if "chart" in data and data["chart"]["result"]:
            result = data["chart"]["result"][0]
            timestamps = result["timestamp"]
            quotes = result["indicators"]["quote"][0]

            df = pd.DataFrame({
                "date": pd.to_datetime(timestamps, unit='s'),
                "gold_open": quotes["open"],
                "gold_high": quotes["high"],
                "gold_low": quotes["low"],
                "gold_close": quotes["close"]
            })

            df = df.dropna().sort_values("date").reset_index(drop=True)
            print(f"  Retrieved {len(df)} days of gold (GLD) data")
            print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")

            df.to_csv("twelvedata_export/gold_usd_daily.csv", index=False)
            print("  Saved to twelvedata_export/gold_usd_daily.csv")
            return df

    except Exception as e:
        print(f"  Yahoo Finance failed: {e}")

    # Fallback: Try TwelveData
    print("  Trying TwelveData API...")
    endpoint = f"{BASE_URL}/time_series"
    params = {
        "symbol": "XAU/USD",
        "interval": "1day",
        "outputsize": outputsize,
        "apikey": API_KEY,
        "format": "JSON"
    }

    for attempt in range(4):
        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if attempt < 3:
                wait_time = 2 ** (attempt + 1)
                print(f"  Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  Failed to fetch gold data: {e}")
                return None

    data = response.json()

    if "values" not in data:
        print(f"  Error: {data.get('message', 'No data')}")
        return None

    df = pd.DataFrame(data["values"])
    df["date"] = pd.to_datetime(df["datetime"])
    df["gold_close"] = pd.to_numeric(df["close"], errors="coerce")
    df["gold_open"] = pd.to_numeric(df["open"], errors="coerce")
    df["gold_high"] = pd.to_numeric(df["high"], errors="coerce")
    df["gold_low"] = pd.to_numeric(df["low"], errors="coerce")

    df = df.sort_values("date").reset_index(drop=True)
    df = df[["date", "gold_open", "gold_high", "gold_low", "gold_close"]]

    print(f"  Retrieved {len(df)} days of gold data")
    print(f"  Date range: {df['date'].min().date()} to {df['date'].max().date()}")

    df.to_csv("twelvedata_export/gold_usd_daily.csv", index=False)
    print("  Saved to twelvedata_export/gold_usd_daily.csv")

    return df


def load_existing_data():
    """Load BTC prices and ETF flow data"""

    # Load BTC prices
    btc_df = pd.read_csv("twelvedata_export/btc_usd_daily.csv")
    btc_df['date'] = pd.to_datetime(btc_df['date']).dt.normalize()
    btc_df = btc_df.rename(columns={'close': 'btc_close', 'open': 'btc_open'})

    # Load merged ETF data
    etf_df = pd.read_csv("twelvedata_export/etf_btc_merged_analysis.csv")
    etf_df['date'] = pd.to_datetime(etf_df['date']).dt.normalize()

    return btc_df, etf_df


def analyze_gold_btc_etf_relationship(gold_df: pd.DataFrame, btc_df: pd.DataFrame, etf_df: pd.DataFrame):
    """
    Analyze the relationship between gold, BTC, and ETF flows
    """
    print("\n" + "="*60)
    print("GOLD-BTC-ETF RELATIONSHIP ANALYSIS")
    print("="*60)

    # Normalize dates for merge
    gold_df['date'] = pd.to_datetime(gold_df['date']).dt.normalize()
    etf_df['date'] = pd.to_datetime(etf_df['date']).dt.normalize()

    # Merge all data
    merged = etf_df.merge(gold_df[['date', 'gold_close']], on='date', how='inner')

    # Calculate returns
    merged['gold_return'] = merged['gold_close'].pct_change() * 100
    merged['btc_return'] = merged['close'].pct_change() * 100

    # Forward returns for BTC
    merged['btc_fwd_1d'] = merged['close'].pct_change().shift(-1) * 100
    merged['btc_fwd_5d'] = merged['close'].pct_change(5).shift(-5) * 100

    # Gold momentum indicators
    merged['gold_5d_return'] = merged['gold_close'].pct_change(5) * 100
    merged['gold_rising'] = (merged['gold_5d_return'] > 0).astype(int)

    print(f"\nMerged data: {len(merged)} trading days")

    # =========================================================================
    # TEST 1: Basic Correlations
    # =========================================================================
    print("\n" + "-"*60)
    print("TEST 1: Basic Correlations")
    print("-"*60)

    corr_btc_gold = merged['btc_return'].corr(merged['gold_return'])
    corr_flow_gold = merged['total_flow_usd_millions'].corr(merged['gold_return'])
    corr_btc_flow = merged['btc_return'].corr(merged['total_flow_usd_millions'])

    print(f"  BTC vs Gold (daily returns): {corr_btc_gold:.4f}")
    print(f"  ETF Flows vs Gold: {corr_flow_gold:.4f}")
    print(f"  BTC vs ETF Flows: {corr_btc_flow:.4f}")

    # =========================================================================
    # TEST 2: Gold as Risk-Off Indicator
    # =========================================================================
    print("\n" + "-"*60)
    print("TEST 2: Gold as Risk-Off Indicator")
    print("-"*60)

    # When gold rises (risk-off), what happens to BTC?
    gold_up_days = merged[merged['gold_return'] > 0]
    gold_down_days = merged[merged['gold_return'] <= 0]

    print(f"  Gold UP days: {len(gold_up_days)}")
    print(f"    Avg BTC return: {gold_up_days['btc_return'].mean():.3f}%")
    print(f"    Avg ETF flow: ${gold_up_days['total_flow_usd_millions'].mean():.1f}M")

    print(f"  Gold DOWN days: {len(gold_down_days)}")
    print(f"    Avg BTC return: {gold_down_days['btc_return'].mean():.3f}%")
    print(f"    Avg ETF flow: ${gold_down_days['total_flow_usd_millions'].mean():.1f}M")

    # =========================================================================
    # TEST 3: Contrarian Signal + Gold Validation
    # =========================================================================
    print("\n" + "-"*60)
    print("TEST 3: Contrarian ETF Signal + Gold Validation")
    print("-"*60)

    # Original contrarian signal: Large outflows = buy signal
    flow_10th = merged['total_flow_usd_millions'].quantile(0.1)
    flow_90th = merged['total_flow_usd_millions'].quantile(0.9)

    # Scenario A: Large outflows + Gold rising (risk-off capitulation)
    scenario_a = merged[
        (merged['total_flow_usd_millions'] <= flow_10th) &
        (merged['gold_rising'] == 1)
    ]

    # Scenario B: Large outflows + Gold falling (risk-on selloff)
    scenario_b = merged[
        (merged['total_flow_usd_millions'] <= flow_10th) &
        (merged['gold_rising'] == 0)
    ]

    # Scenario C: Large inflows + Gold rising (flight to safety includes BTC?)
    scenario_c = merged[
        (merged['total_flow_usd_millions'] >= flow_90th) &
        (merged['gold_rising'] == 1)
    ]

    # Scenario D: Large inflows + Gold falling (risk-on FOMO)
    scenario_d = merged[
        (merged['total_flow_usd_millions'] >= flow_90th) &
        (merged['gold_rising'] == 0)
    ]

    all_days_avg = merged['btc_fwd_5d'].mean()

    print(f"\n  Baseline (all days) 5-day forward return: {all_days_avg:.2f}%\n")

    scenarios = [
        ("A: Large OUTFLOWS + Gold RISING", scenario_a, "STRONGEST BUY?"),
        ("B: Large OUTFLOWS + Gold FALLING", scenario_b, "Moderate buy"),
        ("C: Large INFLOWS + Gold RISING", scenario_c, "Mixed signal"),
        ("D: Large INFLOWS + Gold FALLING", scenario_d, "SELL signal?"),
    ]

    scenario_results = {}
    for name, df, hypothesis in scenarios:
        if len(df) > 0:
            avg_return = df['btc_fwd_5d'].mean()
            edge = avg_return - all_days_avg
            win_rate = (df['btc_fwd_5d'] > 0).mean() * 100

            print(f"  {name}")
            print(f"    N = {len(df)} days")
            print(f"    Avg 5-day forward return: {avg_return:.2f}%")
            print(f"    Edge vs baseline: {edge:+.2f}%")
            print(f"    Win rate: {win_rate:.1f}%")
            print(f"    Hypothesis: {hypothesis}")
            print()

            scenario_results[name] = {
                'n': len(df),
                'avg_return': avg_return,
                'edge': edge,
                'win_rate': win_rate
            }

    # =========================================================================
    # TEST 4: Statistical Significance
    # =========================================================================
    print("-"*60)
    print("TEST 4: Statistical Significance (t-test)")
    print("-"*60)

    # Is Scenario A significantly better than baseline?
    if len(scenario_a) > 5:
        t_stat, p_value = stats.ttest_ind(
            scenario_a['btc_fwd_5d'].dropna(),
            merged['btc_fwd_5d'].dropna()
        )
        print(f"  Scenario A vs Baseline:")
        print(f"    t-statistic: {t_stat:.4f}")
        print(f"    p-value: {p_value:.4f}")
        print(f"    Significant at 5%: {'YES' if p_value < 0.05 else 'NO'}")
        print(f"    Significant at 10%: {'YES' if p_value < 0.10 else 'NO'}")

    # =========================================================================
    # TEST 5: Rolling Correlation Regime Analysis
    # =========================================================================
    print("\n" + "-"*60)
    print("TEST 5: BTC-Gold Correlation Regimes")
    print("-"*60)

    merged['btc_gold_corr_30d'] = merged['btc_return'].rolling(30).corr(merged['gold_return'])

    # High positive correlation = BTC acting as safe haven
    # High negative correlation = BTC acting as risk asset

    high_pos_corr = merged[merged['btc_gold_corr_30d'] > 0.3]
    high_neg_corr = merged[merged['btc_gold_corr_30d'] < -0.3]

    print(f"  High positive correlation (>0.3): {len(high_pos_corr)} days")
    print(f"    BTC acting as 'digital gold' / safe haven")
    if len(high_pos_corr) > 0:
        print(f"    Avg BTC 5d fwd return: {high_pos_corr['btc_fwd_5d'].mean():.2f}%")

    print(f"  High negative correlation (<-0.3): {len(high_neg_corr)} days")
    print(f"    BTC acting as risk asset")
    if len(high_neg_corr) > 0:
        print(f"    Avg BTC 5d fwd return: {high_neg_corr['btc_fwd_5d'].mean():.2f}%")

    # =========================================================================
    # SUMMARY & RECOMMENDATION
    # =========================================================================
    print("\n" + "="*60)
    print("SUMMARY: GOLD VALIDATION OF CONTRARIAN SIGNALS")
    print("="*60)

    # Find best scenario
    if scenario_results:
        best_scenario = max(scenario_results.items(), key=lambda x: x[1]['edge'])
        worst_scenario = min(scenario_results.items(), key=lambda x: x[1]['edge'])

        print(f"\n  BEST SIGNAL: {best_scenario[0]}")
        print(f"    Edge: {best_scenario[1]['edge']:+.2f}%")
        print(f"    Win rate: {best_scenario[1]['win_rate']:.1f}%")

        print(f"\n  WORST SIGNAL: {worst_scenario[0]}")
        print(f"    Edge: {worst_scenario[1]['edge']:+.2f}%")
        print(f"    Win rate: {worst_scenario[1]['win_rate']:.1f}%")

        spread = best_scenario[1]['edge'] - worst_scenario[1]['edge']
        print(f"\n  SIGNAL SPREAD: {spread:.2f}%")

        if spread > 2.0:
            print("\n  ✓ GOLD SIGNIFICANTLY ENHANCES SIGNAL QUALITY")
            print("  → Recommended: Use gold as filter for ETF contrarian signals")
        elif spread > 1.0:
            print("\n  ~ GOLD MODERATELY ENHANCES SIGNAL QUALITY")
            print("  → Recommended: Include gold as secondary confirmation")
        else:
            print("\n  ✗ GOLD DOES NOT SIGNIFICANTLY ENHANCE SIGNALS")
            print("  → Gold may not add value to ETF flow signals")

    # Save results
    results = {
        'correlations': {
            'btc_gold': corr_btc_gold,
            'flow_gold': corr_flow_gold,
            'btc_flow': corr_btc_flow
        },
        'scenarios': scenario_results,
        'timestamp': datetime.now().isoformat()
    }

    with open("twelvedata_export/gold_validation_results.json", 'w') as f:
        json.dump(results, f, indent=2, default=str)

    # Save merged data with gold
    merged.to_csv("twelvedata_export/btc_gold_etf_merged.csv", index=False)

    print("\n  Results saved to:")
    print("    - twelvedata_export/gold_validation_results.json")
    print("    - twelvedata_export/btc_gold_etf_merged.csv")

    return results, merged


def main():
    print("="*60)
    print("GOLD VALIDATION OF ETF CONTRARIAN SIGNALS")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}\n")

    # Fetch gold data
    gold_df = fetch_gold_data()
    if gold_df is None:
        print("Failed to fetch gold data")
        return None

    # Load existing data
    btc_df, etf_df = load_existing_data()

    # Run analysis
    results, merged = analyze_gold_btc_etf_relationship(gold_df, btc_df, etf_df)

    return results, merged


if __name__ == "__main__":
    results, merged = main()
