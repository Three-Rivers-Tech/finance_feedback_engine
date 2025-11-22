# Ensemble Fallback System - Visual Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                     AI Provider Ensemble Request                        │
│                  (Enabled: local, cli, codex, qwen)                     │
└─────────────────────────────────┬───────────────────────────────────────┘
                                  │
                    ┌─────────────┴─────────────┐
                    │  Query All Providers      │
                    │  (parallel requests)       │
                    └─────────────┬─────────────┘
                                  │
        ┌─────────────┬───────────┼───────────┬─────────────┐
        │             │           │           │             │
        ▼             ▼           ▼           ▼             ▼
    ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐     ┌─────────┐
    │ Local │   │  CLI  │   │ Codex │   │ Qwen  │     │ Failure │
    │  LLM  │   │  API  │   │  API  │   │  API  │     │ Handler │
    └───┬───┘   └───┬───┘   └───┬───┘   └───┬───┘     └─────────┘
        │           │           │           │
        │ Success   │ FAILED    │ Success   │ Success
        │           │           │           │
        ▼           ▼           ▼           ▼
    ┌───────┐   ┌───────┐   ┌───────┐   ┌───────┐
    │ Valid │   │  ---  │   │ Valid │   │ Valid │
    │  BUY  │   │       │   │  BUY  │   │ HOLD  │
    │ 85%   │   │       │   │ 75%   │   │ 60%   │
    └───┬───┘   └───────┘   └───┬───┘   └───┬───┘
        │                        │           │
        └────────────────┬───────┴───────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────────┐
        │     EnsembleDecisionManager.aggregate()        │
        │                                                 │
        │  Step 1: Track Failures                        │
        │  ├─ failed_providers = ['cli']                 │
        │  ├─ active_providers = 3                       │
        │  └─ failure_rate = 25%                         │
        │                                                 │
        │  Step 2: Dynamic Weight Recalculation          │
        │  ├─ Original: {local: 0.25, cli: 0.25,        │
        │  │             codex: 0.25, qwen: 0.25}        │
        │  ├─ Active sum: 0.25 + 0.25 + 0.25 = 0.75     │
        │  └─ Adjusted: {local: 0.333, codex: 0.333,    │
        │                qwen: 0.333}                     │
        │                                                 │
        │  Step 3: Apply Fallback Strategy               │
        │  ┌────────────────────────────────────┐        │
        │  │ Tier 1: Primary (weighted)         │        │
        │  │   ├─ Voting power:                 │        │
        │  │   │   local: 0.333 × 0.85 = 0.283  │        │
        │  │   │   codex: 0.333 × 0.75 = 0.250  │        │
        │  │   │   qwen:  0.333 × 0.60 = 0.200  │        │
        │  │   ├─ Normalize: [0.386, 0.341, 0.273]       │
        │  │   ├─ BUY votes: 0.386 + 0.341 = 0.727       │
        │  │   ├─ HOLD votes: 0.273                      │
        │  │   └─ Winner: BUY                   │        │
        │  │                                     │        │
        │  │ ✓ Validation: PASSED               │        │
        │  └────────────────────────────────────┘        │
        │                                                 │
        │  Step 4: Confidence Adjustment                 │
        │  ├─ Factor: 0.7 + 0.3 × (3/4) = 0.925         │
        │  ├─ Original confidence: 86                    │
        │  └─ Adjusted: 86 × 0.925 = 80%                │
        │                                                 │
        │  Step 5: Build Metadata                        │
        │  └─ providers_failed, adjusted_weights,        │
        │     fallback_tier, confidence_adjustment_      │
        │     factor, etc.                               │
        └────────────────┬───────────────────────────────┘
                         │
                         ▼
        ┌────────────────────────────────────────────────┐
        │           Final Ensemble Decision               │
        │                                                 │
        │  action: "BUY"                                  │
        │  confidence: 80  (adjusted from 86)             │
        │  reasoning: "ENSEMBLE DECISION (2 supporting)..." │
        │  amount: 105.0                                  │
        │                                                 │
        │  ensemble_metadata:                             │
        │    providers_used: [local, codex, qwen]         │
        │    providers_failed: [cli]                      │
        │    num_active: 3                                │
        │    num_total: 4                                 │
        │    failure_rate: 0.25                           │
        │    adjusted_weights: {local: 0.333, ...}        │
        │    fallback_tier: "primary"                     │
        │    confidence_adjusted: true                    │
        │    original_confidence: 86                      │
        │    confidence_adjustment_factor: 0.925          │
        └─────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                          FALLBACK TIER PROGRESSION
═══════════════════════════════════════════════════════════════════════════

┌───────────────────────────────────────────────────────────────────────┐
│ Tier 1: PRIMARY STRATEGY                                              │
│ ──────────────────────────────────────────────────────────────────── │
│ Strategy: As configured (weighted/majority/stacking)                  │
│ Requirements: At least 1 valid provider                               │
│ Quality: ★★★★★ (Best)                                                 │
│                                                                        │
│ Process:                                                               │
│  1. Apply dynamic weight adjustment for active providers              │
│  2. Execute voting strategy with adjusted weights                     │
│  3. Validate result (action, confidence, reasoning, amount)           │
│                                                                        │
│ On Success: Return decision, tier="primary"                           │
│ On Failure: ↓ Progress to Tier 2                                     │
└───────────────────────────────────────────────────────────────────────┘
                                     ↓
