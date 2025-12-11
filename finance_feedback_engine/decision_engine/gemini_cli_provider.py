"""Gemini CLI provider for decision engine.

Free Google Gemini CLI integration for trading decisions.
Requires Node.js v20+ and OAuth or API key authentication.
Free tier: 60 requests/min, 1000 requests/day (OAuth)
         100 requests/day (API key)
"""

from typing import Dict, Any
import logging
import subprocess
import json
import re
from .decision_validation import (
    try_parse_decision_json,
    build_fallback_decision,
)
from ..utils.rate_limiter import RateLimiter

logger = logging.getLogger(__name__)


class GeminiCLIProvider:
    """
    Gemini CLI provider for generating trading decisions.
    
    Uses the free Google Gemini CLI tool (requires Node.js v20+).
    Supports OAuth (60 req/min) or API key (100 req/day) authentication.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Gemini CLI provider.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        # Determine rate limiter based on authentication mode
        auth_mode = self.config.get('auth_mode', 'oauth')
        if auth_mode == 'api_key':
            tokens_per_second = 100 / (24 * 3600)
            max_tokens = 100
        else:  # oauth or default
            tokens_per_second = 1.0
            max_tokens = 60  # Allow short bursts but prevent daily quota exhaustion

        self.rate_limiter = RateLimiter(
            tokens_per_second=tokens_per_second,
            max_tokens=max_tokens
        )

        logger.info("Gemini CLI provider initialized")
        
        # Verify gemini is available
        self._verify_gemini_available()

    def _verify_gemini_available(self) -> bool:
        """Check that 'gemini' binary exists and is functional."""
        try:
            result = subprocess.run(
                ['gemini', '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                logger.info("Gemini CLI available: %s", result.stdout.strip())
                return True
            raise ValueError("Gemini CLI returned non-zero exit code")
        except FileNotFoundError as exc:
            raise ValueError(
                "'gemini' binary not found. Install Gemini CLI: "
                "npm install -g @google/gemini-cli "
                "(requires Node.js v20+). "
                "See https://github.com/google-gemini/gemini-cli"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Timeout verifying Gemini CLI") from exc

    def query(self, prompt: str) -> Dict[str, Any]:
        """
        Query Gemini CLI for a trading decision.

        Args:
            prompt: Trading analysis prompt

        Returns:
            Dictionary with action, confidence, reasoning, amount
        """
        # Wait for rate limit token
        try:
            self.rate_limiter.wait_for_token()
        except Exception as e:
            logger.warning(f"Rate limit check failed: {e}")
            # Continue anyway - rate limiter is best-effort
        
        logger.info("Querying Gemini CLI for trading decision")

        formatted_prompt = self._format_prompt_for_gemini(prompt)

        try:
            # Use 'gemini' command in non-interactive mode with JSON output
            # -p flag for prompt, --output-format json for structured output
            result = subprocess.run(
                ['gemini', '-p', formatted_prompt, '--output-format', 'json'],
                capture_output=True,
                text=True,
                timeout=60,  # Gemini might take longer for complex queries
                check=False
            )
            
            if result.returncode != 0:
                logger.warning(
                    "Gemini CLI failed: %s",
                    result.stderr.strip()
                )
                return self._fallback_decision()
            
            output = result.stdout.strip()
            
            # Try JSON parse first
            # (output-format json returns structured data)
            parsed = self._parse_gemini_response(output)
            if parsed:
                return parsed
            
            # Fallback to text extraction if output exists
            if output:
                logger.info("Falling back to text extraction")
                return self._extract_decision_from_text(output)
                
        except subprocess.TimeoutExpired:
            logger.warning("Gemini CLI timeout (60s)")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Gemini CLI error: %s", exc)

        return self._fallback_decision()

    def _format_prompt_for_gemini(self, prompt: str) -> str:
        """Wrap original prompt with explicit JSON response contract."""
        return (
            "You are a concise trading advisor. Return ONLY valid JSON.\n" +
            prompt +
            (
                "\n\nResponse must be valid JSON with this exact schema:\n"
                "{\n"
                '  "action": "BUY|SELL|HOLD",\n'
                '  "confidence": <integer 0-100>,\n'
                '  "reasoning": "<brief explanation>",\n'
                '  "amount": <float or 0>\n'
                "}\n"
            ) +
            "Return only the JSON object, no markdown, "
            "no code blocks, no extra text."
        )

    def _parse_gemini_response(self, output: str) -> Dict[str, Any]:
        """
        Parse Gemini CLI response, expecting JSON.

        Args:
            output: Raw Gemini CLI output

        Returns:
            Parsed decision dict or None if parsing fails
        """
        # Try JSON parse first
        # (output-format json returns structured data)
        # Gemini CLI with --output-format json returns structured output
        def safe_confidence(val):
            try:
                return int(val) if val is not None else 50
            except (ValueError, TypeError):
                return 50

        def safe_amount(val):
            try:
                return float(val) if val is not None else 0
            except (ValueError, TypeError):
                return 0

        try:
            wrapper_data = json.loads(output)
            if isinstance(wrapper_data, dict):
                response_text = (wrapper_data.get('response') or wrapper_data.get('text'))
                if response_text:
                    data = try_parse_decision_json(response_text)
                    if data:
                        data['confidence'] = safe_confidence(data.get('confidence', 50))
                        data['amount'] = safe_amount(data.get('amount', 0))
                        logger.info(
                            "Gemini decision from wrapped response: %s (%d%%)",
                            data['action'], data['confidence']
                        )
                        return data
                    json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', response_text, re.DOTALL)
                    if json_match:
                        data = try_parse_decision_json(json_match.group(1))
                        if data:
                            data['confidence'] = safe_confidence(data.get('confidence', 50))
                            data['amount'] = safe_amount(data.get('amount', 0))
                            logger.info(
                                "Gemini decision from response markdown: %s (%d%%)",
                                data['action'], data['confidence']
                            )
                            return data
        except json.JSONDecodeError:
            pass

        data = try_parse_decision_json(output)
        if data:
            data['confidence'] = safe_confidence(data.get('confidence', 50))
            data['amount'] = safe_amount(data.get('amount', 0))
            logger.info(
                "Gemini decision parsed: %s (%d%%)",
                data['action'], data['confidence']
            )
            return data

        json_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', output, re.DOTALL)
        if json_match:
            data = try_parse_decision_json(json_match.group(1))
            if data:
                data['confidence'] = safe_confidence(data.get('confidence', 50))
                data['amount'] = safe_amount(data.get('amount', 0))
                logger.info(
                    "Gemini decision from code block: %s (%d%%)",
                    data['action'], data['confidence']
                )
                return data

        json_match = re.search(r'\{[^{}]*\}', output, re.DOTALL)
        if json_match:
            data = try_parse_decision_json(json_match.group(0))
            if data:
                data['confidence'] = safe_confidence(data.get('confidence', 50))
                data['amount'] = safe_amount(data.get('amount', 0))
                logger.info(
                    "Gemini decision extracted: %s (%d%%)",
                    data['action'], data['confidence']
                )
                return data

        return {}

    def _extract_decision_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract decision from natural language text.

        Args:
            text: Natural language response

        Returns:
            Parsed decision dictionary
        """
        text_upper = text.upper()
        
        # Determine action
        action = 'HOLD'  # Default
        if 'BUY' in text_upper and 'SELL' not in text_upper:
            action = 'BUY'
        elif 'SELL' in text_upper and 'BUY' not in text_upper:
            action = 'SELL'
        
        # Extract confidence if present
        confidence = 50  # Default
        conf_match = re.search(r'confidence[:\s]+(\d+)', text, re.IGNORECASE)
        if conf_match:
            confidence = min(100, max(0, int(conf_match.group(1))))
        
        # Use first sentence as reasoning
        if text:
            reasoning = text.split('.')[0].strip()
        else:
            reasoning = 'No reasoning provided'
        if len(reasoning) > 200:
            reasoning = reasoning[:197] + '...'
        
        decision = {
            'action': action,
            'confidence': confidence,
            'reasoning': reasoning,
            'amount': 0
        }
        
        logger.info(
            "Extracted from text: %s (%d%%)", action, confidence
        )
        return decision

    def _fallback_decision(self) -> Dict[str, Any]:
        """
        Generate a fallback decision when Gemini CLI fails.

        Returns:
            Conservative fallback decision
        """
        logger.warning("Using fallback decision")
        fallback_confidence = self.config.get('fallback_confidence', 50)
        return build_fallback_decision(
            'Gemini CLI unavailable or failed, using conservative fallback.',
            fallback_confidence=fallback_confidence
        )
