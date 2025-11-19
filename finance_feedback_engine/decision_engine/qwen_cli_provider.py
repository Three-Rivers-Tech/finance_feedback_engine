"""Qwen CLI provider for decision engine.

Free Qwen CLI integration for trading decisions.
Requires Node.js v20+ and OAuth authentication.
"""

from typing import Dict, Any
import logging
import subprocess
import json
import re

logger = logging.getLogger(__name__)


class QwenCLIProvider:
    """
    Qwen CLI provider for generating trading decisions.
    
    Uses the free Qwen CLI tool (requires Node.js v20+ and OAuth).
    No API charges - completely free to use.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Qwen CLI provider.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        logger.info("Qwen CLI provider initialized")
        
        # Verify qwen is available
        self._verify_qwen_available()

    def _verify_qwen_available(self) -> bool:
        """Check that 'qwen' binary exists and is functional."""
        try:
            result = subprocess.run(
                ['qwen', '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            if result.returncode == 0:
                logger.info("Qwen CLI available: %s", result.stdout.strip())
                return True
            raise ValueError("Qwen CLI returned non-zero exit code")
        except FileNotFoundError as exc:
            raise ValueError(
                "'qwen' binary not found. Install Qwen CLI "
                "(requires Node.js v20+). "
                "See https://github.com/QwenLM/Qwen"
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Timeout verifying Qwen CLI") from exc

    def query(self, prompt: str) -> Dict[str, Any]:
        """
        Query Qwen CLI for a trading decision.

        Args:
            prompt: Trading analysis prompt

        Returns:
            Dictionary with action, confidence, reasoning, amount
        """
        logger.info("Querying Qwen CLI for trading decision")

        formatted_prompt = self._format_prompt_for_qwen(prompt)

        try:
            # Use 'qwen' command with prompt
            # Qwen CLI typically accepts prompt via stdin or as argument
            result = subprocess.run(
                ['qwen', formatted_prompt],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            if result.returncode != 0:
                logger.warning(
                    "Qwen CLI failed: %s",
                    result.stderr.strip()
                )
                return self._fallback_decision()
            
            output = result.stdout.strip()
            
            # Try JSON parse first
            parsed = self._parse_qwen_response(output)
            if parsed:
                return parsed
            
            # Fallback to text extraction if output exists
            if output:
                logger.info("Falling back to text extraction")
                return self._extract_decision_from_text(output)
                
        except subprocess.TimeoutExpired:
            logger.warning("Qwen CLI timeout")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Qwen CLI error: %s", exc)

        return self._fallback_decision()

    def _format_prompt_for_qwen(self, prompt: str) -> str:
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

    def _parse_qwen_response(self, output: str) -> Dict[str, Any]:
        """
        Parse Qwen CLI response, expecting JSON.

        Args:
            output: Raw Qwen CLI output

        Returns:
            Parsed decision dict or None if parsing fails
        """
        # Try direct JSON parse
        try:
            data = json.loads(output)
            if self._is_valid_decision(data):
                # Ensure correct types
                data['confidence'] = int(data.get('confidence', 50))
                data['amount'] = float(data.get('amount', 0))
                logger.info(
                    "Qwen decision parsed: %s (%d%%)",
                    data['action'], data['confidence']
                )
                return data
        except json.JSONDecodeError:
            pass

        # Try to extract JSON from markdown code blocks
        json_match = re.search(
            r'```(?:json)?\s*(\{.*?\})\s*```',
            output,
            re.DOTALL
        )
        if json_match:
            try:
                data = json.loads(json_match.group(1))
                if self._is_valid_decision(data):
                    data['confidence'] = int(data.get('confidence', 50))
                    data['amount'] = float(data.get('amount', 0))
                    logger.info(
                        "Qwen decision from code block: %s (%d%%)",
                        data['action'], data['confidence']
                    )
                    return data
            except json.JSONDecodeError:
                pass

        # Try to find JSON object in text
        json_match = re.search(r'\{[^{}]*\}', output, re.DOTALL)
        if json_match:
            try:
                data = json.loads(json_match.group(0))
                if self._is_valid_decision(data):
                    data['confidence'] = int(data.get('confidence', 50))
                    data['amount'] = float(data.get('amount', 0))
                    logger.info(
                        "Qwen decision extracted: %s (%d%%)",
                        data['action'], data['confidence']
                    )
                    return data
            except json.JSONDecodeError:
                pass

        return {}

    def _is_valid_decision(self, data: Dict[str, Any]) -> bool:
        """
        Validate decision structure.

        Args:
            data: Decision dictionary to validate

        Returns:
            True if valid, False otherwise
        """
        required = ['action', 'confidence', 'reasoning']
        if not all(k in data for k in required):
            return False
        
        action = data.get('action', '').upper()
        if action not in ['BUY', 'SELL', 'HOLD']:
            return False
        
        try:
            conf = int(data.get('confidence', -1))
            if not 0 <= conf <= 100:
                return False
        except (TypeError, ValueError):
            return False
        
        return True

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
        Generate a fallback decision when Qwen CLI fails.

        Returns:
            Conservative fallback decision
        """
        logger.warning("Using fallback decision")
        return {
            'action': 'HOLD',
            'confidence': 50,
            'reasoning': (
                'Qwen CLI unavailable or failed, '
                'using conservative fallback.'
            ),
            'amount': 0
        }
