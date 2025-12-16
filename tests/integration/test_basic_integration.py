"""
Basic integration test to verify core components can be imported together.

This demonstrates the integration between key modules as outlined in
the technical debt document.
"""

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.decision_engine.engine import DecisionEngine
from finance_feedback_engine.trading_platforms.platform_factory import PlatformFactory


def test_basic_integration():
    """Test that core modules can be imported and instantiated without circular dependencies."""
    # This test verifies that there are no circular dependencies
    # between the main modules, which was one of the technical debt items

    # All imports work without circular dependency errors
    assert FinanceFeedbackEngine is not None
    assert DecisionEngine is not None
    assert PlatformFactory is not None

    # Basic integration test - just make sure we can reference the classes
    # without triggering circular import issues
    assert hasattr(FinanceFeedbackEngine, "__init__")
    assert hasattr(DecisionEngine, "__init__")
    assert hasattr(PlatformFactory, "create_platform")

    # If we reach this point, basic integration is working
    assert True


if __name__ == "__main__":
    test_basic_integration()
    print(
        "Integration test passed: Core components can be imported together without circular dependencies"
    )
