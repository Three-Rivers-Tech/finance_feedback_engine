"""YAML loader with environment variable substitution.

This module provides a YAML loader that substitutes environment variables
using the ${VAR:-default} syntax before parsing, ensuring .env values
override YAML placeholders.

Example YAML:
    api_key: "${COINBASE_API_KEY:-YOUR_API_KEY}"

With COINBASE_API_KEY="real_key_123" in .env, loads as:
    api_key: "real_key_123"

Without the env var, loads as:
    api_key: "YOUR_API_KEY"
"""

import logging
import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def _load_dotenv_if_needed():
    """Ensure .env is loaded before YAML substitution."""
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        logger.debug(f"Loaded .env from {env_path}")
    else:
        load_dotenv(override=False)
        logger.debug("Loaded .env from current directory")


def substitute_env_vars(yaml_content: str, load_dotenv: bool = True) -> str:
    """
    Substitute environment variables in YAML content.

    Supports two syntaxes:
    - ${VAR:-default}  →  os.getenv("VAR", "default")
    - ${VAR}           →  os.getenv("VAR", "")

    Args:
        yaml_content: Raw YAML string with ${VAR} placeholders
        load_dotenv: Whether to load .env file first (default True)

    Returns:
        YAML string with environment variables substituted

    Example:
        >>> os.environ["API_KEY"] = "secret123"
        >>> substitute_env_vars('key: "${API_KEY:-default}"')
        'key: "secret123"'
    """
    if load_dotenv:
        _load_dotenv_if_needed()

    # Pattern: ${VAR:-default} or ${VAR}
    pattern = re.compile(r'\$\{([^}:]+)(?::[-]?([^}]*))?\}')

    def replacer(match):
        var_name = match.group(1)
        default_value = match.group(2) if match.group(2) is not None else ""
        env_value = os.getenv(var_name)

        if env_value is not None:
            # Environment variable found - use it
            result = env_value
            logger.debug(f"Substituted ${{{var_name}}} → <env value>")
        else:
            # Use default
            result = default_value
            if default_value:
                logger.debug(f"Substituted ${{{var_name}}} → {default_value} (default)")
            else:
                logger.warning(
                    f"Environment variable '{var_name}' not found and no default provided"
                )

        return result

    substituted = pattern.sub(replacer, yaml_content)
    return substituted


def load_yaml_with_env_substitution(yaml_path: Path) -> Dict[str, Any]:
    """
    Load YAML file with environment variable substitution.

    Args:
        yaml_path: Path to YAML file

    Returns:
        Parsed configuration dictionary with env vars substituted

    Raises:
        FileNotFoundError: If YAML file doesn't exist
        yaml.YAMLError: If YAML parsing fails

    Example:
        >>> config = load_yaml_with_env_substitution(Path("config.yaml"))
        >>> # All ${VAR} in YAML have been replaced with actual values
    """
    if not yaml_path.exists():
        raise FileNotFoundError(f"Config file not found: {yaml_path}")

    with open(yaml_path, "r", encoding="utf-8") as f:
        raw_content = f.read()

    # Log original content (truncated for security)
    logger.debug(f"Loading YAML from {yaml_path} ({len(raw_content)} bytes)")

    # Substitute environment variables
    substituted_content = substitute_env_vars(raw_content)

    # Parse YAML
    config = yaml.safe_load(substituted_content)

    logger.info(f"✅ Loaded config from {yaml_path} with env var substitution")
    return config


def validate_env_vars_loaded() -> bool:
    """
    Validate that critical environment variables are loaded.

    Returns:
        True if .env appears to be loaded, False otherwise

    This checks for any of the expected FFE environment variables.
    """
    expected_vars = [
        "ALPHA_VANTAGE_API_KEY",
        "COINBASE_API_KEY",
        "OANDA_API_KEY",
        "DATABASE_URL",
        "ENVIRONMENT",
    ]

    found_vars = [var for var in expected_vars if os.getenv(var)]

    if not found_vars:
        logger.warning(
            "⚠️  No expected environment variables found. "
            "Is .env file present and readable?"
        )
        return False

    logger.debug(f"✅ Found {len(found_vars)}/{len(expected_vars)} expected env vars")
    return True


__all__ = [
    "substitute_env_vars",
    "load_yaml_with_env_substitution",
    "validate_env_vars_loaded",
]
