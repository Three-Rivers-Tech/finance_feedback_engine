#!/usr/bin/env python3
"""Quick import test for two-phase wiring."""

try:
    from finance_feedback_engine.decision_engine.ensemble_manager import (
        EnsembleDecisionManager,
    )

    print("✓ EnsembleDecisionManager imported successfully")

    print("✓ DecisionEngine imported successfully")

    # Check that two-phase method exists
    if not hasattr(EnsembleDecisionManager, "aggregate_decisions_two_phase"):
        raise AttributeError(
            "EnsembleDecisionManager missing aggregate_decisions_two_phase method"
        )
    print("✓ aggregate_decisions_two_phase method exists")

    print("\n✅ All imports successful! Two-phase wiring complete.")
except Exception as e:
    print(f"\n❌ Import failed: {e}")
    import traceback

    traceback.print_exc()
    exit(1)
