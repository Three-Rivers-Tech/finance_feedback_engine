"""GitHub Copilot standalone CLI provider for trading decisions.

Supports the modern 'copilot' binary (deprecated 'gh copilot' extension
is no longer used). If the binary is unavailable or returns only
deprecation text, we fall back gracefully.
"""

import json
import logging
import re
import subprocess
from typing import Any, Dict

logger = logging.getLogger(__name__)


class CopilotCLIProvider:
    """Integration with the standalone GitHub Copilot CLI ('copilot')."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self._verify_copilot_available()

    def _verify_copilot_available(self) -> bool:
        """Check that 'copilot' binary exists and is functional."""
        try:
            result = subprocess.run(
                ["copilot", "--version"],
                capture_output=True,
                text=True,
                timeout=5,
                check=False,
            )
            if result.returncode == 0:
                logger.info("Copilot CLI available: %s", result.stdout.strip())
                return True
            raise ValueError("Copilot CLI returned non-zero exit code")
        except FileNotFoundError as exc:
            raise ValueError(
                "'copilot' binary not found. Install GitHub Copilot CLI."
            ) from exc
        except subprocess.TimeoutExpired as exc:
            raise ValueError("Timeout verifying Copilot CLI") from exc

    def query(self, prompt: str) -> Dict[str, Any]:
        """Query Copilot for a decision; expect JSON or NL text."""
        logger.info("Querying Copilot CLI for trading decision")

        formatted_prompt = self._format_prompt_for_copilot(prompt)

        # Use 'copilot -p "prompt"' format (non-interactive)
        try:
            result = subprocess.run(
                ["copilot", "-p", formatted_prompt],
                capture_output=True,
                text=True,
                timeout=30,
                check=False,
            )

            if result.returncode != 0:
                logger.warning("Copilot CLI failed: %s", result.stderr.strip())
                return self._fallback_decision()

            output = result.stdout.strip()

            # Try JSON parse first
            parsed = self._parse_copilot_response(output)
            if parsed:
                return parsed

            # Fallback to text extraction if output exists
            if output:
                logger.info("Falling back to text extraction")
                return self._extract_decision_from_text(output)

        except subprocess.TimeoutExpired:
            logger.warning("Copilot CLI timeout")
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            logger.warning("Copilot CLI error: %s", exc)

        return self._fallback_decision()

    def _format_prompt_for_copilot(self, prompt: str) -> str:
        """Wrap original prompt with explicit JSON response contract."""
        return (
            "You are a concise trading advisor. Return ONLY JSON.\n"
            + prompt
            + (
                "\nJSON schema: {\n"
                '  "action": "BUY|SELL|HOLD",\n'
                '  "confidence": <0-100>,\n'
                '  "reasoning": "string",\n'
                '  "amount": <float or 0>\n'
                "}\n"
            )
            + "No extra commentary."
        )

    def _parse_copilot_response(self, response: str) -> Dict[str, Any] | None:
        """Attempt JSON parse; return None if unusable."""
        try:
            json_match = re.search(r"\{[\s\S]*\}", response)
            if not json_match:
                return None
            parsed = json.loads(json_match.group(0))
            required = {"action", "confidence", "reasoning"}
            if not required.issubset(parsed.keys()):
                return None
            parsed["action"] = str(parsed["action"]).upper()
            parsed["confidence"] = int(parsed["confidence"])
            parsed["amount"] = parsed.get("amount", 0)
            logger.info(
                "Copilot decision parsed: %s (%d%%)",
                parsed["action"],
                parsed["confidence"],
            )
            return parsed
        except (json.JSONDecodeError, ValueError) as exc:
            logger.warning("JSON parse failed: %s", exc)
            return None

    def _extract_decision_from_text(self, text: str) -> Dict[str, Any]:
        """
        Extract trading decision from natural language text.

        Args:
            text: Copilot response text

        Returns:
            Extracted decision
        """
        text_upper = text.upper()

        # Detect action
        action = "HOLD"
        if "BUY" in text_upper and "SELL" not in text_upper:
            action = "BUY"
        elif "SELL" in text_upper and "BUY" not in text_upper:
            action = "SELL"

        # Extract confidence if mentioned
        confidence = 60
        confidence_match = re.search(r"(\d{1,3})\s*%", text)
        if confidence_match:
            confidence = int(confidence_match.group(1))
            confidence = max(0, min(100, confidence))  # Clamp to 0-100

        # Use first sentence as reasoning
        sentences = text.split(".")
        reasoning = (
            sentences[0].strip()
            if sentences
            else "AI recommendation based on market analysis"
        )

        return {
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning[:200],  # Limit length
            "amount": 0,
        }

    def _fallback_decision(self) -> Dict[str, Any]:
        """
        Fallback decision when Copilot is unavailable.

        Returns:
            Conservative HOLD decision
        """
        logger.warning("Using fallback decision due to Copilot error")
        return {
            "action": "HOLD",
            "confidence": 50,
            "reasoning": ("Unable to get AI recommendation, defaulting to HOLD."),
            "amount": 0,
        }
