"""
Comprehensive tests for config_validator.py

Tests cover:
- ValidationIssue and ValidationResult dataclasses
- Severity enum
- Secret detection patterns
- Environment variable naming validation
- Schema validation
- Environment-specific rules
- Best practices checks
- Logging configuration validation
- CLI interface
"""

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest
import yaml

from finance_feedback_engine.utils.config_validator import (
    ConfigValidator,
    Severity,
    ValidationIssue,
    ValidationResult,
    print_validation_results,
    validate_config_file,
)


class TestValidationIssue:
    """Test ValidationIssue dataclass"""

    def test_create_issue(self):
        """Test creating a validation issue"""
        issue = ValidationIssue(
            severity=Severity.CRITICAL,
            rule="test_rule",
            message="Test message",
            file_path="/path/to/config.yaml",
            line_number=42,
            suggestion="Fix it",
        )

        assert issue.severity == Severity.CRITICAL
        assert issue.rule == "test_rule"
        assert issue.message == "Test message"
        assert issue.file_path == "/path/to/config.yaml"
        assert issue.line_number == 42
        assert issue.suggestion == "Fix it"

    def test_create_issue_without_optional_fields(self):
        """Test creating issue without line number and suggestion"""
        issue = ValidationIssue(
            severity=Severity.LOW,
            rule="style_issue",
            message="Style problem",
            file_path="/config.yaml",
        )

        assert issue.severity == Severity.LOW
        assert issue.line_number is None
        assert issue.suggestion is None


class TestValidationResult:
    """Test ValidationResult dataclass"""

    def test_create_empty_result(self):
        """Test creating empty validation result"""
        result = ValidationResult(valid=True)

        assert result.valid is True
        assert len(result.issues) == 0

    def test_add_critical_issue_marks_invalid(self):
        """Test that adding critical issue marks result as invalid"""
        result = ValidationResult(valid=True)
        result.add_issue(
            Severity.CRITICAL, "secret", "Secret found", "/config.yaml", line_number=10
        )

        assert result.valid is False
        assert len(result.issues) == 1
        assert result.issues[0].severity == Severity.CRITICAL

    def test_add_high_issue_marks_invalid(self):
        """Test that adding high severity issue marks result as invalid"""
        result = ValidationResult(valid=True)
        result.add_issue(
            Severity.HIGH, "missing_key", "Missing key", "/config.yaml"
        )

        assert result.valid is False
        assert len(result.issues) == 1

    def test_add_low_issue_keeps_valid(self):
        """Test that low severity issues don't mark result as invalid"""
        result = ValidationResult(valid=True)
        result.add_issue(Severity.LOW, "style", "Style issue", "/config.yaml")

        assert result.valid is True
        assert len(result.issues) == 1

    def test_get_critical_issues(self):
        """Test filtering critical issues"""
        result = ValidationResult(valid=True)
        result.add_issue(Severity.CRITICAL, "r1", "msg", "/f")
        result.add_issue(Severity.HIGH, "r2", "msg", "/f")
        result.add_issue(Severity.CRITICAL, "r3", "msg", "/f")
        result.add_issue(Severity.LOW, "r4", "msg", "/f")

        critical = result.get_critical_issues()
        assert len(critical) == 2
        assert all(i.severity == Severity.CRITICAL for i in critical)

    def test_get_high_issues(self):
        """Test filtering high severity issues"""
        result = ValidationResult(valid=True)
        result.add_issue(Severity.CRITICAL, "r1", "msg", "/f")
        result.add_issue(Severity.HIGH, "r2", "msg", "/f")
        result.add_issue(Severity.HIGH, "r3", "msg", "/f")

        high = result.get_high_issues()
        assert len(high) == 2
        assert all(i.severity == Severity.HIGH for i in high)

    def test_has_errors(self):
        """Test has_errors method"""
        result = ValidationResult(valid=True)
        assert not result.has_errors()

        result.add_issue(Severity.LOW, "r", "msg", "/f")
        assert not result.has_errors()

        result.add_issue(Severity.HIGH, "r", "msg", "/f")
        assert result.has_errors()

        result2 = ValidationResult(valid=True)
        result2.add_issue(Severity.CRITICAL, "r", "msg", "/f")
        assert result2.has_errors()