┌───────────────────────────────────────────────────────────────────────┐
│ Tier 2: MAJORITY VOTING FALLBACK                                      │
│ ──────────────────────────────────────────────────────────────────── │
│ Strategy: Simple vote counting (1 vote per provider)                  │
│ Requirements: At least 2 valid providers                              │
│ Quality: ★★★★☆ (Good)                                                 │
│                                                                        │
│ Process:                                                               │
│  1. Count votes for each action (BUY/SELL/HOLD)                      │
│  2. Select most common action                                         │
│  3. Average confidence of supporting providers                        │
│  4. Validate result                                                   │
│                                                                        │
│ On Success: Return decision, tier="majority_fallback"                 │
│ On Failure: ↓ Progress to Tier 3                                     │
└───────────────────────────────────────────────────────────────────────┘
                                     ↓
┌───────────────────────────────────────────────────────────────────────┐
│ Tier 3: SIMPLE AVERAGING FALLBACK                                     │
│ ──────────────────────────────────────────────────────────────────── │
│ Strategy: Average all confidences and amounts                         │
│ Requirements: At least 2 valid providers                              │
│ Quality: ★★★☆☆ (Acceptable)                                           │
│                                                                        │
│ Process:                                                               │
│  1. Find most common action                                           │
│  2. Average ALL confidences (not just supporters)                     │
│  3. Average ALL amounts                                               │
│  4. Validate result                                                   │
│                                                                        │
│ Use Case: When providers strongly disagree but decision needed        │
│                                                                        │
│ On Success: Return decision, tier="average_fallback"                  │
│ On Failure: ↓ Progress to Tier 4                                     │
└───────────────────────────────────────────────────────────────────────┘
                                     ↓
┌───────────────────────────────────────────────────────────────────────┐
│ Tier 4: SINGLE PROVIDER FALLBACK                                      │
│ ──────────────────────────────────────────────────────────────────── │
│ Strategy: Use highest confidence provider as sole decision maker      │
│ Requirements: At least 1 valid provider                               │
│ Quality: ★★☆☆☆ (Degraded - Last Resort)                              │
│                                                                        │
│ Process:                                                               │
│  1. Find provider with highest confidence                             │
│  2. Use their decision directly                                       │
│  3. Add metadata: fallback_used=true, fallback_provider               │
│                                                                        │
│ On Success: Return decision, tier="single_provider"                   │
│ On Failure: Raise ValueError (should never happen - validated upstream)│
└───────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                       WEIGHT RECALCULATION EXAMPLES
═══════════════════════════════════════════════════════════════════════════

Example 1: Equal Weights, One Failure
┌──────────────────────────────────────────────────────────────────────┐
│ Original Weights:                                                     │
│   local: 0.25    cli: 0.25    codex: 0.25    qwen: 0.25             │
│                                                                       │
│ Provider States:                                                      │
│   local: ✓       cli: ✗       codex: ✓       qwen: ✓               │
│                                                                       │
│ Active Weight Sum: 0.25 + 0.25 + 0.25 = 0.75                        │
│                                                                       │
│ Adjusted Weights:                                                     │
│   local: 0.25/0.75 = 0.333                                           │
│   codex: 0.25/0.75 = 0.333                                           │
│   qwen:  0.25/0.75 = 0.333                                           │
│                                                                       │
│ ✓ Weights sum to 1.0                                                 │
└──────────────────────────────────────────────────────────────────────┘

Example 2: Asymmetric Weights, One Failure
┌──────────────────────────────────────────────────────────────────────┐
│ Original Weights (learned from performance):                         │
│   local: 0.40    cli: 0.30    codex: 0.20    qwen: 0.10             │
│                                                                       │
│ Provider States:                                                      │
│   local: ✓       cli: ✓       codex: ✗       qwen: ✓               │
│                                                                       │
│ Active Weight Sum: 0.40 + 0.30 + 0.10 = 0.80                        │
│                                                                       │
│ Adjusted Weights:                                                     │
│   local: 0.40/0.80 = 0.500  (still highest)                          │
│   cli:   0.30/0.80 = 0.375                                           │
│   qwen:  0.10/0.80 = 0.125  (still lowest)                           │
│                                                                       │
│ ✓ Proportions preserved                                              │
│ ✓ High-weight providers still dominate                               │
└──────────────────────────────────────────────────────────────────────┘


═══════════════════════════════════════════════════════════════════════════
                       CONFIDENCE DEGRADATION FORMULA
═══════════════════════════════════════════════════════════════════════════

adjustment_factor = 0.7 + 0.3 × (active_providers / total_providers)

┌─────────┬────────┬──────────────────────────────────────────────────┐
│ Active/ │ Factor │ Impact on 85% Confidence                         │
│ Total   │        │                                                  │
├─────────┼────────┼──────────────────────────────────────────────────┤
│ 4/4     │ 1.000  │ 85% → 85% (no change)                            │
│ 3/4     │ 0.925  │ 85% → 79% (-7%)    ◄── Typical 1 failure         │
│ 2/4     │ 0.850  │ 85% → 72% (-15%)   ◄── Half providers down       │
│ 1/4     │ 0.775  │ 85% → 66% (-22%)   ◄── Critical: 1 provider only │
└─────────┴────────┴──────────────────────────────────────────────────┘

Rationale:
• Minimum factor: 0.70 (retain 70% confidence even with 0 active - safety)
• Maximum factor: 1.00 (full confidence with all active)
• Linear scaling: Smooth degradation as providers fail
• Reflects uncertainty: Fewer providers = less consensus
```

---

**Visual created**: November 22, 2025  
**Purpose**: Architecture overview and design documentation  
**Audience**: Developers, operators, auditors
