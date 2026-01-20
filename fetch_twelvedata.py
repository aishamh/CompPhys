"""
TwelveData API Data Fetcher for Cryptocurrency Crash Prediction Thesis
Fetches historical price data for BTC pairs, forex rates, and USD index
"""

import requests
import pandas as pd
import numpy as np
import os
import time
from datetime import datetime

# Configuration
API_KEY = "ee002dce1abd4500b1a2209735df56a4"
BASE_URL = "https://api.twelvedata.com"
OUTPUT_DIR = "twelvedata_export"

# Assets to fetch
ASSETS = [
    {"symbol": "BTC/USD", "filename": "btc_usd_daily.csv", "type": "crypto"},
    {"symbol": "BTC/JPY", "filename": "btc_jpy_daily.csv", "type": "crypto"},
    {"symbol": "BTC/EUR", "filename": "btc_eur_daily.csv", "type": "crypto"},
    {"symbol": "USD/JPY", "filename": "usd_jpy_daily.csv", "type": "forex"},
    {"symbol": "EUR/USD", "filename": "eur_usd_daily.csv", "type": "forex"},
    {"symbol": "UUP", "filename": "uup_daily.csv", "type": "etf"},  # USD Index proxy
]


def fetch_time_series(symbol: str, outputsize: int = 5000, interval: str = "1day", max_retries: int = 4) -> pd.DataFrame:
    """
    Fetch time series data from TwelveData API with retry logic

    Args:
        symbol: Trading pair or ticker symbol
        outputsize: Number of data points (max 5000)
        interval: Time interval (1day for daily)
        max_retries: Maximum number of retry attempts

    Returns:
        DataFrame with OHLCV data
    """
    endpoint = f"{BASE_URL}/time_series"
    params = {
        "symbol": symbol,
        "interval": interval,
        "outputsize": outputsize,
        "apikey": API_KEY,
        "format": "JSON"
    }

    print(f"Fetching {symbol}...")

    for attempt in range(max_retries + 1):
        try:
            response = requests.get(endpoint, params=params, timeout=30)
            response.raise_for_status()
            break
        except requests.exceptions.RequestException as e:
            if attempt < max_retries:
                wait_time = 2 ** (attempt + 1)  # 2, 4, 8, 16 seconds
                print(f"  Attempt {attempt + 1} failed, retrying in {wait_time}s...")
                time.sleep(wait_time)
            else:
                print(f"  Network error fetching {symbol} after {max_retries + 1} attempts: {e}")
                return None

    try:
        data = response.json()
    except Exception as e:
        print(f"  JSON decode error for {symbol}: {e}")
        print(f"  Response text: {response.text[:200]}")
        return None

    if "code" in data and data["code"] != 200:
        print(f"  Error fetching {symbol}: {data.get('message', 'Unknown error')}")
        return None

    if "values" not in data:
        print(f"  No data returned for {symbol}")
        return None

    # Convert to DataFrame
    df = pd.DataFrame(data["values"])

    # Convert columns to appropriate types
    df["datetime"] = pd.to_datetime(df["datetime"])
    for col in ["open", "high", "low", "close"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    if "volume" in df.columns:
        df["volume"] = pd.to_numeric(df["volume"], errors="coerce")
    else:
        df["volume"] = np.nan

    # Sort by date ascending
    df = df.sort_values("datetime").reset_index(drop=True)

    # Rename datetime to date for clarity
    df = df.rename(columns={"datetime": "date"})

    # Format date as YYYY-MM-DD
    df["date"] = df["date"].dt.strftime("%Y-%m-%d")

    # Select and order columns
    columns = ["date", "open", "high", "low", "close", "volume"]
    df = df[columns]

    print(f"  Retrieved {len(df)} data points from {df['date'].iloc[0]} to {df['date'].iloc[-1]}")

    return df


def save_to_csv(df: pd.DataFrame, filename: str) -> None:
    """Save DataFrame to CSV file"""
    filepath = os.path.join(OUTPUT_DIR, filename)
    df.to_csv(filepath, index=False)
    print(f"  Saved to {filepath}")


def calculate_daily_returns(df: pd.DataFrame, price_col: str = "close") -> pd.Series:
    """Calculate daily returns from price series"""
    return df[price_col].pct_change() * 100


def calculate_rolling_correlation(series1: pd.Series, series2: pd.Series, window: int) -> pd.Series:
    """Calculate rolling correlation between two series"""
    return series1.rolling(window=window).corr(series2)


def create_combined_analysis(data_dict: dict) -> pd.DataFrame:
    """
    Create combined analysis file with:
    1. BTC/JPY implied from BTC/USD * USD/JPY (cross-rate validation)
    2. Daily returns for each asset
    3. Rolling 30-day and 60-day correlations between BTC and USD/JPY
    """
    print("\nCreating combined analysis...")

    # Load the required datasets
    btc_usd = data_dict.get("BTC/USD")
    btc_jpy = data_dict.get("BTC/JPY")
    usd_jpy = data_dict.get("USD/JPY")
    eur_usd = data_dict.get("EUR/USD")
    btc_eur = data_dict.get("BTC/EUR")
    uup = data_dict.get("UUP")

    if btc_usd is None or usd_jpy is None:
        print("  Error: Required data for BTC/USD or USD/JPY not available")
        return None

    # Convert date columns to datetime for merging
    for key, df in data_dict.items():
        if df is not None:
            df["date"] = pd.to_datetime(df["date"])

    # Start with BTC/USD as base
    combined = btc_usd[["date", "close"]].copy()
    combined = combined.rename(columns={"close": "btc_usd_close"})

    # Merge USD/JPY
    if usd_jpy is not None:
        usd_jpy_merge = usd_jpy[["date", "close"]].rename(columns={"close": "usd_jpy_close"})
        combined = combined.merge(usd_jpy_merge, on="date", how="outer")

    # Merge BTC/JPY (actual)
    if btc_jpy is not None:
        btc_jpy_merge = btc_jpy[["date", "close"]].rename(columns={"close": "btc_jpy_actual"})
        combined = combined.merge(btc_jpy_merge, on="date", how="outer")

    # Merge EUR/USD
    if eur_usd is not None:
        eur_usd_merge = eur_usd[["date", "close"]].rename(columns={"close": "eur_usd_close"})
        combined = combined.merge(eur_usd_merge, on="date", how="outer")

    # Merge BTC/EUR
    if btc_eur is not None:
        btc_eur_merge = btc_eur[["date", "close"]].rename(columns={"close": "btc_eur_close"})
        combined = combined.merge(btc_eur_merge, on="date", how="outer")

    # Merge UUP (USD Index proxy)
    if uup is not None:
        uup_merge = uup[["date", "close"]].rename(columns={"close": "uup_close"})
        combined = combined.merge(uup_merge, on="date", how="outer")

    # Sort by date
    combined = combined.sort_values("date").reset_index(drop=True)

    # 1. Calculate implied BTC/JPY from BTC/USD * USD/JPY
    combined["btc_jpy_implied"] = combined["btc_usd_close"] * combined["usd_jpy_close"]

    # Calculate cross-rate error (%)
    if "btc_jpy_actual" in combined.columns:
        combined["cross_rate_error_pct"] = (
            (combined["btc_jpy_implied"] - combined["btc_jpy_actual"]) /
            combined["btc_jpy_actual"] * 100
        )

    # 2. Calculate daily returns for each asset
    combined["btc_usd_return"] = combined["btc_usd_close"].pct_change() * 100
    combined["usd_jpy_return"] = combined["usd_jpy_close"].pct_change() * 100

    if "btc_jpy_actual" in combined.columns:
        combined["btc_jpy_return"] = combined["btc_jpy_actual"].pct_change() * 100

    if "eur_usd_close" in combined.columns:
        combined["eur_usd_return"] = combined["eur_usd_close"].pct_change() * 100

    if "btc_eur_close" in combined.columns:
        combined["btc_eur_return"] = combined["btc_eur_close"].pct_change() * 100

    if "uup_close" in combined.columns:
        combined["uup_return"] = combined["uup_close"].pct_change() * 100

    # 3. Rolling correlations between BTC/USD and USD/JPY
    combined["corr_btc_usdjpy_30d"] = (
        combined["btc_usd_return"].rolling(window=30).corr(combined["usd_jpy_return"])
    )
    combined["corr_btc_usdjpy_60d"] = (
        combined["btc_usd_return"].rolling(window=60).corr(combined["usd_jpy_return"])
    )

    # Also calculate BTC vs UUP (USD Index) correlation if available
    if "uup_return" in combined.columns:
        combined["corr_btc_uup_30d"] = (
            combined["btc_usd_return"].rolling(window=30).corr(combined["uup_return"])
        )
        combined["corr_btc_uup_60d"] = (
            combined["btc_usd_return"].rolling(window=60).corr(combined["uup_return"])
        )

    # Format date back to string
    combined["date"] = combined["date"].dt.strftime("%Y-%m-%d")

    return combined


def print_summary_statistics(data_dict: dict, combined: pd.DataFrame) -> None:
    """Print summary statistics for the fetched data"""
    print("\n" + "="*60)
    print("SUMMARY STATISTICS")
    print("="*60)

    for symbol, df in data_dict.items():
        if df is not None:
            print(f"\n{symbol}:")
            print(f"  Date range: {df['date'].iloc[0]} to {df['date'].iloc[-1]}")
            print(f"  Total records: {len(df)}")
            print(f"  Close price - Min: {df['close'].min():.4f}, Max: {df['close'].max():.4f}")

    if combined is not None:
        print("\n" + "-"*60)
        print("CROSS-RATE VALIDATION (BTC/JPY implied vs actual):")
        if "cross_rate_error_pct" in combined.columns:
            error = combined["cross_rate_error_pct"].dropna()
            print(f"  Mean error: {error.mean():.4f}%")
            print(f"  Std dev: {error.std():.4f}%")
            print(f"  Max error: {error.abs().max():.4f}%")

        print("\nROLLING CORRELATIONS (BTC/USD vs USD/JPY):")
        corr_30 = combined["corr_btc_usdjpy_30d"].dropna()
        corr_60 = combined["corr_btc_usdjpy_60d"].dropna()
        if len(corr_30) > 0:
            print(f"  30-day correlation - Mean: {corr_30.mean():.4f}, Std: {corr_30.std():.4f}")
        if len(corr_60) > 0:
            print(f"  60-day correlation - Mean: {corr_60.mean():.4f}, Std: {corr_60.std():.4f}")


def main():
    """Main function to fetch all data and create analysis"""
    print("="*60)
    print("TwelveData API Data Fetcher")
    print("Cryptocurrency Crash Prediction Thesis Analysis")
    print("="*60 + "\n")

    # Create output directory if it doesn't exist
    os.makedirs(OUTPUT_DIR, exist_ok=True)

    # Dictionary to store all fetched data
    data_dict = {}

    # Fetch each asset
    for asset in ASSETS:
        symbol = asset["symbol"]
        filename = asset["filename"]

        df = fetch_time_series(symbol, outputsize=5000)

        if df is not None:
            save_to_csv(df, filename)
            data_dict[symbol] = df

        # Rate limiting - TwelveData has API limits
        time.sleep(1)

    # Try to fetch DXY directly (may not be available)
    print("\nAttempting to fetch DXY (US Dollar Index)...")
    dxy_df = fetch_time_series("DXY", outputsize=5000)
    if dxy_df is not None:
        save_to_csv(dxy_df, "dxy_daily.csv")
        data_dict["DXY"] = dxy_df
    else:
        print("  DXY not available, using UUP as proxy")

    # Create combined analysis
    combined = create_combined_analysis(data_dict)

    if combined is not None:
        save_to_csv(combined, "combined_analysis.csv")
        print(f"  Combined analysis saved with {len(combined)} records")

    # Print summary statistics
    print_summary_statistics(data_dict, combined)

    # List all saved files
    print("\n" + "="*60)
    print("FILES SAVED:")
    print("="*60)
    for f in sorted(os.listdir(OUTPUT_DIR)):
        filepath = os.path.join(OUTPUT_DIR, f)
        size = os.path.getsize(filepath)
        print(f"  {f} ({size:,} bytes)")

    print("\nData export completed successfully!")
    return data_dict, combined


if __name__ == "__main__":
    data_dict, combined = main()
