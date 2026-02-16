#!/usr/bin/env python3
"""
Curriculum Learning Optimizer for FFE
Implements 4-level progressive optimization for LONG/SHORT trading strategies
"""

import os
import sys
import json
import logging
from pathlib import Path
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
import optuna
from optuna.pruners import MedianPruner
from optuna.samplers import TPESampler

# Add parent to path for FFE imports
sys.path.insert(0, str(Path(__file__).parent.parent))

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('data/optimization_logs/curriculum_optimizer.log'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)

# ============================================================================
# LEVEL CONFIGURATIONS
# ============================================================================

LEVEL_1_CONFIG = {
    'name': 'Level 1: LONG-Only Bull Markets',
    'direction': ['LONG'],
    'datasets': {
        'BTC_USD': {'start': '2020-01-01', 'end': '2021-12-31', 'timeframes': ['M5', 'M15', 'H1']},
        'EUR_USD': {'start': '2024-01-01', 'end': '2024-03-31', 'timeframes': ['M5', 'M15', 'H1']},
    },
    'param_ranges': {
        'stop_loss_pct': (0.5, 3.0),
        'take_profit_pct': (1.0, 5.0),
        'rr_ratio': (1.5, 4.0),
        'position_size_pct': (1.0, 5.0),
        'confidence_threshold': (0.6, 0.85),
        'max_positions': [1, 2, 3],
    },
    'success_criteria': {
        'min_win_rate': 0.50,
        'min_sharpe': 0.8,
        'max_drawdown': 0.15,
        'min_profit_factor': 1.3,
        'target_win_rate': 0.55,
        'target_sharpe': 1.0,
    },
    'optuna': {
        'n_trials': 100,
        'n_jobs': 4,
        'timeout': 14400,  # 4 hours
    }
}

LEVEL_2_CONFIG = {
    'name': 'Level 2: SHORT-Only Bear Markets',
    'direction': ['SHORT'],
    'datasets': {
        'BTC_USD': {'start': '2022-01-01', 'end': '2022-12-31', 'timeframes': ['M5', 'M15', 'H1']},
        'EUR_USD': {'start': '2023-04-01', 'end': '2023-12-31', 'timeframes': ['M5', 'M15', 'H1']},
    },
    'param_ranges': {
        'stop_loss_pct': (0.5, 3.0),
        'take_profit_pct': (1.0, 5.0),
        'rr_ratio': (1.5, 4.0),
        'position_size_pct': (1.0, 5.0),
        'confidence_threshold': (0.6, 0.85),
        'max_positions': [1, 2, 3],
    },
    'success_criteria': {
        'min_win_rate': 0.50,
        'min_sharpe': 0.8,
        'max_drawdown': 0.15,
        'min_profit_factor': 1.3,
        'target_win_rate': 0.55,
        'target_sharpe': 1.0,
    },
    'optuna': {
        'n_trials': 100,
        'n_jobs': 4,
        'timeout': 14400,
    }
}

LEVEL_3_CONFIG = {
    'name': 'Level 3: Mixed LONG/SHORT Full Cycles',
    'direction': ['LONG', 'SHORT', 'BOTH'],
    'datasets': {
        'BTC_USD': {'start': '2020-01-01', 'end': '2023-12-31', 'timeframes': ['M5', 'M15', 'H1']},
        'ETH_USD': {'start': '2020-01-01', 'end': '2023-12-31', 'timeframes': ['M5', 'M15', 'H1']},
        'EUR_USD': {'start': '2020-01-01', 'end': '2023-12-31', 'timeframes': ['M5', 'M15', 'H1']},
        'GBP_USD': {'start': '2020-01-01', 'end': '2023-12-31', 'timeframes': ['M5', 'M15', 'H1']},
    },
    'param_ranges': {
        'stop_loss_pct_long': (0.5, 3.0),
        'stop_loss_pct_short': (0.5, 3.0),
        'take_profit_pct_long': (1.0, 5.0),
        'take_profit_pct_short': (1.0, 5.0),
        'rr_ratio_long': (1.5, 4.0),
        'rr_ratio_short': (1.5, 4.0),
        'position_size_pct': (1.0, 5.0),
        'confidence_threshold_long': (0.6, 0.85),
        'confidence_threshold_short': (0.6, 0.85),
        'max_positions': [2, 3, 4],
        'max_long_positions': [1, 2, 3],
        'max_short_positions': [1, 2, 3],
    },
    'success_criteria': {
        'min_win_rate': 0.52,
        'min_sharpe': 1.0,
        'max_drawdown': 0.20,
        'min_profit_factor': 1.4,
        'target_win_rate': 0.55,
        'target_sharpe': 1.3,
    },
    'optuna': {
        'n_trials': 150,
        'n_jobs': 4,
        'timeout': 21600,  # 6 hours
    }
}

