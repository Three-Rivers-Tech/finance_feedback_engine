import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from finance_feedback_engine.cli.main import cli
from finance_feedback_engine.utils.threshold_avoidance import DecisionLoadReport


class _FakeStudy:
    def __init__(self):
        self.best_value = 1.23
        self.best_params = {"risk_per_trade": 0.02}


def test_experiment_command_writes_json_and_csv_outputs():
    runner = CliRunner()

    with runner.isolated_filesystem():
        with patch(
            "finance_feedback_engine.cli.main.load_tiered_config", return_value={}
        ):
            with patch(
                "finance_feedback_engine.cli.commands.experiment.OptunaOptimizer.optimize",
                return_value=_FakeStudy(),
            ):
                result = runner.invoke(
                    cli,
                    [
                        "experiment",
                        "BTC-USD",
                        "--start",
                        "2024-01-01",
                        "--end",
                        "2024-01-31",
                        "--n-trials",
                        "2",
                        "--no-mlflow",
                    ],
                )

        assert result.exit_code == 0, result.output

        out_dir = Path("data/optimization")
        json_files = sorted(out_dir.glob("experiment_*.json"))
        csv_files = sorted(out_dir.glob("experiment_*.csv"))

        assert len(json_files) == 1
        assert len(csv_files) == 1

        payload = json.loads(json_files[0].read_text(encoding="utf-8"))
        assert payload["asset_pairs"] == ["BTCUSD"]
        assert payload["n_trials_per_asset"] == 2


def test_behavior_experiment_command_writes_output():
    runner = CliRunner()

    with runner.isolated_filesystem():
        out_dir = Path("data/decisions")
        out_dir.mkdir(parents=True, exist_ok=True)
        (out_dir / "sample.json").write_text(json.dumps({
            "timestamp": "2026-04-23T14:59:22+00:00",
            "asset_pair": "BTCUSD",
            "decision_origin": "judge",
            "action": "OPEN_MEDIUM_LONG",
            "policy_action": "OPEN_MEDIUM_LONG",
            "confidence": 75,
            "volatility": 0.08,
            "filtered_reason_code": "QUALITY_GATE_BLOCK"
        }), encoding="utf-8")

        with patch(
            "finance_feedback_engine.cli.main.load_tiered_config", return_value={}
        ):
            result = runner.invoke(
                cli,
                [
                    "behavior-experiment",
                    "--asset-pair",
                    "BTCUSD",
                    "--since-hours",
                    "48",
                ],
            )

        assert result.exit_code == 0, result.output
        files = sorted(Path("data/experiments").glob("behavior_experiment_*.json"))
        assert len(files) == 1
        payload = json.loads(files[0].read_text(encoding="utf-8"))
        assert payload["load_report"]["loaded_records"] == 1
        assert payload["summary"]["judged_open_records"] == 1
        assert payload["summary"]["judged_open_confidence_counts"] == {"75": 1}
        assert payload["summary"]["counterfactual"]["75"]["judged_open_passed"] == 1


def test_behavior_experiment_command_fails_when_all_files_are_unreadable():
    runner = CliRunner()
    unreadable_report = DecisionLoadReport(
        records=[],
        scanned_files=2,
        loaded_records=0,
        skipped_unreadable_files=2,
        unreadable_examples=["/tmp/a.json", "/tmp/b.json"],
    )

    with runner.isolated_filesystem():
        out_dir = Path("data/decisions")
        out_dir.mkdir(parents=True, exist_ok=True)
        with patch(
            "finance_feedback_engine.cli.main.load_tiered_config", return_value={}
        ), patch(
            "finance_feedback_engine.cli.commands.behavior_experiment.load_decision_records_report",
            return_value=unreadable_report,
        ):
            result = runner.invoke(
                cli,
                ["behavior-experiment", "--asset-pair", "BTCUSD", "--since-hours", "48"],
            )

    assert result.exit_code != 0
    assert "unreadable_files=2" in result.output
