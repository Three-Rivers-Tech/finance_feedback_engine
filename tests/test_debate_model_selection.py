import asyncio

from finance_feedback_engine.decision_engine.ai_decision_manager import AIDecisionManager


def test_debate_mode_forces_ensemble_provider():
    config = {
        "decision_engine": {"ai_provider": "local"},
        "ensemble": {
            "debate_mode": True,
            "debate_providers": {"bull": "gemini", "bear": "qwen", "judge": "local"},
        },
    }

    mgr = AIDecisionManager(config)
    assert mgr.ai_provider == "ensemble"
    assert mgr.ensemble_manager is not None
    assert mgr.ensemble_manager.debate_mode is True
    assert mgr.ensemble_manager.debate_providers == {
        "bull": "gemini",
        "bear": "qwen",
        "judge": "local",
    }


def test_debate_mode_auto_resolves_incomplete_seats():
    """Debate mode with incomplete seat config auto-resolves with curated defaults."""
    config = {
        "decision_engine": {"ai_provider": "local"},
        "ensemble": {
            "debate_mode": True,
            "debate_providers": {"bull": "gemini", "bear": "qwen", "judge": ""},
            "enabled_providers": ["gemini", "qwen", "cli"],
        },
    }
    # Should not raise; resolver auto-completes the missing/empty judge seat
    mgr = AIDecisionManager(config)
    assert mgr.ai_provider == "ensemble"
    assert mgr.ensemble_manager.debate_mode is True
    # All 3 seats should be assigned after auto-resolution
    assert mgr.ensemble_manager.debate_providers["bull"] is not None
    assert mgr.ensemble_manager.debate_providers["bear"] is not None
    assert mgr.ensemble_manager.debate_providers["judge"] is not None
    assert mgr.ensemble_manager.debate_providers["judge"] != ""  # no longer empty
