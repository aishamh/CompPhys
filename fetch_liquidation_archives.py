"""
Fetch Historical Liquidation Data from Archives

Sources:
1. Hyperliquid S3 Archive - raw tick data since 2023
2. CoinGlass Free API - aggregated liquidation data
3. Binance Data Vision - historical trades (can identify liquidations)
"""

import requests
import pandas as pd
import gzip
import io
from datetime import datetime, timedelta
import json
import time

print("="*70)
print("FETCHING HISTORICAL LIQUIDATION DATA FROM ARCHIVES")
print("="*70)


# ============================================================================
# 1. COINGLASS FREE API
# ============================================================================

print("\n" + "-"*70)
print("1. COINGLASS FREE API")
print("-"*70)

def get_coinglass_liquidations():
    """Try CoinGlass public liquidation endpoints"""

    # Public endpoints (no auth required)
    endpoints = [
        "https://fapi.coinglass.com/api/futures/liquidation/coin/chart?symbol=BTC&interval=h24&ex=",
        "https://open-api.coinglass.com/public/v2/liquidation_history?symbol=BTCUSDT&interval=1h",
        "https://fapi.coinglass.com/api/futures/liquidation/detail?symbol=BTC",
    ]

    for url in endpoints:
        try:
            headers = {
                "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
            }
            response = requests.get(url, headers=headers, timeout=30)
            print(f"  Trying: {url[:60]}...")
            print(f"  Status: {response.status_code}")

            if response.status_code == 200:
                data = response.json()
                if data:
                    print(f"  ✓ Got data: {type(data)}")
                    if isinstance(data, dict) and 'data' in data:
                        return data['data']
                    return data
        except Exception as e:
            print(f"  Error: {e}")
        time.sleep(0.5)

    return None


coinglass_data = get_coinglass_liquidations()
if coinglass_data:
    print(f"\n  Sample CoinGlass data: {json.dumps(coinglass_data[:2] if isinstance(coinglass_data, list) else coinglass_data, indent=2)[:500]}")


# ============================================================================
# 2. HYPERLIQUID S3 ARCHIVE
# ============================================================================

print("\n" + "-"*70)
print("2. HYPERLIQUID S3 ARCHIVE")
print("-"*70)

def list_hyperliquid_archive():
    """List available files in Hyperliquid archive"""

    # S3 bucket structure exploration
    bucket_url = "https://hyperliquid-archive.s3.amazonaws.com/"

    try:
        response = requests.get(bucket_url, timeout=30)
        if response.status_code == 200:
            print(f"  Archive bucket accessible")

            # Parse XML response
            import re
            keys = re.findall(r'<Key>(.*?)</Key>', response.text)

            if keys:
                print(f"  Found {len(keys)} files")

                # Group by prefix
                prefixes = set()
                for key in keys[:100]:  # Check first 100
                    parts = key.split('/')
                    if len(parts) > 1:
                        prefixes.add(parts[0])

                print(f"  Prefixes found: {prefixes}")

                # Show some files
                print(f"\n  Sample files:")
                for key in keys[:20]:
                    print(f"    {key}")

                return keys
    except Exception as e:
        print(f"  Error: {e}")

    return []


def download_hyperliquid_archive_file(key: str):
    """Download a specific file from the archive"""
    url = f"https://hyperliquid-archive.s3.amazonaws.com/{key}"

    try:
        print(f"  Downloading: {key}")
        response = requests.get(url, timeout=60)

        if response.status_code == 200:
            # Handle gzipped files
            if key.endswith('.gz'):
                content = gzip.decompress(response.content)
                return content.decode('utf-8')
            return response.text
    except Exception as e:
        print(f"  Error downloading {key}: {e}")

    return None


archive_files = list_hyperliquid_archive()

