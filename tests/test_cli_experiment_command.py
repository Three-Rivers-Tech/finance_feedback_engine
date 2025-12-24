import json
from pathlib import Path
from unittest.mock import patch

from click.testing import CliRunner

from finance_feedback_engine.cli.main import cli


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
