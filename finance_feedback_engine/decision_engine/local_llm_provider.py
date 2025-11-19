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
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize local LLM provider.

        Args:
            config: Configuration dictionary
        """
        self.config = config
        self.model_name = config.get('model_name', self.DEFAULT_MODEL)
        
        logger.info(f"Initializing local LLM provider with model: {self.model_name}")
        
        # Verify Ollama installation (auto-install if needed)
        if not self._check_ollama_installed():
            raise RuntimeError("Failed to install or verify Ollama")
        
        # Ensure model is available (auto-download if needed)
        self._ensure_model_available()
        
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
                logger.info(f"Ollama installed: {version}")
                return True
            else:
                logger.warning("Ollama command failed, attempting installation...")
                return self._install_ollama()
                
        except FileNotFoundError:
            logger.warning("Ollama not found in PATH, attempting installation...")
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
                logger.info("Running: curl -fsSL https://ollama.ai/install.sh | sh")
                
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
                    logger.error(f"Installation failed: {result.stderr}")
                    raise RuntimeError(f"Ollama installation failed: {result.stderr}")
                
                logger.info(f"Ollama installed successfully on {system}")
                logger.info(f"Installation output: {result.stdout}")
                
            elif system == "Windows":
                logger.error("Automatic installation not supported on Windows")
                raise RuntimeError(
                    "Automatic Ollama installation not supported on Windows.\n"
                    "Please download and install manually from: https://ollama.ai/download\n"
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
                logger.info(f"Installation verified: {verify_result.stdout.strip()}")
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
        Auto-downloads if missing. Fails hard if download fails.
        
        Smart upgrade logic:
        - If primary model available: use it (delete fallback to save space)
        - If only fallback available: try to upgrade to primary
        - If neither available: download primary, fallback to 1B if fails
        """
        primary_available = self._is_model_available(self.DEFAULT_MODEL)
        fallback_available = self._is_model_available(self.FALLBACK_MODEL)
        requested_available = self._is_model_available(self.model_name)
        
        # Case 1: Requested model already available
        if requested_available:
            logger.info(f"Model {self.model_name} already available")
            
            # Clean up: if primary model is available, delete fallback
            if (self.model_name == self.DEFAULT_MODEL and 
                fallback_available):
                logger.info(
                    f"Primary model {self.DEFAULT_MODEL} active. "
                    f"Deleting fallback {self.FALLBACK_MODEL} to free "
                    f"disk space (~2.5GB)..."
                )
                self._delete_model(self.FALLBACK_MODEL)
            
            return
        
        # Case 2: Primary model available (upgrade from fallback)
        if self.model_name == self.FALLBACK_MODEL and primary_available:
            logger.info(
                f"Upgrading from fallback {self.FALLBACK_MODEL} "
                f"to primary {self.DEFAULT_MODEL}"
            )
            self.model_name = self.DEFAULT_MODEL
            logger.info(f"Now using primary model: {self.DEFAULT_MODEL}")
            
            # Delete fallback after successful upgrade
            logger.info(
                f"Deleting fallback model {self.FALLBACK_MODEL} "
                f"to free disk space..."
            )
            self._delete_model(self.FALLBACK_MODEL)
            return
        
        # Case 3: Only fallback available, try to get primary
        if fallback_available and not primary_available:
            if self.model_name == self.DEFAULT_MODEL:
                logger.info(
                    f"Fallback model {self.FALLBACK_MODEL} detected. "
                    f"Attempting to download primary {self.DEFAULT_MODEL}..."
                )
                if self._download_model(self.DEFAULT_MODEL):
                    logger.info(
                        f"Successfully upgraded to primary model: "
                        f"{self.DEFAULT_MODEL}"
                    )
                    # Delete fallback after successful upgrade
                    logger.info(
                        f"Deleting fallback model {self.FALLBACK_MODEL} "
                        f"to free disk space..."
                    )
                    self._delete_model(self.FALLBACK_MODEL)
                    return
                else:
                    logger.warning(
                        f"Primary model download failed. "
                        f"Continuing with fallback: {self.FALLBACK_MODEL}"
                    )
                    self.model_name = self.FALLBACK_MODEL
                    return
        
        # Case 4: Model not found - attempt download
        logger.warning(f"Model {self.model_name} not found. Downloading...")
        logger.info("This is a one-time download (~2GB). Please wait...")
        
        # Try to download requested/primary model
        if self._download_model(self.model_name):
            logger.info(f"Model {self.model_name} downloaded successfully")
            return
        
        # Primary failed - try fallback
        logger.info(f"Attempting fallback model: {self.FALLBACK_MODEL}")
        if self._download_model(self.FALLBACK_MODEL):
            self.model_name = self.FALLBACK_MODEL
            logger.info(f"Using fallback model: {self.FALLBACK_MODEL}")
            logger.warning(
                f"System will attempt to upgrade to {self.DEFAULT_MODEL} "
                f"on next boot"
            )
            return
        
        # Both failed - hard failure
        raise RuntimeError(
            f"Failed to download both primary and fallback models.\n"
            f"Ensure you have internet connection and sufficient disk space.\n"
            f"Manual download: ollama pull {self.DEFAULT_MODEL}"
        )
    
    def _download_model(self, model_name: str) -> bool:
        """
        Download a specific model.
        
        Args:
            model_name: Name of model to download
            
        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            logger.info(f"Pulling {model_name} from Ollama library...")
            
            result = subprocess.run(
                ['ollama', 'pull', model_name],
                capture_output=True,
                text=True,
                timeout=600,  # 10 minute timeout for download
                check=False
            )
            
            if result.returncode != 0:
                error_msg = result.stderr or result.stdout
                logger.error(f"Model {model_name} download failed: {error_msg}")
                return False
            
            # Verify download
            if not self._is_model_available(model_name):
                logger.error(
                    f"Model {model_name} download appeared successful "
                    f"but model not available"
                )
                return False
            
            logger.info(f"Model {model_name} downloaded successfully")
            return True
            
        except subprocess.TimeoutExpired:
            logger.error(
                f"Model {model_name} download timeout (>10 minutes)"
            )
            return False
        except Exception as e:
            logger.error(f"Failed to download model {model_name}: {e}")
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
            system_prompt = (
                "You are a professional day trading advisor. "
                "Analyze market data and provide trading recommendations. "
                "Respond in JSON format with keys: action (BUY/SELL/HOLD), "
                "confidence (0-100), reasoning (brief explanation), "
                "amount (suggested position size)."
            )
            
            # Build Ollama request
            ollama_input = {
                "model": self.model_name,
                "prompt": f"{system_prompt}\n\n{prompt}",
                "stream": False,
                "format": "json",
                "options": {
                    "temperature": 0.7,
                    "num_predict": 500,
                    "top_p": 0.9
                }
            }
            
            # Call Ollama API
            result = subprocess.run(
                ['ollama', 'run', self.model_name, '--format', 'json'],
                input=json.dumps(ollama_input),
                capture_output=True,
                text=True,
                timeout=60,
                check=False
            )
            
            if result.returncode != 0:
                logger.error(f"Ollama inference failed: {result.stderr}")
                return self._create_fallback_response()
            
            response_text = result.stdout.strip()
            
            # Try to parse JSON response
            try:
                decision = json.loads(response_text)
                if self._is_valid_decision(decision):
                    decision['confidence'] = int(decision.get('confidence', 60))
                    decision['amount'] = float(decision.get('amount', 0.1))
                    logger.info(
                        f"Local LLM decision: {decision['action']} "
                        f"({decision['confidence']}%)"
                    )
                    return decision
            except json.JSONDecodeError:
                pass
            
            # Fallback: parse text response
            logger.info("Parsing local LLM text response")
            return self._parse_text_response(response_text)
            
        except subprocess.TimeoutExpired:
            logger.error("Local LLM inference timeout")
            return self._create_fallback_response()
        except Exception as e:
            logger.error(f"Local LLM error: {e}")
            return self._create_fallback_response()

    def _is_valid_decision(self, decision: Dict[str, Any]) -> bool:
        """Check if decision dict has required fields."""
        required = ['action', 'confidence', 'reasoning']
        return all(k in decision for k in required)

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

    def _create_fallback_response(self) -> Dict[str, Any]:
        """Create default HOLD response."""
        return {
            'action': 'HOLD',
            'confidence': 50,
            'reasoning': 'Local LLM unavailable, using fallback decision.',
            'amount': 0
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
