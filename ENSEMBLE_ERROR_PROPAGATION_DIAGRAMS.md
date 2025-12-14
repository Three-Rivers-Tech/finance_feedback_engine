# Ensemble Error Propagation - Visual Flow Diagrams

## Before Fix (BROKEN) ❌

```
┌─────────────────────────────────────────────────────────────────┐
│  Ensemble Mode - Simple Parallel Ensemble                      │
└─────────────────────────────────────────────────────────────────┘

1. Query Local Provider
   ├─ Try: LocalLLMProvider.query()
   └─ Catch RuntimeError: "Ollama service down"
      └─ Return: build_fallback_decision() ← ❌ PROBLEM
         └─ { action: "HOLD", confidence: 50, reasoning: "..." }

2. asyncio.gather([local_task, cli_task, gemini_task])
   └─ Results: [fallback_decision, cli_decision, gemini_decision]

3. Check for exceptions:
   for result in results:
     if isinstance(result, Exception):  ← ❌ NEVER TRIGGERS
       failed_providers.append(...)

4. Validate responses:
   if _is_valid_provider_response(fallback_decision):  ← ✓ PASSES
     provider_decisions['local'] = fallback_decision  ← ❌ WRONG

5. Aggregate decisions:
   └─ Weighted voting with LOCAL INCLUDED
      └─ Weight: 0.33 for local (fallback HOLD)
      └─ Weight: 0.33 for cli (valid decision)
      └─ Weight: 0.34 for gemini (valid decision)

PROBLEMS:
❌ Local provider counted as "succeeded" (not in failed_providers)
❌ Fallback decision influences final vote (dilutes other providers)
❌ Provider weights NOT adjusted (local still has 0.33 weight)
❌ Ensemble metadata shows 3/3 providers active (incorrect)
```

---

## After Fix (WORKING) ✅

```
┌─────────────────────────────────────────────────────────────────┐
│  Ensemble Mode - Simple Parallel Ensemble                      │
└─────────────────────────────────────────────────────────────────┘

1. Query Local Provider
   ├─ Try: LocalLLMProvider.query()
   └─ Catch RuntimeError: "Ollama service down"
      ├─ Log: Enhanced logging with structured data
      └─ Check: if self.ai_provider == 'ensemble':
         └─ Raise RuntimeError  ← ✅ FIX: Re-raise in ensemble mode

2. asyncio.gather([local_task, cli_task, gemini_task], return_exceptions=True)
   └─ Results: [RuntimeError, cli_decision, gemini_decision]

3. Check for exceptions:
   for result in results:
     if isinstance(result, Exception):  ← ✅ NOW TRIGGERS
       failed_providers.append('local')  ← ✅ CORRECT

4. Validate responses:
   ├─ Skip RuntimeError (it's an exception, not a dict)
   ├─ Validate cli_decision: ✓ valid
   └─ Validate gemini_decision: ✓ valid

5. Adjust weights for active providers:
   └─ Original: {local: 0.33, cli: 0.33, gemini: 0.34}
   └─ Adjusted: {cli: 0.50, gemini: 0.50}  ← ✅ LOCAL EXCLUDED

6. Aggregate decisions:
   └─ Weighted voting with ONLY cli and gemini
      └─ Weight: 0.50 for cli
      └─ Weight: 0.50 for gemini
      └─ Metadata:
         ├─ providers_used: ['cli', 'gemini']
         ├─ providers_failed: ['local']
         ├─ num_active: 2
         ├─ num_total: 3
         └─ failure_rate: 0.33

BENEFITS:
✅ Local provider correctly tracked as failed
✅ Fallback decision NOT used in voting
✅ Provider weights adjusted (renormalized to exclude local)
✅ Ensemble metadata accurate (2/3 providers active)
✅ Confidence adjusted down for provider availability
```

---

## Single-Provider Mode (UNCHANGED) ✅

```
┌─────────────────────────────────────────────────────────────────┐
│  Single-Provider Mode (ai_provider='local')                     │
└─────────────────────────────────────────────────────────────────┘

1. Query Local Provider
   ├─ Try: LocalLLMProvider.query()
   └─ Catch RuntimeError: "Ollama service down"
      ├─ Log: Enhanced logging with structured data
      └─ Check: if self.ai_provider == 'ensemble':  ← ✗ FALSE
         └─ Return: build_fallback_decision()  ← ✅ CORRECT
            └─ { action: "HOLD", confidence: 50, reasoning: "..." }

2. Return fallback decision to caller
   └─ Graceful degradation (no exception raised)

BEHAVIOR:
✅ Single-provider mode still returns fallback decisions
✅ No exception propagated (maintains backward compatibility)
✅ User sees low-confidence HOLD with descriptive reasoning
```

