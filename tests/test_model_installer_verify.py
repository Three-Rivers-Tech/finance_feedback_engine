import json
from unittest.mock import patch
import subprocess

from finance_feedback_engine.utils.model_installer import ModelInstaller


def _completed_proc(stdout: str = "", stderr: str = "", returncode: int = 0):
    cp = subprocess.CompletedProcess(args=["ollama"], returncode=returncode)
    cp.stdout = stdout
    cp.stderr = stderr
    return cp


def test_verify_model_success():
    mi = ModelInstaller(data_dir="data")
    show_json = json.dumps({"digest": "sha256:abc123"})
    with patch("subprocess.run") as run:
        run.return_value = _completed_proc(stdout=show_json, returncode=0)
        assert mi._verify_model("gemma2:9b-instruct") is True


def test_verify_model_failure_missing_digest():
    mi = ModelInstaller(data_dir="data")
    show_json = json.dumps({"name": "gemma2:9b-instruct"})
    with patch("subprocess.run") as run:
        run.return_value = _completed_proc(stdout=show_json, returncode=0)
        assert mi._verify_model("gemma2:9b-instruct") is False


def test_download_model_calls_verify_success_progress_off():
    mi = ModelInstaller(data_dir="data")
    with patch("subprocess.run") as run:
        # First call: pull
        pull_proc = _completed_proc(returncode=0)
        # Second call: show json
        show_json = json.dumps({"digest": "sha256:abc123"})
        show_proc = _completed_proc(stdout=show_json, returncode=0)
        run.side_effect = [pull_proc, show_proc]
        assert mi._download_model("gemma2:9b-instruct", use_progress=False) is True


def test_download_model_retry_parallel_result():
    mi = ModelInstaller(data_dir="data")
    # Simulate one failure in parallel executor
    with patch.object(mi, "_download_model", side_effect=[False]):
        results = mi._download_models_parallel(["gemma2:9b-instruct"], max_workers=1)
        assert results["gemma2:9b-instruct"] is False
        assert results["gemma2:9b-instruct"] is False
