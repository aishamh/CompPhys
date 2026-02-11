"""
Identify Liquidations from Binance Historical Trade Data

Liquidation patterns:
1. Large trades executed as market orders (taker)
2. Clusters of same-direction trades in short time windows
3. Trades at round price levels (liquidation prices)
4. Abnormal trade sizes compared to recent average
5. Price impact - trades that move price significantly

Data source: https://data.binance.vision
"""

import requests
import pandas as pd
import numpy as np
from datetime import datetime, timedelta
import zipfile
import io
import os

print("="*70)
print("IDENTIFYING LIQUIDATIONS FROM BINANCE TRADE DATA")
print("="*70)


def download_binance_trades(symbol: str = "BTCUSDT", date: str = None):
    """
    Download historical trades from Binance Data Vision

    Format: https://data.binance.vision/data/futures/um/daily/trades/BTCUSDT/BTCUSDT-trades-2024-01-15.zip
    """
    if date is None:
        # Use a date we know has data (recent but not today)
        date = (datetime.now() - timedelta(days=7)).strftime("%Y-%m-%d")

    base_url = "https://data.binance.vision/data/futures/um/daily/trades"
    url = f"{base_url}/{symbol}/{symbol}-trades-{date}.zip"

    print(f"\nDownloading trades for {symbol} on {date}...")
    print(f"URL: {url}")

    try:
        response = requests.get(url, timeout=120)

        if response.status_code == 200:
            # Extract CSV from ZIP
            with zipfile.ZipFile(io.BytesIO(response.content)) as z:
                csv_name = z.namelist()[0]
                with z.open(csv_name) as f:
                    df = pd.read_csv(f)

            print(f"✓ Downloaded {len(df):,} trades")
            return df
        else:
            print(f"✗ HTTP {response.status_code}")
            return None

    except Exception as e:
        print(f"✗ Error: {e}")
        return None


