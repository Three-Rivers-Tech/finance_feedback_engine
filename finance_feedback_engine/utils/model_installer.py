"""Automatic Ollama model installer with parallel downloads and progress tracking."""

import json
import logging
import shutil
import subprocess
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import Any, Dict, List, Optional

try:
    from tqdm import tqdm
except ImportError:
    tqdm = None

from ..decision_engine.provider_tiers import (
    get_ollama_models,
    MODEL_DOWNLOAD_SIZES,
    get_total_download_size
)

logger = logging.getLogger(__name__)


class ModelInstaller:
    """Handles automatic installation of Ollama models with progress tracking."""
    
    def __init__(self, data_dir: str = "data"):
        """
        Initialize model installer.
        
        Args:
            data_dir: Directory for storing installation state
        """
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)
        self.state_file = self.data_dir / ".models_installed"
    
    def _load_state(self) -> Dict[str, Dict[str, Any]]:
        """
        Load installation state from file.
        
        Returns:
            Dictionary mapping model names to installation state
        """
        if not self.state_file.exists():
            return {}
        
        try:
            with open(self.state_file, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Could not load installation state: {e}")
            return {}
    
    def _save_state(self, state: Dict[str, Dict[str, Any]]):
        """
        Save installation state to file.
        
        Args:
            state: Dictionary mapping model names to installation state
        """
        try:
            with open(self.state_file, 'w') as f:
                json.dump(state, f, indent=2)
        except IOError as e:
            logger.error(f"Could not save installation state: {e}")
    
    def _check_disk_space(self, required_gb: float) -> bool:
        """
        Check if sufficient disk space is available.
        
        Args:
            required_gb: Required space in GB
        
        Returns:
            True if sufficient space available
        """
        try:
            stat = shutil.disk_usage(self.data_dir)
            free_gb = stat.free / (1024 ** 3)
            
            if free_gb < required_gb:
                logger.error(
                    f"Insufficient disk space: {free_gb:.1f}GB available, "
                    f"{required_gb:.1f}GB required"
                )
                return False
            
            logger.info(f"Disk space check: {free_gb:.1f}GB available")
            return True
            
        except Exception as e:
            logger.warning(f"Could not check disk space: {e}")
            return True  # Proceed if check fails
    
    def _check_ollama_installed(self) -> bool:
        """
        Check if Ollama is installed and accessible.
        
        Returns:
            True if Ollama is installed
        """
        try:
            result = subprocess.run(
                ['ollama', '--version'],
                capture_output=True,
                text=True,
                timeout=5
            )
            return result.returncode == 0
        except (subprocess.TimeoutExpired, FileNotFoundError):
            return False
    
    def _get_installed_models(self) -> List[str]:
        """
        Get list of currently installed Ollama models.
        
        Returns:
            List of installed model names
        """
        try:
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            if result.returncode != 0:
                return []
            
            # Parse output (skip header line)
            lines = result.stdout.strip().split('\n')[1:]
            models = []
            for line in lines:
                if line.strip():
                    # Model name is first column
                    model_name = line.split()[0]
                    models.append(model_name)
            
            return models
            
        except Exception as e:
            logger.warning(f"Could not list installed models: {e}")
            return []
    
    def _download_model(self, model: str, use_progress: bool = True) -> bool:
        """
        Download a single Ollama model.
        
        Args:
            model: Model name to download
            use_progress: Whether to show progress bar
        
        Returns:
            True if download successful
        """
        size_gb = MODEL_DOWNLOAD_SIZES.get(model, 0)
        desc = f"Downloading {model} (~{size_gb:.1f}GB)"
        
        try:
            if use_progress and tqdm is not None:
                # Show progress bar
                with tqdm(total=100, desc=desc, unit='%', leave=True) as pbar:
                    process = subprocess.Popen(
                        ['ollama', 'pull', model],
                        stdout=subprocess.PIPE,
                        stderr=subprocess.STDOUT,
                        text=True
                    )
                    
                    last_progress = 0
                    for line in process.stdout:
                        # Try to parse progress from output
                        if '%' in line:
                            try:
                                # Extract percentage (e.g., "pulling... 45%")
                                parts = line.split('%')
                                if parts:
                                    pct_str = parts[0].split()[-1]
                                    pct = float(pct_str)
                                    progress_delta = pct - last_progress
                                    if progress_delta > 0:
                                        pbar.update(progress_delta)
                                        last_progress = pct
                            except (ValueError, IndexError):
                                pass
                    
                    try:
                        process.wait(timeout=600)  # 10 minute timeout
                    except subprocess.TimeoutExpired:
                        process.kill()
                        logger.error(f"Timeout downloading {model}")
                        return False
                    pbar.update(100 - last_progress)  # Ensure we reach 100%
                    if process.returncode != 0:
                        return False
                    # Verify model after successful pull
                    return self._verify_model(model)
            else:
                # No progress bar
                logger.info(desc)
                result = subprocess.run(
                    ['ollama', 'pull', model],
                    capture_output=True,
                    timeout=600  # 10 minute timeout
                )
                if result.returncode != 0:
                    return False
                return self._verify_model(model)
                
        except subprocess.TimeoutExpired:
            logger.error(f"Timeout downloading {model}")
            return False
        except KeyboardInterrupt:
            logger.warning(f"Download interrupted for {model}")
            return False
        except Exception as e:
            logger.error(f"Error downloading {model}: {e}")
            return False

    def _verify_model(self, model: str) -> bool:
        """
        Verify that an Ollama model is present and has a valid digest.

        Args:
            model: Model name/tag to verify

        Returns:
            True if verification succeeds
        """
        try:
            # Prefer 'ollama list' parsing for version-safe verification
            result = subprocess.run(
                ['ollama', 'list'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode != 0:
                logger.error(
                    f"Verification failed for {model}: 'ollama list' returned {result.returncode}\n{result.stderr}"
                )
                return False

            lines = [ln.strip() for ln in result.stdout.strip().split('\n') if ln.strip()]
            # Detect header: look for known keywords or separators
            header_keywords = {'name', 'model', 'tag', 'digest', 'created', 'size'}
            header_found = False
            if lines:
                first_line = lines[0].lower()
                if any(h in first_line for h in header_keywords) or ('  ' in first_line):
                    header_found = True
            entries = lines[1:] if header_found else lines

            installed = set()
            for ln in entries:
                try:
                    name = ln.split()[0].strip().lower()
                    if name:
                        installed.add(name)
                except Exception:
                    continue

            # Normalize requested model
            req_norm = model.strip().lower()
            # Accept exact match, startswith, or base-name match (before colon or dash)
            matched_name = None
            for inst_name in installed:
                # Match exact, or base name before common separators (: or -)
                base_colon = inst_name.split(':')[0]
                base_dash = inst_name.split('-')[0]
                if (
                    inst_name == req_norm
                    or base_colon == req_norm
                    or base_dash == req_norm
                ):
                    matched_name = inst_name
                    break
            if matched_name:
                logger.info(f"Verified {model} is installed (matched: {matched_name})")
                return True

            # Fallback: attempt a lightweight show with JSON format to verify digest
            show = subprocess.run(
                ['ollama', 'show', model, '--format', 'json'],
                capture_output=True,
                text=True,
                timeout=10
            )
            if show.returncode == 0:
                try:
                    show_data = json.loads(show.stdout)
                    if 'digest' in show_data and show_data['digest']:
                        logger.info(f"Verified {model} via 'ollama show' output")
                        return True
                    else:
                        logger.error(f"Verification failed for {model}: missing digest in show output")
                        return False
                except json.JSONDecodeError:
                    logger.error(f"Verification failed for {model}: invalid JSON from 'ollama show'")
                    return False

            logger.error(f"Verification failed for {model}: not listed by 'ollama list' and 'ollama show' failed ({show.returncode})")
            return False
        except subprocess.TimeoutExpired:
            logger.error(f"Verification timed out for {model}")
            return False
        except Exception as e:
            logger.error(f"Error verifying {model}: {e}")
            return False
    
    def _download_models_parallel(
        self,
        models_to_install: List[str],
        max_workers: int = 2
    ) -> Dict[str, bool]:
        """
        Download multiple models in parallel.
        
        Args:
            models_to_install: List of model names to download
            max_workers: Maximum parallel downloads
        
        Returns:
            Dictionary mapping model names to success status
        """
        results = {}
        
        # Use ThreadPoolExecutor for parallel downloads
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            # Submit all download tasks
            future_to_model = {
                executor.submit(self._download_model, model): model
                for model in models_to_install
            }
            
            # Process completed downloads
            for future in as_completed(future_to_model):
                model = future_to_model[future]
                try:
                    success = future.result()
                    results[model] = success
                    
                    if success:
                        logger.info(f"✓ Successfully installed {model}")
                    else:
                        logger.error(f"✗ Failed to install {model}")
                        
                except Exception as e:
                    logger.error(f"✗ Exception installing {model}: {e}")
                    results[model] = False
        
        return results
    
    def ensure_models_installed(self, force_reinstall: bool = False) -> bool:
        """
        Ensure all required Ollama models are installed.
        
        This function:
        1. Checks disk space
        2. Verifies Ollama is installed
        3. Checks which models are already installed
        4. Downloads missing models in parallel (max 2 workers)
        5. Tracks installation state for resumption
        
        Args:
            force_reinstall: Force reinstallation of all models
        
        Returns:
            True if all models successfully installed
        """
        required_models = get_ollama_models()
        
        if not required_models:
            logger.info("No Ollama models required")
            return True
        
        # Check Ollama installation
        if not self._check_ollama_installed():
            logger.error(
                "Ollama is not installed. Please install from: "
                "https://ollama.ai/download"
            )
            print(
                "\n⚠️  Ollama is not installed!\n"
                "Please install Ollama from: https://ollama.ai/download\n"
                "Then run this command again.\n",
                file=sys.stderr
            )
            return False
        
        # Check disk space
        total_size = get_total_download_size()
        if not self._check_disk_space(total_size + 5):  # +5GB buffer
            print(
                f"\n⚠️  Insufficient disk space!\n"
                f"Required: ~{total_size:.1f}GB (plus 5GB buffer)\n"
                f"Please free up disk space and try again.\n",
                file=sys.stderr
            )
            return False
        
        # Load installation state
        state = self._load_state()
        
        # Get currently installed models
        installed = self._get_installed_models()
        
        # Determine which models need installation
        models_to_install = []
        for model in required_models:
            if force_reinstall:
                models_to_install.append(model)
            elif model not in installed:
                # Check if partially installed
                model_state = state.get(model, {})
                if not model_state.get('download_complete', False):
                    models_to_install.append(model)
        
        if not models_to_install:
            logger.info("All required models already installed")
            return True
        
        # Show installation summary
        print(f"\n📦 Installing {len(models_to_install)} Ollama models...")
        print(f"Total download size: ~{sum(MODEL_DOWNLOAD_SIZES.get(m, 0) for m in models_to_install):.1f}GB")
        print("Parallel downloads: 2 workers\n")
        
        # Download models in parallel, with a simple retry on verification failure
        results = self._download_models_parallel(models_to_install, max_workers=2)

        # Retry once for any model that failed verification/download
        failed_once = [m for m, s in results.items() if not s]
        if failed_once:
            logger.info(f"Retrying failed models once: {', '.join(failed_once)}")
            retry_results = self._download_models_parallel(failed_once, max_workers=1)
            # Merge: prefer retry outcome
            results.update(retry_results)
        
        # Update installation state
        for model, success in results.items():
            state[model] = {
                'installed': success,
                'download_complete': success,
                'size_gb': MODEL_DOWNLOAD_SIZES.get(model, 0)
            }
        
        self._save_state(state)
        
        # Check if all installations succeeded
        all_success = all(results.values())
        
        if all_success:
            print("\n✅ All models successfully installed!\n")
            logger.info("Model installation complete")
        else:
            failed = [m for m, s in results.items() if not s]
            print(f"\n⚠️  Some models failed to install: {', '.join(failed)}\n")
            logger.error(f"Failed to install: {failed}")
        
        return all_success

_installer: Optional[ModelInstaller] = None


def get_installer(data_dir: str = "data") -> ModelInstaller:
    """
    Get global ModelInstaller instance.

    Args:
        data_dir: Data directory path

    Returns:
        ModelInstaller instance
    """
    global _installer
    if _installer is None:
        _installer = ModelInstaller(data_dir)
    elif _installer.data_dir != Path(data_dir):
        logger.warning(
            "Ignoring data_dir=%s, installer already initialized with data_dir=%s",
            data_dir, _installer.data_dir
        )
    return _installer


def ensure_models_installed(force_reinstall: bool = False) -> bool:
    """
    Convenience function to ensure models are installed.
    
    Args:
        force_reinstall: Force reinstallation of all models
    
    Returns:
        True if all models successfully installed
    """
    installer = get_installer()
    return installer.ensure_models_installed(force_reinstall)