LEVEL_4_CONFIG = {
    'name': 'Level 4: All Regimes + Robustness',
    'direction': ['LONG', 'SHORT', 'BOTH'],
    'datasets': {
        'BTC_USD': {'start': '2020-01-01', 'end': '2023-12-31', 'timeframes': ['M5', 'M15', 'H1']},
        'ETH_USD': {'start': '2020-01-01', 'end': '2023-12-31', 'timeframes': ['M5', 'M15', 'H1']},
        'EUR_USD': {'start': '2020-01-01', 'end': '2023-12-31', 'timeframes': ['M5', 'M15', 'H1']},
        'GBP_USD': {'start': '2020-01-01', 'end': '2023-12-31', 'timeframes': ['M5', 'M15', 'H1']},
    },
    'param_ranges': {
        'stop_loss_pct_long': (0.5, 3.0),
        'stop_loss_pct_short': (0.5, 3.0),
        'take_profit_pct_long': (1.0, 5.0),
        'take_profit_pct_short': (1.0, 5.0),
        'rr_ratio_long': (1.5, 4.0),
        'rr_ratio_short': (1.5, 4.0),
        'position_size_pct': (1.0, 5.0),
        'confidence_threshold_long': (0.6, 0.85),
        'confidence_threshold_short': (0.6, 0.85),
        'max_positions': [2, 3, 4],
        'adx_threshold': [15, 20, 25, 30],
        'volatility_filter': (0.5, 2.0),
        'max_daily_loss_pct': (2.0, 5.0),
    },
    'success_criteria': {
        'min_win_rate': 0.53,
        'min_sharpe': 1.2,
        'max_drawdown': 0.25,
        'min_profit_factor': 1.5,
        'target_win_rate': 0.56,
        'target_sharpe': 1.5,
    },
    'optuna': {
        'n_trials': 200,
        'n_jobs': 4,
        'timeout': 28800,  # 8 hours
    }
}

LEVEL_CONFIGS = {
    1: LEVEL_1_CONFIG,
    2: LEVEL_2_CONFIG,
    3: LEVEL_3_CONFIG,
    4: LEVEL_4_CONFIG,
}

# ============================================================================
# DATA LOADING
# ============================================================================

def load_historical_data(pair: str, timeframe: str, start_date: str, end_date: str) -> pd.DataFrame:
    """Load historical data for a given pair and timeframe"""
    
    data_dir = Path('data/historical/curriculum_2020_2023')
    filename = f"{pair}_{timeframe}_2020_2023.parquet"
    filepath = data_dir / filename
    
    if not filepath.exists():
        logger.warning(f"Data file not found: {filepath}")
        return pd.DataFrame()
    
    try:
        df = pd.read_parquet(filepath)
        df['time'] = pd.to_datetime(df['time'], utc=True)
        
        # Filter by date range
        start = pd.to_datetime(start_date, utc=True)
        end = pd.to_datetime(end_date, utc=True)
        df = df[(df['time'] >= start) & (df['time'] <= end)]
        
        logger.info(f"Loaded {len(df)} candles for {pair} {timeframe} ({start_date} to {end_date})")
        return df
        
    except Exception as e:
        logger.error(f"Error loading {filepath}: {e}")
        return pd.DataFrame()

