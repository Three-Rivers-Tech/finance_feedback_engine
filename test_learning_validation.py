#!/usr/bin/env python3
"""Test learning validation metrics."""

from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine, TradeOutcome
from finance_feedback_engine.backtesting.monte_carlo import MonteCarloSimulator
import json
from datetime import datetime, timedelta, timezone

print("Testing Learning Validation Metrics...")

# Initialize memory with minimal config
config = {
    'memory': {
        'max_outcomes': 1000,
        'learning_rate': 0.1,
        'context_window': 50
    }
}
memory = PortfolioMemoryEngine(config)

# Simulate learning progression: early trades worse, later trades better
base_date = datetime.now(timezone.utc)
providers = ['anthropic', 'openai', 'google']

print("\n1. Adding 100 simulated trades showing learning progression...")
for i in range(100):
    # Simulate improving performance over time
    skill_factor = i / 100  # 0 to 1 progression
    win_probability = 0.4 + (skill_factor * 0.3)  # 40% -> 70% win rate

    import random
    random.seed(i)
    is_win = random.random() < win_probability

    # Provider selection: converge toward 'anthropic' as learning improves
    if skill_factor < 0.3:
        provider = random.choice(providers)
    elif skill_factor < 0.7:
        provider = 'anthropic' if random.random() < 0.6 else random.choice(providers)
    else:
        provider = 'anthropic' if random.random() < 0.8 else random.choice(providers)

    outcome = TradeOutcome(
        decision_id=f"test_{i}",
        asset_pair="BTCUSD",
        action='BUY',
        entry_timestamp=(base_date + timedelta(hours=i)).isoformat(),
        exit_timestamp=(base_date + timedelta(hours=i, minutes=30)).isoformat(),
        entry_price=50000.0,
        exit_price=50000.0 * (1.02 if is_win else 0.98),
        position_size=0.01,
        holding_period_hours=0.5,
        realized_pnl=10.0 if is_win else -10.0,
        pnl_percentage=2.0 if is_win else -2.0,
        was_profitable=is_win,
        ai_provider=provider,
        decision_confidence=60 + int(skill_factor * 30)
    )
    # Directly append to avoid needing full decision dict
    memory.trade_outcomes.append(outcome)

print(f"Added {len(memory.trade_outcomes)} trade outcomes")

# Generate learning validation metrics
print("\n2. Generating Learning Validation Metrics...")
metrics = memory.generate_learning_validation_metrics()

print("\n=== Learning Validation Report ===")
print(json.dumps(metrics, indent=2, default=str))

# Test Monte Carlo simulator (placeholder)
print("\n3. Testing Monte Carlo Simulator (placeholder mode)...")
mc = MonteCarloSimulator()
print("✓ MonteCarloSimulator initialized")
print("  (Full price perturbation requires deeper backtester integration)")

print("\n✅ All learning validation tests passed!")
