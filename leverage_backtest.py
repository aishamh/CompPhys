"""
Leverage Backtest for Scenario A: Large ETF Outflows + Gold Rising
Determines maximum safe leverage based on drawdown analysis
"""

import pandas as pd
import numpy as np
import json
from datetime import datetime
import warnings
warnings.filterwarnings('ignore')


def load_merged_data():
    """Load the merged BTC-Gold-ETF data"""
    df = pd.read_csv("twelvedata_export/btc_gold_etf_merged.csv")
    df['date'] = pd.to_datetime(df['date'])
    return df


def identify_scenario_a_trades(df: pd.DataFrame) -> pd.DataFrame:
    """
    Identify Scenario A trading signals:
    - Large ETF outflows (bottom 10%)
    - Gold rising (5-day momentum positive)
    """
    # Calculate indicators
    df = df.copy()
    df['gold_5d_return'] = df['gold_close'].pct_change(5) * 100
    df['gold_rising'] = (df['gold_5d_return'] > 0).astype(int)

    # Flow thresholds
    flow_10th = df['total_flow_usd_millions'].quantile(0.1)

    # Forward returns (what we'd capture)
    df['fwd_return_1d'] = df['close'].pct_change().shift(-1)
    df['fwd_return_5d'] = df['close'].pct_change(5).shift(-5)
    df['fwd_return_10d'] = df['close'].pct_change(10).shift(-10)

    # Identify Scenario A signals
    df['signal_a'] = (
        (df['total_flow_usd_millions'] <= flow_10th) &
        (df['gold_rising'] == 1)
    ).astype(int)

    return df, flow_10th