def load_level_data(level: int) -> Dict[str, Dict[str, pd.DataFrame]]:
    """Load all data for a given curriculum level"""
    
    config = LEVEL_CONFIGS[level]
    data = {}
    
    for pair, info in config['datasets'].items():
        data[pair] = {}
        for tf in info['timeframes']:
            df = load_historical_data(pair, tf, info['start'], info['end'])
            if not df.empty:
                data[pair][tf] = df
    
    return data

# ============================================================================
# BACKTEST SIMULATION (SIMPLIFIED FOR NOW)
# ============================================================================

def calculate_indicators(df: pd.DataFrame) -> pd.DataFrame:
    """Add technical indicators to dataframe"""
    
    df = df.copy()
    
    # Simple Moving Averages
    df['sma_20'] = df['close'].rolling(20).mean()
    df['sma_50'] = df['close'].rolling(50).mean()
    
    # ATR for volatility
    df['high_low'] = df['high'] - df['low']
    df['high_close'] = abs(df['high'] - df['close'].shift())
    df['low_close'] = abs(df['low'] - df['close'].shift())
    df['atr'] = df[['high_low', 'high_close', 'low_close']].max(axis=1).rolling(14).mean()
    
    # Returns
    df['returns'] = df['close'].pct_change()
    
    return df

def simulate_trades(df: pd.DataFrame, params: Dict, direction: str = 'LONG') -> Dict:
    """
    Simplified backtest simulation
    
    This is a PLACEHOLDER - will be replaced with actual FFE backtest integration
    """
    
    # Add indicators
    df = calculate_indicators(df)
    df = df.dropna()
    
    if len(df) < 100:
        return {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 1.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'num_trades': 0,
        }
    
    # Simulate simple strategy based on SMA cross
    # This is VERY simplified - actual implementation will use FFE decision engine
    
    trades = []
    position = None
    equity = 100000  # Starting capital
    equity_curve = [equity]
    
    stop_loss_pct = params.get('stop_loss_pct', 1.0) / 100
    take_profit_pct = params.get('take_profit_pct', 2.0) / 100
    position_size_pct = params.get('position_size_pct', 2.0) / 100
    
    for i in range(50, len(df)):
        current_row = df.iloc[i]
        current_price = current_row['close']
        
        # Entry signal (simplified)
        if position is None:
            if direction == 'LONG' and current_row['sma_20'] > current_row['sma_50']:
                # Enter LONG
                position = {
                    'direction': 'LONG',
                    'entry_price': current_price,
                    'size': equity * position_size_pct,
                    'stop_loss': current_price * (1 - stop_loss_pct),
                    'take_profit': current_price * (1 + take_profit_pct),
                }
            elif direction == 'SHORT' and current_row['sma_20'] < current_row['sma_50']:
                # Enter SHORT
                position = {
                    'direction': 'SHORT',
                    'entry_price': current_price,
                    'size': equity * position_size_pct,
                    'stop_loss': current_price * (1 + stop_loss_pct),
                    'take_profit': current_price * (1 - take_profit_pct),
                }
        
        # Exit logic
        elif position is not None:
            exit_trade = False
            profit = 0.0
            
            if position['direction'] == 'LONG':
                if current_price <= position['stop_loss']:
                    # Stop loss hit
                    profit = position['size'] * (position['stop_loss'] / position['entry_price'] - 1)
                    exit_trade = True
                elif current_price >= position['take_profit']:
                    # Take profit hit
                    profit = position['size'] * (position['take_profit'] / position['entry_price'] - 1)
                    exit_trade = True
            
            elif position['direction'] == 'SHORT':
                if current_price >= position['stop_loss']:
                    # Stop loss hit
                    profit = position['size'] * (1 - current_price / position['entry_price'])
                    exit_trade = True
                elif current_price <= position['take_profit']:
                    # Take profit hit
                    profit = position['size'] * (1 - position['take_profit'] / position['entry_price'])
                    exit_trade = True
            
            if exit_trade:
                equity += profit
                trades.append({
                    'direction': position['direction'],
                    'entry_price': position['entry_price'],
                    'exit_price': current_price,
                    'profit': profit,
                    'return': profit / position['size'],
                })
                position = None
        
        equity_curve.append(equity)
    
    # Calculate metrics
    if len(trades) == 0:
        return {
            'total_return': 0.0,
            'sharpe_ratio': 0.0,
            'max_drawdown': 0.0,
            'win_rate': 0.0,
            'profit_factor': 0.0,
            'num_trades': 0,
        }
    
    trades_df = pd.DataFrame(trades)
    winning_trades = trades_df[trades_df['profit'] > 0]
    losing_trades = trades_df[trades_df['profit'] < 0]
    
    win_rate = len(winning_trades) / len(trades_df) if len(trades_df) > 0 else 0.0
    total_return = (equity - 100000) / 100000
    
    # Sharpe ratio
    returns = pd.Series(equity_curve).pct_change().dropna()
    sharpe_ratio = (returns.mean() / returns.std()) * np.sqrt(252) if returns.std() > 0 else 0.0
    
    # Max drawdown
    equity_series = pd.Series(equity_curve)
    running_max = equity_series.expanding().max()
    drawdown = (equity_series - running_max) / running_max
    max_drawdown = abs(drawdown.min())
    
    # Profit factor
    gross_profit = winning_trades['profit'].sum() if len(winning_trades) > 0 else 0.0
    gross_loss = abs(losing_trades['profit'].sum()) if len(losing_trades) > 0 else 0.01
    profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0
    
    return {
        'total_return': total_return,
        'sharpe_ratio': sharpe_ratio,
        'max_drawdown': max_drawdown,
        'win_rate': win_rate,
        'profit_factor': profit_factor,
        'num_trades': len(trades),
    }

