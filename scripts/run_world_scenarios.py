#!/usr/bin/env python3
"""Run world scenario tests from `data/decisions_test/`.

This script:
- Loads each JSON in `data/decisions_test/`
- Persists it to a temporary decision store (under `data/decisions_test_run/`)
- Attempts to execute the decision via `FinanceFeedbackEngine.execute_decision`
- For learn scenarios, records a simulated trade outcome via `record_trade_outcome`
- Summarizes results to stdout
"""
import json
import logging
from pathlib import Path
from finance_feedback_engine.cli.main import load_tiered_config
from finance_feedback_engine.core import FinanceFeedbackEngine


def main():
    logging.basicConfig(level=logging.INFO)

    repo_root = Path(__file__).resolve().parent.parent
    tests_dir = repo_root / "data" / "decisions_test"
    out_store = repo_root / "data" / "decisions_test_run"

    # Load base/tiered config and override a few keys for safe testing
    config = load_tiered_config()
    # Force mock platform and test persistence path
    config['trading_platform'] = 'mock'
    config.setdefault('persistence', {})
    config['persistence']['storage_path'] = str(out_store)

    # Enable portfolio memory to exercise learning path
    config.setdefault('portfolio_memory', {})
    config['portfolio_memory']['enabled'] = True

    engine = FinanceFeedbackEngine(config)

    results = []

    for fp in sorted(tests_dir.glob('*.json')):
        name = fp.stem
        print(f"\n=== Scenario: {fp.name} ===")
        try:
            with open(fp, 'r') as f:
                decision = json.load(f)
        except Exception as e:
            print(f"Failed to load {fp}: {e}")
            continue

        # Persist into the engine's decision store (will write to test output dir)
        engine.decision_store.save_decision(decision)

        scenario_result = {'file': fp.name, 'saved': True}

        # Attempt to execute if not already executed
        decision_id = decision.get('id')
        try:
            if decision.get('executed'):
                print(f"Decision {decision_id} already marked executed; skipping execute call.")
                scenario_result['execute'] = 'skipped-already-executed'
            else:
                print(f"Attempting execute_decision('{decision_id}')...")
                exec_res = engine.execute_decision(decision_id)
                print(f"Execution result: {exec_res}")
                scenario_result['execute'] = 'success'
                scenario_result['execution_result'] = exec_res
        except Exception as e:
            print(f"Execution raised: {type(e).__name__}: {e}")
            scenario_result['execute'] = 'error'
            scenario_result['execute_error'] = f"{type(e).__name__}: {e}"

        # If there's a market_data and entry price, run learning recording for scenarios named '*learn*'
        if 'learn' in fp.name or 'test-learn' in fp.name:
            try:
                # Use a simulated exit price: 10% above entry to show profitable path
                entry_price = decision.get('entry_price') or decision.get('market_data', {}).get('close') or 1.0
                exit_price = entry_price * 1.10
                print(f"Recording trade outcome for {decision_id} (exit_price={exit_price})")
                outcome = engine.record_trade_outcome(decision_id, exit_price)
                print(f"Recorded outcome: {outcome}")
                scenario_result['learn'] = 'recorded'
                scenario_result['outcome'] = outcome
            except Exception as e:
                print(f"Recording outcome raised: {type(e).__name__}: {e}")
                scenario_result['learn'] = 'error'
                scenario_result['learn_error'] = f"{type(e).__name__}: {e}"

        results.append(scenario_result)

    # Summary
    print("\n=== Summary ===")
    for r in results:
        print(json.dumps(r, indent=2, default=str))


if __name__ == '__main__':
    main()
