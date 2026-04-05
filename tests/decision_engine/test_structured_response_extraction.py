"""Tests for structured response extraction and judge path robustness.

Covers the fix for the malformed structured-response fallback bug where
the judge path consistently fell back to HOLD/50 instead of parsing
valid LLM responses.
"""
import json

import pytest

from finance_feedback_engine.decision_engine.decision_validation import (
    _normalize_single_quotes,
    _strip_trailing_commas,
    extract_json_from_text,
    try_parse_decision_json,
)


class TestExtractJsonFromText:
    """Tests for extract_json_from_text helper."""

    def test_plain_json(self):
        text = '{"action": "HOLD", "confidence": 50}'
        assert extract_json_from_text(text) == text.strip()

    def test_json_with_think_tags(self):
        text = '<think>\nLet me analyze this...\n</think>\n{"action": "HOLD", "confidence": 50}'
        result = extract_json_from_text(text)
        assert '"action": "HOLD"' in result
        assert "<think>" not in result

    def test_json_with_markdown_fences(self):
        text = '```json\n{"action": "HOLD", "confidence": 50}\n```'
        result = extract_json_from_text(text)
        assert '"action": "HOLD"' in result
        assert "```" not in result

    def test_json_with_preamble(self):
        text = 'Here is my analysis:\n{"action": "HOLD", "confidence": 50, "reasoning": "test", "amount": 0.1}'
        result = extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["action"] == "HOLD"

    def test_empty_text(self):
        assert extract_json_from_text("") == ""
        assert extract_json_from_text("   ") == "   "

    def test_no_json(self):
        text = "Just a plain text response with no JSON"
        assert extract_json_from_text(text) == text

    def test_nested_json(self):
        text = '{"action": "HOLD", "reasoning": {"thesis": "neither", "basis": "test"}}'
        result = extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["reasoning"]["thesis"] == "neither"

    def test_truncated_json(self):
        """Truncated JSON without closing brace returns original text."""
        text = '{"action": "HOLD", "confidence": 50'
        result = extract_json_from_text(text)
        # No matching close brace, returns original
        assert result == text

    def test_json_with_strings_containing_braces(self):
        text = '{"action": "HOLD", "reasoning": "price is in range {82000-84000}"}'
        result = extract_json_from_text(text)
        parsed = json.loads(result)
        assert "82000-84000" in parsed["reasoning"]


class TestTryParseDecisionJsonRobust:
    """Tests for try_parse_decision_json with edge cases from judge path."""

    def test_valid_json_string_reasoning(self):
        payload = json.dumps({
            "action": "HOLD",
            "confidence": 50,
            "reasoning": "Market is ranging",
            "amount": 0.1,
        })
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["action"] == "HOLD"

    def test_valid_json_dict_reasoning(self):
        """Judge path: deepseek-r1 often returns reasoning as dict."""
        payload = json.dumps({
            "action": "HOLD",
            "confidence": 50,
            "reasoning": {
                "Winning Thesis": "neither",
                "Decision Basis": "RSI neutral",
            },
            "amount": 0,
        })
        result = try_parse_decision_json(payload)
        assert result is not None
        assert "Winning Thesis: neither" in result["reasoning"]

    def test_empty_dict_reasoning_gets_fallback(self):
        """Empty dict reasoning normalizes to empty string; fix adds fallback."""
        payload = json.dumps({
            "action": "HOLD",
            "confidence": 50,
            "reasoning": {},
            "amount": 0,
        })
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["reasoning"]  # non-empty after fallback

    def test_string_confidence_coerced_to_int(self):
        payload = json.dumps({
            "action": "HOLD",
            "confidence": "75",
            "reasoning": "test",
            "amount": 0,
        })
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["confidence"] == 75
        assert isinstance(result["confidence"], int)

    def test_word_confidence_defaults_to_50(self):
        payload = json.dumps({
            "action": "HOLD",
            "confidence": "medium",
            "reasoning": "test",
            "amount": 0,
        })
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["confidence"] == 50

    def test_float_confidence_coerced(self):
        payload = json.dumps({
            "action": "HOLD",
            "confidence": 72.5,
            "reasoning": "test",
            "amount": 0,
        })
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["confidence"] == 72

    def test_think_tags_stripped(self):
        """deepseek-r1 may include <think> blocks before JSON."""
        payload = "<think>\nLet me think about this...\n</think>\n" + json.dumps({
            "action": "HOLD",
            "confidence": 60,
            "reasoning": "Market analysis complete",
            "amount": 0,
        })
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["action"] == "HOLD"
        assert result["confidence"] == 60

    def test_markdown_fenced_json(self):
        payload = "```json\n" + json.dumps({
            "action": "HOLD",
            "confidence": 55,
            "reasoning": "Ranging market",
            "amount": 0,
        }) + "\n```"
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["action"] == "HOLD"

    def test_missing_reasoning_gets_synthetic_fallback(self):
        """Missing reasoning gets a synthetic fallback string."""
        payload = json.dumps({
            "action": "HOLD",
            "confidence": 50,
            "amount": 0,
        })
        result = try_parse_decision_json(payload)
        assert result is not None
        assert "reasoning not provided" in result["reasoning"]

    def test_policy_actions_preserved(self):
        payload = json.dumps({
            "action": "CLOSE_LONG",
            "confidence": 85,
            "reasoning": "Strong bearish signal",
            "amount": 0.5,
        })
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["action"] == "CLOSE_LONG"



