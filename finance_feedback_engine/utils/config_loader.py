import yaml
import os
import re
from typing import Any, Dict

def load_config(config_path: str) -> Dict[str, Any]:
    """
    Loads a YAML configuration file, resolving environment variables.

    This function securely loads a YAML file using yaml.safe_load() and
    then traverses the loaded configuration to resolve any placeholders
    in the format "${ENV_VAR_NAME}" with their corresponding environment
    variable values. If a required environment variable is not set, it
    will raise a ValueError.

    Implementation Notes:
    - **Security:** Always use `yaml.safe_load()` to prevent arbitrary code
      execution from untrusted YAML sources. This is critical in financial
      applications.
    - **Environment Variable Integration:** The function iterates through
      the loaded dictionary and replaces string values matching the
      `${ENV_VAR_NAME}` pattern with the actual environment variable's value.
      This ensures sensitive information (like API keys) is not hardcoded
      in the YAML files.
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
    if not os.path.exists(config_path):
        raise FileNotFoundError(f"Configuration file not found: {config_path}")

    with open(config_path, 'r') as f:
        # TODO: Implement a custom YAML loader that handles environment variables
        # directly during parsing for potentially cleaner code, rather than post-processing.
        # However, for simplicity and explicit security (safe_load first), post-processing is fine.
        config = yaml.safe_load(f)

    # Regex to find ${ENV_VAR_NAME} patterns
    env_var_pattern = re.compile(r'\$\{(\w+)\}')

    def resolve_env_vars(data: Any) -> Any:
        if isinstance(data, dict):
            return {k: resolve_env_vars(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [resolve_env_vars(elem) for elem in data]
        elif isinstance(data, str):
            def replace_env_var(match):
                env_var_name = match.group(1)
                env_var_value = os.getenv(env_var_name)
                if env_var_value is None:
                    raise ValueError(
                        f"Environment variable '{env_var_name}' required by configuration "
                        f"'{config_path}' is not set. Please set it."
                    )
                return env_var_value
            return env_var_pattern.sub(replace_env_var, data)
        return data

    return resolve_env_vars(config)

# Example Usage (for demonstration within this stub)
if __name__ == "__main__":
    # TODO: Create a dummy config file for this example or assume a test config path
    # For now, let's just show how it would be called.
    # config_file = "config/test_config.yaml"
    # os.environ["TEST_API_KEY"] = "my_secret_key_123"
    # try:
    #     app_config = load_config(config_file)
    #     print("Loaded Configuration:")
    #     print(app_config)
    #     # Example of accessing a value: print(app_config['api']['key'])
    # except (FileNotFoundError, ValueError, yaml.YAMLError) as e:
    #     print(f"Error loading configuration: {e}")
    # finally:
    #     # Clean up environment variable
    #     if "TEST_API_KEY" in os.environ:
    #         del os.environ["TEST_API_KEY"]
    pass
