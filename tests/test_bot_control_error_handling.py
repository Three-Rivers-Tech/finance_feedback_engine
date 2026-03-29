import asyncio
import inspect
from types import SimpleNamespace
from unittest.mock import Mock

import finance_feedback_engine.api.bot_control as bc


class _BrokenBreakdownPlatform:
    def get_portfolio_breakdown(self):
        raise RuntimeError('portfolio breakdown unavailable')

    async def aget_portfolio_breakdown(self):
        raise RuntimeError('portfolio breakdown unavailable')

    def get_open_positions(self):
        return [{"symbol": "BTCUSD", "side": "short"}]


def _install_platform(monkeypatch, platform):
    for name in ['_active_platform', '_platform', '_current_platform']:
        if hasattr(bc, name):
            monkeypatch.setattr(bc, name, platform, raising=False)
    if hasattr(bc, '_agent_instance'):
        monkeypatch.setattr(bc, '_agent_instance', SimpleNamespace(platforms=[platform]), raising=False)


def _call_get_open_positions():
    fn = bc.get_open_positions
    return asyncio.run(fn()) if inspect.iscoroutinefunction(fn) else fn()


def _unwrap_response(result):
    if hasattr(result, 'body'):
        import json
        return json.loads(result.body.decode())
    return result


def test_get_open_positions_does_not_lie_with_zero_total_value_on_breakdown_error(monkeypatch):
    _install_platform(monkeypatch, _BrokenBreakdownPlatform())

    result = _unwrap_response(_call_get_open_positions())

    assert result['positions']
    assert result['total_value'] is None
    assert result['portfolio_value_error'] == 'portfolio breakdown unavailable'
    assert result['portfolio_value_degraded'] is True
