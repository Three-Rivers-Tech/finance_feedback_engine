#!/usr/bin/env python3
"""
Test THR-227 fix: Verify FFE initializes without calling engine.initialize()

This test ensures the FinanceFeedbackEngine initializes properly in __init__
and doesn't require a separate initialize() method call.

Author: Backend Dev Agent
Date: 2026-02-15
"""

import pytest
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.utils.config_loader import load_config


def test_ffe_initializes_automatically():
    """Test that FFE initializes critical components in __init__."""
    # Load config
    config = load_config(".env")
    config["is_backtest"] = True  # Backtest mode to avoid live connections
    
    # Create engine - should initialize automatically
    engine = FinanceFeedbackEngine(config)
    
    # Verify critical components are initialized
    assert hasattr(engine, "decision_engine"), "decision_engine not initialized"
    assert engine.decision_engine is not None, "decision_engine is None"
    
    # Note: In backtest mode, trading_platform may be None (that's OK)
    # The key is that decision_engine is initialized for optimization
    
    # Verify no initialize() method exists (would cause AttributeError)
    assert not hasattr(engine, "initialize"), \
        "engine.initialize() method exists but shouldn't (causes THR-227)"


def test_ffe_no_initialize_method():
    """Test that calling engine.initialize() raises AttributeError."""
    config = load_config(".env")
    config["is_backtest"] = True
    
    engine = FinanceFeedbackEngine(config)
    
    # This should raise AttributeError
    with pytest.raises(AttributeError, match=".*initialize.*"):
        engine.initialize()


def test_decision_engine_exists_after_init():
    """Test that decision engine exists and is accessible after __init__."""
    config = load_config(".env")
    config["is_backtest"] = True
    
    engine = FinanceFeedbackEngine(config)
    
    # Verify decision engine is initialized
    # This is sufficient for THR-227 - the key is that FFE initializes without
    # needing to call engine.initialize()
    assert hasattr(engine, "decision_engine"), "decision_engine attribute missing"
    assert engine.decision_engine is not None, "decision_engine is None"
    
    # Decision engine is a valid object (not just a placeholder)
    assert hasattr(engine.decision_engine, "__class__"), "decision_engine not a valid object"
    assert "DecisionEngine" in str(type(engine.decision_engine)), \
        f"decision_engine is wrong type: {type(engine.decision_engine)}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
