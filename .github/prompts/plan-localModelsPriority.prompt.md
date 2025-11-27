Plan: Wire `local_models` & `local_priority`

TL;DR — Add two config keys (`decision_engine.local_models` and `decision_engine.local_priority`), expose them via `DecisionEngine`, pass them into local providers, and change ensemble orchestration so all local models are always queried first; then always query cloud providers as secondary (never skipped). Use `local_priority` to boost local provider weights in aggregation when valid local signals exist. Ensure aggregation and adaptive-weight updates use only valid signals and accept an optional adjusted-weights override. Update tests, CLI, and decision metadata.

### Steps (implementable, file-by-file)

1. Read config into engine
   - Files: `finance_feedback_engine/decision_engine/engine.py`
   - Symbols: `DecisionEngine.__init__`, `DecisionEngine._query_ai`, `DecisionEngine._ensemble_ai_inference`
   - Change: In `DecisionEngine.__init__` read and store:
     - `self.local_models = config.get('decision_engine', {}).get('local_models', [])` (list of strings)
     - `self.local_priority = config.get('decision_engine', {}).get('local_priority', False)` (bool|float|'soft')
     - Add validation/logging for these fields.
   - Rationale: make local preferences available centrally for orchestration.

2. Accept config in `LocalLLMProvider` and expose chosen local models
   - Files: `finance_feedback_engine/decision_engine/local_llm_provider.py`
   - Symbols: `LocalLLMProvider.__init__`, class attributes `DEFAULT_MODEL`, `FALLBACK_MODEL`, `SECONDARY_MODEL`
   - Change:
     - Accept `decision_engine.local_models` (if present) via `config` and set `self.local_models` (ordered list). If empty, fallback to existing `DEFAULT_MODEL`/`SECONDARY_MODEL` behavior.
     - Optionally expose `self.local_priority` if passed (for provider-level behavior).
     - Keep auto-download behavior but iterate `self.local_models` instead of hard-coded `DEFAULT_MODEL`/`SECONDARY_MODEL`.
   - Rationale: provider should be driven by explicit config list and report which local models it attempted.

3. Modify provider-lookup & single-provider calls to prefer explicit `local_models`
   - Files: `finance_feedback_engine/decision_engine/engine.py`
   - Symbols: `DecisionEngine._query_single_provider`, `DecisionEngine._specific_local_inference`, `DecisionEngine._local_ai_inference`, `DecisionEngine._get_all_local_models`
   - Change:
     - In `_query_single_provider`, when mapping a `provider` that resolves to a local model, consult `self.local_models` first (map each `provider` string to a concrete model name if present), then `local_providers` map, then discovered models.
     - Ensure `_specific_local_inference` constructs `LocalLLMProvider` with `temp_config` that includes the chosen model name and the `decision_engine.local_models` list (for transparency).
   - Rationale: deterministic mapping of abstract `local` provider names to configured local model tags.

4. Implement local-first orchestration in ensemble flow
   - Files: `finance_feedback_engine/decision_engine/engine.py`
   - Symbols: `DecisionEngine._ensemble_ai_inference`
   - Change:
     - Build two ordered lists at runtime:
       - `local_candidates` = expand `enabled_providers` and then intersect with `self.local_models` (explicit) or discovered local models (fallback). Ensure deduplication and preserve ordering.
       - `remote_candidates` = `enabled_providers` \ `local_candidates`.
     - Query ALL `local_candidates` sequentially (keep existing sequential local invocation to avoid GPU conflicts). Collect only valid responses (non-None and passing `_is_valid_provider_response`).
     - After local queries: Always proceed to query remote candidates concurrently (existing ThreadPoolExecutor flow).
     - If `self.local_priority` is truthy or numeric/"soft", compute adjusted weights boosting local providers by that factor prior to aggregation (see step 6).
     - Ensure `failed_providers` lists include any local model names that returned invalid/fallback responses.
   - Rationale: enforces always querying local models first and using them as primary signals, with cloud providers as secondary (never skipped).

5. Add optional adjusted-weights parameter to aggregator and apply `local_priority` boost
   - Files: `finance_feedback_engine/decision_engine/ensemble_manager.py`
   - Symbols: `EnsembleDecisionManager.aggregate_decisions`, `_adjust_weights_for_active_providers`, `aggregate_decisions` call sites in `engine.py`
   - Change:
     - Extend `aggregate_decisions` signature to accept an optional `adjusted_weights: Optional[Dict[str,float]] = None` and, if provided, use it directly instead of computing adjusted weights internally.
     - Alternatively (less intrusive) allow `aggregate_decisions` to accept an optional `local_priority_map` parameter (provider->priority) and apply the priority before computing adjusted weights.
     - Ensure `aggregate_decisions` includes `ensemble_metadata['local_priority_applied']` and `ensemble_metadata['local_models_used']` fields in the returned decision.
     - In `DecisionEngine._ensemble_ai_inference`, compute `adjusted_weights` if `local_priority` is numeric/soft by taking `self.ensemble_manager.provider_weights`, multiplying local providers' weights by the `local_priority` factor, then renormalizing, and pass `adjusted_weights` into `aggregate_decisions`.
   - Rationale: preserve separation of concerns (engine computes boost; manager aggregates) while enabling priority weighting.

