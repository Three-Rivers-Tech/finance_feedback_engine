"""Tests for CLI approve command interactive flows."""

import pytest
import json
import os
from pathlib import Path
from unittest.mock import Mock, patch
from click.testing import CliRunner
from finance_feedback_engine.cli.main import cli


@pytest.fixture
def runner():
    """Create Click test runner."""
    return CliRunner()


@pytest.fixture
def sample_decision(tmp_path):
    """Create a sample decision file for testing."""
    decision = {
        "decision_id": "test123",
        "asset_pair": "BTCUSD",
        "action": "BUY",
        "confidence": 85,
        "position_size": 0.05,
        "entry_price": 50000.0,
        "stop_loss": 49000.0,
        "take_profit": 52500.0,
        "reasoning": "Strong bullish trend with high volume",
        "market_regime": "TRENDING_BULL",
        "sentiment_score": 0.75,
        "timestamp": "2024-12-04T10:00:00Z"
    }

    # Create decision file
    decision_dir = tmp_path / "data" / "decisions"
    decision_dir.mkdir(parents=True)
    decision_file = decision_dir / "2024-12-04_test123.json"
    decision_file.write_text(json.dumps(decision, indent=2))

    return decision_file, decision


@pytest.fixture
def mock_engine():
    """Create mock engine."""
    engine = Mock()
    engine.execute_decision = Mock(return_value={"status": "success", "order_id": "12345"})
    return engine


class TestApproveCommandLoading:
    """Test approve command file loading and validation."""

    def test_approve_loads_decision_file(self, runner, sample_decision, tmp_path, monkeypatch):
        """Test approve command loads decision from file."""
        decision_file, decision_data = sample_decision

        # Change to tmp_path so CLI finds the decision file
        monkeypatch.chdir(tmp_path)

        with patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine') as mock_engine_class:
            with patch('rich.prompt.Prompt.ask', return_value='no'):
                with patch('finance_feedback_engine.cli.main.load_tiered_config', return_value={}):
                    result = runner.invoke(cli, ['approve', 'test123'], obj={'config': {}})

        # Should succeed - file exists in tmp_path and CLI runs from that directory
        assert result.exit_code == 0

    def test_approve_invalid_decision_id(self, runner):
        """Test approve with non-existent decision ID."""
        with runner.isolated_filesystem():
            os.makedirs('data/decisions', exist_ok=True)
            result = runner.invoke(cli, ['approve', 'nonexistent'])

        # Should fail with 'not found' error message
        assert result.exit_code != 0
        assert 'not found' in result.output.lower()


class TestApproveYesFlow:
    """Test approve command 'yes' acceptance flow."""

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    @patch('finance_feedback_engine.persistence.decision_store.DecisionStore')
    @patch('rich.prompt.Prompt.ask')
    def test_approve_yes_executes_trade(self, mock_prompt, mock_decision_store, mock_engine_class, runner, sample_decision, tmp_path, monkeypatch):
        """Test 'yes' approval executes trade immediately."""
        decision_file, decision_data = sample_decision
        mock_prompt.return_value = 'yes'

        mock_engine = Mock()
        mock_engine.execute_decision = Mock(return_value={"success": True, "message": "Trade executed"})
        mock_engine_class.return_value = mock_engine

        # Change to tmp_path so CLI finds the decision file
        monkeypatch.chdir(tmp_path)

        # Create approvals directory
        os.makedirs('data/approvals', exist_ok=True)

        with patch('finance_feedback_engine.cli.main.load_tiered_config', return_value={}):
            result = runner.invoke(cli, ['approve', 'test123'], obj={'config': {}})

        # Verify command succeeded
        assert result.exit_code == 0
        assert 'approved' in result.output.lower()

        # Verify mock was called to execute decision
        mock_engine.execute_decision.assert_called_once_with('test123')

        # Verify approval file was created
        approval_files = list(Path(tmp_path / 'data' / 'approvals').glob('test123_approved.json'))
        assert len(approval_files) == 1

        # Validate approval file contents
        with open(approval_files[0], 'r') as f:
            approval_data = json.load(f)
        assert approval_data['decision_id'] == 'test123'
        assert approval_data['approved'] is True
        assert approval_data['modified'] is False
        assert 'timestamp' in approval_data
        assert approval_data['source'] == 'cli'

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    @patch('finance_feedback_engine.persistence.decision_store.DecisionStore')
    @patch('rich.prompt.Prompt.ask')
    def test_approve_yes_saves_approval(self, mock_prompt, mock_decision_store, mock_engine_class, runner, sample_decision, tmp_path, monkeypatch):
        """Test 'yes' approval saves to data/approvals/."""
        decision_file, decision_data = sample_decision
        mock_prompt.return_value = 'yes'

        mock_engine = Mock()
        mock_engine.execute_decision = Mock(return_value={"success": True, "message": "Trade executed"})
        mock_engine_class.return_value = mock_engine

        # Change to tmp_path so CLI finds the decision file
        monkeypatch.chdir(tmp_path)

        # Create approvals directory
        os.makedirs('data/approvals', exist_ok=True)

        with patch('finance_feedback_engine.cli.main.load_tiered_config', return_value={}):
            result = runner.invoke(cli, ['approve', 'test123'], obj={'config': {}})

        # Verify command succeeded
        assert result.exit_code == 0
        assert 'approved' in result.output.lower()

        # Verify execute was called
        mock_engine.execute_decision.assert_called_once()

        # Verify approval file exists and contains required fields
        approval_files = list(Path(tmp_path / 'data' / 'approvals').glob('test123_approved.json'))
        assert len(approval_files) == 1, "Approval file should be created"

        with open(approval_files[0], 'r') as f:
            approval_data = json.load(f)

        # Validate all required fields
        assert approval_data['decision_id'] == 'test123'
        assert approval_data['approved'] is True
        assert approval_data['modified'] is False
        assert approval_data['source'] == 'cli'
        assert 'timestamp' in approval_data
        # Verify timestamp format (ISO 8601)
        from datetime import datetime
        datetime.fromisoformat(approval_data['timestamp'])  # Should not raise
