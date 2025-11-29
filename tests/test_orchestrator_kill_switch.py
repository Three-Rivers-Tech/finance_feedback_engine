import io
import sys
import types
import threading
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
setattr(dummy_mod, 'UnifiedTradingPlatform', object)
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
            orchestrator.run(test_mode=True)
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
        orch.peak_portfolio_value = 100.0
        orch.init_failed = False
        orch._stop_event = threading.Event()
        orch._paused_by_monitor = False
        orch.kill_switch_gain_pct = config.kill_switch_gain_pct
        orch.kill_switch_loss_pct = config.kill_switch_loss_pct
        orch.max_drawdown_pct = config.max_drawdown_percent if config.max_drawdown_percent <= 1.0 else config.max_drawdown_percent / 100.0

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
        orch.peak_portfolio_value = 100.0
        orch.init_failed = False
        orch._stop_event = threading.Event()
        orch._paused_by_monitor = False
        orch.kill_switch_gain_pct = config.kill_switch_gain_pct
        orch.kill_switch_loss_pct = config.kill_switch_loss_pct
        orch.max_drawdown_pct = config.max_drawdown_percent if config.max_drawdown_percent <= 1.0 else config.max_drawdown_percent / 100.0

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
        orch.peak_portfolio_value = 100.0
        orch.init_failed = False
        orch._stop_event = threading.Event()
        orch._paused_by_monitor = False
        orch.kill_switch_gain_pct = config.kill_switch_gain_pct
        orch.kill_switch_loss_pct = config.kill_switch_loss_pct
        orch.max_drawdown_pct = config.max_drawdown_percent if config.max_drawdown_percent <= 1.0 else config.max_drawdown_percent / 100.0

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
        orch.peak_portfolio_value = 100.0
        orch.init_failed = False
        orch._stop_event = threading.Event()
        orch._paused_by_monitor = False
        orch.kill_switch_gain_pct = config.kill_switch_gain_pct
        orch.kill_switch_loss_pct = config.kill_switch_loss_pct
        orch.max_drawdown_pct = config.max_drawdown_percent if config.max_drawdown_percent <= 1.0 else config.max_drawdown_percent / 100.0

        out = self._run_and_capture(orch)
        self.assertNotIn('Kill-switch triggered', out)

    def test_drawdown_kill_switch_triggers(self):
        config = TradingAgentConfig(asset_pairs=[])
        config.max_drawdown_percent = 0.10  # 10% threshold
        config.kill_switch_gain_pct = 0.05
        config.kill_switch_loss_pct = 0.02
        
        orch = object.__new__(TradingAgentOrchestrator)
        orch.config = config
        orch.engine = DummyEngine()
        platform = mock.Mock()
        platform.get_portfolio_breakdown.return_value = {'total_value_usd': 850.0}
        orch.platform = platform
        orch.trades_today = 0
        orch.initial_portfolio_value = 1000.0
        orch.peak_portfolio_value = 1000.0
        orch.init_failed = False
        orch._stop_event = threading.Event()
        orch._paused_by_monitor = False
        orch.kill_switch_gain_pct = config.kill_switch_gain_pct
        orch.kill_switch_loss_pct = config.kill_switch_loss_pct
        orch.max_drawdown_pct = config.max_drawdown_percent if config.max_drawdown_percent <= 1.0 else config.max_drawdown_percent / 100.0
        
        out = self._run_and_capture(orch)
        self.assertIn('Kill-switch triggered: portfolio drawdown of 15.00% exceeds threshold 10.00%', out)

    def test_drawdown_kill_switch_percentage_input(self):
        config = TradingAgentConfig(asset_pairs=[])
        config.max_drawdown_percent = 10.0  # 10% as percentage (should be normalized to 0.10)
        config.kill_switch_gain_pct = 0.05
        config.kill_switch_loss_pct = 0.02
        
        orch = object.__new__(TradingAgentOrchestrator)
        orch.config = config
        orch.engine = DummyEngine()
        platform = mock.Mock()
        platform.get_portfolio_breakdown.return_value = {'total_value_usd': 850.0}
        orch.platform = platform
        orch.trades_today = 0
        orch.initial_portfolio_value = 1000.0
        orch.peak_portfolio_value = 1000.0
        orch.init_failed = False
        orch._stop_event = threading.Event()
        orch._paused_by_monitor = False
        orch.kill_switch_gain_pct = config.kill_switch_gain_pct
        orch.kill_switch_loss_pct = config.kill_switch_loss_pct
        orch.max_drawdown_pct = config.max_drawdown_percent if config.max_drawdown_percent <= 1.0 else config.max_drawdown_percent / 100.0
        
        out = self._run_and_capture(orch)
        self.assertIn('Kill-switch triggered: portfolio drawdown of 15.00% exceeds threshold 10.00%', out)

    def test_drawdown_kill_switch_not_triggers(self):
        config = TradingAgentConfig(asset_pairs=[])
        config.max_drawdown_percent = 0.20  # 20% threshold
        config.kill_switch_gain_pct = 0.05
        config.kill_switch_loss_pct = 0.02
        
        orch = object.__new__(TradingAgentOrchestrator)
        orch.config = config
        orch.engine = DummyEngine()
        platform = mock.Mock()
        platform.get_portfolio_breakdown.return_value = {'total_value_usd': 850.0}
        orch.platform = platform
        orch.trades_today = 0
        orch.initial_portfolio_value = 1000.0
        orch.peak_portfolio_value = 1000.0
        orch.init_failed = False
        orch._stop_event = threading.Event()
        orch._paused_by_monitor = False
        orch.kill_switch_gain_pct = config.kill_switch_gain_pct
        orch.kill_switch_loss_pct = config.kill_switch_loss_pct
        orch.max_drawdown_pct = config.max_drawdown_percent if config.max_drawdown_percent <= 1.0 else config.max_drawdown_percent / 100.0
        
        out = self._run_and_capture(orch)
        self.assertNotIn('drawdown', out)


if __name__ == '__main__':
    unittest.main()