6. Ensure only valid signals update adaptive weights/performance history
   - Files: `finance_feedback_engine/decision_engine/engine.py`, `finance_feedback_engine/decision_engine/ensemble_manager.py`
   - Symbols: `DecisionEngine._ensemble_ai_inference`, `EnsembleDecisionManager.update_provider_weights`
   - Change:
     - Confirm `provider_decisions` passed to `aggregate_decisions` and `update_provider_weights` contains only valid providers (engine already filters, but make explicit). Add an assertion/log and preprocess step: `provider_decisions = {k:v for k,v in provider_decisions.items() if v is not None}` before passing to manager.
     - In `EnsembleDecisionManager.update_provider_weights`, defensively ignore any provider entries that are None or whose decision has `'fallback_used'` or other fallback indicators — only update performance history for keys actually present in `provider_decisions` and passing `_validate_decision`.
   - Rationale: ensure historical weights only reflect genuine provider signals.

7. Persist ensemble metadata and local usage in decisions
   - Files: `finance_feedback_engine/decision_engine/engine.py`, `finance_feedback_engine/persistence/decision_store.py` (if present)
   - Symbols: `DecisionEngine._create_decision`, persistence save methods
   - Change:
     - Make sure the final decision `ensemble_metadata` (assembled by `aggregate_decisions`) contains `local_models_used` (list of local model names actually counted) and `local_priority_applied` (bool/description). If aggregation returns adjusted_weights, include `ensemble_metadata['adjusted_weights']`.
     - Ensure `decision_store` will not break if new keys are present; preserve filename & append semantics.
   - Rationale: observability and post-hoc analysis.

8. Add CLI flags and config example updates
   - Files: `main.py` / `finance_feedback_engine/cli/main.py` (where CLI lives), `config/config.local.yaml`, `docs/AI_PROVIDERS.md`/`docs/ENSEMBLE_SYSTEM.md`
   - Symbols: CLI arg parsing functions, config examples
   - Change:
     - Add optional CLI flags `--local-models "m1,m2"` and `--local-priority <true|false|soft|1.25>` that override config values at runtime. Wire parsed values to `config` before constructing `DecisionEngine`.
     - Add `decision_engine.local_models` and `decision_engine.local_priority` examples/comments to `config/config.local.yaml` and docs.
   - Rationale: quick overrides for experimentation.

9. Tests & test harness updates
   - Files: `tests/test_engine.py`, `tests/test_ensemble_manager.py`, add `tests/test_ensemble_local_models.py`
   - Change:
     - Add unit tests:
       - `test_local_priority_boosts_locals`: with `local_priority: true` or numeric, assert adjusted_weights favor locals when both local and remote providers are queried and return valid decisions.
       - `test_local_priority_fallback_to_remote`: local providers return invalid/fallback; ensure remote providers are queried and used, with locals not affecting aggregation.
       - `test_soft_local_priority_adjusts_weights`: local_priority numeric (e.g., `1.5`) causes adjusted_weights to favor locals; assert `ensemble_metadata.adjusted_weights` reflects boost.
       - `test_weights_updated_only_for_valid_providers`: simulate update_provider_weights call and assert only valid providers written to `ensemble_history.json`.
     - Mock `LocalLLMProvider.query` and `ollama list` subprocesses to make tests deterministic.
   - Rationale: validate behavior and prevent regressions.

10. Docs, logging, and migration notes
    - Files: `docs/AI_PROVIDERS.md`, `docs/ENSEMBLE_FALLBACK_IMPLEMENTATION.md`, `IMPROVEMENTS.md`
    - Change:
      - Document new config keys, semantics, default values, and examples.
      - Add migration note: default behavior unchanged when keys absent.
      - Add debug logs at key decision points (`local_candidates`, `valid_local_count`, `remote_skipped`, `adjusted_weights`).

### Further Considerations
- **Defaults & safe behavior:** keep `decision_engine.local_priority: false` by default to preserve current behavior. Default `local_models: []` should mean “use existing discovery and current defaults” (no change).
- **Backward compatibility:** code must accept older configs; if `local_models` contains model names not present in `ollama list`, treat those as attempted and, on failure, fall back per current logic (do not crash).
- **Aggregate API change:** adding `adjusted_weights` optional param to `aggregate_decisions` is a small breaking change to a public method. Prefer adding as optional param with default `None` to avoid breaking callers.
- **Performance & GPU contention:** retain sequential local queries to avoid memory issues; document expected per-local-model timeout (keep existing 60s) and per-remote timeout (10s).
- **Observability:** include `ensemble_metadata.local_models_used` and `ensemble_metadata.local_priority_applied` to help debug infra issues. Cloud providers are always queried as secondary, never skipped.
