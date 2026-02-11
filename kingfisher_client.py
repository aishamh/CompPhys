"""
Kingfisher API Client
Fetches historical liquidation data with prices and amounts

Docs: https://docs.thekingfisher.io/products/kf-api

Requires:
- Kingfisher subscription (API access)
- Login credentials or API token
"""

import requests
import pandas as pd
import numpy as np
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import warnings
warnings.filterwarnings('ignore')


class KingfisherClient:
    """
    Client for Kingfisher Liquidation API
    """

    BASE_URL = "https://api.thekingfisher.io"  # or alpha.thekingfisher.io

    def __init__(self, login: str = None, password: str = None, token: str = None):
        """
        Initialize with credentials or existing token

        Args:
            login: Kingfisher username/email
            password: Kingfisher password
            token: Existing bearer token (if already authenticated)
        """
        self.login = login
        self.password = password
        self.token = token
        self.session = requests.Session()

        if token:
            self.session.headers.update({
                "Authorization": f"Bearer {token}"
            })

    def authenticate(self) -> bool:
        """
        Authenticate and get bearer token

        Returns:
            True if authentication successful
        """
        if not self.login or not self.password:
            print("Error: Login credentials required")
            return False

        url = f"{self.BASE_URL}/api/auth/login"
        payload = {
            "login": self.login,
            "password": self.password
        }

        try:
            response = self.session.post(url, json=payload, timeout=30)
            data = response.json()

            if response.status_code == 200 and 'token' in data:
                self.token = data['token']
                self.session.headers.update({
                    "Authorization": f"Bearer {self.token}"
                })
                print("✓ Authentication successful")
                return True
            else:
                print(f"✗ Authentication failed: {data}")
                return False
        except Exception as e:
            print(f"✗ Authentication error: {e}")
            return False

    def get_latest_liquidation_map(
        self,
        exchange: str = "binance",
        pair: str = "BTC/USDT",
        liq_type: str = "all_leverage"
    ) -> Optional[Dict]:
        """
        Get the latest liquidation map

        Args:
            exchange: Exchange name (binance, bybit, okx, etc.)
            pair: Trading pair (BTC/USDT, ETH/USDT, etc.)
            liq_type: Type of liquidation data:
                - "all_leverage": All leverage positions
                - "high_leverage": High leverage positions only

        Returns:
            Liquidation map data with price clusters and densities
        """
        if not self.token:
            print("Error: Not authenticated. Call authenticate() first.")
            return None

        url = f"{self.BASE_URL}/api/private/map/latest"
        payload = {
            "exchange": exchange,
            "pair": pair,
            "type": liq_type
        }

        try:
            response = self.session.post(url, json=payload, timeout=30)
            data = response.json()

            if response.status_code == 200:
                return data
            else:
                print(f"Error: {data}")
                return None
        except Exception as e:
            print(f"Error fetching liquidation map: {e}")
            return None

    def get_historical_liquidation_map(
        self,
        exchange: str = "binance",
        pair: str = "BTC/USDT",
        timestamp: int = None,
        liq_type: str = "all_leverage"
    ) -> Optional[Dict]:
        """
        Get historical liquidation map at specific timestamp

        NOTE: This endpoint is being reworked according to Kingfisher docs

        Args:
            exchange: Exchange name
            pair: Trading pair
            timestamp: Unix timestamp (milliseconds)
            liq_type: Type of liquidation data

        Returns:
            Historical liquidation map data
        """
        if not self.token:
            print("Error: Not authenticated")
            return None

        if timestamp is None:
            # Default to 24 hours ago
            timestamp = int((datetime.now() - timedelta(days=1)).timestamp() * 1000)

        url = f"{self.BASE_URL}/api/private/map/timestamp"
        payload = {
            "exchange": exchange,
            "pair": pair,
            "ts": timestamp,
            "type": liq_type
        }

        try:
            response = self.session.post(url, json=payload, timeout=30)
            data = response.json()

            if response.status_code == 200:
                return data
            else:
                print(f"Error: {data}")
                return None
        except Exception as e:
            print(f"Error: {e}")
            return None


