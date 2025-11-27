"""
Local LLM provider using Ollama with automatic model deployment.

Automatically downloads and configures Llama-3.2-3B-Instruct for
trading decisions if not already available.
"""

from typing import Dict, Any
import logging
import subprocess
import json
import re
import sys
from .decision_validation import (
    is_valid_decision,
    try_parse_decision_json,
    build_fallback_decision,
)

logger = logging.getLogger(__name__)


class LocalLLMProvider:
    """
    Local LLM provider using Ollama.
    
    Automatically deploys Llama-3.2-3B-Instruct (optimal for day traders):
    - 3B parameters (fits in 4-8GB RAM)
    - CPU-optimized inference
    - Financial reasoning capable
    - No API costs
    """

    # Model selection based on research
    DEFAULT_MODEL = "llama3.2:3b-instruct-fp16"
    FALLBACK_MODEL = "llama3.2:1b-instruct-fp16"  # Ultra-compact fallback
    # Enforce at least one secondary model for robustness
    SECONDARY_MODEL = "deepseek-r1:8b"
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize local LLM provider.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        
        # Read local models and priority from config
        decision_engine_config = config.get('decision_engine', {})
        self.local_models = decision_engine_config.get('local_models', [])
        if not isinstance(self.local_models, list):
            logger.warning("local_models must be a list, using empty list.")
            self.local_models = []
        self.local_priority = decision_engine_config.get('local_priority', False)
        
        # Normalize model name: "default" -> actual default model
        requested_model = config.get('model_name', 'default')
        if requested_model == 'default':
            self.model_name = self.DEFAULT_MODEL
        else:
            self.model_name = requested_model
        
        logger.info(
            f"Initializing local LLM provider with model: {self.model_name}, "
            f"local_models: {self.local_models}, local_priority: {self.local_priority}"
        )
        
        # Verify Ollama installation (auto-install if needed)
        if not self._check_ollama_installed():
            raise RuntimeError("Failed to install or verify Ollama")
        
        # Ensure model is available (auto-download if needed)
        self._ensure_model_available()

        # Ensure secondary model exists for robustness (required)
        try:
            # Use configured local_models if available, else defaults
            if self.local_models:
                secondary_candidates = self.local_models[1:] if len(self.local_models) > 1 else [self.SECONDARY_MODEL]
            else:
                secondary_candidates = [self.SECONDARY_MODEL]
            
            for secondary_model in secondary_candidates:
                if not self._is_model_available(secondary_model):
                    logger.info(
                        "Secondary model %s not found. Downloading for "
                        "ensemble robustness...",
                        secondary_model,
                    )
                    if not self._download_model(secondary_model):
                        # Non-recoverable: require at least two local models
                        raise RuntimeError(
                            "Failed to ensure required secondary model: %s. "
                            "Please run: ollama pull %s"
                            % (secondary_model, secondary_model)
                        )
                    logger.info(
                        "Successfully downloaded secondary model: %s",
                        secondary_model,
                    )
        except RuntimeError:
            raise  # Re-raise without wrapping
        except Exception as e:
            raise RuntimeError(f"Failed to ensure secondary model: {e}") from e
        
        logger.info("Local LLM provider initialized successfully")

    def _check_ollama_installed(self) -> bool:
        """
        Check if Ollama is installed. If not, attempt automatic installation.
        
        Returns:
            bool: True if Ollama is available or successfully installed
        """
        try:
            result = subprocess.run(
                ['ollama', '--version'],
                capture_output=True,
                text=True,
                timeout=5,
                check=False
            )
            
            if result.returncode == 0:
                version = result.stdout.strip()
                logger.info("Ollama installed: %s", version)
                return True
            else:
                logger.warning(
                    "Ollama command failed, attempting installation..."
                )
                return self._install_ollama()
                
        except FileNotFoundError:
            logger.warning(
                "Ollama not found in PATH, attempting installation..."
            )
            return self._install_ollama()
        except subprocess.TimeoutExpired:
            logger.error("Ollama version check timeout")
            return False
        except Exception as e:
            logger.error(f"Error checking Ollama: {e}")
            return False

    def _install_ollama(self) -> bool:
        """
        Automatically install Ollama based on platform.
        
        Returns:
            bool: True if installation successful
        """
        import platform
        
        system = platform.system()
        logger.info(f"Detected platform: {system}")
        
        try:
            if system == "Linux" or system == "Darwin":  # Linux or macOS
                logger.info(f"Installing Ollama on {system}...")
                logger.info(
                    "Running: curl -fsSL https://ollama.ai/install.sh | sh"
                )
                
                # Download and execute install script
                install_cmd = "curl -fsSL https://ollama.ai/install.sh | sh"
                result = subprocess.run(
                    install_cmd,
                    shell=True,
                    capture_output=True,
                    text=True,
                    timeout=300  # 5 minutes
                )
                
                if result.returncode != 0:
                    logger.error("Installation failed: %s", result.stderr)
                    raise RuntimeError(
                        "Ollama installation failed: %s" % result.stderr
                    )
                
                logger.info(f"Ollama installed successfully on {system}")
                logger.info(f"Installation output: {result.stdout}")
                
            elif system == "Windows":
                logger.error(
                    "Automatic installation not supported on Windows"
                )
                raise RuntimeError(
                    "Automatic Ollama installation not supported on Windows.\n"
                    "Please download and install manually from: "
                    "https://ollama.ai/download\n"
                    "After installation, restart your terminal and try again."
                )
            else:
                raise RuntimeError(f"Unsupported platform: {system}")
            
            # Verify installation
            verify_result = subprocess.run(
                ["ollama", "--version"],
                capture_output=True,
                text=True,
                timeout=5
            )
            
            if verify_result.returncode == 0:
                logger.info(
                    "Installation verified: %s" % verify_result.stdout.strip()
                )
                return True
            else:
                raise RuntimeError("Ollama installed but verification failed")
                
        except subprocess.TimeoutExpired:
            raise RuntimeError("Ollama installation timed out (>5 minutes)")
        except Exception as e:
            raise RuntimeError(f"Ollama installation failed: {str(e)}")

    def _ensure_model_available(self) -> None:
        """
        Ensure model is downloaded and ready.
        
        Download strategy:
        1. Check if requested model is available -> use it
        2. If not, attempt to download requested model
        3. If download fails and requested was primary, try fallback
        4. If all fails, raise error with clear instructions
        """
        # Check if model already exists
        if self._is_model_available(self.model_name):
            logger.info(f"Model {self.model_name} is already available")
            return
        
        # Model not available - need to download
        logger.info(
            f"Model {self.model_name} not found locally. "
            f"Downloading..."
        )
        logger.info(
            "This is a one-time download. Please wait..."
        )
        
        # Attempt to download requested model
        if self._download_model(self.model_name):
            logger.info(
                f"Successfully downloaded {self.model_name}"
            )
            return
        
        # Download failed - try fallback if we were trying primary
        if self.model_name == self.DEFAULT_MODEL:
            logger.warning(
                f"Failed to download primary model {self.DEFAULT_MODEL}. "
                f"Trying fallback {self.FALLBACK_MODEL}..."
            )
            
            if self._download_model(self.FALLBACK_MODEL):
                self.model_name = self.FALLBACK_MODEL
                logger.info(
                    f"Using fallback model: {self.FALLBACK_MODEL}"
                )
                logger.warning(
                    f"Primary model {self.DEFAULT_MODEL} download failed. "
                    f"Performance may be reduced with fallback model."
                )
                return
        
        # Both failed or custom model failed - hard error
        raise RuntimeError(
            f"Failed to download model: {self.model_name}\n"
            f"Please check:\n"
            f"  1. Internet connection is active\n"
            f"  2. Sufficient disk space (~5GB free)\n"
            f"  3. Ollama service is running\n"
            f"Manual download: ollama pull {self.model_name}"
        )
    
    def _download_model(self, model_name: str) -> bool:
        """
        Download a specific model from Ollama library.
        
        Args:
            model_name: Name of model to download (e.g.,
                'llama3.2:3b-instruct-fp16')
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            logger.info(
                f"Downloading {model_name} from Ollama library..."
            )
            logger.info(
                "This may take several minutes depending on your connection."
            )
            
            # Run ollama pull command
            result = subprocess.run(
                ['ollama', 'pull', model_name],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for download
                check=False
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(
                    f"Download failed for {model_name}: {error_msg}"
                )
                return False
            
            # Verify the model was actually downloaded
            if not self._is_model_available(model_name):
                logger.error(
                    f"Download reported success but {model_name} "
                    f"is not available. This may indicate a disk space "
                    f"or permission issue."
                )
                return False
            
            logger.info(f"Successfully downloaded {model_name}")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(
                f"Download timeout for {model_name} (>10 minutes). "
                f"Check your internet connection and try again."
            )
            return False
        except Exception as e:
            logger.error(
                f"Unexpected error downloading {model_name}: {e}"
            )
            return False

    def _delete_model(self, model_name: str) -> bool:
        """
        Delete a model to free disk space.
        
        Args:
            model_name: Name of model to delete
            
        Returns:
            bool: True if deletion successful, False otherwise
        """
        try:
            logger.info(f"Deleting model {model_name}...")
            
            result = subprocess.run(
                ['ollama', 'rm', model_name],
                capture_output=True,
                text=True,
                timeout=30,
                check=False
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.warning(
                    f"Failed to delete model {model_name}: {error_msg}"
                )
                return False
            
            # Verify deletion
            if self._is_model_available(model_name):
                logger.warning(
                    f"Model {model_name} still available after deletion"
                )
                return False
            
            logger.info(
                f"Model {model_name} deleted successfully. "
                f"Freed ~2.5GB disk space."
            )
            return True
            
        except subprocess.TimeoutExpired:
            logger.warning(f"Model {model_name} deletion timeout")
            return False
        except Exception as e:
            logger.warning(f"Failed to delete model {model_name}: {e}")
            return False

    def _unload_model(self) -> None:
        """
        Unload the current model from GPU memory to free resources.
        
        This is called after each query to allow sequential loading
        of different models without memory conflicts.
        """
        try:
            logger.debug(f"Unloading model {self.model_name} from memory")
            
            result = subprocess.run(
                ['ollama', 'stop', self.model_name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            if result.returncode == 0:
                logger.debug(f"Successfully unloaded model {self.model_name}")
            else:
                logger.debug(
                    f"Model {self.model_name} may not have been loaded: "
                    f"{result.stderr.strip()}"
                )
                
        except subprocess.TimeoutExpired:
            logger.warning(f"Timeout unloading model {self.model_name}")
        except Exception as e:
            logger.warning(f"Error unloading model {self.model_name}: {e}")

    def _is_model_available(self, model_name: str) -> bool:
        """Check if model is available locally."""
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            if result.returncode == 0:
                # Parse model list
                models = result.stdout.lower()
                # Handle both full name and short name
                model_base = model_name.split(':')[0].lower()
                return model_base in models or model_name.lower() in models
            
            return False
            
        except Exception as e:
            logger.error(f"Error checking model availability: {e}")
            return False

    def query(self, prompt: str) -> Dict[str, Any]:
        """
        Query local LLM for trading decision.

        Args:
            prompt: Trading analysis prompt

        Returns:
            Dictionary with action, confidence, reasoning, amount
        """
        try:
            logger.info(f"Querying local LLM: {self.model_name}")
            
            # Create system prompt for trading
            full_prompt = (
                "You are a professional day trading advisor. "
                "Analyze market data and provide trading recommendations. "
                "Respond ONLY with valid JSON containing these exact keys: "
                "action (BUY/SELL/HOLD), confidence (0-100 integer), "
                "reasoning (brief explanation string), "
                "amount (decimal number for position size).\n\n"
                f"{prompt}"
            )
            
            # Call Ollama with proper format
            result = subprocess.run(
                [
                    'ollama', 'run', self.model_name,
                    '--format', 'json',
                    full_prompt
                ],
                capture_output=True,
                text=True,
                timeout=60,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Ollama inference failed: {result.stderr}")
                return build_fallback_decision(
                    "Local LLM unavailable, using fallback decision."
                )
            
            response_text = result.stdout.strip()
            logger.debug(f"Raw LLM response: {response_text[:200]}")
            
            decision = try_parse_decision_json(response_text)
            if decision:
                # Safely convert confidence to int (default 60 if missing/invalid)
                try:
                    confidence_val = decision.get('confidence', 60)
                    decision['confidence'] = int(confidence_val) if confidence_val is not None else 60
                except (ValueError, TypeError):
                    decision['confidence'] = 60
                
                # Safely convert amount to float (default 0.1 if missing/invalid)
                try:
                    amount_val = decision.get('amount', 0.1)
                    decision['amount'] = float(amount_val) if amount_val is not None else 0.1
                except (ValueError, TypeError):
                    decision['amount'] = 0.1
                
                logger.info(
                    f"Local LLM decision: {decision['action']} "
                    f"({decision['confidence']}%)"
                )
                
                # Unload model from memory to free GPU resources for next model
                self._unload_model()
                
                return decision

            logger.warning(
                "LLM response missing required fields or not JSON, "
                "attempting text parsing"
            )
            return self._parse_text_response(response_text)
            
        except subprocess.TimeoutExpired:
            logger.error("Local LLM inference timeout (>60s)")
            return build_fallback_decision(
                "Local LLM timeout, using fallback decision."
            )
        except Exception as e:
            logger.error(f"Local LLM error: {e}")
            return build_fallback_decision(
                "Local LLM error, using fallback decision."
            )

    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        """Parse text response for trading decision."""
        text_upper = text.upper()
        
        # Extract action
        if 'BUY' in text_upper and 'SELL' not in text_upper:
            action = 'BUY'
        elif 'SELL' in text_upper and 'BUY' not in text_upper:
            action = 'SELL'
        else:
            action = 'HOLD'
        
        # Extract confidence
        confidence_match = re.search(r'(\d+)\s*%', text)
        confidence = int(confidence_match.group(1)) if confidence_match else 65
        
        # Extract reasoning (first meaningful line)
        lines = [line.strip() for line in text.split('\n') if line.strip()]
        reasoning = lines[0][:200] if lines else "Local LLM analysis"
        
        # Extract amount
        amount_match = re.search(r'(\d+\.?\d*)\s*(BTC|ETH|units?)', text, re.IGNORECASE)
        amount = float(amount_match.group(1)) if amount_match else 0.1
        
        return {
            'action': action,
            'confidence': confidence,
            'reasoning': reasoning,
            'amount': amount
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        try:
            result = subprocess.run(
                ['ollama', 'show', self.model_name],
                capture_output=True,
                text=True,
                timeout=10,
                check=False
            )
            
            if result.returncode == 0:
                return {
                    'model_name': self.model_name,
                    'status': 'available',
                    'info': result.stdout
                }
            
            return {
                'model_name': self.model_name,
                'status': 'error',
                'info': result.stderr
            }
            
        except Exception as e:
            return {
                'model_name': self.model_name,
                'status': 'error',
                'info': str(e)
            }