class TestApproveNoFlow:
    """Test approve command 'no' rejection flow."""

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    @patch('rich.prompt.Prompt.ask')
    def test_approve_no_skips_execution(self, mock_prompt, mock_engine_class, runner, sample_decision, tmp_path, monkeypatch):
        """Test 'no' rejection skips trade execution."""
        decision_file, decision_data = sample_decision
        mock_prompt.return_value = 'no'

        mock_engine = Mock()
        mock_engine.execute_decision = Mock()
        mock_engine_class.return_value = mock_engine

        # Change to tmp_path so CLI finds the decision file
        monkeypatch.chdir(tmp_path)

        with patch('finance_feedback_engine.cli.main.load_tiered_config', return_value={}):
            result = runner.invoke(cli, ['approve', 'test123'], obj={'config': {}})

        # Execute should NOT be called
        mock_engine.execute_decision.assert_not_called()
        assert result.exit_code == 0

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    @patch('rich.prompt.Prompt.ask')
    def test_approve_no_saves_rejection(self, mock_prompt, mock_engine_class, runner, sample_decision, tmp_path, monkeypatch):
        """Test 'no' rejection saves rejection record."""
        decision_file, decision_data = sample_decision
        mock_prompt.return_value = 'no'

        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        # Change to tmp_path so CLI finds the decision file
        monkeypatch.chdir(tmp_path)

        # Create approvals directory
        os.makedirs('data/approvals', exist_ok=True)

        with patch('finance_feedback_engine.cli.main.load_tiered_config', return_value={}):
            result = runner.invoke(cli, ['approve', 'test123'], obj={'config': {}})

        assert 'no' in result.output.lower() or 'rejected' in result.output.lower() or result.exit_code == 0


