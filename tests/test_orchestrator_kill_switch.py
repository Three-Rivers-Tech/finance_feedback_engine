import io
import sys
import types
import unittest
from unittest import mock

# Prevent import-time dependency on the real UnifiedPlatform symbol by
# injecting a lightweight dummy module before importing the orchestrator.
# Make a lightweight package module to prevent executing finance_feedback_engine/__init__.py
finance_pkg = types.ModuleType('finance_feedback_engine')
finance_pkg.__path__ = [
    # Path to the package directory (relative to repo root)
    'finance_feedback_engine'
]
sys.modules['finance_feedback_engine'] = finance_pkg

# Inject a dummy unified_platform module to satisfy imports used by the orchestrator
dummy_mod = types.ModuleType('finance_feedback_engine.trading_platforms.unified_platform')
setattr(dummy_mod, 'UnifiedPlatform', object)
sys.modules['finance_feedback_engine.trading_platforms.unified_platform'] = dummy_mod

from finance_feedback_engine.agent.config import TradingAgentConfig
from finance_feedback_engine.agent.orchestrator import TradingAgentOrchestrator


class DummyEngine:
    def analyze(self, *a, **k):
        class D:
            decision = 'HOLD'
            confidence = 0.0
            reasoning = ''
            asset_pair = ''
        return D()


class TestOrchestratorKillSwitch(unittest.TestCase):
    def _run_and_capture(self, orchestrator):
        buf = io.StringIO()
        old_stdout = sys.stdout
        sys.stdout = buf
        try:
            orchestrator.run()
        finally:
            sys.stdout = old_stdout
        return buf.getvalue()

    def test_gain_kill_switch_triggers(self):
        config = TradingAgentConfig(asset_pairs=[])
        config.kill_switch_gain_pct = 0.05
        config.kill_switch_loss_pct = 0.02

        orch = object.__new__(TradingAgentOrchestrator)
        orch.config = config
        orch.engine = DummyEngine()
        platform = mock.Mock()
        platform.get_portfolio_breakdown.return_value = {'total_value_usd': 105.0, 'unrealized_pnl': 5.0}
        orch.platform = platform
        orch.trades_today = 0
        orch.initial_portfolio_value = 100.0
        orch.init_failed = False

        out = self._run_and_capture(orch)
        self.assertIn('Kill-switch triggered: portfolio gain', out)

    def test_loss_kill_switch_triggers(self):
        config = TradingAgentConfig(asset_pairs=[])
        config.kill_switch_gain_pct = 0.05
        config.kill_switch_loss_pct = 0.02

        orch = object.__new__(TradingAgentOrchestrator)
        orch.config = config
        orch.engine = DummyEngine()
        platform = mock.Mock()
        # Current value reflects a >2% loss (97.0 on 100 -> -3%)
        platform.get_portfolio_breakdown.return_value = {'total_value_usd': 97.0, 'unrealized_pnl': -3.0}
        orch.platform = platform
        orch.trades_today = 0
        orch.initial_portfolio_value = 100.0
        orch.init_failed = False

        out = self._run_and_capture(orch)
        self.assertIn('Kill-switch triggered: portfolio loss', out)

    def test_gain_kill_switch_not_triggers(self):
        config = TradingAgentConfig(asset_pairs=[])
        config.kill_switch_gain_pct = 0.05
        config.kill_switch_loss_pct = 0.02

        orch = object.__new__(TradingAgentOrchestrator)
        orch.config = config
        orch.engine = DummyEngine()
        platform = mock.Mock()
        # Gain of 4% (below 5% threshold)
        platform.get_portfolio_breakdown.return_value = {'total_value_usd': 104.0, 'unrealized_pnl': 4.0}
        orch.platform = platform
        orch.trades_today = 0
        orch.initial_portfolio_value = 100.0
        orch.init_failed = False

        out = self._run_and_capture(orch)
        self.assertNotIn('Kill-switch triggered', out)

    def test_loss_kill_switch_not_triggers(self):
        config = TradingAgentConfig(asset_pairs=[])
        config.kill_switch_gain_pct = 0.05
        config.kill_switch_loss_pct = 0.02

        orch = object.__new__(TradingAgentOrchestrator)
        orch.config = config
        orch.engine = DummyEngine()
        platform = mock.Mock()
        # Loss of 1% (above -2% threshold)
        platform.get_portfolio_breakdown.return_value = {'total_value_usd': 99.0, 'unrealized_pnl': -1.0}
        orch.platform = platform
        orch.trades_today = 0
        orch.initial_portfolio_value = 100.0
        orch.init_failed = False

        out = self._run_and_capture(orch)
        self.assertNotIn('Kill-switch triggered', out)

    def test_init_failed_exits_gracefully(self):
        config = TradingAgentConfig(asset_pairs=[])
        orch = object.__new__(TradingAgentOrchestrator)
        orch.config = config
        orch.engine = DummyEngine()
        orch.platform = mock.Mock()
        orch.trades_today = 0
        orch.initial_portfolio_value = 0.0
        orch.init_failed = True

        out = self._run_and_capture(orch)
        self.assertIn('Could not obtain initial portfolio snapshot after retries. Exiting gracefully.', out)


if __name__ == '__main__':
    unittest.main()
