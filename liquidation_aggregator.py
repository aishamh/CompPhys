"""
Free Historical Liquidation Data Aggregator
Fetches liquidation data from multiple free sources

Sources:
1. Hyperliquid API (free) - https://api.hyperliquid.xyz
2. CoinGlass public endpoints (limited free)
3. Coinalyze (free API)
4. Binance public API (limited)
5. Bybit public API (limited)
"""

import requests
import pandas as pd
import numpy as np
import json
import time
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import warnings
warnings.filterwarnings('ignore')


# ============================================================================
# HYPERLIQUID API (FREE)
# ============================================================================

class HyperliquidAPI:
    """
    Hyperliquid DEX API - Completely free, no API key needed
    Docs: https://hyperliquid.gitbook.io/hyperliquid-docs/for-developers/api
    """
    BASE_URL = "https://api.hyperliquid.xyz"

    @staticmethod
    def get_meta() -> Dict:
        """Get exchange metadata"""
        url = f"{HyperliquidAPI.BASE_URL}/info"
        payload = {"type": "meta"}
        try:
            response = requests.post(url, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            print(f"  Error: {e}")
            return None

    @staticmethod
    def get_all_mids() -> Dict:
        """Get all mid prices"""
        url = f"{HyperliquidAPI.BASE_URL}/info"
        payload = {"type": "allMids"}
        try:
            response = requests.post(url, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            print(f"  Error: {e}")
            return None

    @staticmethod
    def get_funding_history(coin: str = "BTC", start_time: int = None) -> List:
        """Get historical funding rates"""
        url = f"{HyperliquidAPI.BASE_URL}/info"

        if start_time is None:
            start_time = int((datetime.now() - timedelta(days=30)).timestamp() * 1000)

        payload = {
            "type": "fundingHistory",
            "coin": coin,
            "startTime": start_time
        }

        try:
            response = requests.post(url, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            print(f"  Error: {e}")
            return None

    @staticmethod
    def get_user_fills(user_address: str) -> List:
        """Get user's trade fills (including liquidations)"""
        url = f"{HyperliquidAPI.BASE_URL}/info"
        payload = {
            "type": "userFills",
            "user": user_address
        }
        try:
            response = requests.post(url, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            print(f"  Error: {e}")
            return None

    @staticmethod
    def get_clearinghouse_state(user_address: str) -> Dict:
        """Get user's positions and margin state"""
        url = f"{HyperliquidAPI.BASE_URL}/info"
        payload = {
            "type": "clearinghouseState",
            "user": user_address
        }
        try:
            response = requests.post(url, json=payload, timeout=30)
            return response.json()
        except Exception as e:
            print(f"  Error: {e}")
            return None


# ============================================================================
# COINALYZE API (FREE)
# ============================================================================

class CoinalyzeAPI:
    """
    Free derivatives data API
    Docs: https://api.coinalyze.net/v1/doc/
    """
    BASE_URL = "https://api.coinalyze.net/v1"

    @staticmethod
    def get_supported_exchanges() -> List:
        """Get list of supported exchanges"""
        url = f"{CoinalyzeAPI.BASE_URL}/exchanges"
        try:
            response = requests.get(url, timeout=30)
            return response.json()
        except Exception as e:
            print(f"  Error: {e}")
            return None

    @staticmethod
    def get_liquidation_history(symbol: str = "BTCUSD_PERP.A", days: int = 365) -> pd.DataFrame:
        """Fetch historical liquidations - AGGREGATED across exchanges"""
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
                if records:
                    df = pd.DataFrame(records)
                    df['date'] = pd.to_datetime(df['t'], unit='s')
                    df['liq_long'] = df.get('l', 0).astype(float)
                    df['liq_short'] = df.get('s', 0).astype(float)
                    df['liq_total'] = df['liq_long'] + df['liq_short']
                    df['source'] = 'coinalyze'
                    print(f"  Retrieved {len(df)} days")
                    return df[['date', 'liq_long', 'liq_short', 'liq_total', 'source']]
        except Exception as e:
            print(f"  Error: {e}")

        return None


# ============================================================================
# BINANCE PUBLIC API (FREE)
# ============================================================================

class BinanceAPI:
    """
    Binance public API - Free, no key needed for public endpoints
    Note: Liquidation stream is websocket only, historical limited
    """
    FAPI_URL = "https://fapi.binance.com"

    @staticmethod
    def get_funding_rate_history(symbol: str = "BTCUSDT", limit: int = 1000) -> pd.DataFrame:
        """Get historical funding rates (proxy for market stress)"""
        print(f"Fetching Binance funding rates for {symbol}...")

        url = f"{BinanceAPI.FAPI_URL}/fapi/v1/fundingRate"
        params = {
            "symbol": symbol,
            "limit": limit
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['fundingTime'], unit='ms')
                df['funding_rate'] = df['fundingRate'].astype(float)
                df['source'] = 'binance'
                print(f"  Retrieved {len(df)} funding rate records")
                return df[['date', 'funding_rate', 'source']]
        except Exception as e:
            print(f"  Error: {e}")

        return None

    @staticmethod
    def get_open_interest_history(symbol: str = "BTCUSDT", period: str = "1d", limit: int = 500) -> pd.DataFrame:
        """Get historical open interest"""
        print(f"Fetching Binance OI for {symbol}...")

        url = f"{BinanceAPI.FAPI_URL}/futures/data/openInterestHist"
        params = {
            "symbol": symbol,
            "period": period,
            "limit": limit
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                df['open_interest'] = df['sumOpenInterest'].astype(float)
                df['open_interest_value'] = df['sumOpenInterestValue'].astype(float)
                df['source'] = 'binance'
                print(f"  Retrieved {len(df)} OI records")
                return df[['date', 'open_interest', 'open_interest_value', 'source']]
        except Exception as e:
            print(f"  Error: {e}")

        return None

    @staticmethod
    def get_long_short_ratio(symbol: str = "BTCUSDT", period: str = "1d", limit: int = 500) -> pd.DataFrame:
        """Get long/short ratio history"""
        print(f"Fetching Binance long/short ratio for {symbol}...")

        url = f"{BinanceAPI.FAPI_URL}/futures/data/globalLongShortAccountRatio"
        params = {
            "symbol": symbol,
            "period": period,
            "limit": limit
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                df['long_short_ratio'] = df['longShortRatio'].astype(float)
                df['long_account'] = df['longAccount'].astype(float)
                df['short_account'] = df['shortAccount'].astype(float)
                df['source'] = 'binance'
                print(f"  Retrieved {len(df)} L/S ratio records")
                return df[['date', 'long_short_ratio', 'long_account', 'short_account', 'source']]
        except Exception as e:
            print(f"  Error: {e}")

        return None

    @staticmethod
    def get_taker_buy_sell_ratio(symbol: str = "BTCUSDT", period: str = "1d", limit: int = 500) -> pd.DataFrame:
        """Get taker buy/sell volume ratio"""
        print(f"Fetching Binance taker buy/sell for {symbol}...")

        url = f"{BinanceAPI.FAPI_URL}/futures/data/takerlongshortRatio"
        params = {
            "symbol": symbol,
            "period": period,
            "limit": limit
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if isinstance(data, list) and len(data) > 0:
                df = pd.DataFrame(data)
                df['date'] = pd.to_datetime(df['timestamp'], unit='ms')
                df['buy_sell_ratio'] = df['buySellRatio'].astype(float)
                df['buy_vol'] = df['buyVol'].astype(float)
                df['sell_vol'] = df['sellVol'].astype(float)
                df['source'] = 'binance'
                print(f"  Retrieved {len(df)} taker records")
                return df[['date', 'buy_sell_ratio', 'buy_vol', 'sell_vol', 'source']]
        except Exception as e:
            print(f"  Error: {e}")

        return None


# ============================================================================
# BYBIT PUBLIC API (FREE)
# ============================================================================

class BybitAPI:
    """
    Bybit public API - Free
    """
    BASE_URL = "https://api.bybit.com"

    @staticmethod
    def get_funding_rate_history(symbol: str = "BTCUSDT", category: str = "linear", limit: int = 200) -> pd.DataFrame:
        """Get historical funding rates"""
        print(f"Fetching Bybit funding rates for {symbol}...")

        url = f"{BybitAPI.BASE_URL}/v5/market/funding/history"
        params = {
            "category": category,
            "symbol": symbol,
            "limit": limit
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                records = data['result']['list']
                df = pd.DataFrame(records)
                df['date'] = pd.to_datetime(df['fundingRateTimestamp'].astype(int), unit='ms')
                df['funding_rate'] = df['fundingRate'].astype(float)
                df['source'] = 'bybit'
                print(f"  Retrieved {len(df)} funding rate records")
                return df[['date', 'funding_rate', 'source']]
        except Exception as e:
            print(f"  Error: {e}")

        return None

    @staticmethod
    def get_open_interest(symbol: str = "BTCUSDT", category: str = "linear", interval: str = "1d", limit: int = 200) -> pd.DataFrame:
        """Get historical open interest"""
        print(f"Fetching Bybit OI for {symbol}...")

        url = f"{BybitAPI.BASE_URL}/v5/market/open-interest"
        params = {
            "category": category,
            "symbol": symbol,
            "intervalTime": interval,
            "limit": limit
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            data = response.json()

            if data.get('retCode') == 0 and data.get('result', {}).get('list'):
                records = data['result']['list']
                df = pd.DataFrame(records)
                df['date'] = pd.to_datetime(df['timestamp'].astype(int), unit='ms')
                df['open_interest'] = df['openInterest'].astype(float)
                df['source'] = 'bybit'
                print(f"  Retrieved {len(df)} OI records")
                return df[['date', 'open_interest', 'source']]
        except Exception as e:
            print(f"  Error: {e}")

        return None


# ============================================================================
# COINGLASS PUBLIC (LIMITED FREE)
# ============================================================================

class CoinGlassPublic:
    """
    CoinGlass has some public endpoints without API key
    """

    @staticmethod
    def get_liquidation_chart_data() -> Optional[Dict]:
        """Try to get public liquidation data"""
        print("Fetching CoinGlass public liquidation data...")

        # This endpoint may or may not work without auth
        url = "https://open-api.coinglass.com/public/v2/liquidation_history"
        params = {
            "symbol": "BTC",
            "time_type": "h24"
        }

        try:
            response = requests.get(url, params=params, timeout=30)
            if response.status_code == 200:
                data = response.json()
                if data.get('success'):
                    print(f"  Retrieved CoinGlass data")
                    return data.get('data')
        except Exception as e:
            print(f"  CoinGlass public endpoint failed: {e}")

        return None


# ============================================================================
# AGGREGATE ALL DATA
# ============================================================================

def aggregate_liquidation_data() -> pd.DataFrame:
    """
    Aggregate liquidation-related data from all free sources
    """
    print("="*60)
    print("AGGREGATING FREE LIQUIDATION DATA")
    print("="*60)

    all_data = []

    # 1. Coinalyze liquidations
    print("\n--- COINALYZE ---")
    liq_data = CoinalyzeAPI.get_liquidation_history(days=365)
    if liq_data is not None:
        all_data.append(('liquidations', liq_data))
    time.sleep(1)

    # 2. Binance funding rates
    print("\n--- BINANCE ---")
    binance_funding = BinanceAPI.get_funding_rate_history()
    if binance_funding is not None:
        all_data.append(('binance_funding', binance_funding))
    time.sleep(0.5)

    # 3. Binance OI
    binance_oi = BinanceAPI.get_open_interest_history()
    if binance_oi is not None:
        all_data.append(('binance_oi', binance_oi))
    time.sleep(0.5)

    # 4. Binance Long/Short ratio
    binance_ls = BinanceAPI.get_long_short_ratio()
    if binance_ls is not None:
        all_data.append(('binance_ls', binance_ls))
    time.sleep(0.5)

    # 5. Binance Taker Buy/Sell
    binance_taker = BinanceAPI.get_taker_buy_sell_ratio()
    if binance_taker is not None:
        all_data.append(('binance_taker', binance_taker))
    time.sleep(0.5)

    # 6. Bybit funding
    print("\n--- BYBIT ---")
    bybit_funding = BybitAPI.get_funding_rate_history()
    if bybit_funding is not None:
        all_data.append(('bybit_funding', bybit_funding))
    time.sleep(0.5)

    # 7. Bybit OI
    bybit_oi = BybitAPI.get_open_interest()
    if bybit_oi is not None:
        all_data.append(('bybit_oi', bybit_oi))
    time.sleep(0.5)

    # 8. Hyperliquid funding
    print("\n--- HYPERLIQUID ---")
    hl_funding = HyperliquidAPI.get_funding_history("BTC")
    if hl_funding:
        df = pd.DataFrame(hl_funding)
        if len(df) > 0:
            df['date'] = pd.to_datetime(df['time'], unit='ms')
            df['funding_rate'] = df['fundingRate'].astype(float)
            df['source'] = 'hyperliquid'
            print(f"  Retrieved {len(df)} Hyperliquid funding records")
            all_data.append(('hyperliquid_funding', df[['date', 'funding_rate', 'source']]))

    # 9. CoinGlass public
    print("\n--- COINGLASS ---")
    cg_data = CoinGlassPublic.get_liquidation_chart_data()
    if cg_data:
        all_data.append(('coinglass', cg_data))

    # Summary
    print("\n" + "="*60)
    print("DATA SUMMARY")
    print("="*60)

    for name, data in all_data:
        if isinstance(data, pd.DataFrame):
            print(f"  {name}: {len(data)} records")
        else:
            print(f"  {name}: {type(data)}")

    return all_data


def merge_and_save_data(all_data: List) -> pd.DataFrame:
    """Merge all data into a single dataframe"""
    print("\n" + "="*60)
    print("MERGING DATA")
    print("="*60)

    # Start with BTC price data
    try:
        btc = pd.read_csv("twelvedata_export/btc_usd_daily.csv")
        btc['date'] = pd.to_datetime(btc['date']).dt.normalize()
        print(f"  Loaded BTC prices: {len(btc)} days")
    except:
        print("  Failed to load BTC prices")
        return None

    merged = btc.copy()

    # Merge each dataset
    for name, data in all_data:
        if isinstance(data, pd.DataFrame) and 'date' in data.columns:
            data = data.copy()
            data['date'] = pd.to_datetime(data['date']).dt.normalize()

            # Remove source column before merge to avoid conflicts
            merge_cols = [c for c in data.columns if c not in ['source']]

            # Rename columns to include source
            rename_dict = {c: f"{name}_{c}" if c != 'date' else c for c in merge_cols}
            data_renamed = data[merge_cols].rename(columns=rename_dict)

            # Aggregate if multiple entries per day
            data_agg = data_renamed.groupby('date').last().reset_index()

            merged = merged.merge(data_agg, on='date', how='left')
            print(f"  Merged {name}: {len(data_agg)} unique dates")

    print(f"\n  Final merged dataset: {len(merged)} rows, {len(merged.columns)} columns")

    # Save
    output_file = "twelvedata_export/aggregated_liquidation_data.csv"
    merged.to_csv(output_file, index=False)
    print(f"  Saved to {output_file}")

    return merged


def main():
    print("="*60)
    print("FREE LIQUIDATION DATA AGGREGATOR")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}\n")

    # Fetch all data
    all_data = aggregate_liquidation_data()

    # Merge and save
    merged = merge_and_save_data(all_data)

    # List available columns
    if merged is not None:
        print("\n" + "="*60)
        print("AVAILABLE COLUMNS FOR BACKTESTING")
        print("="*60)
        for col in sorted(merged.columns):
            non_null = merged[col].notna().sum()
            print(f"  {col}: {non_null} values")

    return merged


if __name__ == "__main__":
    merged = main()