class TestFenceNestedJson:
    """Regression: fence regex was non-greedy, truncating nested objects."""

    def test_nested_json_in_markdown_fences(self):
        text = '```json\n{"action": "HOLD", "confidence": 50, "reasoning": {"thesis": "neither", "basis": "RSI neutral"}, "amount": 0}\n```'
        result = extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["reasoning"]["thesis"] == "neither"
        assert parsed["amount"] == 0

    def test_deeply_nested_json_in_fences(self):
        text = '```json\n{"action": "HOLD", "confidence": 50, "reasoning": {"a": {"b": {"c": "deep"}}}, "amount": 0}\n```'
        result = extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["reasoning"]["a"]["b"]["c"] == "deep"


class TestTrailingCommas:
    """LLMs frequently emit trailing commas in JSON."""

    def test_trailing_comma_before_close_brace(self):
        result = _strip_trailing_commas('{"action": "HOLD", "confidence": 50,}')
        parsed = json.loads(result)
        assert parsed["action"] == "HOLD"

    def test_trailing_comma_before_close_bracket(self):
        result = _strip_trailing_commas('["a", "b",]')
        parsed = json.loads(result)
        assert parsed == ["a", "b"]

    def test_trailing_comma_with_whitespace(self):
        result = _strip_trailing_commas('{"action": "HOLD" ,  }')
        parsed = json.loads(result)
        assert parsed["action"] == "HOLD"

    def test_no_trailing_comma_unchanged(self):
        text = '{"action": "HOLD"}'
        assert _strip_trailing_commas(text) == text

    def test_full_decision_with_trailing_comma(self):
        payload = '{"action": "HOLD", "confidence": 50, "reasoning": "test", "amount": 0,}'
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["action"] == "HOLD"


class TestSingleQuoteNormalization:
    """LLMs sometimes emit Python dict syntax instead of JSON."""

    def test_single_quoted_keys_and_values(self):
        text = "{'action': 'HOLD', 'confidence': 50, 'reasoning': 'test', 'amount': 0}"
        result = _normalize_single_quotes(text)
        parsed = json.loads(result)
        assert parsed["action"] == "HOLD"

    def test_mixed_quotes_not_converted(self):
        """If double-quoted keys already exist, leave text alone."""
        text = '{"action": "HOLD", ' + "'extra': 'val'}"
        result = _normalize_single_quotes(text)
        # Should not convert since double-quoted keys already present
        assert result == text

    def test_full_decision_with_single_quotes(self):
        payload = "{'action': 'HOLD', 'confidence': 50, 'reasoning': 'market ranging', 'amount': 0}"
        result = try_parse_decision_json(payload)
        assert result is not None
        assert result["action"] == "HOLD"


class TestUnclosedThinkTags:
    """Token limit may cut off mid-<think> block."""

    def test_unclosed_think_tag(self):
        text = '<think>\nLet me analyze the market conditions...\nThe RSI is at 45 which suggests\n{"action": "HOLD", "confidence": 50, "reasoning": "test", "amount": 0}'
        # The unclosed think tag should strip everything from <think> onward,
        # but the JSON is inside the think block, so it gets stripped too.
        # This is correct behavior -- unclosed think means the model didn't
        # finish reasoning, so the JSON (if any) is unreliable.
        result = extract_json_from_text(text)
        # With unclosed think stripped, no JSON remains -> returns original
        assert result == text

    def test_closed_think_then_json(self):
        text = '<think>\nAnalyzing...\n</think>\n{"action": "HOLD", "confidence": 50, "reasoning": "done", "amount": 0}'
        result = extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["action"] == "HOLD"

    def test_unclosed_think_after_json(self):
        """JSON before unclosed think is recoverable."""
        text = '{"action": "HOLD", "confidence": 50, "reasoning": "test", "amount": 0}\n<think>\nLet me reconsider...'
        result = extract_json_from_text(text)
        parsed = json.loads(result)
        assert parsed["action"] == "HOLD"


class TestCombinedEdgeCases:
    """Integration tests combining multiple salvage scenarios."""

    def test_think_tags_plus_fenced_nested_json(self):
        text = (
            '<think>\nI should analyze...\n</think>\n'
            '```json\n{"action": "HOLD", "confidence": 60, '
            '"reasoning": {"thesis": "neutral"}, "amount": 0}\n```'
        )
        result = try_parse_decision_json(text)
        assert result is not None
        assert result["action"] == "HOLD"
        assert result["confidence"] == 60

    def test_preamble_plus_trailing_comma(self):
        text = 'Based on my analysis:\n{"action": "HOLD", "confidence": 55, "reasoning": "ranging", "amount": 0.1,}'
        result = try_parse_decision_json(text)
        assert result is not None
        assert result["action"] == "HOLD"

    def test_single_quotes_plus_trailing_comma(self):
        text = "{'action': 'HOLD', 'confidence': 50, 'reasoning': 'test', 'amount': 0,}"
        result = try_parse_decision_json(text)
        assert result is not None
        assert result["action"] == "HOLD"
