# Ensemble Error Propagation Analysis

**Date**: December 13, 2025
**Status**: Critical Issues Identified - Requires Immediate Attention

## Executive Summary

The current error handling in `_local_ai_inference()` (lines 838-843 of `engine.py`) converts all exceptions to fallback decisions using `build_fallback_decision()`. This creates **four critical issues** that undermine ensemble integrity, provider failure tracking, and operational visibility.

## Critical Issues Identified

### Issue 1: Ensemble Provider Failure Tracking is Broken

**Problem**: The ensemble uses `asyncio.gather(return_exceptions=True)` and checks `isinstance(result, Exception)` to detect provider failures (line 787 in `_simple_parallel_ensemble()`). When exceptions are converted to fallback decisions, they appear as valid responses instead of failures.

**Current Code Path**:
```python
# engine.py:787-797
results = await asyncio.gather(*tasks, return_exceptions=True)

for provider, result in zip(self.ensemble_manager.enabled_providers, results):
    if isinstance(result, Exception):  # ❌ This check NEVER triggers now
        logger.error(f"Provider {provider} failed: {result}")
        failed_providers.append(provider)
    else:
        decision = result
        if self.ensemble_manager._is_valid_provider_response(decision, provider):
            provider_decisions[provider] = decision
```

**Impact**:
- Failed providers are counted as "succeeded" with low-confidence HOLD decisions
- `failed_providers` list is incomplete
- Provider weight adjustments don't account for actual failures
- Ensemble metadata shows incorrect provider success counts

**Evidence from Code**:
```python
# decision_validation.py:140-148
def build_fallback_decision(reasoning: str, fallback_confidence: int = 50) -> Dict[str, Any]:
    """Standardized fallback decision structure."""
    return {
        'action': 'HOLD',
        'confidence': fallback_confidence,  # Default: 50
        'reasoning': reasoning,
        'amount': 0
    }
```

This fallback decision **passes validation** in `_is_valid_provider_response()`:
```python
# ensemble_manager.py:1110-1142
def _is_valid_provider_response(self, decision: Dict[str, Any], provider: str) -> bool:
    if not isinstance(decision, dict):
        return False
    if 'action' not in decision or 'confidence' not in decision:
        return False
    if decision['action'] not in ['BUY', 'SELL', 'HOLD']:  # ✓ HOLD is valid
        return False
    if not (0 <= conf <= 100):  # ✓ confidence=50 is valid
        return False
    return True  # ✓ Fallback decision passes validation
```

### Issue 2: Local Priority Fallback Chain is Bypassed

**Problem**: When `local_priority` is configured (line 130), the system should fall back to other providers if local LLM fails. Converting exceptions to fallback decisions bypasses this mechanism entirely.

**Expected Behavior** (based on config):
```yaml
# config.yaml
decision_engine:
  local_models: ["llama3.2:3b", "mistral:7b"]
  local_priority: "soft"  # Try local first, fallback to remote if it fails
```

**What Should Happen**:
1. Try local Ollama provider
2. If exception (service down, model missing, etc.), propagate exception
3. Ensemble manager catches exception, marks provider as failed
4. Falls back to remote providers (cli, codex, gemini, qwen)

**What Actually Happens**:
1. Try local Ollama provider
2. Exception caught and converted to fallback HOLD decision (confidence=50)
3. Ensemble manager sees valid response, no fallback triggered
4. Remote providers never consulted (if local_priority=True)

### Issue 3: RuntimeError Scope is Too Broad

**Problem**: `RuntimeError` is an extremely generic exception that catches many unrelated failures:

```python
# engine.py:841-842
except RuntimeError as e:
    logger.error(f"Local LLM failed due to runtime error: {e}")
    return build_fallback_decision(f"Local LLM runtime error: {str(e)}, using fallback decision.")
```

**What RuntimeError Catches**:
- Ollama service not running (`ConnectionRefusedError` wrapped in RuntimeError)
- Model not found (`Model 'llama3.2:3b' not found`)
- GPU/CUDA initialization failures
- Thread pool exhaustion
- asyncio event loop errors
- Any other runtime condition

**Consequence**: All these diverse failure modes get the same treatment (50% confidence HOLD), making diagnosis impossible.