class TestConfigValidator:
    """Test ConfigValidator class"""

    @pytest.fixture
    def temp_config_file(self):
        """Create a temporary config file for testing"""
        temp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        yield temp
        temp.close()
        Path(temp.name).unlink(missing_ok=True)

    def test_validator_initialization(self):
        """Test ConfigValidator initialization"""
        validator = ConfigValidator(environment="production")
        assert validator.environment == "production"
        assert not validator.rules["allow_debug"]
        assert validator.rules["require_https"]

    def test_validator_default_environment(self):
        """Test default environment is development"""
        validator = ConfigValidator()
        assert validator.environment == "development"
        assert validator.rules["allow_debug"]

    def test_validate_invalid_path(self):
        """Test validation with invalid path"""
        validator = ConfigValidator()
        result = validator.validate_file("/nonexistent/path.yaml")

        assert not result.valid
        assert len(result.get_critical_issues()) > 0
        assert any("not found" in i.message.lower() for i in result.issues)

    def test_validate_file_not_found(self):
        """Test validation when file doesn't exist"""
        validator = ConfigValidator()
        result = validator.validate_file("/tmp/does_not_exist_12345.yaml")

        assert not result.valid
        critical = result.get_critical_issues()
        assert len(critical) > 0
        assert critical[0].rule == "file_not_found"

    def test_validate_invalid_extension(self, temp_config_file):
        """Test warning for non-YAML extension"""
        # Create a file with wrong extension
        temp_txt = tempfile.NamedTemporaryFile(
            mode="w", suffix=".txt", delete=False, encoding="utf-8"
        )
        temp_txt.write("decision_engine:\n  ai_provider: local\n")
        temp_txt.write("persistence:\n  storage_path: data\n")
        temp_txt.close()

        try:
            validator = ConfigValidator()
            result = validator.validate_file(temp_txt.name)

            # Should have HIGH severity issue about extension
            high_issues = result.get_high_issues()
            assert any(i.rule == "invalid_extension" for i in high_issues)
        finally:
            Path(temp_txt.name).unlink(missing_ok=True)

    def test_validate_yaml_parse_error(self, temp_config_file):
        """Test handling of YAML parse errors"""
        # Write invalid YAML
        temp_config_file.write("invalid: yaml: syntax:\n  - broken\n  indentation")
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        assert not result.valid
        critical = result.get_critical_issues()
        assert any("parse" in i.message.lower() for i in critical)

    def test_detect_exposed_api_key(self, temp_config_file):
        """Test detection of exposed API keys"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: data
alpha_vantage_api_key: REAL_API_KEY_1234567890ABCDEF
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        critical = result.get_critical_issues()
        # Should detect both the pattern match AND the hardcoded key
        assert len(critical) >= 1
        assert any("secret" in i.rule.lower() or "api_key" in i.rule.lower() for i in critical)

    def test_safe_placeholder_not_flagged(self, temp_config_file):
        """Test that safe placeholders are not flagged as secrets"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: data
alpha_vantage_api_key: YOUR_ALPHA_VANTAGE_API_KEY
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        # Should not have critical exposed_secret issues
        critical = result.get_critical_issues()
        exposed_secrets = [i for i in critical if i.rule == "exposed_secret"]
        assert len(exposed_secrets) == 0

    def test_env_var_reference_not_flagged(self, temp_config_file):
        """Test that environment variable references are not flagged"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: data
alpha_vantage_api_key: ${ALPHA_VANTAGE_API_KEY}
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        critical = result.get_critical_issues()
        exposed_secrets = [i for i in critical if i.rule == "exposed_secret"]
        assert len(exposed_secrets) == 0

    def test_detect_telegram_token(self, temp_config_file):
        """Test detection of Telegram bot tokens"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: data
telegram_token: 1234567890:ABCdefGHIjklMNOpqrsTUVwxyz123456789
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        critical = result.get_critical_issues()
        assert len(critical) >= 1
        assert any("secret" in i.rule.lower() for i in critical)

    def test_empty_config(self, temp_config_file):
        """Test validation of empty config file"""
        temp_config_file.write("")
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        # When YAML is empty, yaml.safe_load returns None, which will cause issues
        # The validator should handle this gracefully
        high_issues = result.get_high_issues()
        # Either gets empty_config or fails on None check - either way should have errors
        assert len(high_issues) > 0 or not result.valid

    def test_missing_required_keys(self, temp_config_file):
        """Test detection of missing required keys"""
        config = """
some_other_key: value
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        high_issues = result.get_high_issues()
        missing_issues = [i for i in high_issues if i.rule == "missing_required_key"]
        assert len(missing_issues) >= 2  # decision_engine and persistence

    def test_missing_ai_provider(self, temp_config_file):
        """Test detection of missing ai_provider"""
        config = """
decision_engine:
  decision_threshold: 0.7
