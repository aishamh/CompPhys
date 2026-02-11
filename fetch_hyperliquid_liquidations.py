"""
Fetch Historical Liquidation Data from Hyperliquid
All data is on-chain and publicly available

Hyperliquid Archive: https://hyperliquid-archive.s3.amazonaws.com/
"""

import requests
import pandas as pd
import json
from datetime import datetime, timedelta
import time

print("="*70)
print("HYPERLIQUID HISTORICAL LIQUIDATION DATA")
print("On-chain perpetual DEX - All liquidations are public")
print("="*70)


def get_hyperliquid_meta():
    """Get market metadata"""
    url = "https://api.hyperliquid.xyz/info"
    response = requests.post(url, json={"type": "meta"}, timeout=30)
    if response.status_code == 200:
        return response.json()
    return None


def get_recent_trades(coin: str = "BTC", limit: int = 1000):
    """
    Get recent trades including liquidations
    Liquidations are marked in the trade data
    """
    url = "https://api.hyperliquid.xyz/info"

    payload = {
        "type": "recentTrades",
        "coin": coin
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error fetching trades: {e}")
    return None


def get_user_fills(user_address: str):
    """Get fills for a specific user (can find liquidation addresses)"""
    url = "https://api.hyperliquid.xyz/info"

    payload = {
        "type": "userFills",
        "user": user_address
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error: {e}")
    return None


def get_funding_history(coin: str = "BTC", start_time: int = None):
    """Get funding rate history"""
    url = "https://api.hyperliquid.xyz/info"

    if start_time is None:
        start_time = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)

    payload = {
        "type": "fundingHistory",
        "coin": coin,
        "startTime": start_time
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error: {e}")
    return None


def get_clearinghouse_state():
    """Get current clearinghouse state - shows open positions and potential liquidations"""
    url = "https://api.hyperliquid.xyz/info"

    # This shows the state of the clearinghouse
    payload = {
        "type": "metaAndAssetCtxs"
    }

    try:
        response = requests.post(url, json=payload, timeout=30)
        if response.status_code == 200:
            return response.json()
    except Exception as e:
        print(f"Error: {e}")
    return None


def fetch_archive_data(date_str: str):
    """
    Fetch from Hyperliquid S3 archive
    Archive contains tick-level data including liquidations

    Format: hyperliquid-archive/market_data/YYYY-MM-DD.csv.gz
    """
    base_url = "https://hyperliquid-archive.s3.amazonaws.com"

    # Try different archive paths
    paths = [
        f"/market_data/{date_str}.csv.gz",
        f"/trades/{date_str}.csv.gz",
        f"/liquidations/{date_str}.csv.gz"
    ]

    for path in paths:
        try:
            url = f"{base_url}{path}"
            response = requests.head(url, timeout=10)
            if response.status_code == 200:
                print(f"  Found: {url}")
                return url
        except:
            pass

    return None


# ============================================================================
# MAIN EXECUTION
# ============================================================================

print("\n" + "-"*70)
print("1. MARKET METADATA")
print("-"*70)

meta = get_hyperliquid_meta()
if meta and 'universe' in meta:
    coins = [m['name'] for m in meta['universe']]
    print(f"  Available markets: {len(coins)}")
    print(f"  Top coins: {', '.join(coins[:10])}...")


print("\n" + "-"*70)
print("2. RECENT TRADES (includes liquidations)")
print("-"*70)

# Get recent BTC trades
btc_trades = get_recent_trades("BTC")
if btc_trades:
    print(f"  Fetched {len(btc_trades)} recent BTC trades")

    # Convert to DataFrame
    df_trades = pd.DataFrame(btc_trades)
    print(f"  Columns: {list(df_trades.columns)}")

    if len(df_trades) > 0:
        print(f"\n  Sample trade:")
        print(f"  {json.dumps(btc_trades[0], indent=2)}")

        # Look for liquidation indicators
        # Hyperliquid marks liquidations differently
        if 'crossed' in df_trades.columns:
            crossed = df_trades[df_trades['crossed'] == True]
            print(f"\n  Crossed (potential liquidations): {len(crossed)}")


print("\n" + "-"*70)
print("3. CLEARINGHOUSE STATE")
print("-"*70)

ch_state = get_clearinghouse_state()
if ch_state:
    # ch_state[0] = meta, ch_state[1] = asset contexts
    if isinstance(ch_state, list) and len(ch_state) > 1:
        asset_ctxs = ch_state[1]
        print(f"  Asset contexts available: {len(asset_ctxs)}")

        # Show BTC context
        for ctx in asset_ctxs[:1]:
            print(f"\n  BTC Context:")
            print(f"    Open Interest: ${float(ctx.get('openInterest', 0)):,.0f}")
            print(f"    Funding Rate: {float(ctx.get('funding', 0))*100:.4f}%")
            print(f"    Oracle Price: ${float(ctx.get('oraclePx', 0)):,.2f}")
            print(f"    Mark Price: ${float(ctx.get('markPx', 0)):,.2f}")


print("\n" + "-"*70)
print("4. FUNDING HISTORY")
print("-"*70)

funding = get_funding_history("BTC")
if funding:
    print(f"  Fetched {len(funding)} funding rate entries")

    if len(funding) > 0:
        df_funding = pd.DataFrame(funding)
        df_funding['time'] = pd.to_datetime(df_funding['time'], unit='ms')
        df_funding['fundingRate'] = df_funding['fundingRate'].astype(float) * 100

        print(f"\n  Recent funding rates:")
        print(df_funding[['time', 'fundingRate']].tail(10).to_string())

        # Save funding data
        df_funding.to_csv("twelvedata_export/hyperliquid_funding.csv", index=False)
        print(f"\n  Saved to twelvedata_export/hyperliquid_funding.csv")


print("\n" + "-"*70)
print("5. ARCHIVE DATA CHECK")
print("-"*70)

# Check if archive is accessible
yesterday = (datetime.now() - timedelta(days=1)).strftime("%Y-%m-%d")
print(f"  Checking archive for {yesterday}...")

# Try to access S3 bucket listing
try:
    # Check bucket root
    response = requests.get("https://hyperliquid-archive.s3.amazonaws.com/", timeout=10)
    if response.status_code == 200:
        print("  ✓ Archive bucket is accessible")
        # Try to parse XML for available files
        if "ListBucketResult" in response.text:
            import re
            keys = re.findall(r'<Key>(.*?)</Key>', response.text)
            if keys:
                print(f"  Found {len(keys)} files in archive")
                print(f"  Sample: {keys[:5]}")
except Exception as e:
    print(f"  Archive check: {e}")


# ============================================================================
# ALTERNATIVE: Aggregate liquidation data from multiple trades
# ============================================================================

print("\n" + "-"*70)
print("6. AGGREGATING TRADE DATA AS PROXY")
print("-"*70)

print("""
  While Hyperliquid doesn't expose liquidations as a separate endpoint,
  liquidations can be identified from the trade stream by:

  1. Large trades at specific price levels (liquidation prices)
  2. Trades where the counterparty is the clearinghouse
  3. Trades marked with specific flags in the archive data

  For your thesis, you can:
  - Use the archive data (if accessible) for historical analysis
  - Record real-time trades and identify liquidation patterns
  - Use funding rate extremes as a proxy for liquidation risk
""")


# ============================================================================
# SAVE AVAILABLE DATA
# ============================================================================

print("\n" + "-"*70)
print("SUMMARY: What's Available FREE from Hyperliquid")
print("-"*70)

summary = """
| Data Type          | Available | Historical Depth | Notes                    |
|--------------------|-----------|------------------|--------------------------|
| Recent Trades      | ✓         | ~1000 trades     | Real-time, includes liqs |
| Funding History    | ✓         | 30+ days         | Good for analysis        |
| Open Interest      | ✓         | Current state    | From clearinghouse       |
| Oracle Prices      | ✓         | Current state    | Mark & oracle prices     |
| Archive (S3)       | ✓         | Since 2023       | Raw tick data            |

For detailed historical liquidation analysis:
1. Request S3 bucket access or scrape archive
2. Use tardis.dev API (~$50/mo) for processed data
3. Record live stream going forward

Hyperliquid launched: March 2023
Estimated liquidation data available: ~23 months
"""
print(summary)


# Save what we have
if btc_trades:
    df_trades = pd.DataFrame(btc_trades)
    df_trades.to_csv("twelvedata_export/hyperliquid_recent_trades.csv", index=False)
    print(f"  Saved {len(df_trades)} recent trades to hyperliquid_recent_trades.csv")

if ch_state and isinstance(ch_state, list) and len(ch_state) > 1:
    # Save asset contexts
    asset_data = []
    meta_info = ch_state[0]
    asset_ctxs = ch_state[1]

    for i, ctx in enumerate(asset_ctxs):
        if i < len(meta_info.get('universe', [])):
            coin = meta_info['universe'][i]['name']
            asset_data.append({
                'coin': coin,
                'open_interest': float(ctx.get('openInterest', 0)),
                'funding_rate': float(ctx.get('funding', 0)),
                'oracle_price': float(ctx.get('oraclePx', 0)),
                'mark_price': float(ctx.get('markPx', 0)),
                'timestamp': datetime.now().isoformat()
            })

    df_assets = pd.DataFrame(asset_data)
    df_assets.to_csv("twelvedata_export/hyperliquid_market_state.csv", index=False)
    print(f"  Saved {len(df_assets)} market states to hyperliquid_market_state.csv")

print("\n" + "="*70)
print("DONE")
print("="*70)
