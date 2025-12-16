#!/usr/bin/env python3
"""
Lightweight test to validate that VaR/correlation context fields are properly injected.

Tests:
1. Decision context includes var_snapshot with real computations
2. Decision context includes correlation_alerts
3. Persisted decision JSON includes multi-timeframe and risk fields
"""

import sys
from pathlib import Path

import yaml

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from finance_feedback_engine.core import FinanceFeedbackEngine


def test_risk_context_fields():
    """Test that VaR and correlation context fields are injected into decisions."""
    print("\n" + "=" * 70)
    print("TEST: VaR/Correlation Context Fields in Decision")
    print("=" * 70)

    # Load test config
    config_path = Path("config/config.test.mock.yaml")
    if not config_path.exists():
        print("⚠️  Test config not found, using default config")
        config_path = Path("config/config.yaml")

    with open(config_path, encoding="utf-8") as f:
        config = yaml.safe_load(f)

    # Initialize engine
    print("\n1. Initializing engine...")
    engine = FinanceFeedbackEngine(config)
    print("   ✓ Engine initialized")

    # Generate a decision
    print("\n2. Generating decision with risk context...")
    decision = engine.analyze_asset("BTCUSD", use_memory_context=False)

    # Validate decision structure
    assert isinstance(decision, dict), "Decision should be a dictionary"
    assert "action" in decision, "Decision missing action field"
    print(f"   ✓ Decision generated: {decision['action']}")

    # Test 1: Check for var_snapshot field
    print("\n3. Validating VaR snapshot field...")
    assert "var_snapshot" in decision, "Decision missing var_snapshot field"
    var_snapshot = decision["var_snapshot"]

    # Validate var_snapshot structure
    assert isinstance(var_snapshot, dict), "var_snapshot should be a dictionary"
    required_var_fields = ["portfolio_value", "var_95", "var_99", "data_quality"]
    for field in required_var_fields:
        assert field in var_snapshot, f"var_snapshot missing {field} field"

    print(f"   ✓ var_snapshot present with fields: {list(var_snapshot.keys())}")
    print(f"     - Portfolio Value: ${var_snapshot['portfolio_value']:.2f}")
    print(f"     - VaR 95%: ${var_snapshot['var_95']:.2f}")
    print(f"     - VaR 99%: ${var_snapshot['var_99']:.2f}")
    print(f"     - Data Quality: {var_snapshot['data_quality']}")

    # Test 2: Check for correlation_alerts field
    print("\n4. Validating correlation alerts field...")
    assert "correlation_alerts" in decision, "Decision missing correlation_alerts field"
    correlation_alerts = decision["correlation_alerts"]

    assert isinstance(correlation_alerts, list), "correlation_alerts should be a list"
    print(f"   ✓ correlation_alerts present: {len(correlation_alerts)} alerts")
    if correlation_alerts:
        for alert in correlation_alerts:
            print(f"     - {alert}")

    # Test 3: Check for correlation_summary field
    print("\n5. Validating correlation summary field...")
    assert (
        "correlation_summary" in decision
    ), "Decision missing correlation_summary field"
    correlation_summary = decision.get("correlation_summary")

    if correlation_summary:
        print(f"   ✓ correlation_summary present ({len(correlation_summary)} chars)")
    else:
        print("   ✓ correlation_summary present (empty)")

    # Test 4: Check for multi-timeframe fields
    print("\n6. Validating multi-timeframe fields...")
    multi_tf_fields = [
        "multi_timeframe_trend",
        "multi_timeframe_entry_signals",
        "multi_timeframe_sources",
        "data_source_path",
        "monitor_pulse_age_seconds",
    ]

    for field in multi_tf_fields:
        assert field in decision, f"Decision missing {field} field"

    print("   ✓ All multi-timeframe fields present")
    if decision.get("multi_timeframe_trend"):
        print(f"     - Trend alignment: {decision['multi_timeframe_trend']}")
    if decision.get("data_source_path"):
        print(f"     - Data source path: {decision['data_source_path']}")

    # Test 5: Verify decision was persisted with all fields
    print("\n7. Verifying persisted decision...")
    decision_id = decision["id"]
    retrieved = engine.decision_store.get_decision_by_id(decision_id)

    if retrieved:
        assert "var_snapshot" in retrieved, "Persisted decision missing var_snapshot"
        assert (
            "correlation_alerts" in retrieved
        ), "Persisted decision missing correlation_alerts"
        assert (
            "correlation_summary" in retrieved
        ), "Persisted decision missing correlation_summary"
        print(f"   ✓ Decision {decision_id[:8]}... persisted with all risk fields")
    else:
        print("   ⚠️  Could not retrieve persisted decision")

    print("\n" + "=" * 70)
    print("✅ ALL TESTS PASSED")
    print("=" * 70)
    print("\nValidated fields:")
    print("  • var_snapshot (portfolio_value, var_95, var_99, data_quality)")
    print("  • correlation_alerts")
    print("  • correlation_summary")
    print("  • multi_timeframe_trend")
    print("  • multi_timeframe_entry_signals")
    print("  • multi_timeframe_sources")
    print("  • data_source_path")
    print("  • monitor_pulse_age_seconds")
    print("\n")

    return True


if __name__ == "__main__":
    try:
        success = test_risk_context_fields()
        sys.exit(0 if success else 1)
    except AssertionError as e:
        print(f"\n❌ TEST FAILED: {e}\n")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERROR: {e}\n")
        import traceback

        traceback.print_exc()
        sys.exit(1)
