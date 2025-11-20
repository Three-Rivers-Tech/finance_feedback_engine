"""
Example demonstrating dynamic weight adjustment when AI providers fail.

This example shows how the ensemble system gracefully handles provider
failures by dynamically adjusting weights to maintain decision quality.
"""

import logging
from finance_feedback_engine.core import FinanceFeedbackEngine

# Configure verbose logging to see weight adjustments
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s:%(name)s:%(message)s'
)

print("\n" + "=" * 70)
print("Dynamic Weight Adjustment Example")
print("=" * 70)
print("""
When using ensemble mode, the system queries multiple AI providers (local,
Copilot CLI, Codex CLI, Qwen CLI) and combines their decisions using
weighted voting.

If any providers fail to respond (e.g., service down, network issues,
configuration problems), the ensemble manager automatically:

1. Tracks which providers failed
2. Removes failed providers from the decision
3. Dynamically renormalizes weights for remaining providers
4. Ensures weights always sum to 1.0
5. Logs the adjustment for transparency
6. Includes failure metadata in the decision

This ensures robust decision-making even when some AI services are
unavailable.
""")

# Example configuration with ensemble enabled
config = {
    'alpha_vantage_api_key': 'demo',  # Use demo key for testing
    'trading_platform': 'coinbase',
    'platform_credentials': {
        'api_key': 'demo',
        'api_secret': 'demo'
    },
    'decision_engine': {
        'ai_provider': 'ensemble',  # Enable ensemble mode
        'decision_threshold': 0.7
    },
    'ensemble': {
        'enabled_providers': ['local', 'cli', 'codex', 'qwen'],
        'provider_weights': {
            'local': 0.40,   # Higher weight for local (always available)
            'cli': 0.20,     # Lower weights for CLI tools (may fail)
            'codex': 0.20,
            'qwen': 0.20
        },
        'voting_strategy': 'weighted',
        'agreement_threshold': 0.6,
        'adaptive_learning': True,
        'learning_rate': 0.1
    },
    'persistence': {
        'storage_path': 'data/decisions',
        'max_decisions': 100
    }
}

# Initialize the engine
engine = FinanceFeedbackEngine(config)

print("\n--- Scenario: Analyzing BTCUSD with Ensemble ---")
print("The system will try to query all enabled providers.")
print("Expected behavior:")
print("  - Local LLM: Should succeed (if Ollama installed)")
print("  - CLI providers: May fail if not configured")
print("  - Weights will be adjusted for successful providers")
print()

# Analyze an asset (this will trigger ensemble inference)
print("Analyzing BTCUSD...")
try:
    decision = engine.analyze_asset(
        'BTCUSD',
        include_sentiment=False,  # Skip to avoid API rate limits
        include_macro=False
    )
    
    print("\n" + "=" * 70)
    print("DECISION RESULT")
    print("=" * 70)
    print(f"Action: {decision['action']}")
    print(f"Confidence: {decision['confidence']}%")
    print(f"AI Provider: {decision['ai_provider']}")
    
    # Show ensemble metadata
    if 'ensemble_metadata' in decision:
        meta = decision['ensemble_metadata']
        print(f"\nEnsemble Metadata:")
        print(f"  Providers used: {meta.get('providers_used', [])}")
        print(f"  Providers failed: {meta.get('providers_failed', [])}")
        
        if meta.get('weight_adjustment_applied'):
            print(f"\n  ⚠️  Weight adjustment was applied!")
            print(f"  Original weights:")
            for p, w in meta.get('original_weights', {}).items():
                print(f"    {p}: {w:.3f}")
            print(f"  Adjusted weights (renormalized):")
            for p, w in meta.get('adjusted_weights', {}).items():
                print(f"    {p}: {w:.3f}")
            
            # Verify sum
            total = sum(meta.get('adjusted_weights', {}).values())
            print(f"  Sum of adjusted weights: {total:.6f} (should be 1.0)")
        else:
            print(f"\n  ✓ All providers responded successfully")
            print(f"  Weights used:")
            for p, w in meta.get('adjusted_weights', {}).items():
                print(f"    {p}: {w:.3f}")
        
        print(f"\n  Agreement score: {meta.get('agreement_score', 0):.2f}")
        print(f"  Confidence variance: {meta.get('confidence_variance', 0):.2f}")
        
        if meta.get('all_providers_failed'):
            print(f"\n  ⚠️  ALL PROVIDERS FAILED - Using rule-based fallback")
    
    print("\n" + "=" * 70)
    
except Exception as e:
    print(f"\nError during analysis: {e}")
    logging.exception("Analysis failed")

print("\n" + "=" * 70)
print("Key Takeaways:")
print("=" * 70)
print("""
1. The ensemble system is resilient to provider failures
2. Weights are automatically renormalized when providers fail
3. Decision metadata shows which providers succeeded/failed
4. You can see the original vs adjusted weights in the output
5. Even with failures, the system produces a valid decision
6. If ALL providers fail, a rule-based fallback is used
7. This ensures 100% uptime for trading decisions

Best Practices:
- Use higher weights for more reliable providers (e.g., local LLM)
- Enable adaptive learning to improve weights over time
- Monitor ensemble_metadata to track provider health
- Consider provider redundancy in your configuration
""")
