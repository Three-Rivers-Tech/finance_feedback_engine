# TICKET-WF-001: Debug and fix `walk-forward` CLI command

Summary
- The `walk-forward` CLI command (`python main.py walk-forward`) is failing under QA with import and argument errors. QA logs show failures like "cannot import name 'AdvancedBacktester'" and "WalkForwardAnalyzer.run_walk_forward() got an unexpected keyword argument 'train_ratio'".

Reproduction
1. From project root, run:

```
python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-01-31 --train-ratio 0.7
```

2. Observe error output referencing missing imports or unexpected keyword args (see `qa_results_full.json` and `qa_results_fixed.json` for examples).

Investigation notes
- Tests and QA scripts expect a `--train-ratio` flag and an implemented `WalkForwardAnalyzer` / `AdvancedBacktester` integration.
- `DELIVERABLES_SUMMARY.txt` lists Walk-forward as incomplete.
- Files referencing `walk-forward` include `README.md`, `CLAUDE.md`, and `qa_test_harness.py` which use the above syntax.

Acceptance criteria
- `python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-01-31 --train-ratio 0.7` runs without raising import or unexpected-argument exceptions.
- Outputs a summary of windows and results similar to README examples (Date range, Train/Test ratios, Provider used).
- Add/adjust unit tests in `tests/test_cli_commands_comprehensive.py` to assert successful run or mock backtester responses.
- Update `docs/QA_ISSUES.md` and `DELIVERABLES_SUMMARY.txt` to reflect status when fixed.

Suggested steps
- Run the failing QA test to reproduce exact stack trace.
- Inspect `finance_feedback_engine/backtesting` for `AdvancedBacktester`, `WalkForwardAnalyzer` and their APIs.
- Align CLI handler in `main.py` to match `WalkForwardAnalyzer` signature or adapt the analyzer to accept `train_ratio`.
- Add a small integration test that runs the CLI with a short date range and a mock backtester.

Owner: TBD
Estimate: 2-4 hours

Related files
- `main.py`
- `finance_feedback_engine/backtesting/backtester.py`
- `finance_feedback_engine/backtesting/walk_forward.py`
- `qa_results_full.json`, `qa_results_fixed.json`
- `docs/QA_ISSUES.md`