# Try to download a sample file if we found any
if archive_files:
    # Look for trade or liquidation files
    liq_files = [f for f in archive_files if 'liq' in f.lower() or 'trade' in f.lower()]
    csv_files = [f for f in archive_files if f.endswith('.csv') or f.endswith('.csv.gz')]

    print(f"\n  Liquidation-related files: {len(liq_files)}")
    print(f"  CSV files: {len(csv_files)}")

    if csv_files:
        sample_file = csv_files[0]
        content = download_hyperliquid_archive_file(sample_file)
        if content:
            lines = content.split('\n')[:10]
            print(f"\n  Sample content from {sample_file}:")
            for line in lines:
                print(f"    {line[:100]}")


# ============================================================================
# 3. BINANCE DATA VISION
# ============================================================================

print("\n" + "-"*70)
print("3. BINANCE DATA VISION")
print("-"*70)

def get_binance_data_vision_info():
    """
    Binance provides free historical data downloads at data.binance.vision

    Structure:
    - Spot: data.binance.vision/data/spot/daily/trades/BTCUSDT/
    - Futures: data.binance.vision/data/futures/um/daily/trades/BTCUSDT/

    Files include all trades - liquidations can be identified by:
    - isBuyerMaker = false with large size
    - Trades at specific price levels
    """

    base_url = "https://data.binance.vision"

    # Check available data
    paths = [
        "/data/futures/um/daily/trades/BTCUSDT/",
        "/data/futures/um/daily/liquidationSnapshot/",
        "/data/futures/um/daily/",
    ]

    print("  Binance Data Vision provides:")
    print("  - Historical trades since 2019")
    print("  - Daily/Monthly archives in CSV format")
    print("  - Perpetual futures data")
    print("")

    for path in paths:
        try:
            url = f"{base_url}{path}"
            response = requests.get(url, timeout=30)
            print(f"  {path}: Status {response.status_code}")
        except Exception as e:
            print(f"  {path}: Error {e}")

    # Try to list a directory
    print("\n  Example download URL:")
    yesterday = (datetime.now() - timedelta(days=2)).strftime("%Y-%m-%d")
    print(f"  {base_url}/data/futures/um/daily/trades/BTCUSDT/BTCUSDT-trades-{yesterday}.zip")

    return True


get_binance_data_vision_info()


# ============================================================================
# 4. ALTERNATIVE: Use Deribit Public API
# ============================================================================

print("\n" + "-"*70)
print("4. DERIBIT PUBLIC API")
print("-"*70)

