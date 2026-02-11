"""
FREE Actual Liquidation Data Sources
What prices people were liquidated at, and for how much

This script tests all known free sources and shows what data is actually available.
"""

import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import time

print("="*70)
print("FREE HISTORICAL LIQUIDATION DATA SOURCES")
print("Actual liquidations: price, amount, side, timestamp")
print("="*70)


# ============================================================================
# 1. COINALYZE - FREE API
# ============================================================================
print("\n" + "="*70)
print("1. COINALYZE (FREE)")
print("   Aggregated liquidations across exchanges")
print("="*70)

def test_coinalyze():
    """Test Coinalyze free liquidation API"""
    base_url = "https://api.coinalyze.net/v1"

    # List available endpoints
    endpoints = [
        "/liquidation-history",
        "/exchanges",
        "/future-markets"
    ]

    # Test liquidation history
    print("\nTesting liquidation history endpoint...")

    # Try to get BTC liquidations
    end_time = int(datetime.now().timestamp())
    start_time = end_time - (365 * 24 * 60 * 60)  # 1 year ago

    params = {
        "symbols": "BTCUSD_PERP.A",  # Aggregated BTC perpetual
        "interval": "daily",
        "from": start_time,
        "to": end_time
    }

    try:
        response = requests.get(f"{base_url}/liquidation-history", params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data and len(data) > 0 and 'history' in data[0]:
                history = data[0]['history']
                print(f"  ✓ SUCCESS: {len(history)} days of daily liquidation data")

                # Show sample
                if len(history) > 0:
                    first = history[0]
                    last = history[-1]
                    print(f"  Date range: {datetime.fromtimestamp(first['t']).date()} to {datetime.fromtimestamp(last['t']).date()}")
                    print(f"  Sample data: t={first.get('t')}, long_liq={first.get('l', 'N/A')}, short_liq={first.get('s', 'N/A')}")
                return history
            else:
                print(f"  ✗ No data returned")
        else:
            print(f"  ✗ Error: {response.status_code}")
    except Exception as e:
        print(f"  ✗ Exception: {e}")

    return None

coinalyze_data = test_coinalyze()


# ============================================================================
# 2. BINANCE PUBLIC API - Forced Liquidations (LIMITED)
# ============================================================================
print("\n" + "="*70)
print("2. BINANCE FUTURES (FREE but LIMITED)")
print("   Real-time feed only, no historical download")
print("   Note: Since April 2021, only 1 liquidation/second is published")
print("="*70)

def test_binance_liquidations():
    """Test Binance liquidation endpoint"""
    # Binance only provides real-time liquidation stream via WebSocket
    # REST API has forceOrders but limited

    print("\n  Binance liquidation data:")
    print("  - Real-time: wss://fstream.binance.com/ws/!forceOrder@arr")
    print("  - Historical: NOT available via public API")
    print("  - Rate limit: 1 liquidation per second per symbol")
    print("  - Alternative: Use Binance Data Vision for historical trades")

    # Check Binance Data Vision
    print("\n  Binance Data Vision (data.binance.vision):")
    print("  - Has historical futures TRADES (not liquidations specifically)")
    print("  - Free CSV download")
    print("  - Goes back to 2019")

test_binance_liquidations()


# ============================================================================
# 3. BYBIT PUBLIC API
# ============================================================================
print("\n" + "="*70)
print("3. BYBIT (FREE)")
print("   Full liquidation data restored Feb 2025")
print("="*70)

def test_bybit_liquidations():
    """Test Bybit liquidation endpoint"""
    # Bybit has a public recent trades endpoint that includes liquidations
    base_url = "https://api.bybit.com"

    print("\n  Testing Bybit API...")

    # Get recent trades (may include liquidations marked as such)
    url = f"{base_url}/v5/market/recent-trade"
    params = {
        "category": "linear",
        "symbol": "BTCUSDT",
        "limit": 100
    }

    try:
        response = requests.get(url, params=params, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if data.get('retCode') == 0:
                trades = data.get('result', {}).get('list', [])
                print(f"  ✓ Got {len(trades)} recent trades")
                print("  Note: Liquidations are part of trade feed, not separate endpoint")
                print("  Historical: Via WebSocket recording or 3rd party (Tardis)")
    except Exception as e:
        print(f"  ✗ Exception: {e}")

test_bybit_liquidations()


# ============================================================================
# 4. HYPERLIQUID (FREE) - On-chain DEX
# ============================================================================
print("\n" + "="*70)
print("4. HYPERLIQUID (FREE)")
print("   Decentralized perp DEX - all data is public")
print("="*70)

def test_hyperliquid():
    """Test Hyperliquid liquidation data"""
    base_url = "https://api.hyperliquid.xyz"

    print("\n  Hyperliquid data sources:")
    print("  - All trades including liquidations are on-chain")
    print("  - Archive bucket: hyperliquid-archive (S3)")
    print("  - API: Real-time clearinghouse state")

    # Get meta info
    try:
        response = requests.post(f"{base_url}/info", json={"type": "meta"}, timeout=30)
        if response.status_code == 200:
            meta = response.json()
            if 'universe' in meta:
                print(f"  ✓ {len(meta['universe'])} markets available")
    except Exception as e:
        print(f"  ✗ Exception: {e}")

test_hyperliquid()


# ============================================================================
# 5. TARDIS.DEV - Best Source (PAID but has samples)
# ============================================================================
print("\n" + "="*70)
print("5. TARDIS.DEV (PAID - Best quality)")
print("   Tick-level liquidation data since 2019")
print("="*70)

print("""
  Tardis.dev offers:
  - Tick-level liquidation data with exact timestamp, price, quantity
  - Coverage: Binance, Bybit, OKX, Deribit, BitMEX, FTX (historical), etc.
  - Format: CSV download or API
  - History: Since March 2019 for most exchanges

  Sample code to download:
  ```python
  from tardis_dev import datasets

  datasets.download(
      exchange="binance-futures",
      data_types=["liquidations"],
      from_date="2024-01-01",
      to_date="2024-01-31",
      symbols=["BTCUSDT"],
      api_key="YOUR_KEY"
  )
  ```

  Free trial: Check tardis.dev for current promotions
  Pricing: Starts ~$50/month for historical data access
""")


# ============================================================================
# 6. GITHUB: liquidations-chart (FREE)
# ============================================================================
print("\n" + "="*70)
print("6. GITHUB: StephanAkkerman/liquidations-chart (FREE)")
print("   Scrapes/accumulates liquidation data from Binance")
print("="*70)

print("""
  Repository: https://github.com/StephanAkkerman/liquidations-chart

  Features:
  - Fetches from Binance public data
  - Accumulates historical data with each run
  - Generates Coinglass-style charts
  - MIT License (free)

  How to use:
  ```bash
  git clone https://github.com/StephanAkkerman/liquidations-chart
  cd liquidations-chart
  pip install -r requirements.txt
  python src/main.py
  ```

  Data range: ~180 days (accumulates more over time)
""")


# ============================================================================
# SUMMARY
# ============================================================================
print("\n" + "="*70)
print("SUMMARY: FREE LIQUIDATION DATA SOURCES")
print("="*70)

summary = """
| Source                | Data Type              | Historical Depth     | Cost    | Quality |
|-----------------------|------------------------|----------------------|---------|---------|
| Coinalyze API         | Aggregated daily liq   | Years (daily)        | FREE    | Good    |
| Binance WS            | Real-time only         | None (live stream)   | FREE    | Limited |
| Bybit API             | Real-time trades       | Limited              | FREE    | Medium  |
| Hyperliquid           | On-chain (all trades)  | Since launch (2023)  | FREE    | Good    |
| GitHub liquidations   | Accumulated daily      | ~180 days+           | FREE    | Medium  |
| Tardis.dev            | Tick-level everything  | Since 2019           | ~$50/mo | Best    |
| CryptoDataDownload    | Summary timeseries     | Varies               | FREE    | Limited |

RECOMMENDATION FOR YOUR THESIS:

1. FREE OPTION: Use Coinalyze daily aggregated data
   - Goes back years on daily timeframe
   - Aggregated across exchanges
   - Good for correlation studies

2. DETAILED OPTION: Tardis.dev (~$50/mo or free trial)
   - Exact liquidation prices and amounts
   - Tick-level timestamps
   - Best for detailed analysis

3. DIY OPTION: Record live liquidations going forward
   - Use Binance/Bybit WebSocket feeds
   - Accumulate your own dataset
   - Free but takes time to build history
"""
print(summary)


# ============================================================================
# SAVE COINALYZE DATA IF AVAILABLE
# ============================================================================
if coinalyze_data:
    print("\n" + "="*70)
    print("SAVING COINALYZE DATA")
    print("="*70)

    df = pd.DataFrame(coinalyze_data)
    df['date'] = pd.to_datetime(df['t'], unit='s')
    df = df.rename(columns={'l': 'long_liq_usd', 's': 'short_liq_usd', 'o': 'open_interest'})

    if 'long_liq_usd' in df.columns and 'short_liq_usd' in df.columns:
        df['total_liq_usd'] = df['long_liq_usd'].fillna(0) + df['short_liq_usd'].fillna(0)

    # Save
    output_file = "twelvedata_export/coinalyze_liquidations.csv"
    df.to_csv(output_file, index=False)
    print(f"  Saved to {output_file}")
    print(f"  Records: {len(df)}")
    print(f"  Columns: {list(df.columns)}")

    # Show sample
    print(f"\n  Sample data:")
    print(df[['date', 'long_liq_usd', 'short_liq_usd', 'total_liq_usd']].head(10).to_string())