# ============================================================================
# OPTUNA OPTIMIZATION
# ============================================================================

def suggest_params(trial: optuna.Trial, level: int) -> Dict:
    """Suggest parameters for optimization based on level"""
    
    config = LEVEL_CONFIGS[level]
    ranges = config['param_ranges']
    params = {}
    
    for param_name, param_range in ranges.items():
        if isinstance(param_range, tuple):
            # Continuous range
            params[param_name] = trial.suggest_float(param_name, param_range[0], param_range[1])
        elif isinstance(param_range, list):
            # Categorical
            params[param_name] = trial.suggest_categorical(param_name, param_range)
    
    return params

def objective_function(trial: optuna.Trial, level: int, data: Dict) -> float:
    """
    Objective function for Optuna optimization
    Maximizes Sharpe ratio with penalties for constraint violations
    """
    
    # Suggest parameters
    params = suggest_params(trial, level)
    
    # Get config
    config = LEVEL_CONFIGS[level]
    criteria = config['success_criteria']
    direction = config['direction'][0]  # For Level 1 and 2
    
    # Run backtest on all datasets
    all_results = []
    
    for pair, timeframes in data.items():
        for tf, df in timeframes.items():
            result = simulate_trades(df, params, direction)
            all_results.append(result)
    
    # Aggregate results
    if not all_results:
        return -999.0
    
    avg_sharpe = np.mean([r['sharpe_ratio'] for r in all_results])
    avg_win_rate = np.mean([r['win_rate'] for r in all_results])
    avg_drawdown = np.mean([r['max_drawdown'] for r in all_results])
    avg_pf = np.mean([r['profit_factor'] for r in all_results])
    
    # Start with Sharpe ratio
    score = avg_sharpe
    
    # Apply penalties for constraint violations
    if avg_win_rate < criteria['min_win_rate']:
        score *= 0.5
    
    if avg_drawdown > criteria['max_drawdown']:
        score *= 0.7
    
    if avg_pf < criteria['min_profit_factor']:
        score *= 0.8
    
    # Bonus for exceeding targets
    if avg_win_rate > criteria['target_win_rate']:
        score *= 1.1
    
    # Log trial results
    trial.set_user_attr('win_rate', avg_win_rate)
    trial.set_user_attr('max_drawdown', avg_drawdown)
    trial.set_user_attr('profit_factor', avg_pf)
    
    return score

