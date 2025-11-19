"""Codex CLI provider for decision engine."""

from typing import Dict, Any
import logging
import subprocess
import json
import re

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
                return self._create_fallback_response()
            
            response_text = result.stdout.strip()
            
            # Try to parse JSON response first
            try:
                decision = json.loads(response_text)
                if self._is_valid_decision(decision):
                    decision['confidence'] = int(decision.get('confidence', 50))
                    decision['amount'] = float(decision.get('amount', 0))
                    logger.info(f"Codex decision parsed: {decision['action']} ({decision['confidence']}%)")
                    return decision
            except json.JSONDecodeError:
                pass
            
            # Fallback: parse text response
            logger.info("Parsing Codex text response")
            return self._parse_text_response(response_text)
            
        except subprocess.TimeoutExpired:
            logger.error("Codex CLI timeout")
            return self._create_fallback_response()
        except FileNotFoundError:
            logger.error("Codex CLI not found - install from https://github.com/openai/codex")
            return self._create_fallback_response()
        except Exception as e:
            logger.error(f"Codex CLI error: {e}")
            return self._create_fallback_response()

    def _is_valid_decision(self, decision: Dict[str, Any]) -> bool:
        """Check if decision dict has required fields."""
        required = ['action', 'confidence', 'reasoning']
        return all(k in decision for k in required)

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

    def _create_fallback_response(self) -> Dict[str, Any]:
        """Create a default HOLD response."""
        return {
            'action': 'HOLD',
            'confidence': 50,
            'reasoning': 'Codex CLI unavailable, using fallback decision.',
            'amount': 0
        }
