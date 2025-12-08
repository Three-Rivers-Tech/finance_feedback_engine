#!/usr/bin/env python3
"""
Quick demo of the new backtest formatter output.
Run with: python demo_formatter.py
"""

from finance_feedback_engine.cli.backtest_formatter import (
    format_full_results,
    format_single_asset_backtest
)

# Sample portfolio backtest results
portfolio_results = {
    'initial_value': 10000.0,
    'final_value': 12450.75,
    'total_return': 24.51,
    'sharpe_ratio': 1.85,
    'max_drawdown': -8.32,
    'total_trades': 45,
    'completed_trades': 42,
    'win_rate': 57.14,
    'avg_win': 125.50,
    'avg_loss': -85.25,
    'asset_attribution': {
        'BTCUSD': {
            'total_pnl': 1200.50,
            'num_trades': 18,
            'win_rate': 61.11,
            'contribution_pct': 49.0
        },
        'ETHUSD': {
            'total_pnl': 950.75,
            'num_trades': 16,
            'win_rate': 56.25,
            'contribution_pct': 38.8
        },
        'EURUSD': {
            'total_pnl': 299.50,
            'num_trades': 8,
            'win_rate': 50.0,
            'contribution_pct': 12.2
        }
    },
    'equity_curve': [
        ('2025-01-01', 10000.0),
        ('2025-01-10', 10450.0),
        ('2025-02-01', 11200.0),
        ('2025-03-31', 12450.75)
    ],
    'trade_history': [
        {
            'date': '2025-03-30',
            'asset_pair': 'BTCUSD',
            'action': 'BUY',
            'entry_price': 65000,
            'price': 66500,
            'pnl': 150.0,
            'reason': 'Signal'
        },
        {
            'date': '2025-03-29',
            'asset_pair': 'ETHUSD',
            'action': 'SELL',
            'entry_price': 3500,
            'price': 3400,
            'pnl': 100.0,
            'reason': 'TP Hit'
        },
        {
            'date': '2025-03-28',
            'asset_pair': 'EURUSD',
            'action': 'BUY',
            'entry_price': 1.0850,
            'price': 1.0820,
            'pnl': -30.0,
            'reason': 'SL Hit'
        }
    ]
}

# Sample single-asset backtest results
single_results = {
    'initial_balance': 10000.0,
    'final_value': 11850.50,
    'total_return_pct': 18.51,
    'annualized_return_pct': 22.45,
    'sharpe_ratio': 2.15,
    'max_drawdown_pct': -5.75,
    'total_trades': 28,
    'win_rate': 60.71,
    'avg_win': 98.50,
    'avg_loss': -65.25,
    'total_fees': 125.50,
    'trades': [
        {
            'date': '2025-03-30',
            'action': 'BUY',
            'entry_price': 65000,
            'exit_price': 66500,
            'pnl_value': 1500,
            'reason': 'Signal'
        },
        {
            'date': '2025-03-29',
            'action': 'SELL',
            'entry_price': 65500,
            'exit_price': 64800,
            'pnl_value': 700,
            'reason': 'TP Hit'
        }
    ]
}

if __name__ == '__main__':
    print("\n" + "="*70)
    print("PORTFOLIO BACKTEST OUTPUT DEMO")
    print("="*70)

    format_full_results(
        results=portfolio_results,
        asset_pairs=['BTCUSD', 'ETHUSD', 'EURUSD'],
        start_date='2025-01-01',
        end_date='2025-03-31',
        initial_balance=10000.0
    )

    print("\n" + "="*70)
    print("SINGLE-ASSET BACKTEST OUTPUT DEMO")
    print("="*70 + "\n")

    format_single_asset_backtest(
        metrics=single_results,
        trades=single_results['trades'],
        asset_pair='BTCUSD',
        start_date='2025-01-01',
        end_date='2025-03-31',
        initial_balance=10000.0
    )