def identify_liquidation_patterns(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify potential liquidations based on trade patterns

    Binance trade columns:
    - id: trade id
    - price: trade price
    - qty: quantity
    - quote_qty: quote quantity (price * qty)
    - time: timestamp in milliseconds
    - is_buyer_maker: True if buyer was maker (seller was taker/market order)
    """
    print("\n" + "-"*70)
    print("ANALYZING TRADE PATTERNS FOR LIQUIDATIONS")
    print("-"*70)

    df = df.copy()

    # Convert timestamp
    df['datetime'] = pd.to_datetime(df['time'], unit='ms')
    df['price'] = df['price'].astype(float)
    df['qty'] = df['qty'].astype(float)
    df['quote_qty'] = df['quote_qty'].astype(float)

    # Trade direction: is_buyer_maker=True means SELL (seller was taker)
    df['side'] = np.where(df['is_buyer_maker'], 'SELL', 'BUY')

    print(f"\nTotal trades: {len(df):,}")
    print(f"Time range: {df['datetime'].min()} to {df['datetime'].max()}")
    print(f"Price range: ${df['price'].min():,.2f} to ${df['price'].max():,.2f}")

    # =========================================================================
    # PATTERN 1: Large trades (potential liquidations are bigger than average)
    # =========================================================================
    print("\n" + "-"*50)
    print("PATTERN 1: Large Trades")
    print("-"*50)

    # Calculate trade size statistics
    mean_size = df['quote_qty'].mean()
    std_size = df['quote_qty'].std()
    p99_size = df['quote_qty'].quantile(0.99)
    p999_size = df['quote_qty'].quantile(0.999)

    print(f"  Mean trade size: ${mean_size:,.2f}")
    print(f"  Std dev: ${std_size:,.2f}")
    print(f"  99th percentile: ${p99_size:,.2f}")
    print(f"  99.9th percentile: ${p999_size:,.2f}")

    # Flag large trades (> 99th percentile)
    df['is_large'] = df['quote_qty'] > p99_size
    df['is_very_large'] = df['quote_qty'] > p999_size

    large_trades = df[df['is_large']]
    print(f"\n  Large trades (>99th pctl): {len(large_trades):,} ({len(large_trades)/len(df)*100:.2f}%)")
    print(f"  Very large trades (>99.9th pctl): {len(df[df['is_very_large']]):,}")

    # =========================================================================
    # PATTERN 2: Trade clusters (liquidation cascades)
    # =========================================================================
    print("\n" + "-"*50)
    print("PATTERN 2: Trade Clusters (Cascades)")
    print("-"*50)

    # Group trades into 1-second windows
    df['second'] = df['datetime'].dt.floor('1s')

    cluster_stats = df.groupby('second').agg({
        'quote_qty': ['count', 'sum'],
        'side': lambda x: (x == 'SELL').sum() - (x == 'BUY').sum(),  # Net direction
        'price': ['min', 'max']
    }).reset_index()

    cluster_stats.columns = ['second', 'trade_count', 'volume', 'net_direction', 'low', 'high']
    cluster_stats['price_range'] = cluster_stats['high'] - cluster_stats['low']
    cluster_stats['price_range_pct'] = cluster_stats['price_range'] / cluster_stats['low'] * 100

    # High activity clusters
    high_activity = cluster_stats[cluster_stats['trade_count'] > cluster_stats['trade_count'].quantile(0.99)]

    print(f"  Total 1-second windows: {len(cluster_stats):,}")
    print(f"  High activity windows (>99th pctl): {len(high_activity):,}")

    if len(high_activity) > 0:
        print(f"\n  Top 10 highest activity seconds:")
        top_clusters = high_activity.nlargest(10, 'trade_count')
        for _, row in top_clusters.iterrows():
            direction = "SELL CASCADE" if row['net_direction'] > 5 else ("BUY CASCADE" if row['net_direction'] < -5 else "MIXED")
            print(f"    {row['second']} - {int(row['trade_count'])} trades, ${row['volume']:,.0f} vol, {direction}")

    # =========================================================================
    # PATTERN 3: Price impact (liquidations move price)
    # =========================================================================
    print("\n" + "-"*50)
    print("PATTERN 3: Price Impact Trades")
    print("-"*50)

    # Calculate price change per trade
    df['price_change'] = df['price'].diff()
    df['price_change_pct'] = df['price_change'] / df['price'].shift(1) * 100

    # Large price moves
    df['big_move'] = abs(df['price_change_pct']) > 0.01  # >0.01% move

    big_moves = df[df['big_move']]
    print(f"  Trades causing >0.01% price move: {len(big_moves):,}")

    # Correlate large trades with price impact
    large_with_impact = df[(df['is_large']) & (df['big_move'])]
    print(f"  Large trades with price impact: {len(large_with_impact):,}")

    # =========================================================================
    # PATTERN 4: Liquidation price levels (round numbers)
    # =========================================================================
    print("\n" + "-"*50)
    print("PATTERN 4: Round Number Liquidation Levels")
    print("-"*50)

    # Check for trades at round price levels (multiples of $100 or $1000)
    df['at_100'] = (df['price'] % 100) < 10  # Within $10 of $X00
    df['at_1000'] = (df['price'] % 1000) < 50  # Within $50 of $X000

    trades_at_100 = df[df['at_100'] & df['is_large']]
    trades_at_1000 = df[df['at_1000'] & df['is_large']]

    print(f"  Large trades near $X00 levels: {len(trades_at_100):,}")
    print(f"  Large trades near $X000 levels: {len(trades_at_1000):,}")

    # =========================================================================
    # PATTERN 5: Identify likely liquidations
    # =========================================================================
    print("\n" + "-"*50)
    print("PATTERN 5: LIKELY LIQUIDATIONS")
    print("-"*50)

    # A trade is likely a liquidation if:
    # - Large size (>99th percentile) OR
    # - Part of a cascade (many trades same direction in short window) AND
    # - Causes price impact

    # Score each trade
    df['liq_score'] = 0
    df.loc[df['is_large'], 'liq_score'] += 2
    df.loc[df['is_very_large'], 'liq_score'] += 2
    df.loc[df['big_move'], 'liq_score'] += 1
    df.loc[df['at_1000'], 'liq_score'] += 1

    # High score = likely liquidation
    likely_liquidations = df[df['liq_score'] >= 3]

    print(f"  Likely liquidations identified: {len(likely_liquidations):,}")
    print(f"  Percentage of all trades: {len(likely_liquidations)/len(df)*100:.3f}%")

    if len(likely_liquidations) > 0:
        # Breakdown by side
        long_liqs = likely_liquidations[likely_liquidations['side'] == 'SELL']
        short_liqs = likely_liquidations[likely_liquidations['side'] == 'BUY']

        print(f"\n  Long liquidations (forced sells): {len(long_liqs):,} (${long_liqs['quote_qty'].sum():,.0f})")
        print(f"  Short liquidations (forced buys): {len(short_liqs):,} (${short_liqs['quote_qty'].sum():,.0f})")

        # Show sample
        print(f"\n  Sample likely liquidations:")
        sample = likely_liquidations.head(10)[['datetime', 'price', 'qty', 'quote_qty', 'side', 'liq_score']]
        print(sample.to_string())

    return df, likely_liquidations, cluster_stats


def aggregate_liquidations_hourly(df: pd.DataFrame, likely_liqs: pd.DataFrame) -> pd.DataFrame:
    """Aggregate identified liquidations into hourly buckets"""

    print("\n" + "-"*70)
    print("HOURLY LIQUIDATION SUMMARY")
    print("-"*70)

    if len(likely_liqs) == 0:
        print("  No liquidations identified")
        return None

    likely_liqs = likely_liqs.copy()
    likely_liqs['hour'] = likely_liqs['datetime'].dt.floor('1h')

    hourly = likely_liqs.groupby('hour').agg({
        'quote_qty': 'sum',
        'id': 'count',
        'side': lambda x: (x == 'SELL').sum()  # Count long liquidations
    }).reset_index()

    hourly.columns = ['hour', 'total_liq_usd', 'liq_count', 'long_liqs']
    hourly['short_liqs'] = hourly['liq_count'] - hourly['long_liqs']

    print(f"\n  Hourly breakdown:")
    print(hourly.to_string())

    return hourly


def main():
    # Try to download recent data
    dates_to_try = [
        (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        for i in range(3, 10)  # Try last week
    ]

    df = None
    for date in dates_to_try:
        df = download_binance_trades("BTCUSDT", date)
        if df is not None:
            break

    if df is None:
        print("\n✗ Could not download trade data from Binance Data Vision")
        print("  This may be due to network restrictions on this server")
        print("  To run locally:")
        print("  1. Download from: https://data.binance.vision/data/futures/um/daily/trades/BTCUSDT/")
        print("  2. Extract the CSV and load with pandas")
        return None

    # Analyze trades
    df_analyzed, likely_liqs, clusters = identify_liquidation_patterns(df)

    # Aggregate hourly
    hourly = aggregate_liquidations_hourly(df_analyzed, likely_liqs)

    # Save results
    print("\n" + "="*70)
    print("SAVING RESULTS")
    print("="*70)

    if len(likely_liqs) > 0:
        likely_liqs.to_csv("twelvedata_export/binance_identified_liquidations.csv", index=False)
        print(f"  Saved {len(likely_liqs):,} identified liquidations")

    if hourly is not None:
        hourly.to_csv("twelvedata_export/binance_hourly_liquidations.csv", index=False)
        print(f"  Saved hourly aggregation")

    # Summary
    print("\n" + "="*70)
    print("SUMMARY: LIQUIDATION IDENTIFICATION FROM TRADE PATTERNS")
    print("="*70)

    print("""
┌─────────────────────────────────────────────────────────────────────┐
│ LIQUIDATION DETECTION PATTERNS                                       │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ Pattern 1: LARGE TRADES                                              │
│   - Trades > 99th percentile in size                                │
│   - Liquidations are typically larger than normal trades            │
│                                                                      │
│ Pattern 2: TRADE CLUSTERS                                            │
│   - Many same-direction trades in short time window                 │
│   - Cascading liquidations trigger each other                       │
│                                                                      │
│ Pattern 3: PRICE IMPACT                                              │
│   - Trades that move price significantly                            │
│   - Forced market orders hit the book hard                          │
│                                                                      │
│ Pattern 4: ROUND PRICE LEVELS                                        │
│   - Liquidations cluster at $X00 and $X000 levels                   │
│   - Traders set stop losses at round numbers                        │
│                                                                      │
│ SCORING SYSTEM:                                                      │
│   +2 points: Large trade (>99th percentile)                         │
│   +2 points: Very large trade (>99.9th percentile)                  │
│   +1 point:  Causes price impact (>0.01% move)                      │
│   +1 point:  Near round $1000 price level                           │
│                                                                      │
│   Score >= 3: LIKELY LIQUIDATION                                    │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│ ACCURACY NOTES:                                                      │
│   - This is a PROXY, not exact liquidation data                     │
│   - False positives: Large whale trades, OTC settlements            │
│   - False negatives: Small liquidations that don't stand out        │
│   - Best for: Identifying MAJOR liquidation cascades                │
└─────────────────────────────────────────────────────────────────────┘
""")

    return df_analyzed, likely_liqs


if __name__ == "__main__":
    results = main()
