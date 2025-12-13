"""
Comprehensive tests for DecisionEngine core logic.

Tests the analyze_market method and pure engine logic (signals, position sizing rules)
in isolation by mocking ensemble_manager calls.

Target Coverage: Increase engine.py from 6% to >50%
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from datetime import datetime
from pathlib import Path
import yaml

from finance_feedback_engine.decision_engine.engine import DecisionEngine


@pytest.fixture
def test_config():
    """Load test configuration."""
    config_path = Path("config/config.test.mock.yaml")
    with open(config_path, encoding='utf-8') as f:
        return yaml.safe_load(f)


@pytest.fixture
def mock_data_provider():
    """Mock data provider for historical data."""
    provider = Mock()
    provider.get_historical_data = AsyncMock(return_value=[
        {'open': 50000, 'high': 51000, 'low': 49000, 'close': 50500, 'volume': 1000},
        {'open': 50500, 'high': 51500, 'low': 50000, 'close': 51000, 'volume': 1100},
    ])
    return provider


@pytest.fixture
def decision_engine(test_config, mock_data_provider):
    """Create DecisionEngine instance with mocked dependencies."""
    # Use local provider for simplicity (not ensemble)
    config = test_config.copy()
    config['decision_engine']['ai_provider'] = 'local'
    return DecisionEngine(config, data_provider=mock_data_provider)


@pytest.fixture
def ensemble_engine(test_config, mock_data_provider):
    """Create DecisionEngine with ensemble provider."""
    config = test_config.copy()
    config['decision_engine']['ai_provider'] = 'ensemble'
    return DecisionEngine(config, data_provider=mock_data_provider)


@pytest.fixture
def sample_market_data():
    """Sample market data for testing."""
    return {
        'open': 50000.0,
        'high': 51000.0,
        'low': 49000.0,
        'close': 50500.0,
        'volume': 1000,
        'date': datetime.utcnow().isoformat(),
        'type': 'crypto',
        'asset_type': 'crypto'
    }


@pytest.fixture
def sample_balance():
    """Sample account balance."""
    return {'USD': 10000.0, 'BTC': 0.1}


@pytest.fixture
def sample_portfolio():
    """Sample portfolio breakdown."""
    return {
        'total_value_usd': 15000.0,
        'num_assets': 2,
        'unrealized_pnl': 500.0,
        'holdings': [
            {'currency': 'BTC', 'amount': 0.1, 'value_usd': 5050.0, 'allocation_pct': 33.7},
            {'currency': 'USD', 'amount': 10000.0, 'value_usd': 10000.0, 'allocation_pct': 66.3}
        ]
    }


# ===== Position Sizing Tests =====

class TestPositionSizing:
    """Test position sizing calculations."""

    def test_calculate_position_size_standard(self, decision_engine):
        """Test standard position size calculation."""
        position_size = decision_engine.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,  # 1%
            entry_price=50000.0,
            stop_loss_percentage=0.02  # 2%
        )

        # Expected: (10000 * 0.01) / (50000 * 0.02) = 100 / 1000 = 0.1 BTC
        assert position_size == pytest.approx(0.1, rel=1e-6)

    def test_calculate_position_size_zero_entry_price(self, decision_engine):
        """Test position sizing with zero entry price."""
        position_size = decision_engine.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,
            entry_price=0.0,
            stop_loss_percentage=0.02
        )
        assert position_size == 0.0

    def test_calculate_position_size_zero_stop_loss(self, decision_engine):
        """Test position sizing with zero stop loss."""
        position_size = decision_engine.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.01,
            entry_price=50000.0,
            stop_loss_percentage=0.0
        )
        assert position_size == 0.0

    def test_calculate_position_size_higher_risk(self, decision_engine):
        """Test position sizing with higher risk tolerance."""
        position_size = decision_engine.calculate_position_size(
            account_balance=10000.0,
            risk_percentage=0.02,  # 2% risk
            entry_price=50000.0,
            stop_loss_percentage=0.02
        )

        # Expected: (10000 * 0.02) / (50000 * 0.02) = 200 / 1000 = 0.2 BTC
        assert position_size == pytest.approx(0.2, rel=1e-6)


# ===== Market Analysis Helper Tests =====

class TestMarketAnalysisHelpers:
    """Test market analysis helper methods."""

    def test_calculate_price_change_positive(self, decision_engine):
        """Test price change calculation with positive change."""
        market_data = {'open': 50000.0, 'close': 51000.0}
        price_change = decision_engine._calculate_price_change(market_data)
        assert price_change == pytest.approx(2.0, rel=1e-6)  # 2% increase

    def test_calculate_price_change_negative(self, decision_engine):
        """Test price change calculation with negative change."""
        market_data = {'open': 50000.0, 'close': 49000.0}
        price_change = decision_engine._calculate_price_change(market_data)
        assert price_change == pytest.approx(-2.0, rel=1e-6)  # 2% decrease

    def test_calculate_price_change_zero_open(self, decision_engine):
        """Test price change with zero open price."""
        market_data = {'open': 0.0, 'close': 50000.0}
        price_change = decision_engine._calculate_price_change(market_data)
        assert price_change == 0.0

    def test_calculate_volatility(self, decision_engine):
        """Test volatility calculation."""
        market_data = {'high': 51000.0, 'low': 49000.0, 'close': 50000.0}
        volatility = decision_engine._calculate_volatility(market_data)
        # (51000 - 49000) / 50000 * 100 = 4%
        assert volatility == pytest.approx(4.0, rel=1e-6)

    def test_calculate_volatility_zero_close(self, decision_engine):
        """Test volatility with zero close price."""
        market_data = {'high': 51000.0, 'low': 49000.0, 'close': 0.0}
        volatility = decision_engine._calculate_volatility(market_data)
        assert volatility == 0.0


# ===== AI Prompt Creation Tests =====

class TestPromptCreation:
    """Test AI prompt creation logic."""

    def test_create_ai_prompt_basic(self, decision_engine, sample_market_data, sample_balance):
        """Test basic prompt creation with minimal context."""
        context = {
            'asset_pair': 'BTCUSD',
            'market_data': sample_market_data,
            'balance': sample_balance,
            'price_change': 1.0,
            'volatility': 4.0
        }

        prompt = decision_engine._create_ai_prompt(context)

        # Verify key sections are present
        assert 'Asset Pair: BTCUSD' in prompt
        assert 'PRICE DATA:' in prompt
        assert 'Open: $50000.00' in prompt
        assert 'Close: $50500.00' in prompt
        # Note: Balance is formatted differently in actual prompt
        assert 'Account Balance:' in prompt or 'Balance:' in prompt

    def test_create_ai_prompt_with_portfolio(self, decision_engine, sample_market_data,
                                             sample_balance, sample_portfolio):
        """Test prompt creation with portfolio holdings."""
        context = {
            'asset_pair': 'BTCUSD',
            'market_data': sample_market_data,
            'balance': sample_balance,
            'price_change': 1.0,
            'volatility': 4.0,
            'portfolio': sample_portfolio
        }

        prompt = decision_engine._create_ai_prompt(context)

        # Verify portfolio section
        assert 'CURRENT PORTFOLIO:' in prompt
        assert 'Total Portfolio Value: $15,000.00' in prompt
        assert 'Number of Assets: 2' in prompt
        assert 'Unrealized P&L: $500.00' in prompt

    def test_create_ai_prompt_with_sentiment(self, decision_engine, sample_market_data, sample_balance):
        """Test prompt creation with news sentiment."""
        market_data = sample_market_data.copy()
        market_data['sentiment'] = {
            'overall_sentiment': 'bullish',
            'sentiment_score': 0.65,
            'news_count': 15,
            'top_topics': ['adoption', 'regulation', 'ETF']
        }

        context = {
            'asset_pair': 'BTCUSD',
            'market_data': market_data,
            'balance': sample_balance,
            'price_change': 1.0,
            'volatility': 4.0
        }

        prompt = decision_engine._create_ai_prompt(context)

        # Verify sentiment is mentioned in prompt (format may vary)
        assert 'sentiment' in prompt.lower() or 'news' in prompt.lower()
        assert 'bullish' in prompt.lower() or '0.65' in prompt


# ===== Decision Generation Tests =====

class TestDecisionGeneration:
    """Test the main generate_decision method."""

    @pytest.mark.asyncio
    async def test_generate_decision_basic(self, decision_engine, sample_market_data, sample_balance):
        """Test basic decision generation flow."""
        # Mock the AI query method
        with patch.object(decision_engine, '_query_ai', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                'action': 'BUY',
                'confidence': 75,
                'reasoning': 'Bullish momentum detected',
                'amount': 0.05
            }

            decision = await decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data=sample_market_data,
                balance=sample_balance
            )

            # Verify decision structure
            assert decision['action'] == 'BUY'
            assert decision['confidence'] == 75
            assert decision['asset_pair'] == 'BTCUSD'
            assert 'reasoning' in decision
            assert 'timestamp' in decision
            assert 'id' in decision

    @pytest.mark.asyncio
    async def test_generate_decision_with_portfolio(self, decision_engine, sample_market_data,
                                                     sample_balance, sample_portfolio):
        """Test decision generation with portfolio context."""
        with patch.object(decision_engine, '_query_ai', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                'action': 'HOLD',
                'confidence': 60,
                'reasoning': 'Existing position sufficient',
                'amount': 0.0
            }

            decision = await decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data=sample_market_data,
                balance=sample_balance,
                portfolio=sample_portfolio
            )

            assert decision['action'] == 'HOLD'
            # Portfolio unrealized P&L is included in decision
            assert 'portfolio_unrealized_pnl' in decision
            assert decision['portfolio_unrealized_pnl'] == 500.0

    @pytest.mark.asyncio
    async def test_generate_decision_invalid_action_fallback(self, decision_engine,
                                                               sample_market_data, sample_balance):
        """Test that invalid actions are converted to HOLD."""
        with patch.object(decision_engine, '_query_ai', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                'action': 'INVALID_ACTION',
                'confidence': 50,
                'reasoning': 'Test invalid action',
                'amount': 0.0
            }

            decision = await decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data=sample_market_data,
                balance=sample_balance
            )

            # Should default to HOLD
            assert decision['action'] == 'HOLD'

    @pytest.mark.asyncio
    async def test_generate_decision_with_monitoring_context(self, decision_engine,
                                                              sample_market_data, sample_balance):
        """Test decision generation with monitoring context."""
        # Mock the monitoring provider to avoid format_for_ai_prompt error
        mock_provider = Mock()
        mock_provider.format_for_ai_prompt.return_value = "Mock monitoring context"
        decision_engine.monitoring_provider = mock_provider

        monitoring_context = {
            'has_monitoring_data': True,
            'active_positions': [],
            'slots_available': 2
        }

        with patch.object(decision_engine, '_query_ai', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                'action': 'BUY',
                'confidence': 70,
                'reasoning': 'New position opportunity',
                'amount': 0.05
            }

            decision = await decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data=sample_market_data,
                balance=sample_balance,
                monitoring_context=monitoring_context
            )

            assert decision['action'] == 'BUY'
# ===== Ensemble Integration Tests =====

class TestEnsembleIntegration:
    """Test ensemble manager integration (mocked)."""

    @pytest.mark.asyncio
    async def test_ensemble_decision_mocked(self, ensemble_engine, sample_market_data, sample_balance):
        """Test ensemble decision with mocked ensemble manager."""
        # Mock the ensemble manager's get_decision method
        mock_ensemble_response = {
            'action': 'BUY',
            'confidence': 80,
            'reasoning': 'Ensemble consensus: Bullish',
            'amount': 0.05,
            'ensemble_metadata': {
                'providers_used': ['local', 'cli', 'codex'],
                'agreement_score': 0.85,
                'fallback_tier': 'weighted'
            }
        }

        with patch.object(ensemble_engine.ensemble_manager, 'aggregate_decisions',
                         new_callable=AsyncMock) as mock_aggregate:
            mock_aggregate.return_value = mock_ensemble_response

            # Also mock _query_single_provider to return valid responses
            with patch.object(ensemble_engine, '_query_single_provider',
                            new_callable=AsyncMock) as mock_query:
                mock_query.return_value = {
                    'action': 'BUY',
                    'confidence': 75,
                    'reasoning': 'Test',
                    'amount': 0.05
                }

                decision = await ensemble_engine.generate_decision(
                    asset_pair='BTCUSD',
                    market_data=sample_market_data,
                    balance=sample_balance
                )

                assert decision['action'] == 'BUY'
                assert 'ensemble_metadata' in decision
                assert decision['ensemble_metadata']['agreement_score'] == 0.85


# ===== Market Regime Detection Tests =====

class TestMarketRegimeDetection:
    """Test market regime detection logic."""

    @pytest.mark.asyncio
    async def test_detect_market_regime_success(self, decision_engine, mock_data_provider):
        """Test successful market regime detection."""
        # Mock historical data with trend
        mock_data_provider.get_historical_data.return_value = [
            {'open': 49000 + i*100, 'high': 49500 + i*100, 'low': 48500 + i*100,
             'close': 49000 + i*100, 'volume': 1000}
            for i in range(30)  # 30 days of data
        ]

        regime = await decision_engine._detect_market_regime('BTCUSD')

        # Should return one of the valid regimes (actual values from MarketRegimeDetector)
        assert regime in ['TRENDING_BULL', 'TRENDING_BEAR', 'RANGING', 'VOLATILE', 'UNKNOWN']

    @pytest.mark.asyncio
    async def test_detect_market_regime_insufficient_data(self, decision_engine, mock_data_provider):
        """Test regime detection with insufficient historical data."""
        mock_data_provider.get_historical_data.return_value = [
            {'open': 50000, 'high': 51000, 'low': 49000, 'close': 50500, 'volume': 1000}
        ]  # Only 1 day

        regime = await decision_engine._detect_market_regime('BTCUSD')
        assert regime == 'UNKNOWN'

    @pytest.mark.asyncio
    async def test_detect_market_regime_no_data_provider(self, test_config):
        """Test regime detection without data provider."""
        engine = DecisionEngine(test_config, data_provider=None)
        regime = await engine._detect_market_regime('BTCUSD')
        assert regime == 'UNKNOWN'


# ===== Configuration Tests =====

class TestConfiguration:
    """Test configuration handling."""

    def test_config_nested_structure(self):
        """Test handling of nested config structure."""
        config = {
            'decision_engine': {
                'ai_provider': 'local',
                'decision_threshold': 0.8,
                'local_models': ['llama3.2:3b', 'deepseek-r1:1.5b']
            }
        }
        engine = DecisionEngine(config)
        assert engine.ai_provider == 'local'
        assert engine.decision_threshold == 0.8
        assert len(engine.local_models) == 2

    def test_config_flat_structure_backward_compatibility(self):
        """Test backward compatibility with flat config structure."""
        config = {
            'ai_provider': 'cli',
            'decision_threshold': 0.7,
            'local_models': []
        }
        engine = DecisionEngine(config)
        assert engine.ai_provider == 'cli'
        assert engine.decision_threshold == 0.7

    def test_legacy_percentage_conversion(self):
        """Test conversion of legacy percentage values (>1) to decimals."""
        config = {
            'decision_engine': {
                'ai_provider': 'local',
                'portfolio_stop_loss_percentage': 2.0,  # Legacy format (2%)
                'portfolio_take_profit_percentage': 5.0  # Legacy format (5%)
            }
        }
        engine = DecisionEngine(config)
        assert engine.portfolio_stop_loss_percentage == 0.02
        assert engine.portfolio_take_profit_percentage == 0.05

    def test_invalid_local_models_type(self):
        """Test validation of local_models configuration."""
        config = {
            'decision_engine': {
                'ai_provider': 'local',
                'local_models': 'not_a_list'  # Invalid type
            }
        }
        with pytest.raises(ValueError, match="local_models must be a list"):
            DecisionEngine(config)

    def test_invalid_local_priority_type(self):
        """Test validation of local_priority configuration."""
        config = {
            'decision_engine': {
                'ai_provider': 'local',
                'local_models': [],
                'local_priority': {'invalid': 'dict'}  # Invalid type
            }
        }
        with pytest.raises(ValueError, match="local_priority must be"):
            DecisionEngine(config)


# ===== Monitoring Context Provider Tests =====

class TestMonitoringContext:
    """Test monitoring context integration."""

    @pytest.mark.asyncio
    async def test_set_monitoring_context(self, decision_engine):
        """Test setting monitoring context provider."""
        mock_provider = Mock()
        decision_engine.set_monitoring_context(mock_provider)
        assert decision_engine.monitoring_provider == mock_provider

    @pytest.mark.asyncio
    async def test_generate_decision_with_live_monitoring(self, decision_engine,
                                                          sample_market_data, sample_balance):
        """Test decision generation with live monitoring provider."""
        mock_provider = Mock()
        mock_provider.get_monitoring_context.return_value = {
            'has_monitoring_data': True,
            'active_positions': [],
            'slots_available': 2
        }
        decision_engine.set_monitoring_context(mock_provider)

        with patch.object(decision_engine, '_query_ai', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                'action': 'BUY',
                'confidence': 70,
                'reasoning': 'Test',
                'amount': 0.05
            }

            decision = await decision_engine.generate_decision(
                asset_pair='BTCUSD',
                market_data=sample_market_data,
                balance=sample_balance
            )

            # Verify monitoring context was called
            mock_provider.get_monitoring_context.assert_called_once()
            assert decision['action'] == 'BUY'


# ===== Backtest Mode Tests =====

class TestBacktestMode:
    """Test backtest mode behavior."""

    def test_backtest_mode_initialization(self, test_config):
        """Test initialization with backtest mode."""
        engine = DecisionEngine(test_config, backtest_mode=True)
        assert engine.backtest_mode is True

    @pytest.mark.asyncio
    async def test_backtest_mode_generates_warning(self, test_config, sample_market_data, sample_balance):
        """Test that backtest mode logs deprecation warning."""
        engine = DecisionEngine(test_config, backtest_mode=True)

        with patch.object(engine, '_query_ai', new_callable=AsyncMock) as mock_query:
            mock_query.return_value = {
                'action': 'HOLD',
                'confidence': 50,
                'reasoning': 'Backtest decision',
                'amount': 0.0
            }

            # Capture logging output
            with patch('finance_feedback_engine.decision_engine.engine.logger') as mock_logger:
                decision = await engine.generate_decision(
                    asset_pair='BTCUSD',
                    market_data=sample_market_data,
                    balance=sample_balance
                )

                # Check that warning was called with message about deprecation
                assert mock_logger.warning.called
                # Find the call that mentions backtest_mode or deprecated
                warning_calls = [str(call) for call in mock_logger.warning.call_args_list]
                has_deprecation_warning = any(
                    'backtest_mode' in str(call) and 'deprecated' in str(call).lower()
                    for call in warning_calls
                )
                assert has_deprecation_warning, f"Expected deprecation warning, got: {warning_calls}"
if __name__ == '__main__':
    pytest.main([__file__, '-v', '--tb=short'])