def parse_liquidation_map(liq_map: Dict) -> pd.DataFrame:
    """
    Parse Kingfisher liquidation map response into DataFrame

    The response contains clusters with:
    - Price levels
    - Density/concentration values
    - Long/short positions

    Args:
        liq_map: Raw API response

    Returns:
        DataFrame with price levels and liquidation amounts
    """
    if not liq_map or 'result' not in liq_map:
        return None

    result = liq_map['result']
    records = []

    # Parse clusters (structure depends on Kingfisher's response format)
    if isinstance(result, dict):
        # Handle different possible response structures
        for key, value in result.items():
            if isinstance(value, list):
                for item in value:
                    if isinstance(item, dict):
                        records.append({
                            'cluster': key,
                            'price': item.get('price', item.get('p')),
                            'density': item.get('density', item.get('d')),
                            'amount': item.get('amount', item.get('a')),
                            'side': item.get('side', 'unknown')
                        })
            elif isinstance(value, dict):
                records.append({
                    'cluster': key,
                    'price': value.get('price'),
                    'density': value.get('density'),
                    'amount': value.get('amount'),
                    'side': value.get('side')
                })

    if records:
        return pd.DataFrame(records)

    # If simple list structure
    if isinstance(result, list):
        return pd.DataFrame(result)

    return None


def load_kingfisher_export(filepath: str) -> pd.DataFrame:
    """
    Load Kingfisher data exported from the web interface

    Kingfisher allows CSV/JSON exports of liquidation data

    Args:
        filepath: Path to exported file

    Returns:
        DataFrame with liquidation data
    """
    if not os.path.exists(filepath):
        print(f"File not found: {filepath}")
        return None

    ext = os.path.splitext(filepath)[1].lower()

    try:
        if ext == '.csv':
            df = pd.read_csv(filepath)
        elif ext == '.json':
            with open(filepath, 'r') as f:
                data = json.load(f)
            df = pd.DataFrame(data)
        else:
            print(f"Unsupported file type: {ext}")
            return None

        print(f"Loaded {len(df)} records from {filepath}")
        return df
    except Exception as e:
        print(f"Error loading file: {e}")
        return None


def analyze_liquidation_levels(liq_df: pd.DataFrame, current_price: float) -> Dict:
    """
    Analyze liquidation levels relative to current price

    Args:
        liq_df: DataFrame with liquidation data (needs 'price' and 'amount' columns)
        current_price: Current BTC price

    Returns:
        Analysis of liquidation clusters above/below price
    """
    if liq_df is None or 'price' not in liq_df.columns:
        return None

    liq_df = liq_df.dropna(subset=['price'])

    # Liquidations above price (shorts)
    above = liq_df[liq_df['price'] > current_price]
    # Liquidations below price (longs)
    below = liq_df[liq_df['price'] < current_price]

    # Find nearest major clusters
    if 'amount' in liq_df.columns or 'density' in liq_df.columns:
        amount_col = 'amount' if 'amount' in liq_df.columns else 'density'

        # Sort by amount/density
        above_sorted = above.nlargest(5, amount_col) if len(above) > 0 else pd.DataFrame()
        below_sorted = below.nlargest(5, amount_col) if len(below) > 0 else pd.DataFrame()
    else:
        above_sorted = above.head(5)
        below_sorted = below.head(5)

    analysis = {
        'current_price': current_price,
        'total_liq_above': len(above),
        'total_liq_below': len(below),
        'nearest_short_squeeze': above_sorted['price'].min() if len(above_sorted) > 0 else None,
        'nearest_long_liquidation': below_sorted['price'].max() if len(below_sorted) > 0 else None,
        'major_levels_above': above_sorted['price'].tolist() if len(above_sorted) > 0 else [],
        'major_levels_below': below_sorted['price'].tolist() if len(below_sorted) > 0 else [],
    }

    # Calculate distance to nearest levels
    if analysis['nearest_short_squeeze']:
        analysis['pct_to_short_squeeze'] = (
            (analysis['nearest_short_squeeze'] - current_price) / current_price * 100
        )
    if analysis['nearest_long_liquidation']:
        analysis['pct_to_long_liquidation'] = (
            (current_price - analysis['nearest_long_liquidation']) / current_price * 100
        )

    return analysis


# ============================================================================
# EXAMPLE USAGE / INTEGRATION WITH OUR STRATEGY
# ============================================================================

