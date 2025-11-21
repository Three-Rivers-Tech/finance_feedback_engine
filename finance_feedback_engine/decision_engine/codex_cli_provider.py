"""Codex CLI provider for decision engine."""

from typing import Dict, Any
import logging
import subprocess
import json
import re
from .decision_validation import (
    is_valid_decision,
    try_parse_decision_json,
    build_fallback_decision,
)

logger = logging.getLogger(__name__)


class CodexCLIProvider:
    """
    Codex CLI provider for generating trading decisions.
    
    Uses the local Codex CLI tool (similar to Copilot CLI).
    No API charges - runs locally.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Codex CLI provider.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        logger.info("Codex CLI provider initialized")
        
        # Verify codex is available
        try:
            result = subprocess.run(
                ['codex', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            if result.returncode == 0:
                logger.info(f"Codex CLI available: {result.stdout.strip()}")
            else:
                logger.warning("Codex CLI command exists but returned error")
        except FileNotFoundError:
            logger.warning("Codex CLI not found in PATH")
        except Exception as e:
            logger.warning(f"Could not verify Codex CLI: {e}")

    def query(self, prompt: str) -> Dict[str, Any]:
        """
        Query Codex CLI for a trading decision.

        Args:
            prompt: Trading analysis prompt

        Returns:
            Dictionary with action, confidence, reasoning, amount
        """
        try:
            # Call codex exec (non-interactive mode)
            cmd = ['codex', 'exec', prompt]
            
            logger.info("Querying Codex CLI for trading decision")
            
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=30
            )
            
            if result.returncode != 0:
                logger.error(f"Codex CLI error: {result.stderr}")
                return build_fallback_decision(
                    "Codex CLI unavailable, using fallback decision."
                )
            
            response_text = result.stdout.strip()
            
            decision = try_parse_decision_json(response_text)
            if decision:
                decision['confidence'] = int(decision.get('confidence', 50))
                decision['amount'] = float(decision.get('amount', 0))
                logger.info(
                    f"Codex decision parsed: {decision['action']} "
                    f"({decision['confidence']}%)"
                )
                return decision
            
            # Fallback: parse text response
            logger.info("Parsing Codex text response")
            return self._parse_text_response(response_text)
            
        except subprocess.TimeoutExpired:
            logger.error("Codex CLI timeout")
            return build_fallback_decision(
                "Codex CLI timeout, using fallback decision."
            )
        except FileNotFoundError:
            logger.error("Codex CLI not found - install from https://github.com/openai/codex")
            return build_fallback_decision(
                "Codex CLI not found, using fallback decision."
            )
        except Exception as e:
            logger.error(f"Codex CLI error: {e}")
            return build_fallback_decision(
                "Codex CLI error, using fallback decision."
            )

    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        """
        Parse text response for trading decision.

        Args:
            text: Response text from Codex

        Returns:
            Parsed decision dictionary
        """
        text_upper = text.upper()
        
        # Extract action
        if 'BUY' in text_upper and 'SELL' not in text_upper:
            action = 'BUY'
        elif 'SELL' in text_upper and 'BUY' not in text_upper:
            action = 'SELL'
        else:
            action = 'HOLD'
        
        # Extract confidence percentage
        confidence_match = re.search(r'(\d+)\s*%', text)
        confidence = int(confidence_match.group(1)) if confidence_match else 60
        
        # Extract reasoning (first meaningful line)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        reasoning = lines[0][:200] if lines else "Codex CLI analysis"
        
        # Extract amount if mentioned
        amount_match = re.search(r'(\d+\.?\d*)\s*(BTC|ETH|units?)', text, re.IGNORECASE)
        amount = float(amount_match.group(1)) if amount_match else 0.1
        
        return {
            'action': action,
            'confidence': confidence,
            'reasoning': reasoning,
            'amount': amount
        }
