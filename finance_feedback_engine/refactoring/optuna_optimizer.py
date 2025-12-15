"""Optuna-based optimization for agent configuration."""

import asyncio
import logging
from typing import Dict, Any, Optional
import optuna
from optuna.trial import Trial

from finance_feedback_engine.benchmarking import quick_benchmark

logger = logging.getLogger(__name__)


class AgentConfigOptimizer:
    """
    Uses Optuna for Bayesian optimization of agent configuration.

    Optimizes:
    - Provider weights
    - Risk parameters (stop-loss, position size)
    - Confidence thresholds
    - Technical indicator parameters
    """

    def __init__(self, base_config: Dict[str, Any]):
        """
        Initialize optimizer.

        Args:
            base_config: Base configuration dictionary
        """
        self.base_config = base_config
        self.best_config = None
        self.best_sharpe = -float('inf')

        # Benchmark parameters
        self.benchmark_params = {
            'asset_pairs': base_config.get('benchmark', {}).get('asset_pairs', ['BTCUSD']),
            'start_date': base_config.get('benchmark', {}).get('start_date', '2024-10-01'),
            'end_date': base_config.get('benchmark', {}).get('end_date', '2024-12-01')
        }

    async def optimize(
        self,
        n_trials: int = 50,
        timeout: Optional[int] = None,
        optimize_for: str = 'sharpe_ratio'
    ) -> Dict[str, Any]:
        """
        Run Bayesian optimization to find optimal configuration.

        Args:
            n_trials: Number of optimization trials
            timeout: Optional timeout in seconds
            optimize_for: Metric to optimize ('sharpe_ratio', 'total_return', 'profit_factor')

        Returns:
            Best configuration found
        """
        logger.info(f"Starting Optuna optimization ({n_trials} trials)")
        logger.info(f"Optimizing for: {optimize_for}")

        # Create study
        study = optuna.create_study(
            direction='maximize',
            sampler=optuna.samplers.TPESampler(seed=42),
            pruner=optuna.pruners.MedianPruner(n_startup_trials=5, n_warmup_steps=3)
        )

        # Store optimize_for metric
        self.optimize_for = optimize_for

        # Run optimization
        def objective_wrapper(trial: Trial) -> float:
            return asyncio.run(self._objective(trial))

        study.optimize(
            objective_wrapper,
            n_trials=n_trials,
            timeout=timeout,
            show_progress_bar=True
        )

        # Log results
        logger.info("\n" + "=" * 70)
        logger.info("OPTIMIZATION COMPLETE")
        logger.info("=" * 70)
        logger.info(f"Best {optimize_for}: {study.best_value:.3f}")
        logger.info("\nBest parameters:")
        for param, value in study.best_params.items():
            logger.info(f"  {param}: {value}")

        # Build best config
        self.best_config = self._build_config_from_params(study.best_params)

        return {
            'best_config': self.best_config,
            'best_score': study.best_value,
            'best_params': study.best_params,
            'n_trials': len(study.trials),
            'optimization_history': [
                {'trial': i, 'score': trial.value}
                for i, trial in enumerate(study.trials)
                if trial.value is not None
            ]
        }

    async def _objective(self, trial: Trial) -> float:
        """
        Objective function for optimization.

        Args:
            trial: Optuna trial

        Returns:
            Score to maximize
        """
        logger.info(f"\n--- Trial {trial.number} ---")

        # Sample hyperparameters
        params = self._sample_hyperparameters(trial)

        logger.info("Sampled parameters:")
        for param, value in params.items():
            logger.info(f"  {param}: {value}")

        # Build config with sampled params
        config = self._build_config_from_params(params)

        try:
            # Run benchmark with this configuration
            logger.info("Running benchmark...")
            report = quick_benchmark(
                asset_pairs=self.benchmark_params['asset_pairs'],
                start_date=self.benchmark_params['start_date'],
                end_date=self.benchmark_params['end_date'],
                config=config
            )

            # Get score based on optimization metric
            if self.optimize_for == 'sharpe_ratio':
                score = report.sharpe_ratio
            elif self.optimize_for == 'total_return':
                score = report.total_return
            elif self.optimize_for == 'profit_factor':
                score = report.profit_factor
            elif self.optimize_for == 'win_rate':
                score = report.win_rate * 100  # Scale to 0-100
            else:
                score = report.sharpe_ratio  # Default

            logger.info(f"Score: {score:.3f}")
            logger.info(f"  Sharpe: {report.sharpe_ratio:.2f}")
            logger.info(f"  Win Rate: {report.win_rate:.1%}")
            logger.info(f"  Total Return: {report.total_return:.2f}%")

            # Track best
            if score > self.best_sharpe:
                self.best_sharpe = score
                logger.info(f"✨ New best score: {score:.3f}")

            return score

        except Exception as e:
            logger.error(f"Trial failed: {e}")
            return -float('inf')

    def _sample_hyperparameters(self, trial: Trial) -> Dict[str, Any]:
        """
        Sample hyperparameters for this trial.

        Args:
            trial: Optuna trial

        Returns:
            Sampled parameters
        """
        params = {}

        # Provider weights (if using ensemble)
        if self.base_config.get('decision_engine', {}).get('ai_provider') == 'ensemble':
            providers = self.base_config.get('ensemble', {}).get('enabled_providers', [])

            if len(providers) >= 2:
                # Sample weights that sum to 1.0
                weights = []
                for i, provider in enumerate(providers[:-1]):
                    remaining = 1.0 - sum(weights)
                    weight = trial.suggest_float(
                        f'weight_{provider}',
                        0.1,
                        remaining - 0.1 * (len(providers) - i - 1)
                    )
                    weights.append(weight)
                    params[f'weight_{provider}'] = weight

                # Last weight is determined
                last_weight = 1.0 - sum(weights)
                params[f'weight_{providers[-1]}'] = last_weight

        # Risk parameters
        params['stop_loss_pct'] = trial.suggest_float('stop_loss_pct', 0.01, 0.05)
        params['position_size_pct'] = trial.suggest_float('position_size_pct', 0.005, 0.02)
        params['confidence_threshold'] = trial.suggest_float('confidence_threshold', 0.65, 0.85)

        # Technical indicator parameters
        params['rsi_period'] = trial.suggest_int('rsi_period', 10, 20)
        params['rsi_overbought'] = trial.suggest_int('rsi_overbought', 65, 75)
        params['rsi_oversold'] = trial.suggest_int('rsi_oversold', 25, 35)

        # Dynamic stop-loss
        params['use_dynamic_stop'] = trial.suggest_categorical('use_dynamic_stop', [True, False])
        if params['use_dynamic_stop']:
            params['atr_multiplier'] = trial.suggest_float('atr_multiplier', 1.5, 3.0)

        return params

    def _build_config_from_params(self, params: Dict[str, Any]) -> Dict[str, Any]:
        """
        Build configuration dictionary from parameters.

        Args:
            params: Sampled parameters

        Returns:
            Complete configuration
        """
        config = self.base_config.copy()

        # Update provider weights
        if 'ensemble' not in config:
            config['ensemble'] = {}
        if 'provider_weights' not in config['ensemble']:
            config['ensemble']['provider_weights'] = {}

        for key, value in params.items():
            if key.startswith('weight_'):
                provider = key.replace('weight_', '')
                config['ensemble']['provider_weights'][provider] = value

        # Update agent config
        if 'agent' not in config:
            config['agent'] = {}

        if 'stop_loss_pct' in params:
            config['agent']['sizing_stop_loss_percentage'] = params['stop_loss_pct']
        if 'position_size_pct' in params:
            config['agent']['sizing_risk_percentage'] = params['position_size_pct']
        if 'confidence_threshold' in params:
            config['agent']['min_confidence_threshold'] = params['confidence_threshold']

        # Dynamic stop-loss
        if 'use_dynamic_stop' in params:
            config['agent']['use_dynamic_stop_loss'] = params['use_dynamic_stop']
            if params['use_dynamic_stop'] and 'atr_multiplier' in params:
                config['agent']['atr_multiplier'] = params['atr_multiplier']

        # Technical indicators (would need to be integrated with data providers)
        # For now, just store as metadata
        config['optimization_metadata'] = {
            'rsi_period': params.get('rsi_period', 14),
            'rsi_overbought': params.get('rsi_overbought', 70),
            'rsi_oversold': params.get('rsi_oversold', 30)
        }

        return config

    def visualize_optimization(self, study: optuna.Study):
        """
        Create visualization of optimization results.

        Args:
            study: Optuna study
        """
        try:
            from optuna.visualization import (
                plot_optimization_history,
                plot_param_importances,
                plot_slice
            )

            logger.info("Generating optimization visualizations...")

            # Optimization history
            fig = plot_optimization_history(study)
            fig.write_html('data/refactoring/optuna_history.html')

            # Parameter importances
            fig = plot_param_importances(study)
            fig.write_html('data/refactoring/optuna_importances.html')

            # Slice plot
            fig = plot_slice(study)
            fig.write_html('data/refactoring/optuna_slice.html')

            logger.info("✓ Visualizations saved to data/refactoring/")

        except ImportError:
            logger.warning("plotly not installed - skipping visualizations")
        except Exception as e:
            logger.error(f"Visualization failed: {e}")