### Issue 4: Critical Infrastructure Failures Are Masked

**Problem**: Converting all failures to fallback decisions hides critical issues that operators need to address immediately:

**Critical Failures That Should Alert Operators**:
- Ollama service down (system-wide issue)
- Missing models (configuration issue)
- Import failures (dependency issue)
- Out of memory (resource issue)

**Current Behavior**: All appear as low-confidence HOLD decisions in logs:
```
INFO: Provider local -> HOLD (50%)
```

**Operators Cannot Distinguish**:
- Legitimate "market too uncertain" HOLD from model
- vs. "Ollama service crashed" HOLD from fallback
- vs. "Model not found" HOLD from fallback

## Recommended Fixes

### Fix 1: Propagate Exceptions in Ensemble Mode

**Strategy**: Let exceptions bubble up in ensemble contexts so `asyncio.gather` can catch them properly.

```python
async def _local_ai_inference(self, prompt: str, model_name: Optional[str] = None) -> Dict[str, Any]:
    """Local AI inference using Ollama LLM."""
    # ... existing code ...

    try:
        from .local_llm_provider import LocalLLMProvider
        provider_config = dict(self.config, model_name=model_name or self.config.get('model_name', 'default'))
        provider = LocalLLMProvider(provider_config)
        return await asyncio.to_thread(provider.query, prompt)
    except ImportError as e:
        logger.error(f"Local LLM failed due to missing import: {e}")
        # Re-raise in ensemble mode for proper failure tracking
        if self.ai_provider == 'ensemble':
            raise
        return build_fallback_decision("Local LLM import error, using fallback decision.")
    except RuntimeError as e:
        logger.error(f"Local LLM failed due to runtime error: {e}")
        # Re-raise in ensemble mode for proper failure tracking
        if self.ai_provider == 'ensemble':
            raise
        return build_fallback_decision(f"Local LLM runtime error: {str(e)}, using fallback decision.")
    except Exception as e:
        logger.error(f"Local LLM failed due to unexpected error: {e}")
        # Re-raise in ensemble mode for proper failure tracking
        if self.ai_provider == 'ensemble':
            raise
        return build_fallback_decision(f"Local LLM unexpected error: {str(e)}, using fallback decision.")
```

**Benefits**:
- Ensemble properly tracks failed providers
- Provider weights adjust correctly
- Fallback tiers work as designed
- Metadata reflects actual provider status

### Fix 2: Add Specific Exception Types for Infrastructure Failures

**Strategy**: Create custom exceptions for critical failures that should always be surfaced.

```python
# New file: finance_feedback_engine/exceptions.py
class InfrastructureError(Exception):
    """Critical infrastructure failure requiring operator attention."""
    pass

class OllamaServiceUnavailable(InfrastructureError):
    """Ollama service is not running or unreachable."""
    pass

class ModelNotFoundError(InfrastructureError):
    """Requested model is not installed."""
    pass
```

```python
# local_llm_provider.py
def query(self, prompt: str) -> Dict[str, Any]:
    try:
        response = ollama.generate(model=self.model_name, prompt=prompt)
    except ollama.ConnectionError:
        raise OllamaServiceUnavailable(f"Cannot connect to Ollama service") from None
    except ollama.ModelNotFoundError:
        raise ModelNotFoundError(f"Model {self.model_name} not installed") from None
```

### Fix 3: Add Infrastructure Health Check

**Strategy**: Proactively check critical dependencies before attempting inference.

```python
# New file: finance_feedback_engine/utils/health_check.py
async def check_ollama_health() -> dict:
    """Check if Ollama service is available."""
    try:
        import ollama
        models = ollama.list()
        return {'available': True, 'models': [m['name'] for m in models]}
    except Exception as e:
        return {'available': False, 'error': str(e)}

# Usage in DecisionEngine.__init__:
if self.ai_provider in ('local', 'ensemble'):
    health = await check_ollama_health()
    if not health['available']:
        logger.warning(f"Ollama service unavailable: {health['error']}")
        if self.ai_provider == 'local':
            raise InfrastructureError("Local provider selected but Ollama unavailable")
```

### Fix 4: Enhanced Logging and Monitoring

**Strategy**: Add structured logging with failure categorization.