def integrate_with_etf_strategy(
    liq_data: pd.DataFrame,
    etf_data: pd.DataFrame,
    gold_data: pd.DataFrame
) -> pd.DataFrame:
    """
    Integrate Kingfisher liquidation data with our ETF + Gold strategy

    Enhanced signal:
    - ETF outflows (contrarian buy signal)
    - Gold rising (risk-off confirmation)
    - Price near major liquidation cluster (catalyst for move)

    Args:
        liq_data: Kingfisher liquidation levels
        etf_data: ETF flow data
        gold_data: Gold price data

    Returns:
        Combined signal DataFrame
    """
    # This is a template - actual implementation depends on your Kingfisher data format
    print("Integration template - customize based on your Kingfisher export format")

    # Example logic:
    # 1. Load daily liquidation levels
    # 2. Calculate distance from current price to nearest liq cluster
    # 3. Add as additional signal to ETF + Gold strategy

    # Signal enhancement:
    # ULTRA_BUY = etf_outflow + gold_rising + price_near_liq_cluster
    # ULTRA_SELL = etf_inflow + gold_falling + price_near_liq_cluster

    return None


def main():
    """
    Demo of Kingfisher integration

    To use:
    1. Set your Kingfisher credentials
    2. Or load exported data file
    """
    print("="*60)
    print("KINGFISHER LIQUIDATION DATA CLIENT")
    print("="*60)

    # Option 1: Use API with credentials
    # Uncomment and fill in your credentials:
    #
    # client = KingfisherClient(
    #     login="your_email@example.com",
    #     password="your_password"
    # )
    #
    # if client.authenticate():
    #     # Get latest liquidation map
    #     liq_map = client.get_latest_liquidation_map(
    #         exchange="binance",
    #         pair="BTC/USDT",
    #         liq_type="all_leverage"
    #     )
    #
    #     if liq_map:
    #         df = parse_liquidation_map(liq_map)
    #         print(df.head())

    # Option 2: Load exported file
    print("\nTo use with exported Kingfisher data:")
    print("  1. Export liquidation data from app.thekingfisher.io")
    print("  2. Save as CSV or JSON")
    print("  3. Call: load_kingfisher_export('path/to/file.csv')")

    # Example with mock data
    print("\n" + "-"*60)
    print("EXAMPLE: Analyzing liquidation levels")
    print("-"*60)

    # Mock liquidation data (replace with your actual data)
    mock_data = pd.DataFrame({
        'price': [85000, 87000, 89000, 91000, 93000, 82000, 80000, 78000, 75000, 70000],
        'amount': [150, 200, 180, 250, 300, 180, 220, 190, 280, 350],
        'side': ['short', 'short', 'short', 'short', 'short', 'long', 'long', 'long', 'long', 'long']
    })

    current_price = 84000

    analysis = analyze_liquidation_levels(mock_data, current_price)

    if analysis:
        print(f"\n  Current BTC Price: ${analysis['current_price']:,.0f}")
        print(f"\n  SHORT SQUEEZE LEVELS (above price):")
        print(f"    Nearest: ${analysis['nearest_short_squeeze']:,.0f} ({analysis.get('pct_to_short_squeeze', 0):.1f}% away)")
        print(f"    Major levels: {['$' + f'{p:,.0f}' for p in analysis['major_levels_above']]}")

        print(f"\n  LONG LIQUIDATION LEVELS (below price):")
        print(f"    Nearest: ${analysis['nearest_long_liquidation']:,.0f} ({analysis.get('pct_to_long_liquidation', 0):.1f}% away)")
        print(f"    Major levels: {['$' + f'{p:,.0f}' for p in analysis['major_levels_below']]}")

    print("\n" + "="*60)
    print("TO INTEGRATE WITH YOUR STRATEGY:")
    print("="*60)
    print("""
    1. Export your Kingfisher data (CSV/JSON)
    2. Load with: df = load_kingfisher_export('path/to/data.csv')
    3. Analyze levels: analysis = analyze_liquidation_levels(df, current_price)
    4. Add to strategy:

       ULTRA_SIGNAL = (
           etf_outflow &
           gold_rising &
           (price_near_major_liq_cluster)  # Within 3% of cluster
       )
    """)


if __name__ == "__main__":
    main()