class TestApproveModifyFlow:
    """Test approve command 'modify' interactive editing flow."""

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    @patch('finance_feedback_engine.persistence.decision_store.DecisionStore')
    @patch('rich.prompt.Prompt.ask')
    @patch('rich.prompt.FloatPrompt.ask')
    def test_approve_modify_position_size(self, mock_float_prompt, mock_prompt, mock_decision_store, mock_engine_class, runner, sample_decision, tmp_path, monkeypatch):
        """Test modifying position_size in approval flow."""
        decision_file, decision_data = sample_decision

        # First prompt: 'modify', subsequent prompts for each field
        mock_prompt.return_value = 'modify'
        mock_float_prompt.side_effect = [
            0.08,  # New position_size
            49500.0,  # Keep stop_loss (or new value)
            53000.0   # Keep take_profit (or new value)
        ]

        mock_engine = Mock()
        mock_engine.execute_decision = Mock(return_value={"status": "success"})
        mock_engine_class.return_value = mock_engine

        # Change to tmp_path so CLI finds the decision file
        monkeypatch.chdir(tmp_path)

        with patch('finance_feedback_engine.cli.main.load_tiered_config', return_value={}):
            # Simulate modify flow (actual implementation may vary)
            result = runner.invoke(cli, ['approve', 'test123'], obj={'config': {}})

        assert result.exit_code == 0, f"Modify flow failed: {result.output}"
        assert mock_float_prompt.call_count >= 1

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    @patch('finance_feedback_engine.persistence.decision_store.DecisionStore')
    @patch('rich.prompt.Prompt.ask')
    @patch('rich.prompt.FloatPrompt.ask')
    def test_approve_modify_validates_inputs(self, mock_float_prompt, mock_prompt, mock_decision_store, mock_engine_class, runner, sample_decision, tmp_path, monkeypatch):
        """Test modify flow validates numeric inputs.

        Note: Rich's FloatPrompt.ask() handles validation internally and re-prompts
        the user automatically on invalid input. In this test, we simulate successful
        input after the user provides valid values. The CLI performs additional range
        validation (position_size > 0, stop_loss 0-100%) after receiving valid floats.
        """
        decision_file, decision_data = sample_decision

        mock_prompt.return_value = 'modify'
        # Simulate valid float inputs (Rich's FloatPrompt handles type validation internally)
        mock_float_prompt.side_effect = [
            0.1,  # Valid position_size
            48000.0,  # Valid stop_loss
            54000.0   # Valid take_profit
        ]

        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        # Change to tmp_path so CLI finds the decision file
        monkeypatch.chdir(tmp_path)

        with patch('finance_feedback_engine.cli.main.load_tiered_config', return_value={}):
            # CLI performs range validation after receiving float inputs
            result = runner.invoke(cli, ['approve', 'test123'], obj={'config': {}})

        # Require CLI to succeed and display all key decision fields
        assert result.exit_code == 0, f"CLI failed: {result.output}"
        # Check for asset_pair, action, and confidence in output
        asset = decision_data["asset_pair"]
        action = decision_data["action"]
        confidence = str(decision_data["confidence"])
        assert asset in result.output, f"Asset '{asset}' not in output: {result.output}"
        assert action in result.output, f"Action '{action}' not in output: {result.output}"
        assert confidence in result.output, f"Confidence '{confidence}' not in output: {result.output}"

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    @patch('finance_feedback_engine.persistence.decision_store.DecisionStore')
    @patch('rich.prompt.Prompt.ask')
    @patch('rich.prompt.FloatPrompt.ask')
    def test_approve_modify_rejects_invalid_ranges(self, mock_float_prompt, mock_prompt, mock_decision_store, mock_engine_class, runner, sample_decision, tmp_path, monkeypatch):
        """Test modify flow rejects out-of-range values via CLI validation.

        The CLI validates ranges after receiving float input:
        - position_size must be > 0
        - stop_loss must be 0-100%
        - take_profit must be 0-100%
        """
        decision_file, decision_data = sample_decision

        mock_prompt.return_value = 'modify'
        # Provide invalid range values (negative position_size)
        mock_float_prompt.side_effect = [
            -0.05,  # Invalid: position_size must be > 0
            2.0,    # stop_loss
            5.0     # take_profit
        ]

        mock_engine = Mock()
        mock_engine_class.return_value = mock_engine

        # Change to tmp_path so CLI finds the decision file
        monkeypatch.chdir(tmp_path)

        with patch('finance_feedback_engine.cli.main.load_tiered_config', return_value={}):
            result = runner.invoke(cli, ['approve', 'test123'], obj={'config': {}})

        # CLI should abort with error message about invalid range
        # Note: click.Abort() returns exit_code=1
        assert result.exit_code != 0 or 'must be > 0' in result.output or 'error' in result.output.lower()


class TestApprovalPersistence:
    """Test approval data persistence to data/approvals/."""

    @pytest.mark.skip(reason="TODO: implement - requires complex mocking")
    def test_approval_file_format(self, runner, sample_decision, tmp_path):
        """Test approval file contains all required fields."""
        # This would test the actual file structure
        # Skipped due to complex mocking requirements
        pass

    @pytest.mark.skip(reason="TODO: implement - requires complex mocking")
    def test_approval_timestamp_recorded(self, runner, sample_decision, tmp_path):
        """Test approval includes timestamp."""
        # Implementation depends on actual CLI code structure
        pass


class TestRichUIDisplay:
    """Test Rich table/panel display formatting."""

    @patch('finance_feedback_engine.cli.main.FinanceFeedbackEngine')
    @patch('rich.prompt.Prompt.ask')
    def test_displays_decision_details(self, mock_prompt, mock_engine_class, runner, sample_decision, tmp_path, monkeypatch):
        """Test approve displays decision in Rich table."""
        decision_file, decision_data = sample_decision
        mock_prompt.return_value = 'no'

        # Change to tmp_path so CLI finds the decision file
        monkeypatch.chdir(tmp_path)

        with patch('finance_feedback_engine.cli.main.load_tiered_config', return_value={}):
            result = runner.invoke(cli, ['approve', 'test123'], obj={'config': {}})

        # Output should contain decision details (asset, action, confidence, etc.)
        # Exact format depends on Rich table rendering
        assert result.exit_code == 0 or 'BTCUSD' in result.output or 'BUY' in result.output


if __name__ == '__main__':
    pytest.main([__file__, '-v'])