```python
# Add to _local_ai_inference error handlers:
logger.error(
    "Provider failure",
    extra={
        'provider': 'local',
        'model': model_name or self.model_name,
        'failure_type': 'infrastructure',  # or 'timeout', 'validation', etc.
        'error_class': type(e).__name__,
        'error_message': str(e),
        'ensemble_mode': self.ai_provider == 'ensemble',
        'will_fallback': self.ai_provider != 'ensemble'
    }
)
```

## Testing Requirements

### Test 1: Ensemble Properly Tracks Provider Failures
```python
async def test_ensemble_tracks_local_failures():
    """Verify failed local provider is correctly tracked in failed_providers."""
    config = {
        'decision_engine': {'ai_provider': 'ensemble'},
        'ensemble': {
            'enabled_providers': ['local', 'cli'],
            'provider_weights': {'local': 0.5, 'cli': 0.5}
        }
    }
    engine = DecisionEngine(config)

    # Mock local to raise exception, cli to return valid decision
    with patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider') as mock_local:
        mock_local.side_effect = RuntimeError("Ollama service down")

        decision = await engine._ensemble_ai_inference("test prompt")

        # Verify local is in failed_providers
        assert 'local' in decision['ensemble_metadata']['failed_providers']
        assert 'cli' in decision['ensemble_metadata']['active_providers']
```

### Test 2: Local Priority Falls Back to Remote Providers
```python
async def test_local_priority_fallback():
    """Verify local_priority triggers fallback when local fails."""
    config = {
        'decision_engine': {
            'ai_provider': 'ensemble',
            'local_priority': 'soft'
        },
        'ensemble': {
            'enabled_providers': ['local', 'gemini'],
            'provider_weights': {'local': 0.7, 'gemini': 0.3}
        }
    }
    engine = DecisionEngine(config)

    with patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider') as mock_local:
        mock_local.side_effect = RuntimeError("Model not found")

        decision = await engine._ensemble_ai_inference("test prompt")

        # Verify gemini was actually queried (not just ignored)
        assert 'gemini' in decision['ensemble_metadata']['active_providers']
        # Verify fallback tier was used
        assert decision['ensemble_metadata']['fallback_tier'] != 'weighted'
```

### Test 3: Single Provider Mode Uses Fallback Decisions
```python
async def test_single_local_provider_uses_fallback():
    """Verify single local provider returns fallback (not exception)."""
    config = {'decision_engine': {'ai_provider': 'local'}}
    engine = DecisionEngine(config)

    with patch('finance_feedback_engine.decision_engine.engine.LocalLLMProvider') as mock_local:
        mock_local.side_effect = RuntimeError("Ollama down")

        decision = await engine._local_ai_inference("test prompt")

        # Should return fallback, NOT raise exception
        assert decision['action'] == 'HOLD'
        assert 'fallback' in decision['reasoning'].lower()
```

## Implementation Priority

1. **CRITICAL (Immediate)**: Fix 1 - Propagate exceptions in ensemble mode
2. **HIGH (This Sprint)**: Test coverage for ensemble failure tracking
3. **MEDIUM (Next Sprint)**: Fix 2 - Specific exception types
4. **MEDIUM (Next Sprint)**: Fix 3 - Health checks
5. **LOW (Backlog)**: Fix 4 - Enhanced logging

## Backward Compatibility Notes

**Breaking Changes**: None - the fixes maintain current single-provider behavior while fixing ensemble mode.

**Migration Required**: None - existing configs continue to work.

**Deprecations**: None.

## Related Files

- `finance_feedback_engine/decision_engine/engine.py` (lines 814-843)
- `finance_feedback_engine/decision_engine/ensemble_manager.py` (lines 757-812, 1110-1142)
- `finance_feedback_engine/decision_engine/decision_validation.py` (lines 140-148)
- `finance_feedback_engine/decision_engine/local_llm_provider.py`
- `tests/test_ensemble_manager_validation.py`
- `tests/test_ensemble_tiers.py`

## References

- Ensemble fallback system docs: `docs/ENSEMBLE_FALLBACK_SYSTEM.md`
- Copilot instructions: `.github/copilot-instructions.md` (lines 95-105, ensemble behavior)
- Config reference: `config/config.yaml` (ensemble section)