---

## Exception Types Handled

```
┌──────────────────────────────────────────────────────────────┐
│  Exception Handling in _local_ai_inference()               │
└──────────────────────────────────────────────────────────────┘

try:
    from .local_llm_provider import LocalLLMProvider
    provider = LocalLLMProvider(config)
    return await asyncio.to_thread(provider.query, prompt)

except ImportError as e:
    # Missing dependency (ollama module not installed)
    logger.error(..., extra={'failure_type': 'dependency'})
    if ensemble_mode: raise
    return fallback_decision

except RuntimeError as e:
    # Infrastructure failures:
    # - Ollama service not running
    # - Model not found
    # - GPU/CUDA initialization failure
    # - Thread pool exhaustion
    logger.error(..., extra={'failure_type': 'infrastructure'})
    if ensemble_mode: raise
    return fallback_decision

except Exception as e:
    # Generic catch-all for unexpected errors
    logger.error(..., extra={'failure_type': 'unknown'})
    if ensemble_mode: raise
    return fallback_decision
```

---

## Ensemble Metadata Structure

```json
{
  "ensemble_metadata": {
    "providers_used": ["cli", "gemini"],
    "providers_failed": ["local"],
    "num_active": 2,
    "num_total": 3,
    "failure_rate": 0.33,
    "original_weights": {
      "local": 0.33,
      "cli": 0.33,
      "gemini": 0.34
    },
    "adjusted_weights": {
      "cli": 0.50,
      "gemini": 0.50
    },
    "weight_adjustment_applied": true,
    "voting_strategy": "weighted",
    "fallback_tier": "weighted",
    "provider_decisions": {
      "cli": { "action": "BUY", "confidence": 80, ... },
      "gemini": { "action": "HOLD", "confidence": 70, ... }
    },
    "agreement_score": 0.5,
    "confidence_variance": 25.0,
    "timestamp": "2025-12-13T..."
  }
}
```

---

## Local Priority Fallback Chain

```
┌──────────────────────────────────────────────────────────────┐
│  Local Priority Fallback (local_priority='soft')           │
└──────────────────────────────────────────────────────────────┘

Config:
  enabled_providers: ['local', 'gemini']
  provider_weights: {local: 0.7, gemini: 0.3}
  local_priority: 'soft'

Flow:
  1. Try local provider → RuntimeError (model not found)
     └─ Exception raised (ensemble mode)

  2. asyncio.gather catches exception
     └─ failed_providers.append('local')

  3. Query gemini provider → Success
     └─ provider_decisions['gemini'] = {...}

  4. Adjust weights:
     └─ Original: {local: 0.7, gemini: 0.3}
     └─ Adjusted: {gemini: 1.0}  ← Only active provider

  5. Aggregate with gemini decision:
     └─ Final action: Gemini's recommendation (BUY)
     └─ NOT fallback HOLD (local failure didn't bypass fallback)

BEFORE FIX: ❌
  Local returns fallback HOLD → gemini never queried
  Final decision: HOLD (no fallback to remote provider)

AFTER FIX: ✅
  Local raises exception → gemini queried successfully
  Final decision: BUY (proper fallback to remote provider)
```

---

## Test Coverage Matrix

```
┌─────────────────────────────────────────────────────────────────┐
│  Test Category                      │  Tests │  Status         │
├─────────────────────────────────────┼────────┼─────────────────┤
│  Ensemble Failure Tracking          │   3    │  ✅ ALL PASS    │
│  Single-Provider Fallback           │   3    │  ✅ ALL PASS    │
│  Local Priority Fallback Chain      │   2    │  ✅ ALL PASS    │
│  Provider Weight Adjustment         │   1    │  ✅ ALL PASS    │
│  Ensemble Fallback Tiers            │   1    │  ✅ ALL PASS    │
├─────────────────────────────────────┼────────┼─────────────────┤
│  TOTAL                              │  10    │  ✅ 10/10 PASS  │
└─────────────────────────────────────┴────────┴─────────────────┘

Existing Ensemble Tests: 65 passed, 18 skipped ✅
No Regressions Detected ✅
```
