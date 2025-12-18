import logging
import os
import re
from pathlib import Path
from typing import Any, Dict

import yaml
from dotenv import load_dotenv

logger = logging.getLogger(__name__)


def load_config(config_path: str) -> Dict[str, Any]:
    """
    Loads a YAML configuration file, resolving environment variables securely.

    This function securely loads a YAML file using yaml.safe_load() and
    then traverses the loaded configuration to resolve any placeholders
    in the format "${ENV_VAR_NAME}" with their corresponding environment
    variable values. If a required environment variable is not set, it
    will raise a ValueError.

    Implementation Notes:
    - **Environment Loading:** Automatically loads .env file from project root
      using load_dotenv(override=False) to respect existing environment variables.
    - **Security:** Always use `yaml.safe_load()` to prevent arbitrary code
      execution from untrusted YAML sources. This is critical in financial
      applications.
    - **Environment Variable Integration:** The function iterates through
      the loaded dictionary and replaces string values matching the
      `${ENV_VAR_NAME}` pattern with the actual environment variable's value.
      This ensures sensitive information (like API keys) is not hardcoded
      in the YAML files.
    - **Secure Credential Handling:** The function ensures that sensitive values
      are loaded only from environment variables, never from the config file itself.
      This prevents credentials from being accidentally committed to version control.
    - **Error Handling:** If an environment variable specified in the YAML
      (e.g., `${API_KEY}`) is not found in the system's environment, a
      `ValueError` is raised, prompting the user to set the required variable.
    - **Modularity:** This function provides a centralized, robust way to
      handle configuration loading, separating concerns from other parts of
      the application.

    Args:
        config_path (str): The absolute or relative path to the YAML configuration file.

    Returns:
        Dict[str, Any]: A dictionary containing the loaded and resolved configuration.

    Raises:
        FileNotFoundError: If the configuration file does not exist.
        yaml.YAMLError: If there is an error parsing the YAML file.
        ValueError: If a required environment variable is not set.
    """
    # Load .env file from project root (auto-detect)
    # override=False ensures existing env vars take precedence
    env_path = Path(__file__).parent.parent.parent / ".env"
    if env_path.exists():
        load_dotenv(dotenv_path=env_path, override=False)
        logger.debug(f"Loaded environment variables from {env_path}")
    else:
        # Try loading from current working directory as fallback
        load_dotenv(override=False)
        logger.debug("Attempted to load .env from current directory")

    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, "r") as f:
        config = yaml.safe_load(f)

    # Enhanced regex to find ${ENV_VAR_NAME} patterns with optional default values
    # Pattern: ${ENV_VAR_NAME:default_value} or ${ENV_VAR_NAME}
    env_var_pattern = re.compile(r"\$\{([^}]+)\}")

    # Track which env vars are being used (for debugging)
    used_env_vars = set()
    defaulted_env_vars = set()

    def resolve_env_vars(data: Any) -> Any:
        if isinstance(data, dict):
            return {k: resolve_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [resolve_env_vars(elem) for elem in data]
        elif isinstance(data, str):

            def replace_env_var(match):
                full_match = match.group(1)

                # Handle default values: ENV_VAR_NAME:default_value
                if ":" in full_match:
                    env_var_name, default_value = full_match.split(":", 1)
                    env_var_value = os.getenv(env_var_name.strip())
                    if env_var_value is None:
                        defaulted_env_vars.add(env_var_name.strip())
                        # Log a warning for using default values (as they might contain sensitive info)
                        if (
                            "key" in env_var_name.lower()
                            or "secret" in env_var_name.lower()
                            or "password" in env_var_name.lower()
                        ):
                            logger.warning(
                                f"Using default value for sensitive environment variable '{env_var_name.strip()}'"
                            )
                        return default_value.strip()
                    used_env_vars.add(env_var_name.strip())
                    return env_var_value.strip()
                else:
                    env_var_name = full_match.strip()
                    env_var_value = os.getenv(env_var_name)
                    if env_var_value is None:
                        raise ValueError(
                            f"Environment variable '{env_var_name}' required by configuration "
                            f"'{config_path}' is not set. Please set it in .env or export it."
                        )
                    used_env_vars.add(env_var_name)
                    return env_var_value.strip()

            return env_var_pattern.sub(replace_env_var, data)
        return data

    resolved_config = resolve_env_vars(config)

    # Log summary of env var usage
    if used_env_vars:
        logger.debug(f"Loaded {len(used_env_vars)} environment variables from .env")
    if defaulted_env_vars:
        logger.info(f"Using defaults for {len(defaulted_env_vars)} environment variables")

    return resolved_config


# Example Usage (for demonstration within this stub)
if __name__ == "__main__":
    # Example configuration file content (config/example.yaml):
    # ---
    # api:
    #   key: "${API_KEY}"  # Will be replaced with the value of the API_KEY environment variable
    #   secret: "${API_SECRET:default_secret}"  # Will use API_SECRET env var, or 'default_secret' if not set
    #   timeout: 30
    # database:
    #   password: "${DB_PASSWORD}"  # Will be replaced with the value of the DB_PASSWORD environment variable
    #   host: "localhost"
    # ---
    #
    # Usage:
    # os.environ["API_KEY"] = "my_secret_key_123"
    # os.environ["DB_PASSWORD"] = "my_secure_password"
    # config = load_config("config/example.yaml")
    pass