def run_level_optimization(level: int) -> optuna.Study:
    """Run optimization for a specific curriculum level"""
    
    logger.info(f"=" * 80)
    logger.info(f"Starting Level {level} Optimization")
    logger.info(f"=" * 80)
    
    config = LEVEL_CONFIGS[level]
    logger.info(f"Level: {config['name']}")
    logger.info(f"Trials: {config['optuna']['n_trials']}")
    logger.info(f"Parallel Jobs: {config['optuna']['n_jobs']}")
    
    # Load data
    logger.info("Loading data...")
    data = load_level_data(level)
    
    if not data:
        logger.error("No data loaded! Cannot proceed.")
        return None
    
    logger.info(f"Loaded data for {len(data)} pairs")
    
    # Create Optuna study
    study_name = f"curriculum_level_{level}"
    storage = "sqlite:///data/optuna_studies.db"
    
    study = optuna.create_study(
        study_name=study_name,
        storage=storage,
        direction='maximize',
        sampler=TPESampler(),
        pruner=MedianPruner(),
        load_if_exists=True,
    )
    
    # Run optimization
    logger.info("Starting optimization...")
    
    study.optimize(
        lambda trial: objective_function(trial, level, data),
        n_trials=config['optuna']['n_trials'],
        n_jobs=config['optuna']['n_jobs'],
        timeout=config['optuna']['timeout'],
    )
    
    # Save results
    output_dir = Path(f'optimization_results/level_{level}')
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Best parameters
    best_params_file = output_dir / 'LEVEL_{}_BEST_PARAMS.json'.format(level)
    with open(best_params_file, 'w') as f:
        json.dump(study.best_params, f, indent=2)
    
    logger.info(f"✅ Best parameters saved: {best_params_file}")
    logger.info(f"Best Sharpe Ratio: {study.best_value:.4f}")
    logger.info(f"Best Parameters: {study.best_params}")
    
    # All trials
    trials_df = study.trials_dataframe()
    trials_file = output_dir / f'LEVEL_{level}_OPTIMIZATION_RESULTS.csv'
    trials_df.to_csv(trials_file, index=False)
    
    logger.info(f"✅ All trial results saved: {trials_file}")
    
    return study

# ============================================================================
# MAIN EXECUTION
# ============================================================================

def main():
    """Main execution function"""
    
    import argparse
    
    parser = argparse.ArgumentParser(description='FFE Curriculum Learning Optimizer')
    parser.add_argument('--level', type=int, required=True, choices=[1, 2, 3, 4],
                       help='Curriculum level to optimize (1-4)')
    parser.add_argument('--trials', type=int, help='Override number of trials')
    
    args = parser.parse_args()
    
    # Override trial count if specified
    if args.trials:
        LEVEL_CONFIGS[args.level]['optuna']['n_trials'] = args.trials
    
    # Ensure log directory exists
    Path('data/optimization_logs').mkdir(parents=True, exist_ok=True)
    
    # Run optimization
    study = run_level_optimization(args.level)
    
    if study:
        logger.info("=" * 80)
        logger.info("OPTIMIZATION COMPLETE")
        logger.info("=" * 80)
        logger.info(f"Level {args.level}: {LEVEL_CONFIGS[args.level]['name']}")
        logger.info(f"Best Score: {study.best_value:.4f}")
        logger.info(f"Completed Trials: {len(study.trials)}")
        return 0
    else:
        logger.error("Optimization failed")
        return 1

if __name__ == '__main__':
    sys.exit(main())