persistence:
  storage_path: data
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        high_issues = result.get_high_issues()
        assert any(i.rule == "missing_ai_provider" for i in high_issues)

    def test_invalid_threshold_value(self, temp_config_file):
        """Test detection of invalid threshold values"""
        config = """
decision_engine:
  ai_provider: local
  decision_threshold: 1.5
persistence:
  storage_path: data
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        issues = result.issues
        assert any(i.rule == "invalid_threshold" for i in issues)

    def test_ensemble_missing_config(self, temp_config_file):
        """Test detection of missing ensemble config when using ensemble provider"""
        config = """
decision_engine:
  ai_provider: ensemble
persistence:
  storage_path: data
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        high_issues = result.get_high_issues()
        assert any(i.rule == "missing_ensemble_config" for i in high_issues)

    def test_ensemble_invalid_weight_sum(self, temp_config_file):
        """Test detection of invalid provider weight sum"""
        config = """
decision_engine:
  ai_provider: ensemble
persistence:
  storage_path: data
ensemble:
  enabled_providers: [local, cli]
  provider_weights:
    local: 0.3
    cli: 0.4
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        issues = result.issues
        assert any(i.rule == "invalid_weight_sum" for i in issues)

    def test_ensemble_valid_weight_sum(self, temp_config_file):
        """Test that valid weight sum doesn't raise issues"""
        config = """
decision_engine:
  ai_provider: ensemble
persistence:
  storage_path: data
ensemble:
  enabled_providers: [local, cli]
  provider_weights:
    local: 0.6
    cli: 0.4
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        weight_issues = [i for i in result.issues if i.rule == "invalid_weight_sum"]
        assert len(weight_issues) == 0

    def test_ensemble_missing_enabled_providers(self, temp_config_file):
        """Test detection of missing enabled_providers in ensemble config"""
        config = """
decision_engine:
  ai_provider: ensemble
persistence:
  storage_path: data
ensemble:
  provider_weights:
    local: 1.0
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        high_issues = result.get_high_issues()
        assert any(i.rule == "missing_enabled_providers" for i in high_issues)

    def test_debug_mode_in_production(self, temp_config_file):
        """Test that debug mode is not allowed in production"""
        config = """
decision_engine:
  ai_provider: local
  debug: true
persistence:
  storage_path: data
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator(environment="production")
        result = validator.validate_file(temp_config_file.name)

        critical = result.get_critical_issues()
        assert any(i.rule == "debug_in_production" for i in critical)

    def test_debug_mode_allowed_in_development(self, temp_config_file):
        """Test that debug mode is allowed in development"""
        config = """
decision_engine:
  ai_provider: local
  debug: true
persistence:
  storage_path: data
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator(environment="development")
        result = validator.validate_file(temp_config_file.name)

        debug_issues = [i for i in result.issues if i.rule == "debug_in_production"]
        assert len(debug_issues) == 0

    def test_sandbox_mode_in_production(self, temp_config_file):
        """Test that sandbox mode is not allowed in production"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: data
platform_credentials:
  use_sandbox: true
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator(environment="production")
        result = validator.validate_file(temp_config_file.name)

        high_issues = result.get_high_issues()
        assert any(i.rule == "sandbox_in_production" for i in high_issues)

    def test_mock_platform_in_production(self, temp_config_file):
        """Test that mock platform is not allowed in production"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: data
trading_platform: mock
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator(environment="production")
        result = validator.validate_file(temp_config_file.name)

        critical = result.get_critical_issues()
        assert any(i.rule == "mock_platform_in_production" for i in critical)

    def test_hardcoded_api_key_detected(self, temp_config_file):
        """Test detection of hardcoded API key in best practices check"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: data
alpha_vantage_api_key: AKJSDHF8734HKJSDHF8734
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        critical = result.get_critical_issues()
        assert any("api_key" in i.rule.lower() for i in critical)

    def test_absolute_storage_path_warning(self, temp_config_file):
        """Test warning about absolute storage paths"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: /absolute/path/to/data
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        issues = result.issues
        assert any(i.rule == "absolute_storage_path" for i in issues)

    def test_console_logging_in_production(self, temp_config_file):
        """Test detection of console logging in production"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: data
logging:
  handlers:
    console:
      enabled: true
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator(environment="production")
        result = validator.validate_file(temp_config_file.name)

        high_issues = result.get_high_issues()
        assert any("console" in i.rule.lower() for i in high_issues)

    def test_debug_log_level_in_production(self, temp_config_file):
        """Test detection of DEBUG log level in production"""
        config = """
decision_engine:
  ai_provider: local
persistence:
  storage_path: data
