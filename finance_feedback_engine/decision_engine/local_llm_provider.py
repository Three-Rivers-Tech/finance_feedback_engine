"""
Local LLM provider using Ollama with automatic model deployment and connection pooling.

Automatically downloads and configures Llama-3.2-3B-Instruct for
trading decisions if not already available.

Phase 2 optimization: Singleton pattern for connection reuse, eliminating 1-2s overhead per decision.
"""

import logging
import os
import re
import subprocess
import time
from datetime import datetime, timezone
from typing import Any, Dict, Optional

import ollama

from .decision_validation import build_fallback_decision, try_parse_decision_json

logger = logging.getLogger(__name__)


def _candidate_audit_view(decision: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    payload = decision if isinstance(decision, dict) else {}
    return {
        "action": payload.get("action"),
        "policy_action": payload.get("policy_action"),
        "candidate_actions": payload.get("candidate_actions"),
        "confidence": payload.get("confidence"),
        "decision_origin": payload.get("decision_origin"),
        "filtered_reason_code": payload.get("filtered_reason_code"),
    }

_POLICY_ACTION_ORDER = [
    "HOLD",
    "OPEN_SMALL_LONG",
    "OPEN_MEDIUM_LONG",
    "ADD_SMALL_LONG",
    "REDUCE_LONG",
    "CLOSE_LONG",
    "OPEN_SMALL_SHORT",
    "OPEN_MEDIUM_SHORT",
    "ADD_SMALL_SHORT",
    "REDUCE_SHORT",
    "CLOSE_SHORT",
]
_ALLOWED_POLICY_ACTIONS_BLOCK_RE = re.compile(
    r"Allowed Policy Actions(?: ONLY| for the current position state)?\s*:\s*(.*?)(?:\n\s*\n|$)",
    re.IGNORECASE | re.DOTALL,
)
_ALLOWED_POLICY_ACTION_TOKEN_RE = re.compile(
    r"\b(?:" + "|".join(_POLICY_ACTION_ORDER) + r")\b"
)


def _extract_allowed_policy_actions(prompt: str) -> list[str]:
    """Extract a narrowed policy-action set from the prompt when present."""
    text = str(prompt or "")
    matches = _ALLOWED_POLICY_ACTIONS_BLOCK_RE.findall(text)
    if not matches:
        return list(_POLICY_ACTION_ORDER)
    found = set()
    for block in matches:
        found.update(_ALLOWED_POLICY_ACTION_TOKEN_RE.findall(block.upper()))
    narrowed = [action for action in _POLICY_ACTION_ORDER if action in found]
    return narrowed or list(_POLICY_ACTION_ORDER)


class LocalLLMProvider:
    """
    Local LLM provider using Ollama with connection pooling (Phase 2 optimization).

    Automatically deploys Llama-3.2-3B-Instruct (optimal for day traders):
    - 3B parameters (fits in 4-8GB RAM)
    - CPU-optimized inference
    - Financial reasoning capable
    - No API costs
    - Singleton pattern for connection reuse
    """

    # Model selection based on research
    DEFAULT_MODEL = "llama3.2:3b-instruct-q4_0"
    FALLBACK_MODEL = "llama3.2:1b-instruct-q4_0"  # Ultra-compact fallback
    # Enforce at least one secondary model for robustness
    SECONDARY_MODEL = "deepseek-r1:8b"

    # Singleton instance (Phase 2 optimization)
    _instance = None
    _initialized = False
    _connection_time = None

    def __new__(cls, *args, **kwargs):
        """Singleton pattern - only one instance per process."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize local LLM provider (only once due to singleton).

        Args:
            config: Configuration dictionary
        """
        # Only initialize once (singleton pattern)
        if self._initialized:
            logger.debug("LocalLLMProvider already initialized, reusing instance")
            return

        self.config = config

        # Initialize Ollama client (uses OLLAMA_HOST env var automatically)
        ollama_host = os.getenv("OLLAMA_HOST", "http://localhost:11434")
        logger.info(f"Connecting to Ollama at: {ollama_host}")
        self.ollama_client = ollama.Client(host=ollama_host)

        # Read local models and priority from config
        decision_engine_config = config.get("decision_engine", {})
        self.local_models = decision_engine_config.get("local_models", [])
        if not isinstance(self.local_models, list):
            logger.warning("local_models must be a list, using empty list.")
            self.local_models = []
        self.local_priority = decision_engine_config.get("local_priority", False)

        # Normalize model name: "default" -> actual default model
        requested_model = config.get("model_name", "default")
        if requested_model == "default":
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

        # Check GPU capability and warn about model compatibility
        self._check_gpu_compatibility()

        # Ensure model is available (auto-download if needed)
        self._ensure_model_available()

        # Ensure secondary model exists for robustness (required)
        try:
            # Use configured local_models if available, else defaults
            if self.local_models:
                secondary_candidates = (
                    self.local_models[1:]
                    if len(self.local_models) > 1
                    else [self.SECONDARY_MODEL]
                )
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

        # Mark as initialized and record connection time
        self._initialized = True
        self._connection_time = datetime.now(timezone.utc)
        logger.info("Local LLM provider initialized successfully (singleton instance)")

    def _check_ollama_installed(self) -> bool:
        """
        Check if Ollama is accessible via HTTP API.

        Returns:
            bool: True if Ollama is available
        """
        try:
            # Test connection by listing models
            models_response = self.ollama_client.list()
            available_models = (
                models_response.models
                if hasattr(models_response, "models")
                else models_response.get("models", [])
            )
            logger.info(
                f"Ollama connected successfully. Available models: {len(available_models)}"
            )
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Ollama: {e}")
            logger.error(
                "Make sure Ollama is running and OLLAMA_HOST environment variable is set correctly"
            )
            return False

    def _check_gpu_compatibility(self) -> None:
        """
        Check GPU compute capability and warn about model compatibility.

        CUDA fp16 models require compute capability ≥ 5.3 for stable operation.
        Quantized models (q4_0, q8_0) are more compatible across GPU generations.

        Logs warnings if fp16 models are used with potentially incompatible GPUs.
        """
        try:
            # Check if model uses fp16
            if 'fp16' in self.model_name.lower():
                logger.warning(
                    f"Using fp16 model: {self.model_name}. "
                    "This requires CUDA compute capability ≥ 5.3 and may cause segfaults on older GPUs."
                )

                # Try to detect GPU compute capability (best effort)
                try:
                    result = subprocess.run(
                        ["nvidia-smi", "--query-gpu=compute_cap", "--format=csv,noheader"],
                        capture_output=True,
                        text=True,
                        timeout=5
                    )
                    if result.returncode == 0 and result.stdout.strip():
                        compute_caps = [float(cap) for cap in result.stdout.strip().split('\n')]
                        min_compute_cap = min(compute_caps)

                        if min_compute_cap < 5.3:
                            logger.error(
                                f"GPU compute capability {min_compute_cap} is below minimum 5.3 for fp16 models. "
                                f"Segmentation faults likely. Recommend using quantized model: "
                                f"llama3.2:3b-instruct-q4_0"
                            )
                        else:
                            logger.info(f"GPU compute capability {min_compute_cap} is sufficient for fp16 models")
                except FileNotFoundError:
                    logger.info("nvidia-smi not found, skipping GPU capability check (CPU mode or non-NVIDIA GPU)")
                except Exception as e:
                    logger.debug(f"Could not detect GPU compute capability: {e}")
            else:
                logger.info(f"Using quantized model: {self.model_name} (GPU-compatible)")
        except Exception as e:
            logger.debug(f"GPU compatibility check failed (non-critical): {e}")

    def _install_ollama(self) -> bool:
        """
        Automatically install Ollama based on platform.

        Returns:
            bool: True if installation successful
        """
        import os
        import platform
        import tempfile

        system = platform.system()
        logger.info(f"Detected platform: {system}")

        temp_script_path = None
        try:
            if system == "Linux" or system == "Darwin":  # Linux or macOS
                logger.info(f"Installing Ollama on {system}...")

                # Download script first to avoid shell injection
                with tempfile.NamedTemporaryFile(
                    mode="w+", delete=False, suffix=".sh"
                ) as temp_script:
                    # Download the install script to a temporary file
                    import requests

                    response = requests.get("https://ollama.ai/install.sh", timeout=60)
                    response.raise_for_status()
                    temp_script.write(response.text)
                    temp_script_path = temp_script.name

                try:
                    # Run the downloaded script safely
                    result = subprocess.run(
                        [temp_script_path],
                        capture_output=True,
                        text=True,
                        timeout=300,  # 5 minutes
                    )

                    if result.returncode != 0:
                        logger.error("Installation failed: %s", result.stderr)
                        raise RuntimeError(
                            "Ollama installation failed: %s" % result.stderr
                        )

                    logger.info(f"Ollama installed successfully on {system}")
                    logger.info(f"Installation output: {result.stdout}")
                finally:
                    # Clean up the temporary script file
                    if temp_script_path is not None and os.path.exists(
                        temp_script_path
                    ):
                        try:
                            os.unlink(temp_script_path)
                        except Exception as cleanup_error:
                            logger.warning(
                                f"Failed to clean up temporary script: {cleanup_error}"
                            )

            elif system == "Windows":
                logger.error("Automatic installation not supported on Windows")
                raise RuntimeError(
                    "Automatic Ollama installation not supported on Windows.\n"
                    "Please download and install manually from: "
                    "https://ollama.ai/download\n"
                    "After installation, restart your terminal and try again."
                )
            else:
                raise RuntimeError(f"Unsupported platform: {system}")

            # Verify installation by checking if Ollama service responds
            try:
                self.ollama_client.list()
                logger.info("Installation verified: Ollama service is responding")
                return True
            except Exception as e:
                raise RuntimeError(f"Ollama installed but service verification failed: {e}")

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
        logger.info(f"Model {self.model_name} not found locally. " f"Downloading...")
        logger.info("This is a one-time download. Please wait...")

        # Attempt to download requested model
        if self._download_model(self.model_name):
            logger.info(f"Successfully downloaded {self.model_name}")
            return

        # Download failed - try fallback if we were trying primary
        if self.model_name == self.DEFAULT_MODEL:
            logger.warning(
                f"Failed to download primary model {self.DEFAULT_MODEL}. "
                f"Trying fallback {self.FALLBACK_MODEL}..."
            )

            if self._download_model(self.FALLBACK_MODEL):
                self.model_name = self.FALLBACK_MODEL
                logger.info(f"Using fallback model: {self.FALLBACK_MODEL}")
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
        Download a specific model from Ollama library via HTTP API.

        Args:
            model_name: Name of model to download (e.g.,
                'llama3.2:3b-instruct-fp16')

        Returns:
            bool: True if download successful, False otherwise
        """
        try:
            logger.info(f"Downloading {model_name} from Ollama library...")
            logger.info("This may take several minutes depending on your connection.")

            # Pull model via HTTP API
            self.ollama_client.pull(model_name)

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

        except Exception as e:
            logger.error(f"Error downloading {model_name}: {e}")
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

            # Use HTTP API to delete the model
            self.ollama_client.delete(model_name)

            # Verify deletion
            if self._is_model_available(model_name):
                logger.warning(f"Model {model_name} still available after deletion")
                return False

            logger.info(
                f"Model {model_name} deleted successfully. " f"Freed ~2.5GB disk space."
            )
            return True

        except Exception as e:
            logger.warning(f"Failed to delete model {model_name}: {e}")
            return False

    def _unload_model(self) -> None:
        """
        Unload the current model from GPU memory to free resources.

        This is called after each query to allow sequential loading
        of different models without memory conflicts.

        Note: In Docker/HTTP mode, Ollama manages model memory automatically.
        This is a no-op when using the HTTP API.
        """
        # Ollama HTTP API doesn't expose a stop/unload endpoint
        # The Ollama server manages model memory automatically
        # Note: active_model not in scope here, would need to be passed or stored
        logger.debug(f"Model memory managed by Ollama (no explicit unload needed)")

    def _is_model_available(self, model_name: str) -> bool:
        """Check if model is available locally via HTTP API."""
        try:
            models_response = self.ollama_client.list()
            # Handle both dict and typed response
            available_models = (
                models_response.models
                if hasattr(models_response, "models")
                else models_response.get("models", [])
            )

            # Check both full name and short name
            model_base = model_name.split(":")[0].lower()
            for model in available_models:
                # Handle both dict and typed Model object
                model_full_name = (
                    model.model if hasattr(model, "model") else model.get("name", "")
                ).lower()
                if (
                    model_name.lower() in model_full_name
                    or model_base in model_full_name
                ):
                    return True

            return False

        except Exception as e:
            logger.error(f"Error checking model availability: {e}")
            return False

    def check_connection_health(self) -> bool:
        """
        Verify LLM connection is healthy (Phase 2 optimization).

        Returns:
            bool: True if connection is healthy, False otherwise
        """
        try:
            # Simple health check - verify Ollama is responsive via HTTP API
            self.ollama_client.list()
            logger.debug("LLM connection health check: OK")
            return True

        except Exception as e:
            logger.warning(f"LLM connection health check failed: {e}")
            return False

    def ensure_connection(self) -> None:
        """
        Ensure connection is healthy, reconnect if needed (Phase 2 optimization).

        For Ollama (subprocess-based), this primarily validates that the
        Ollama service is running and responsive.
        """
        if not self.check_connection_health():
            logger.info("LLM connection unhealthy, verifying Ollama installation")

            # Re-verify Ollama is installed and models are available
            if not self._check_ollama_installed():
                raise RuntimeError("Ollama connection lost and reinstallation failed")

            # Verify our model is still available
            if not self._is_model_available(self.model_name):
                logger.warning(
                    f"Model {self.model_name} no longer available, re-downloading"
                )
                self._ensure_model_available()

            logger.info("LLM connection restored")

    def raw_query(
        self,
        prompt: str,
        model_name: str = None,
        system_prompt: Optional[str] = None,
        response_format: Optional[str] = "json",
        request_timeout_s: Optional[float] = None,
    ) -> str:
        """
        Query local LLM without injecting the trading advisor wrapper.

        This is intended for auxiliary structured tasks (for example pre-reason
        market briefs) that need direct control of the prompt/schema and should
        not be parsed as a trading decision.
        """
        active_model = model_name or self.model_name

        if active_model != self.model_name and not self._is_model_available(active_model):
            logger.warning("Requested model %s not available, downloading...", active_model)
            if not self._download_model(active_model):
                logger.error(
                    "Failed to download %s, falling back to %s",
                    active_model,
                    self.model_name,
                )
                active_model = self.model_name

        logger.info(
            "Using raw local LLM query with model: %s (instance default: %s)",
            active_model,
            self.model_name,
        )
        ensure_connection_started = time.perf_counter()
        self.ensure_connection()
        ensure_connection_s = time.perf_counter() - ensure_connection_started

        max_retries = self.config.get("decision_engine", {}).get("max_retries", 3)
        llm_timeout = request_timeout_s or self.config.get("api_timeouts", {}).get("llm_query", 120)
        full_prompt = (
            f"{system_prompt.strip()}\n\n{prompt}" if system_prompt else prompt
        )

        for attempt in range(max_retries):
            try:
                logger.info(
                    "Querying local LLM raw mode: %s (attempt %d/%d)",
                    active_model,
                    attempt + 1,
                    max_retries,
                )

                from concurrent.futures import ThreadPoolExecutor

                request_kwargs = {
                    "model": active_model,
                    "prompt": full_prompt,
                    "options": {
                        "temperature": 0.7,
                        "top_p": 0.9,
                    },
                }
                if response_format:
                    request_kwargs["format"] = response_format

                generate_started = time.perf_counter()
                with ThreadPoolExecutor(max_workers=1) as executor:
                    future = executor.submit(self.ollama_client.generate, **request_kwargs)
                    try:
                        response = future.result(timeout=llm_timeout)
                    except Exception:
                        future.cancel()
                        raise
                generate_s = time.perf_counter() - generate_started
                response_text = response.get("response", "").strip()
                if response_text:
                    logger.info(
                        "Raw local LLM success | model=%s ensure_connection_s=%.3f generate_s=%.3f timeout_s=%s response_chars=%d",
                        active_model,
                        ensure_connection_s,
                        generate_s,
                        llm_timeout,
                        len(response_text),
                    )
                    logger.debug("Raw local LLM response: %s", response_text[:200])
                    self._unload_model()
                    return response_text

                logger.warning(
                    "Empty raw response from LLM on attempt %d/%d",
                    attempt + 1,
                    max_retries,
                )
            except TimeoutError:
                logger.error(
                    "Raw local LLM query timed out after %ss on attempt %d | model=%s ensure_connection_s=%.3f",
                    llm_timeout,
                    attempt + 1,
                    active_model,
                    ensure_connection_s,
                )
            except Exception as e:
                logger.warning(
                    "Raw local LLM query failed on attempt %d/%d: %s",
                    attempt + 1,
                    max_retries,
                    e,
                )

            if attempt < max_retries - 1:
                time.sleep(2 * (attempt + 1))

        self._unload_model()
        raise RuntimeError(
            f"Local raw query failed after {max_retries} attempts for model {active_model}"
        )

    def query(
        self,
        prompt: str,
        model_name: str = None,
        request_label: Optional[str] = None,
        request_timeout_s: Optional[float] = None,
    ) -> Dict[str, Any]:
        """
        Query local LLM with connection pooling (Phase 2 optimization).

        Connection is verified before use, eliminating 1-2s initialization overhead.

        Args:
            prompt: Trading analysis prompt
            model_name: Optional model override (defaults to instance model_name)

        Returns:
            Dictionary with action, confidence, reasoning, amount
        """
        # Use provided model or fall back to instance default
        active_model = model_name or self.model_name
        
        # Ensure the requested model is available (auto-download if needed)
        if active_model != self.model_name and not self._is_model_available(active_model):
            logger.warning(f"Requested model {active_model} not available, downloading...")
            if not self._download_model(active_model):
                logger.error(f"Failed to download {active_model}, falling back to {self.model_name}")
                active_model = self.model_name
        
        logger.info(
            f"Using model: {active_model} (instance default: {self.model_name})"
            + (f" request_label={request_label}" if request_label else "")
        )
        # Verify connection before query (Phase 2 optimization)
        ensure_connection_started = time.perf_counter()
        self.ensure_connection()
        ensure_connection_s = time.perf_counter() - ensure_connection_started

        # Get max_retries from config (defaults to 3)
        max_retries = self.config.get("decision_engine", {}).get("max_retries", 3)
        for attempt in range(max_retries):
            try:
                logger.info(
                    f"Querying local LLM: {active_model} (attempt {attempt + 1}/{max_retries})"
                )

                # Create system prompt for trading
                allowed_actions = _extract_allowed_policy_actions(prompt)
                allowed_actions_str = ", ".join(allowed_actions)
                full_prompt = (
                    "You are a professional day trading advisor. "
                    "Analyze market data and provide trading recommendations. "
                    "Respond ONLY with valid JSON containing these exact keys: "
                    f"action (one of {allowed_actions_str}), confidence (0-100 integer), "
                    "reasoning (brief explanation string), "
                    "amount (decimal number for position size). "
                    "Never output an action outside the allowed policy-action list in the prompt.\n\n"
                    f"{prompt}"
                )

                # Call Ollama via HTTP API with timeout protection
                import asyncio
                from concurrent.futures import ThreadPoolExecutor

                # Get LLM timeout from config (default 120s for CPU-based Ollama)
                # CPU inference can take 45-120s for complex prompts
                llm_timeout = request_timeout_s or self.config.get("api_timeouts", {}).get("llm_query", 120)

                generate_started = time.perf_counter()
                try:
                    # Run synchronous Ollama call with timeout
                    with ThreadPoolExecutor(max_workers=1) as executor:
                        future = executor.submit(
                            self.ollama_client.generate,
                            model=active_model,  # Use active_model instead of self.model_name
                            prompt=full_prompt,
                            format="json",
                            options={
                                "temperature": 0.7,
                                "top_p": 0.9,
                            },
                        )
                        try:
                            response = future.result(timeout=llm_timeout)
                        except Exception:
                            future.cancel()
                            raise
                except TimeoutError:
                    generate_wait_s = time.perf_counter() - generate_started
                    logger.error(
                        f"Local LLM query timed out after {llm_timeout}s on attempt {attempt + 1} | "
                        f"request_label={request_label or 'none'} model={active_model} "
                        f"ensure_connection_s={ensure_connection_s:.3f} generate_wait_s={generate_wait_s:.3f}"
                    )
                    if attempt == max_retries - 1:
                        return build_fallback_decision(
                            f"Local LLM timed out after {llm_timeout}s, using fallback decision."
                        )
                    time.sleep(2 * (attempt + 1))
                    continue

                generate_s = time.perf_counter() - generate_started
                response_text = response.get("response", "").strip()

                # Check if response is empty
                if not response_text:
                    logger.warning(
                        f"Empty response from LLM on attempt {attempt + 1}: {response_text}"
                    )

                    # If this is the last attempt, return fallback
                    if attempt == max_retries - 1:
                        return build_fallback_decision(
                            "Local LLM returned empty or error response, using fallback decision."
                        )

                    # Retry with a brief delay
                    time.sleep(2 * (attempt + 1))
                    continue

                logger.debug(f"Raw LLM response: {response_text[:200]}")
                logger.info(
                    "CANDIDATE_AUDIT raw_probe request_label=%s model=%s raw_len=%s has_candidate_key=%s has_policy_action_key=%s raw_prefix=%r",
                    request_label or "none",
                    active_model,
                    len(response_text),
                    'candidate_actions' in response_text,
                    'policy_action' in response_text,
                    response_text[:200],
                )

                decision = try_parse_decision_json(response_text)
                if decision:
                    logger.info(
                        "CANDIDATE_AUDIT local_parse_ok request_label=%s model=%s parsed=%s",
                        request_label or "none",
                        active_model,
                        _candidate_audit_view(decision),
                    )
                    # Safely convert confidence to int (default 60 if missing/invalid)
                    try:
                        confidence_val = decision.get("confidence", 60)
                        decision["confidence"] = (
                            int(confidence_val) if confidence_val is not None else 60
                        )
                    except (ValueError, TypeError):
                        decision["confidence"] = 60

                    # FIX-HOLD-CONF: 72% of HOLD decisions have confidence 0-9%.
                    # Models output low/zero confidence for HOLD, meaning "no trade
                    # conviction" — but downstream systems interpret 0% as "zero
                    # confidence in the HOLD decision itself". Remap to 50% (neutral).
                    if (
                        str(decision.get("action", "")).upper() == "HOLD"
                        and decision["confidence"] < 10
                    ):
                        decision["confidence"] = 50

                    # Safely convert amount to float (get default from config)
                    default_position_size = self.config.get("decision_engine", {}).get("default_position_size", 0.1)
                    try:
                        amount_val = decision.get("amount", default_position_size)
                        decision["amount"] = (
                            float(amount_val) if amount_val is not None else default_position_size
                        )
                    except (ValueError, TypeError):
                        decision["amount"] = default_position_size

                    logger.info(
                        f"Local LLM decision: {decision['action']} "
                        f"({decision['confidence']}%) | request_label={request_label or 'none'} "
                        f"model={active_model} ensure_connection_s={ensure_connection_s:.3f} generate_s={generate_s:.3f}"
                    )

                    # Unload model from memory to free GPU resources for next model
                    self._unload_model()

                    return decision

                logger.info(
                    f"LLM response missing required fields or not JSON on attempt {attempt + 1}, "
                    f"raw_len={len(response_text)}, raw prefix: {repr(response_text[:200])}"
                )
                self._unload_model()
                is_structured_fragment = any(fragment in response_text for fragment in ("{", "}"))
                if is_structured_fragment and attempt < max_retries - 1:
                    time.sleep(2 * (attempt + 1))
                    continue
                parsed_text_decision = self._parse_text_response(response_text)
                logger.info(
                    "CANDIDATE_AUDIT local_text_fallback request_label=%s model=%s parsed=%s",
                    request_label or "none",
                    active_model,
                    _candidate_audit_view(parsed_text_decision),
                )
                return parsed_text_decision

            except Exception as e:
                logger.error(f"Local LLM error on attempt {attempt + 1}: {e}")

                # If this is the last attempt, return fallback
                if attempt == max_retries - 1:
                    return build_fallback_decision(
                        f"Local LLM error after multiple attempts: {str(e)}, using fallback decision."
                    )

                # Retry with a brief delay
                time.sleep(2 * (attempt + 1))

        # This should never be reached due to the return statements in the loop,
        # but included for completeness
        return build_fallback_decision(
            "Local LLM failed after all retries, using fallback decision."
        )

    def _parse_text_response(self, text: str) -> Dict[str, Any]:
        """Parse text response for trading decision."""
        # If text contains JSON fragments, attempt structured extraction first
        if any(fragment in text for fragment in ("{", "}")):
            from .decision_validation import extract_json_from_text, try_parse_decision_json
            extracted = extract_json_from_text(text)
            decision = try_parse_decision_json(extracted)
            if decision:
                logger.info("Recovered valid decision from structured response fragment")
                return decision
            logger.warning(
                f"Could not recover decision from structured fragment "
                f"(extracted_len={len(extracted)}, raw_len={len(text)}), "
                f"falling through to text parsing"
            )

        text_upper = text.upper()

        # Extract action
        if "BUY" in text_upper and "SELL" not in text_upper:
            action = "BUY"
        elif "SELL" in text_upper and "BUY" not in text_upper:
            action = "SELL"
        else:
            action = "HOLD"

        # Extract confidence
        confidence_match = re.search(r"(\d+)\s*%", text)
        confidence = int(confidence_match.group(1)) if confidence_match else 65

        # Extract reasoning (first meaningful line)
        lines = [line.strip() for line in text.split("\n") if line.strip()]
        reasoning = lines[0][:200] if lines else "Local LLM analysis"

        # Extract amount
        amount_match = re.search(r"(\d+\.?\d*)\s*(BTC|ETH|units?)", text, re.IGNORECASE)
        amount = float(amount_match.group(1)) if amount_match else 0.1

        return {
            "action": action,
            "confidence": confidence,
            "reasoning": reasoning,
            "amount": amount,
            "model_name": self.model_name,  # Include provider model used
        }

    def get_model_info(self) -> Dict[str, Any]:
        """Get information about the loaded model."""
        try:
            # Use HTTP API to get model information
            result = self.ollama_client.show(self.model_name)

            # Convert result to string format for consistency
            info_str = str(result) if result else "No information available"

            return {
                "model_name": self.model_name,
                "status": "available",
                "info": info_str,
            }

        except Exception as e:
            return {"model_name": self.model_name, "status": "error", "info": str(e)}

    def get_connection_stats(self) -> Dict[str, Any]:
        """
        Get connection statistics for monitoring (Phase 2 optimization).

        Returns:
            Dictionary with connection metadata
        """
        uptime_seconds = (
            (datetime.now(timezone.utc) - self._connection_time).total_seconds()
            if self._connection_time
            else 0
        )

        return {
            "is_singleton": True,
            "initialized": self._initialized,
            "connection_time": (
                self._connection_time.isoformat() if self._connection_time else None
            ),
            "uptime_seconds": uptime_seconds,
            "uptime_hours": uptime_seconds / 3600,
            "model_name": self.model_name,
            "connection_healthy": self.check_connection_health(),
        }