def backtest_strategy(df: pd.DataFrame, holding_period: int = 5) -> dict:
    """
    Backtest the Scenario A strategy

    Args:
        df: DataFrame with signals
        holding_period: Days to hold after signal (default 5)

    Returns:
        Dictionary with backtest results
    """
    print("="*60)
    print(f"SCENARIO A BACKTEST (Holding Period: {holding_period} days)")
    print("="*60)

    # Get signal dates
    signal_dates = df[df['signal_a'] == 1]['date'].tolist()
    print(f"\nTotal signals: {len(signal_dates)}")
    print(f"First signal: {min(signal_dates).date() if signal_dates else 'N/A'}")
    print(f"Last signal: {max(signal_dates).date() if signal_dates else 'N/A'}")

    # Calculate trade returns
    if holding_period == 5:
        return_col = 'fwd_return_5d'
    elif holding_period == 10:
        return_col = 'fwd_return_10d'
    else:
        return_col = 'fwd_return_1d'

    trades = df[df['signal_a'] == 1][['date', 'close', return_col, 'total_flow_usd_millions', 'gold_5d_return']].copy()
    trades = trades.dropna()
    trades = trades.rename(columns={return_col: 'trade_return'})
    trades['trade_return_pct'] = trades['trade_return'] * 100

    print(f"Valid trades (with return data): {len(trades)}")

    if len(trades) == 0:
        return None

    # =========================================================================
    # TRADE-BY-TRADE ANALYSIS
    # =========================================================================
    print("\n" + "-"*60)
    print("TRADE-BY-TRADE RESULTS")
    print("-"*60)

    trades['cumulative_return'] = (1 + trades['trade_return']).cumprod() - 1
    trades['trade_num'] = range(1, len(trades) + 1)

    # Calculate running drawdown
    trades['cumulative_value'] = (1 + trades['trade_return']).cumprod()
    trades['running_max'] = trades['cumulative_value'].cummax()
    trades['drawdown'] = (trades['cumulative_value'] - trades['running_max']) / trades['running_max']

    # Print each trade
    print(f"\n{'Trade':<6} {'Date':<12} {'Return':<10} {'Cumulative':<12} {'Drawdown':<10}")
    print("-"*50)

    for _, row in trades.iterrows():
        print(f"{int(row['trade_num']):<6} {row['date'].strftime('%Y-%m-%d'):<12} "
              f"{row['trade_return_pct']:>+7.2f}%  {row['cumulative_return']*100:>+9.2f}%  "
              f"{row['drawdown']*100:>+8.2f}%")

    # =========================================================================
    # SUMMARY STATISTICS
    # =========================================================================
    print("\n" + "-"*60)
    print("SUMMARY STATISTICS")
    print("-"*60)

    total_return = trades['cumulative_return'].iloc[-1] * 100
    avg_return = trades['trade_return_pct'].mean()
    std_return = trades['trade_return_pct'].std()
    win_rate = (trades['trade_return'] > 0).mean() * 100
    max_drawdown = trades['drawdown'].min() * 100

    # Calculate Sharpe-like ratio (per trade)
    sharpe = avg_return / std_return if std_return > 0 else 0

    # Profit factor
    wins = trades[trades['trade_return'] > 0]['trade_return'].sum()
    losses = abs(trades[trades['trade_return'] < 0]['trade_return'].sum())
    profit_factor = wins / losses if losses > 0 else float('inf')

    # Max consecutive wins/losses
    trades['win'] = (trades['trade_return'] > 0).astype(int)
    wins_streak = trades['win'].groupby((trades['win'] != trades['win'].shift()).cumsum()).cumsum()
    max_win_streak = wins_streak.max()

    trades['loss'] = (trades['trade_return'] < 0).astype(int)
    loss_streak = trades['loss'].groupby((trades['loss'] != trades['loss'].shift()).cumsum()).cumsum()
    max_loss_streak = loss_streak.max()

    print(f"  Total Return: {total_return:+.2f}%")
    print(f"  Average Return per Trade: {avg_return:+.2f}%")
    print(f"  Std Dev per Trade: {std_return:.2f}%")
    print(f"  Win Rate: {win_rate:.1f}%")
    print(f"  Profit Factor: {profit_factor:.2f}")
    print(f"  Sharpe (per trade): {sharpe:.2f}")
    print(f"  Max Drawdown: {max_drawdown:.2f}%")
    print(f"  Max Win Streak: {int(max_win_streak)}")
    print(f"  Max Loss Streak: {int(max_loss_streak)}")

    # =========================================================================
    # LEVERAGE ANALYSIS
    # =========================================================================
    print("\n" + "-"*60)
    print("MAXIMUM LEVERAGE ANALYSIS")
    print("-"*60)

    # The key insight: Max leverage = 1 / Max Drawdown (to avoid liquidation)
    # But we need safety margin, so typically use 50% of theoretical max

    max_dd_decimal = abs(max_drawdown / 100)

    # Theoretical max leverage (would get liquidated at max DD)
    theoretical_max_leverage = 1 / max_dd_decimal if max_dd_decimal > 0 else float('inf')

    # Safe leverage levels
    conservative_leverage = theoretical_max_leverage * 0.25  # 25% of max
    moderate_leverage = theoretical_max_leverage * 0.50      # 50% of max
    aggressive_leverage = theoretical_max_leverage * 0.75   # 75% of max

    print(f"\n  Max Drawdown: {max_drawdown:.2f}%")
    print(f"  Theoretical Max Leverage: {theoretical_max_leverage:.1f}x (100% ruin at max DD)")
    print(f"\n  RECOMMENDED LEVERAGE LEVELS:")
    print(f"    Conservative (25% risk): {conservative_leverage:.1f}x")
    print(f"    Moderate (50% risk):     {moderate_leverage:.1f}x")
    print(f"    Aggressive (75% risk):   {aggressive_leverage:.1f}x")

    # Calculate leveraged returns
    print(f"\n  LEVERAGED RETURNS (Total over {len(trades)} trades):")
    for lev in [1, 2, 3, 5, 10]:
        # Simple approximation: leveraged return = leverage * return
        # In reality, leverage compounds differently
        leveraged_return = total_return * lev
        leveraged_max_dd = max_drawdown * lev

        status = "✓ SAFE" if abs(leveraged_max_dd) < 100 else "✗ LIQUIDATED"
        print(f"    {lev}x leverage: {leveraged_return:+.1f}% return, {leveraged_max_dd:.1f}% max DD - {status}")

    # =========================================================================
    # PROFITABILITY TIMELINE
    # =========================================================================
    print("\n" + "-"*60)
    print("PROFITABILITY TIMELINE")
    print("-"*60)

    # Group by month
    trades['month'] = trades['date'].dt.to_period('M')
    monthly = trades.groupby('month').agg({
        'trade_return': ['count', 'sum', 'mean'],
        'cumulative_return': 'last'
    }).round(4)
    monthly.columns = ['trades', 'monthly_return', 'avg_return', 'cumulative']
    monthly['monthly_return'] *= 100
    monthly['avg_return'] *= 100
    monthly['cumulative'] *= 100

    print(f"\n{'Month':<10} {'Trades':<8} {'Monthly %':<12} {'Cumulative %':<12}")
    print("-"*45)
    for month, row in monthly.iterrows():
        print(f"{str(month):<10} {int(row['trades']):<8} {row['monthly_return']:>+9.2f}%  {row['cumulative']:>+10.2f}%")

    # Profitable months
    profitable_months = (monthly['monthly_return'] > 0).sum()
    total_months = len(monthly)

    print(f"\n  Profitable months: {profitable_months}/{total_months} ({profitable_months/total_months*100:.1f}%)")

    # =========================================================================
    # WORST CASE ANALYSIS
    # =========================================================================
    print("\n" + "-"*60)
    print("WORST CASE ANALYSIS")
    print("-"*60)

    worst_trade = trades.loc[trades['trade_return'].idxmin()]
    best_trade = trades.loc[trades['trade_return'].idxmax()]

    print(f"\n  Worst Trade:")
    print(f"    Date: {worst_trade['date'].strftime('%Y-%m-%d')}")
    print(f"    Return: {worst_trade['trade_return_pct']:.2f}%")
    print(f"    ETF Flow: ${worst_trade['total_flow_usd_millions']:.1f}M")

    print(f"\n  Best Trade:")
    print(f"    Date: {best_trade['date'].strftime('%Y-%m-%d')}")
    print(f"    Return: {best_trade['trade_return_pct']:.2f}%")
    print(f"    ETF Flow: ${best_trade['total_flow_usd_millions']:.1f}M")

    # =========================================================================
    # KELLY CRITERION FOR OPTIMAL LEVERAGE
    # =========================================================================
    print("\n" + "-"*60)
    print("KELLY CRITERION (Optimal Bet Size)")
    print("-"*60)

    # Kelly formula: f* = (p * b - q) / b
    # where p = win probability, q = 1-p, b = win/loss ratio

    p = win_rate / 100
    q = 1 - p

    avg_win = trades[trades['trade_return'] > 0]['trade_return'].mean() if (trades['trade_return'] > 0).any() else 0
    avg_loss = abs(trades[trades['trade_return'] < 0]['trade_return'].mean()) if (trades['trade_return'] < 0).any() else 1

    b = avg_win / avg_loss if avg_loss > 0 else 1

    kelly = (p * b - q) / b if b > 0 else 0
    kelly = max(0, kelly)  # Can't be negative

    # Half-Kelly is often recommended
    half_kelly = kelly / 2
    quarter_kelly = kelly / 4

    print(f"\n  Win Rate (p): {p:.2%}")
    print(f"  Avg Win / Avg Loss (b): {b:.2f}")
    print(f"\n  Full Kelly: {kelly:.2%} of portfolio per trade")
    print(f"  Half Kelly (recommended): {half_kelly:.2%} of portfolio per trade")
    print(f"  Quarter Kelly (conservative): {quarter_kelly:.2%} of portfolio per trade")

    # Convert to effective leverage
    kelly_leverage = 1 / half_kelly if half_kelly > 0 else float('inf')
    print(f"\n  Half-Kelly implies max {min(kelly_leverage, 20):.1f}x leverage equivalent")

    # =========================================================================
    # FINAL RECOMMENDATION
    # =========================================================================
    print("\n" + "="*60)
    print("FINAL RECOMMENDATION")
    print("="*60)

    recommended_leverage = min(conservative_leverage, kelly_leverage, 10)  # Cap at 10x

    print(f"\n  Based on:")
    print(f"    - Max Drawdown: {max_drawdown:.2f}%")
    print(f"    - Win Rate: {win_rate:.1f}%")
    print(f"    - Profit Factor: {profit_factor:.2f}")
    print(f"    - Kelly Criterion")

    print(f"\n  ➤ RECOMMENDED MAX LEVERAGE: {recommended_leverage:.1f}x")

    if recommended_leverage >= 5:
        print(f"  ➤ SIGNAL QUALITY: EXCELLENT")
    elif recommended_leverage >= 3:
        print(f"  ➤ SIGNAL QUALITY: GOOD")
    elif recommended_leverage >= 2:
        print(f"  ➤ SIGNAL QUALITY: MODERATE")
    else:
        print(f"  ➤ SIGNAL QUALITY: USE CAUTION")

    # Save results
    results = {
        'total_trades': len(trades),
        'total_return_pct': total_return,
        'avg_return_per_trade': avg_return,
        'win_rate': win_rate,
        'max_drawdown_pct': max_drawdown,
        'profit_factor': profit_factor,
        'sharpe_per_trade': sharpe,
        'theoretical_max_leverage': theoretical_max_leverage,
        'conservative_leverage': conservative_leverage,
        'moderate_leverage': moderate_leverage,
        'aggressive_leverage': aggressive_leverage,
        'kelly_full': kelly,
        'kelly_half': half_kelly,
        'recommended_leverage': recommended_leverage,
        'first_signal': str(min(signal_dates).date()) if signal_dates else None,
        'last_signal': str(max(signal_dates).date()) if signal_dates else None,
        'timestamp': datetime.now().isoformat()
    }

    with open("twelvedata_export/leverage_backtest_results.json", 'w') as f:
        json.dump(results, f, indent=2)

    trades.to_csv("twelvedata_export/scenario_a_trades.csv", index=False)

    print(f"\n  Results saved to:")
    print(f"    - twelvedata_export/leverage_backtest_results.json")
    print(f"    - twelvedata_export/scenario_a_trades.csv")

    return results


def main():
    print("="*60)
    print("LEVERAGE BACKTEST: SCENARIO A")
    print("Large ETF Outflows + Gold Rising")
    print("="*60)
    print(f"Timestamp: {datetime.now().isoformat()}\n")

    # Load data
    df = load_merged_data()
    print(f"Loaded {len(df)} days of merged data")

    # Identify signals
    df, flow_threshold = identify_scenario_a_trades(df)
    print(f"ETF outflow threshold (10th percentile): ${flow_threshold:.1f}M")

    # Run backtest
    results = backtest_strategy(df, holding_period=5)

    return results


if __name__ == "__main__":
    results = main()