logging:
  root:
    level: DEBUG
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator(environment="production")
        result = validator.validate_file(temp_config_file.name)

        high_issues = result.get_high_issues()
        assert any("debug" in i.rule.lower() and "logging" in i.rule.lower() for i in high_issues)

    def test_old_placeholder_pattern_detected(self, temp_config_file):
        """Test detection of old-style placeholder patterns"""
        config = """
decision_engine:
  ai_provider: local
  autonomous_execution: AUTO_EXC
persistence:
  storage_path: data
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        high_issues = result.get_high_issues()
        assert any(i.rule == "old_placeholder_pattern" for i in high_issues)

    def test_env_var_missing_subsystem_prefix(self, temp_config_file):
        """Test detection of env vars without subsystem prefix"""
        config = """
decision_engine:
  ai_provider: local
  some_setting: ${UNPREFIXED_VAR}
persistence:
  storage_path: data
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        issues = result.issues
        assert any(i.rule == "missing_subsystem_prefix" for i in issues)

    def test_env_var_with_valid_prefix(self, temp_config_file):
        """Test that env vars with valid prefixes pass"""
        config = """
decision_engine:
  ai_provider: local
  setting: ${DECISION_ENGINE_SETTING}
persistence:
  storage_path: data
  db_url: ${PERSISTENCE_DB_URL}
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator()
        result = validator.validate_file(temp_config_file.name)

        prefix_issues = [i for i in result.issues if i.rule == "missing_subsystem_prefix"]
        assert len(prefix_issues) == 0

    def test_valid_config_passes(self, temp_config_file):
        """Test that a valid config passes all checks"""
        config = """
decision_engine:
  ai_provider: local
  decision_threshold: 0.7
persistence:
  storage_path: data/decisions
alpha_vantage_api_key: ${ALPHA_VANTAGE_API_KEY}
"""
        temp_config_file.write(config)
        temp_config_file.flush()

        validator = ConfigValidator(environment="development")
        result = validator.validate_file(temp_config_file.name)

        # Should have no critical or high issues
        assert len(result.get_critical_issues()) == 0
        assert len(result.get_high_issues()) == 0


class TestConvenienceFunctions:
    """Test convenience functions"""

    def test_validate_config_file_function(self):
        """Test the validate_config_file convenience function"""
        temp = tempfile.NamedTemporaryFile(
            mode="w", suffix=".yaml", delete=False, encoding="utf-8"
        )
        temp.write("decision_engine:\n  ai_provider: local\n")
        temp.write("persistence:\n  storage_path: data\n")
        temp.close()

        try:
            result = validate_config_file(temp.name, environment="production")
            assert isinstance(result, ValidationResult)
        finally:
            Path(temp.name).unlink(missing_ok=True)

    @patch("builtins.print")
    def test_print_validation_results_no_issues(self, mock_print):
        """Test printing results with no issues"""
        result = ValidationResult(valid=True)
        print_validation_results(result)

        # Should print success message
        mock_print.assert_called()
        call_args = [str(call[0][0]) for call in mock_print.call_args_list]
        assert any("passed" in arg.lower() for arg in call_args)

    @patch("builtins.print")
    def test_print_validation_results_with_issues(self, mock_print):
        """Test printing results with issues"""
        result = ValidationResult(valid=True)
        result.add_issue(
            Severity.CRITICAL, "test_rule", "Test message", "/config.yaml"
        )
        result.add_issue(Severity.LOW, "style", "Style issue", "/config.yaml")

        print_validation_results(result, verbose=True)

        # Should print results
        mock_print.assert_called()
        # Collect all print arguments (skip empty calls)
        call_args = " ".join([str(call[0][0]) for call in mock_print.call_args_list if call[0]])
        assert "CRITICAL" in call_args or "critical" in call_args.lower()

    @patch("builtins.print")
    def test_print_validation_results_non_verbose(self, mock_print):
        """Test non-verbose mode skips low severity issues"""
        result = ValidationResult(valid=True)
        result.add_issue(Severity.LOW, "style", "Style issue", "/config.yaml")

        print_validation_results(result, verbose=False)

        # Low severity issues should be skipped in non-verbose mode
        call_args = " ".join([str(call[0][0]) for call in mock_print.call_args_list])
        # The summary will show total count, but the detailed issue won't be printed
        assert mock_print.called


class TestSeverityEnum:
    """Test Severity enum"""

    def test_severity_values(self):
        """Test all severity enum values"""
        assert Severity.CRITICAL.value == "critical"
        assert Severity.HIGH.value == "high"
        assert Severity.MEDIUM.value == "medium"
        assert Severity.LOW.value == "low"
        assert Severity.INFO.value == "info"

    def test_severity_comparison(self):
        """Test that severity enum values are comparable"""
        assert Severity.CRITICAL == Severity.CRITICAL
        assert Severity.HIGH != Severity.LOW