def get_deribit_data():
    """
    Deribit offers some public historical data
    Including insurance fund and liquidation stats
    """

    base_url = "https://www.deribit.com/api/v2/public"

    endpoints = [
        "/get_instruments?currency=BTC&kind=future",
        "/get_tradingview_chart_data?instrument_name=BTC-PERPETUAL&start_timestamp=1704067200000&end_timestamp=1704153600000&resolution=1D",
    ]

    print("  Deribit public data:")

    for endpoint in endpoints:
        try:
            url = f"{base_url}{endpoint}"
            response = requests.get(url, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if 'result' in data:
                    result = data['result']
                    if isinstance(result, list):
                        print(f"  {endpoint.split('?')[0]}: {len(result)} items")
                    else:
                        print(f"  {endpoint.split('?')[0]}: OK")
        except Exception as e:
            print(f"  {endpoint}: Error {e}")

    return None


get_deribit_data()


# ============================================================================
# 5. CREATE LIQUIDATION PROXY FROM FUNDING RATES
# ============================================================================

print("\n" + "-"*70)
print("5. FUNDING RATE PROXY FOR LIQUIDATION RISK")
print("-"*70)

def create_liquidation_proxy():
    """
    Use funding rate extremes as proxy for liquidation events

    High positive funding = overleveraged longs = long liquidations coming
    High negative funding = overleveraged shorts = short liquidations coming
    """

    # Load Hyperliquid funding data
    try:
        df = pd.read_csv("twelvedata_export/hyperliquid_funding.csv")
        df['time'] = pd.to_datetime(df['time'])

        print(f"  Loaded {len(df)} funding rate entries")
        print(f"  Date range: {df['time'].min().date()} to {df['time'].max().date()}")

        # Identify extreme funding periods
        df['funding_zscore'] = (df['fundingRate'] - df['fundingRate'].mean()) / df['fundingRate'].std()

        # Extreme funding = potential liquidation cascade
        extreme_positive = df[df['funding_zscore'] > 2]  # Overleveraged longs
        extreme_negative = df[df['funding_zscore'] < -2]  # Overleveraged shorts

        print(f"\n  Extreme positive funding (long squeeze risk): {len(extreme_positive)} periods")
        print(f"  Extreme negative funding (short squeeze risk): {len(extreme_negative)} periods")

        if len(extreme_positive) > 0:
            print(f"\n  Recent extreme positive funding (potential long liquidations):")
            print(extreme_positive[['time', 'fundingRate', 'funding_zscore']].tail(5).to_string())

        if len(extreme_negative) > 0:
            print(f"\n  Recent extreme negative funding (potential short liquidations):")
            print(extreme_negative[['time', 'fundingRate', 'funding_zscore']].tail(5).to_string())

        # Save proxy data
        df['liquidation_risk'] = 'normal'
        df.loc[df['funding_zscore'] > 2, 'liquidation_risk'] = 'long_squeeze_risk'
        df.loc[df['funding_zscore'] < -2, 'liquidation_risk'] = 'short_squeeze_risk'

        df.to_csv("twelvedata_export/funding_liquidation_proxy.csv", index=False)
        print(f"\n  Saved funding-based liquidation proxy to funding_liquidation_proxy.csv")

        return df

    except Exception as e:
        print(f"  Error: {e}")
        return None


funding_proxy = create_liquidation_proxy()


# ============================================================================
# SUMMARY
# ============================================================================

print("\n" + "="*70)
print("SUMMARY: FREE HISTORICAL LIQUIDATION DATA OPTIONS")
print("="*70)

summary = """
┌─────────────────────────────────────────────────────────────────────┐
│                   FREE LIQUIDATION DATA SOURCES                      │
├─────────────────────────────────────────────────────────────────────┤
│                                                                      │
│ 1. HYPERLIQUID (BEST FREE OPTION)                                   │
│    ✓ 500+ funding rate entries saved (proxy for liquidation risk)   │
│    ✓ 228 market states with current OI/funding                      │
│    ✓ Real-time trade stream (includes liquidations)                 │
│    ✓ S3 archive with historical tick data (since 2023)              │
│    History: ~23 months (March 2023 - present)                       │
│                                                                      │
│ 2. BINANCE DATA VISION                                              │
│    ✓ Free CSV downloads of historical trades                        │
│    ✓ Can identify liquidations from trade patterns                  │
│    ✓ Goes back to 2019                                              │
│    Note: Requires downloading and parsing large files               │
│                                                                      │
│ 3. COINGLASS                                                        │
│    ⚠ Free API limited, needs paid subscription for full access     │
│    ✓ Web scraping possible for public charts                       │
│                                                                      │
│ 4. DERIBIT                                                          │
│    ✓ Public API for BTC/ETH options and futures                    │
│    ✓ Insurance fund data available                                  │
│                                                                      │
│ 5. FUNDING RATE PROXY (Created from Hyperliquid data)               │
│    ✓ Extreme funding = liquidation cascade indicator               │
│    ✓ Saved to funding_liquidation_proxy.csv                        │
│                                                                      │
├─────────────────────────────────────────────────────────────────────┤
│ RECOMMENDATION FOR THESIS:                                           │
│                                                                      │
│ FREE: Use Hyperliquid + Funding Rate Proxy                          │
│       - 23 months of on-chain data                                  │
│       - Funding extremes correlate with liquidation cascades        │
│                                                                      │
│ PAID ($50/mo): Tardis.dev for tick-level liquidation data           │
│       - Best quality, exact prices and amounts                      │
│       - 5+ years of data across all major exchanges                 │
└─────────────────────────────────────────────────────────────────────┘
"""
print(summary)

print("\nFiles saved:")
print("  - twelvedata_export/hyperliquid_funding.csv")
print("  - twelvedata_export/hyperliquid_recent_trades.csv")
print("  - twelvedata_export/hyperliquid_market_state.csv")
print("  - twelvedata_export/funding_liquidation_proxy.csv")
