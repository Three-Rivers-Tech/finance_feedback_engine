"""Command-line interface for Finance Feedback Engine."""

import click
import logging
import json
import yaml
import subprocess
import sys
import re
import os
import copy
from pathlib import Path
from rich.console import Console
from rich.table import Table
from packaging.requirements import Requirement
# from rich import print as rprint  # unused

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.cli.interactive import start_interactive_session
from finance_feedback_engine.dashboard import (
    PortfolioDashboardAggregator,
    display_portfolio_dashboard
)


console = Console()


def _parse_requirements_file(req_file: Path) -> list:
    """Parse requirements.txt and return list of package names (base names only)."""
    packages = []
    if not req_file.exists():
        return packages
    
    with open(req_file, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith('#'):
                continue
            
            # Remove inline comments
            line = line.split('#')[0].strip()
            if not line:
                continue
            
            # Try using packaging library first (most robust)
            try:
                req = Requirement(line)
                packages.append(req.name)
                continue
            except ImportError:
                pass  # Fall back to regex approach
            except Exception:
                pass  # Invalid requirement, try regex fallback
            
            # Fallback: Use regex to extract package name
            # Handles operators: ~=, !=, <=, <, >, ==, >=
            # Also strips extras [extra1,extra2] and environment markers
            match = re.match(
                r'^([a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?)',
                line
            )
            if match:
                pkg = match.group(1)
                if pkg:
                    packages.append(pkg)
    return packages


def _get_installed_packages() -> dict:
    """Get currently installed packages as dict {name: version}."""
    try:
        result = subprocess.run(
            [sys.executable, '-m', 'pip', 'list', '--format=json'],
            capture_output=True,
            text=True,
            check=True
        )
        installed = json.loads(result.stdout)
        return {pkg['name'].lower(): pkg['version'] for pkg in installed}
    except Exception as e:
        console.print(f"[yellow]Warning: Could not retrieve installed packages: {e}[/yellow]")
        return {}


def _check_dependencies() -> tuple:
    """Check which dependencies are missing. Returns (missing, installed) tuples."""
    req_file = Path('requirements.txt')
    if not req_file.exists():
        return ([], [])
    
    required = _parse_requirements_file(req_file)
    installed_dict = _get_installed_packages()
    
    missing = []
    installed = []
    
    for pkg in required:
        pkg_lower = pkg.lower()
        # Normalize both hyphen and underscore for comparison
        pkg_normalized = pkg_lower.replace('-', '_')
        
        # Check both forms (hyphen and underscore)
        if (pkg_lower in installed_dict or 
            pkg_normalized in installed_dict or
            pkg_lower.replace('_', '-') in installed_dict):
            installed.append(pkg)
        else:
            missing.append(pkg)
    
    return (missing, installed)


def setup_logging(verbose: bool = False):
    """Setup logging configuration."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )


def _deep_merge_dicts(d1: dict, d2: dict) -> dict:
    """Deep merges d2 into d1, overwriting values in d1 with those from d2."""
    for k, v in d2.items():
        if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
            d1[k] = _deep_merge_dicts(d1[k], v)
        else:
            d1[k] = v
    return d1


def _deep_fill_missing(target: dict, source: dict) -> dict:
    """Fill missing keys in target from source without overwriting existing values.

    Recurses into nested dicts so that local overrides remain intact and base
    defaults are used only where keys are absent.
    """
    for k, v in source.items():
        if k not in target:
            target[k] = v
        else:
            if isinstance(target[k], dict) and isinstance(v, dict):
                _deep_fill_missing(target[k], v)
            # if target has a value (not dict) we keep it — do not overwrite
    return target


def load_tiered_config() -> dict:
    """
    Loads configuration from multiple sources with a tiered precedence:
    1. config/config.local.yaml (local overrides - highest file priority)
    2. config/config.yaml (base defaults used only where local is missing)
    3. Environment variables (highest overall precedence)
    """
    import logging
    logger = logging.getLogger(__name__)
    
    base_config_path = Path('config/config.yaml')
    local_config_path = Path('config/config.local.yaml')

    # Prefer local config as the primary file so local values take precedence.
    # Start with local (if present) then fill missing values from base config.
    config = {}
    # 1. Load local config first (preferred)
    if local_config_path.exists():
        with open(local_config_path, 'r', encoding='utf-8') as f:
            local_config = yaml.safe_load(f)
            if local_config:
                config.update(local_config)

    # 2. Load base config and fill missing keys from it
    if base_config_path.exists():
        with open(base_config_path, 'r', encoding='utf-8') as f:
            base_config = yaml.safe_load(f)
            if base_config:
                _deep_fill_missing(config, base_config)
    else:
        logger.warning(f"Base config file not found: {base_config_path}")
    
    # 3. Apply environment variables
    env_var_mappings = {
        'ALPHA_VANTAGE_API_KEY': ('alpha_vantage_api_key',),
        'COINBASE_API_KEY': ('trading_platform', 'coinbase', 'api_key'),
        'COINBASE_API_SECRET': ('trading_platform', 'coinbase', 'api_secret'),
        'COINBASE_PASSPHRASE': ('trading_platform', 'coinbase', 'passphrase'),
        'OANDA_API_KEY': ('trading_platform', 'oanda', 'api_key'),
        'OANDA_ACCOUNT_ID': ('trading_platform', 'oanda', 'account_id'),
        'OANDA_LIVE': ('trading_platform', 'oanda', 'live'), # Boolean conversion needed
        'GEMINI_API_KEY': ('decision_engine', 'gemini', 'api_key'),
        'GEMINI_MODEL_NAME': ('decision_engine', 'gemini', 'model_name'),
        # Add more as needed
    }

    for env_var, config_path_keys in env_var_mappings.items():
        value = os.getenv(env_var)
        if value is not None:
            # Handle boolean conversion for specific keys
            if env_var == 'OANDA_LIVE':
                value = value.lower() == 'true'

            current_level = config
            for i, key in enumerate(config_path_keys):
                if i == len(config_path_keys) - 1: # Last key
                    current_level[key] = value
                else:
                    current_level = current_level.setdefault(key, {})
    
    return config


def load_config(config_path: str) -> dict:
    """
    Load a specific configuration from file.
    This function is for loading explicitly specified config files, not for the
    tiered loading process.
    """
    path = Path(config_path)
    
    if not path.exists():
        raise click.ClickException(
            f"Configuration file not found: {config_path}"
        )
    
    with open(path, 'r', encoding='utf-8') as f:
        if path.suffix in ['.yaml', '.yml']:
            config = yaml.safe_load(f)
            if config is None:
                raise click.ClickException(
                    f"Configuration file {config_path} is empty or invalid YAML"
                )
            return config
        elif path.suffix == '.json':
            config = json.load(f)
            if config is None:
                raise click.ClickException(
                    f"Configuration file {config_path} is empty or invalid JSON"
                )
            return config
        else:
            raise click.ClickException(
                f"Unsupported config format: {path.suffix}"
            )


def _get_nested(config: dict, keys: tuple, default=None):
    """Safely fetch a nested value from a dict."""
    cur = config
    for key in keys:
        if not isinstance(cur, dict) or key not in cur:
            return default
        cur = cur[key]
    return cur


def _set_nested(config: dict, keys: tuple, value):
    """Set a nested value inside a dict, creating intermediate levels."""
    cur = config
    for key in keys[:-1]:
        cur = cur.setdefault(key, {})
    cur[keys[-1]] = value

@click.group(invoke_without_command=True)
@click.option(
    '--config', '-c',
    default=None, # Change default to None
    help='Path to a specific config file (overrides tiered loading)'
)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option(
    '--interactive', '-i', is_flag=True, help='Start in interactive mode'
)
@click.pass_context
def cli(ctx, config, verbose, interactive):
    """Finance Feedback Engine 2.0 - AI-powered trading decision tool."""
    setup_logging(verbose)
    ctx.ensure_object(dict)

    if config: # If a specific config file is provided by the user
        final_config = load_config(config) # Use the old load_config
        ctx.obj['config_path'] = config # Store the path for other commands
    else: # Use tiered loading
        final_config = load_tiered_config()
        # Indicate that tiered loading was used, might not have a single path
        ctx.obj['config_path'] = 'tiered' # Set a placeholder
    
    ctx.obj['config'] = final_config # Store the final config
    ctx.obj['verbose'] = verbose

    # On interactive boot, check versions and prompt for update if needed
    if interactive:
        import subprocess
        import sys
        from importlib.metadata import version, PackageNotFoundError
        from rich.prompt import Confirm
        console.print("\n[bold cyan]Checking AI Provider Versions (interactive mode)...[/bold cyan]\n")
        # Map known packages to provider features for clearer reporting
        libraries = [
            ("coinbase-advanced-py", "Coinbase Advanced"),
            ("oandapyV20", "Oanda API"),
            ("click", "Click CLI"),
            ("rich", "Rich Terminal"),
            ("pyyaml", "PyYAML"),
        ]
        missing_libs = []
        for lib_name, _ in libraries:
            try:
                _ = version(lib_name)
            except PackageNotFoundError:
                missing_libs.append(lib_name)
        cli_tools = [
            ("Ollama", ["ollama", "--version"], "curl -fsSL https://ollama.com/install.sh | sh"),
            ("Copilot CLI", ["copilot", "--version"], "npm i -g @githubnext/github-copilot-cli"),
            ("Qwen CLI", ["qwen", "--version"], "npm i -g @qwen/cli"),
            ("Node.js", ["node", "--version"], "nvm install --lts"),
        ]
        missing_tools = []
        for tool, cmd, upgrade_cmd in cli_tools:
            try:
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
                if result.returncode != 0:
                    missing_tools.append((tool, upgrade_cmd))
            except (subprocess.TimeoutExpired, FileNotFoundError):
                missing_tools.append((tool, upgrade_cmd))
        # Emit a concise status log mapping missing components to AI providers
        import logging as _logging
        _logger = _logging.getLogger(__name__)

        provider_impact = {}
        # Map package/tool -> provider keys
        mapping = {
            'ollama': 'local',
            'copilot': 'cli',
            'qwen': 'qwen',
            'coinbase-advanced-py': 'coinbase',
            'oandapyV20': 'oanda',
            'node': 'cli',
        }

        for lib in missing_libs:
            prov = mapping.get(lib, 'unknown')
            provider_impact.setdefault(prov, []).append(lib)

        for tool, _ in missing_tools:
            key = tool.lower().split()[0] if isinstance(tool, str) else str(tool)
            prov = mapping.get(key, 'unknown')
            provider_impact.setdefault(prov, []).append(tool)

        if provider_impact:
            _logger.info("Interactive startup: provider dependency status:")
            for prov, items in provider_impact.items():
                _logger.info("  %s: missing/outdated -> %s", prov, ', '.join(map(str, items)))

        if missing_libs or missing_tools:
            console.print("[yellow]Some AI provider dependencies are missing or outdated.[/yellow]")
            if Confirm.ask("Would you like to update/install them now?"):
                ctx.invoke(update_ai, update=True)
        start_interactive_session(cli)
        return

    if ctx.invoked_subcommand is None:
        console.print(cli.get_help(ctx))
        return



@cli.command(name='config-editor')
@click.option(
    '--output', '-o',
    default='config/config.local.yaml',
    show_default=True,
    help='Where to write your customized config overlay.'
)
@click.pass_context
def config_editor(ctx, output):
    """Interactive helper to capture API keys and core settings.

    Writes a focused overlay file (defaults to config/config.local.yaml) so your
    secrets are kept separate from the base config/config.yaml defaults.
    """
    base_path = Path('config/config.yaml')
    target_path = Path(output)

    base_config = {}
    if base_path.exists():
        try:
            base_config = load_config(str(base_path))
        except Exception as e:
            console.print(f"[yellow]Warning: could not read base config: {e}[/yellow]")

    existing_config = {}
    if target_path.exists():
        try:
            existing_config = load_config(str(target_path))
        except Exception as e:
            console.print(f"[yellow]Warning: could not read existing {target_path}: {e}[/yellow]")

    # Start from existing overlay so we don't drop user-specific keys
    updated_config = copy.deepcopy(existing_config)

    def current(keys, fallback=None):
        return _get_nested(existing_config, keys, _get_nested(base_config, keys, fallback))

    def prompt_text(label, keys, secret=False, allow_empty=True):
        default_val = current(keys, '')
        show_default = bool(default_val)
        val = click.prompt(
            label,
            default=default_val,
            show_default=show_default,
            hide_input=secret,
        )
        if isinstance(val, str) and not val and default_val and not allow_empty:
            val = default_val
        _set_nested(updated_config, keys, val)

    def prompt_choice(label, keys, choices):
        default_val = current(keys, choices[0])
        val = click.prompt(
            label,
            type=click.Choice(choices, case_sensitive=False),
            default=default_val,
            show_default=True,
        )
        _set_nested(updated_config, keys, val)
        return val

    def prompt_bool(label, keys):
        cur_val = current(keys, False)
        if isinstance(cur_val, str):
            default_val = cur_val.lower() == 'true'
        else:
            default_val = bool(cur_val)
        val = click.confirm(label, default=default_val, show_default=True)
        _set_nested(updated_config, keys, val)

    console.print("\n[bold cyan]Config Editor[/bold cyan]")
    console.print("You'll be prompted for common settings. Press Enter to keep the shown default.")

    # API keys and platform selection
    prompt_text("Alpha Vantage API key", ("alpha_vantage_api_key",), secret=True)

    platform = prompt_choice(
        "Trading platform",
        ("trading_platform",),
        ["coinbase_advanced", "coinbase", "oanda", "mock", "unified"],
    )

    if platform in {"coinbase", "coinbase_advanced"}:
        console.print("\n[bold]Coinbase Advanced credentials[/bold]")
        prompt_text("API key", ("platform_credentials", "api_key"), secret=True)
        prompt_text("API secret", ("platform_credentials", "api_secret"), secret=True)
        prompt_bool("Use sandbox?", ("platform_credentials", "use_sandbox"))
        prompt_text(
            "Passphrase (optional; leave blank to skip)",
            ("platform_credentials", "passphrase"),
            secret=True,
            allow_empty=True,
        )
    elif platform == "oanda":
        console.print("\n[bold]Oanda credentials[/bold]")
        prompt_text("API token", ("platform_credentials", "api_key"), secret=True)
        prompt_text("Account ID", ("platform_credentials", "account_id"))
        prompt_choice(
            "Environment",
            ("platform_credentials", "environment"),
            ["practice", "live"],
        )
    elif platform == "mock":
        console.print("\n[yellow]Mock platform selected — no credentials required.[/yellow]")
    elif platform == "unified":
        console.print(
            "\n[yellow]Unified mode detected. Configure per-platform entries in the YAML manually if needed.[/yellow]"
        )

    # Decision engine settings
    console.print("\n[bold]Decision engine[/bold]")
    ai_choice = prompt_choice(
        "AI provider",
        ("decision_engine", "ai_provider"),
        ["local", "cli", "codex", "qwen", "gemini", "ensemble"],
    )
    prompt_text("Model name", ("decision_engine", "model_name"))
    prompt_text("Decision confidence threshold (0.0-1.0)", ("decision_engine", "decision_threshold"))

    if ai_choice == "gemini":
        console.print("Gemini settings (stored under decision_engine.gemini)")
        prompt_text("Gemini API key", ("decision_engine", "gemini", "api_key"), secret=True)
        prompt_text(
            "Gemini model name",
            ("decision_engine", "gemini", "model_name"),
        )

    if ai_choice == "ensemble":
        console.print("\n[bold]Ensemble configuration[/bold]")
        # For simplicity, we'll prompt for common providers and basic weights
        console.print("Select enabled providers (space-separated, e.g., 'local cli gemini'):")
        enabled_providers_input = click.prompt(
            "Enabled providers",
            default="local",
            show_default=True,
        )
        enabled_providers = [p.strip() for p in enabled_providers_input.split() if p.strip()]
        _set_nested(updated_config, ("ensemble", "enabled_providers"), enabled_providers)
        
        # Simple equal weights for now
        if len(enabled_providers) > 1:
            weight = round(1.0 / len(enabled_providers), 2)
            weights = {prov: weight for prov in enabled_providers}
            _set_nested(updated_config, ("ensemble", "provider_weights"), weights)
        
        prompt_choice(
            "Voting strategy",
            ("ensemble", "voting_strategy"),
            ["weighted", "majority", "stacking"],
        )
        prompt_text("Agreement threshold (0.0-1.0)", ("ensemble", "agreement_threshold"))
        prompt_bool("Enable adaptive learning?", ("ensemble", "adaptive_learning"))

    # Monitoring + persistence toggles
    console.print("\n[bold]Monitoring & persistence[/bold]")
    prompt_bool("Enable monitoring context integration?", ("monitoring", "enable_context_integration"))
    prompt_bool("Include sentiment in monitoring?", ("monitoring", "include_sentiment"))
    prompt_bool("Include macro indicators?", ("monitoring", "include_macro"))
    prompt_text("Decision storage path", ("persistence", "storage_path"))
    prompt_bool("Enable portfolio memory?", ("portfolio_memory", "enabled"))
    prompt_bool("Enable backtesting flag by default?", ("backtesting", "enabled"))

    # Signal-only and safety settings
    console.print("\n[bold]Safety & execution[/bold]")
    prompt_bool("Force signal-only mode by default?", ("signal_only_default",))
    
    console.print("Safety thresholds:")
    prompt_text("Max leverage", ("safety", "max_leverage"))
    prompt_text("Max position percentage", ("safety", "max_position_pct"))
    
    console.print("Circuit breaker settings:")
    prompt_text("Failure threshold", ("circuit_breaker", "failure_threshold"))
    prompt_text("Recovery timeout (seconds)", ("circuit_breaker", "recovery_timeout_seconds"))
    prompt_text("Half-open retry count", ("circuit_breaker", "half_open_retry"))

    # Logging
    console.print("\n[bold]Logging[/bold]")
    prompt_choice(
        "Log level",
        ("logging", "level"),
        ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"],
    )

    target_path.parent.mkdir(parents=True, exist_ok=True)
    with open(target_path, 'w', encoding='utf-8') as f:
        yaml.safe_dump(updated_config, f, sort_keys=False)


@click.option(
    '--auto-install', '-y',
    is_flag=True,
    help='Automatically install missing dependencies without prompting'
)
@click.pass_context
def install_deps(ctx, auto_install):
    """Check and install missing project dependencies."""
    console.print("[bold cyan]Checking project dependencies...[/bold cyan]\n")
    
    missing, installed = _check_dependencies()
    
    if not missing and not installed:
        console.print("[yellow]requirements.txt not found.[/yellow]")
        return
    
    # Display summary table
    from rich.table import Table
    table = Table(title="Dependency Status")
    table.add_column("Status", style="bold")
    table.add_column("Count", justify="right")
    table.add_column("Packages", style="dim")
    
    if installed:
        installed_preview = ', '.join(installed[:5])
        if len(installed) > 5:
            installed_preview += f" ... (+{len(installed) - 5} more)"
        table.add_row("[green]✓ Installed[/green]", str(len(installed)), installed_preview)
    
    if missing:
        missing_preview = ', '.join(missing[:5])
        if len(missing) > 5:
            missing_preview += f" ... (+{len(missing) - 5} more)"
        table.add_row("[red]✗ Missing[/red]", str(len(missing)), missing_preview)
    
    console.print(table)
    console.print()
    
    # Check additional dependencies: ollama, node.js, coinbase-advanced-py
    console.print("[bold cyan]Checking additional dependencies...[/bold cyan]\n")
    
    additional_missing = []
    additional_installed = []
    
    # Check coinbase-advanced-py (Python package)
    try:
        import coinbase_advanced_py
        additional_installed.append("coinbase-advanced-py")
    except ImportError:
        additional_missing.append("coinbase-advanced-py")
        missing.append("coinbase-advanced-py")  # Add to pip install list
    
    # Check CLI tools
    cli_checks = [
        ("ollama", ["ollama", "--version"], "curl -fsSL https://ollama.com/install.sh | sh"),
        ("node", ["node", "--version"], "nvm install --lts"),
    ]
    
    for tool, cmd, install_cmd in cli_checks:
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                additional_installed.append(tool)
            else:
                additional_missing.append(tool)
        except (subprocess.TimeoutExpired, FileNotFoundError):
            additional_missing.append(tool)
    
    # Display additional status
    if additional_installed or additional_missing:
        add_table = Table(title="Additional Dependencies")
        add_table.add_column("Component", style="cyan")
        add_table.add_column("Status", style="white")
        
        for comp in additional_installed:
            add_table.add_row(comp, "[green]✓ Installed[/green]")
        for comp in additional_missing:
            add_table.add_row(comp, "[red]✗ Missing[/red]")
        
        console.print(add_table)
        console.print()
    
    if not missing and not additional_missing:
        console.print("[bold green]✓ All dependencies are installed![/bold green]")
        return
    
    # Show missing packages
    if missing:
        console.print("[yellow]Missing Python dependencies:[/yellow]")
        for pkg in missing:
            console.print(f"  • {pkg}")
        console.print()
    
    if additional_missing:
        console.print("[yellow]Missing additional dependencies:[/yellow]")
        for comp in additional_missing:
            console.print(f"  • {comp}")
        console.print()
    
    # Prompt for installation (unless auto-install)
    if not auto_install:
        if ctx.obj.get('interactive'):
            response = console.input("[bold]Install missing dependencies? [y/N]: [/bold]")
        else:
            response = input("Install missing dependencies? [y/N]: ")
        
        if response.strip().lower() != 'y':
            console.print("[yellow]Installation cancelled.[/yellow]")
            return
    
    # Install missing Python packages
    if missing:
        console.print("\n[bold cyan]Installing missing Python dependencies...[/bold cyan]")
        try:
            subprocess.run(
                [sys.executable, '-m', 'pip', 'install'] + missing,
                check=True,
                timeout=600
            )
            console.print(
                "\n[bold green]✓ Python dependencies installed successfully!"
                "[/bold green]"
            )
        except subprocess.TimeoutExpired:
            console.print(
                "\n[bold red]✗ Installation timed out after 10 minutes"
                "[/bold red]"
            )
            console.print(
                "[yellow]Please retry the installation or check your network "
                "connection and permissions.[/yellow]"
            )
        except subprocess.CalledProcessError as e:
            console.print(f"\n[bold red]✗ Installation failed: {e}[/bold red]")
            console.print(
                "[yellow]You may need to run with elevated permissions or "
                "check your pip configuration.[/yellow]"
            )
        except Exception as e:
            console.print(f"\n[bold red]✗ Unexpected error: {e}[/bold red]")
    
    # Install missing CLI tools
    if additional_missing:
        console.print("\n[bold cyan]Installing missing CLI tools...[/bold cyan]")
        for comp in additional_missing:
            if comp == "ollama":
                console.print(f"Installing {comp}...")
                try:
                    subprocess.run(
                        ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                        check=True,
                        timeout=300
                    )
                    console.print(f"[green]✓ {comp} installed successfully[/green]")
                except Exception as e:
                    console.print(f"[red]✗ {comp} installation failed: {e}[/red]")
            elif comp == "node":
                console.print(f"Installing {comp} via nvm...")
                try:
                    # Assume nvm is installed; if not, this will fail
                    subprocess.run(
                        ["bash", "-c", "nvm install --lts && nvm use --lts"],
                        check=True,
                        timeout=300
                    )
                    console.print(f"[green]✓ {comp} installed successfully[/green]")
                except Exception as e:
                    console.print(f"[red]✗ {comp} installation failed: {e}[/red]")
                    console.print("[yellow]Note: nvm must be installed first. Install nvm from https://github.com/nvm-sh/nvm[/yellow]")


@cli.command()
@click.argument('asset_pair')
@click.option(
    '--provider', '-p',
    type=click.Choice(
        ['local', 'cli', 'codex', 'qwen', 'gemini', 'ensemble'],
        case_sensitive=False
    ),
    help='AI provider (local/cli/codex/qwen/gemini/ensemble)'
)
@click.pass_context
def analyze(ctx, asset_pair, provider):
    """Analyze an asset pair and generate trading decision."""
    from ..utils.validation import standardize_asset_pair
    
    try:
        # Standardize asset pair input (uppercase, remove separators)
        asset_pair = standardize_asset_pair(asset_pair)
        
        config = ctx.obj['config']
        
        # Override provider if specified
        if provider:
            if 'decision_engine' not in config:
                config['decision_engine'] = {}
            config['decision_engine']['ai_provider'] = provider.lower()
            
            if provider.lower() == 'ensemble':
                console.print(
                    "[yellow]Using ensemble mode (multiple providers)[/yellow]"
                )
            else:
                console.print(
                    f"[yellow]Using AI provider: {provider}[/yellow]"
                )
        
        try:
            engine = FinanceFeedbackEngine(config)
        except ValueError as e:
            # Provide a clear, actionable message when Alpha Vantage API key is missing
            msg = str(e)
            if 'Alpha Vantage API key' in msg or 'api key is required' in msg.lower() or 'alpha_vantage' in msg.lower():
                console.print(
                    "[bold red]Alpha Vantage API key is required to fetch market data.[/bold red]"
                )
                console.print("Set the key via one of the following:")
                console.print("  - Run `python main.py config-editor` and enter the Alpha Vantage key when prompted")
                console.print("  - Export the environment variable `ALPHA_VANTAGE_API_KEY` before running the CLI")
                console.print("  - Add `alpha_vantage_api_key: YOUR_KEY` to `config/config.local.yaml`")
                return
            # Fall back to existing platform-init interactive prompt for other ValueErrors
            if ctx.obj.get('interactive'):
                console.print(
                    f"[yellow]Platform init failed: {e}. You can retry using the 'mock' platform.[/yellow]"
                )
                use_mock = console.input("Use mock platform for this session? [y/N]: ")
                if use_mock.strip().lower() == 'y':
                    config['trading_platform'] = 'mock'
                    engine = FinanceFeedbackEngine(config)
                else:
                    raise
            else:
                raise
        except Exception as e:
            # Preserve existing behavior for non-ValueError exceptions
            if ctx.obj.get('interactive'):
                console.print(
                    f"[yellow]Platform init failed: {e}. You can retry using the 'mock' platform.[/yellow]"
                )
                use_mock = console.input("Use mock platform for this session? [y/N]: ")
                if use_mock.strip().lower() == 'y':
                    config['trading_platform'] = 'mock'
                    engine = FinanceFeedbackEngine(config)
                else:
                    raise
            else:
                raise

        console.print(f"[bold blue]Analyzing {asset_pair}...[/bold blue]")

        decision = engine.analyze_asset(asset_pair)
        
        # Display decision
        console.print("\n[bold green]Trading Decision Generated[/bold green]")
        console.print(f"Decision ID: {decision['id']}")
        console.print(f"Asset: {decision['asset_pair']}")
        console.print(f"Action: [bold]{decision['action']}[/bold]")
        console.print(f"Confidence: {decision['confidence']}%")
        console.print(f"Reasoning: {decision['reasoning']}")
        
        # Check if signal-only mode (no position sizing)
        if decision.get('signal_only'):
            console.print(
                "\n[yellow]⚠ Signal-Only Mode: "
                "Portfolio data unavailable, no position sizing provided"
                "[/yellow]"
            )
        
        # Display position type and sizing (only if available)
        if (
            decision.get('position_type') and
            not decision.get('signal_only')
        ):
            console.print("\n[bold]Position Details:[/bold]")
            console.print(f"  Type: {decision['position_type']}")
            console.print(
                f"  Entry Price: ${decision.get('entry_price', 0):.2f}"
            )
            console.print(
                f"  Recommended Size: "
                f"{decision.get('recommended_position_size', 0):.6f} units"
            )
            console.print(
                f"  Risk: {decision.get('risk_percentage', 1)}% of account"
            )
            console.print(
                f"  Stop Loss: {decision.get('stop_loss_fraction', 0.02)*100:.1f}% "
                "from entry"
            )
        
        if decision['suggested_amount'] > 0:
            console.print(f"Suggested Amount: {decision['suggested_amount']}")
        
        console.print("\nMarket Data:")
        console.print(
            f"  Open: ${decision['market_data'].get('open', 0):.2f}"
        )
        console.print(
            f"  Close: ${decision['market_data']['close']:.2f}"
        )
        console.print(
            f"  High: ${decision['market_data']['high']:.2f}"
        )
        console.print(
            f"  Low: ${decision['market_data']['low']:.2f}"
        )
        console.print(
            f"  Price Change: {decision['price_change']:.2f}%"
        )
        console.print(
            f"  Volatility: {decision['volatility']:.2f}%"
        )
        
        # Display additional technical data if available
        md = decision['market_data']
        if 'trend' in md:
            console.print("\nTechnical Analysis:")
            console.print(f"  Trend: {md.get('trend', 'N/A')}")
            console.print(
                f"  Price Range: ${md.get('price_range', 0):.2f} ("
                f"{md.get('price_range_pct', 0):.2f}%)"
            )
            console.print(f"  Body %: {md.get('body_pct', 0):.2f}%")
            
        if 'rsi' in md:
            console.print(
                f"  RSI: {md.get('rsi', 0):.2f} ("
                f"{md.get('rsi_signal', 'neutral')})"
            )
            
        if md.get('type') == 'crypto' and 'volume' in md:
            console.print("\nCrypto Metrics:")
            console.print(f"  Volume: {md.get('volume', 0):,.0f}")
            if 'market_cap' in md and md.get('market_cap', 0) > 0:
                console.print(f"  Market Cap: ${md.get('market_cap', 0):,.0f}")
        
        # Display sentiment analysis if available
        if 'sentiment' in md and md['sentiment'].get('available'):
            sent = md['sentiment']
            console.print("\nNews Sentiment:")
            console.print(
                f"  Overall: "
                f"{sent.get('overall_sentiment', 'neutral').upper()}"
            )
            console.print(f"  Score: {sent.get('sentiment_score', 0):.3f}")
            console.print(f"  Articles: {sent.get('news_count', 0)}")
            if sent.get('top_topics'):
                topics = ', '.join(sent.get('top_topics', [])[:3])
                console.print(f"  Topics: {topics}")
        
        # Display macro indicators if available
        if 'macro' in md and md['macro'].get('available'):
            console.print("\nMacroeconomic Indicators:")
            for indicator, data in md['macro'].get('indicators', {}).items():
                name = indicator.replace('_', ' ').title()
                console.print(
                    f"  {name}: {data.get('value')} ({data.get('date')})"
                )
        
        # Display ensemble metadata if available
        if decision.get('ensemble_metadata'):
            meta = decision['ensemble_metadata']
            console.print("\n[bold cyan]Ensemble Analysis:[/bold cyan]")
            console.print(
                f"  Providers Used: {', '.join(meta['providers_used'])}"
            )
            if meta.get('providers_failed'):
                console.print(
                    f"  Providers Failed: {', '.join(meta['providers_failed'])}"
                )
            console.print(f"  Voting Strategy: {meta['voting_strategy']}")
            console.print(f"  Agreement Score: {meta['agreement_score']:.1%}")
            console.print(
                f"  Confidence Variance: {meta['confidence_variance']:.1f}"
            )
            
            # Show individual provider decisions
            console.print("\n[bold]Provider Decisions:[/bold]")
            for provider, pdecision in meta['provider_decisions'].items():
                original_w = meta.get('original_weights', {}).get(provider, 0)
                adjusted_w = meta.get('adjusted_weights', {}).get(provider, 0)
                vote_power = meta.get('voting_power', {}).get(provider, None)
                weight_str = (
                    f"orig {original_w:.2f}, adj {adjusted_w:.2f}"
                )
                if vote_power is not None:
                    weight_str += f", vote {vote_power:.2f}"
                console.print(
                    f"  [{provider.upper()}] {pdecision['action']} "
                    f"({pdecision['confidence']}%) - {weight_str}"
                )
            
            # Display local priority metadata if available
            if meta.get('local_models_used'):
                console.print(f"  Local Models Used: {', '.join(meta['local_models_used'])}")
            if meta.get('local_priority_applied'):
                console.print("  Local Priority Applied: Yes")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.pass_context
def balance(ctx):
    """Show current account balances."""
    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)
        
        balances = engine.get_balance()
        
        # Display balances in a table
        table = Table(title="Account Balances")
        table.add_column("Asset", style="cyan")
        table.add_column("Balance", style="green", justify="right")
        
        for asset, amount in balances.items():
            table.add_row(asset, f"{amount:,.2f}")
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.pass_context
def dashboard(ctx):
    """Show unified dashboard aggregating all platform portfolios."""
    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)
        
        # For now, we only have one platform instance
        # Future: support multiple platforms from config
        platforms = [engine.trading_platform]
        
        # Aggregate portfolio data
        aggregator = PortfolioDashboardAggregator(platforms)
        aggregated_data = aggregator.aggregate()
        
        # Display unified dashboard
        display_portfolio_dashboard(aggregated_data)
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.option('--asset', '-a', help='Filter by asset pair')
@click.option('--limit', '-l', default=10, help='Number of decisions to show')
@click.pass_context
def history(ctx, asset, limit):
    """Show decision history."""
    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)
        
        decisions = engine.get_decision_history(asset_pair=asset, limit=limit)
        
        if not decisions:
            console.print("[yellow]No decisions found[/yellow]")
            return
        
        # Display decisions in a table
        table = Table(title=f"Decision History ({len(decisions)} decisions)")
        table.add_column("Timestamp", style="cyan")
        table.add_column("Asset", style="blue")
        table.add_column("Action", style="magenta")
        table.add_column("Confidence", style="green", justify="right")
        table.add_column("Executed", style="yellow")
        
        for decision in decisions:
            timestamp = decision['timestamp'].split('T')[1][:8]  # Just time
            executed = "✓" if decision.get('executed') else "✗"
            
            table.add_row(
                timestamp,
                decision['asset_pair'],
                decision['action'],
                f"{decision['confidence']}%",
                executed
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument('decision_id', required=False)
@click.pass_context
def execute(ctx, decision_id):
    """Execute a trading decision."""
    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)
        
        # If no decision_id provided, show recent decisions and let user select
        if not decision_id:
            console.print("[bold blue]Recent Trading Decisions:[/bold blue]\n")
            
            # Get recent decisions (limit to 10)
            decisions = engine.get_decision_history(limit=10)
            
            # Filter out HOLD decisions since they don't execute trades
            decisions = [d for d in decisions if d.get('action') != 'HOLD']
            
            if not decisions:
                console.print(
                    "[yellow]No executable decisions found. Generate some "
                    "BUY/SELL decisions first with 'analyze' command.[/yellow]"
                )
                return
            
            # Display decisions in a table with numbers
            num_decisions = len(decisions)
            title = f"Select a Decision to Execute ({num_decisions} available)"
            table = Table(title=title)
            table.add_column("#", style="cyan", justify="right")
            table.add_column("Timestamp", style="cyan")
            table.add_column("Asset", style="blue")
            table.add_column("Action", style="magenta")
            table.add_column("Confidence", style="green", justify="right")
            table.add_column("Executed", style="yellow")
            
            for i, decision in enumerate(decisions, 1):
                # Just time part of timestamp
                timestamp = decision['timestamp'].split('T')[1][:8]
                executed = "✓" if decision.get('executed') else "✗"
                
                table.add_row(
                    str(i),
                    timestamp,
                    decision['asset_pair'],
                    decision['action'],
                    f"{decision['confidence']}%",
                    executed
                )
            
            console.print(table)
            console.print()
            
            # Prompt user to select
            while True:
                try:
                    choice = console.input(
                        "Enter decision number to execute (or 'q' to quit): "
                    ).strip()
                    
                    if choice.lower() in ['q', 'quit', 'exit']:
                        console.print("[dim]Cancelled.[/dim]")
                        return
                    
                    choice_num = int(choice)
                    if 1 <= choice_num <= len(decisions):
                        selected_decision = decisions[choice_num - 1]
                        decision_id = selected_decision['id']
                        console.print(
                            f"[green]Selected decision: {decision_id}[/green]"
                        )
                        break
                    else:
                        console.print(
                            f"[red]Invalid choice. Please enter a number "
                            f"between 1 and {len(decisions)}.[/red]"
                        )
                        
                except ValueError:
                    console.print(
                        "[red]Invalid input. Please enter a number or "
                        "'q' to quit.[/red]"
                    )
        
        console.print(
            f"[bold blue]Executing decision {decision_id}...[/bold blue]"
        )
        
        result = engine.execute_decision(decision_id)
        
        if result.get('success'):
            console.print(
                "[bold green]✓ Trade executed successfully[/bold green]"
            )
        else:
            console.print(
                "[bold red]✗ Trade execution failed[/bold red]"
            )
        
        console.print(f"Platform: {result.get('platform')}")
        console.print(f"Message: {result.get('message')}")
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.pass_context
def status(ctx):
    """Show engine status and configuration."""
    try:
        config = ctx.obj['config']
        
        console.print("[bold]Finance Feedback Engine Status[/bold]\n")
        console.print(
            f"Trading Platform: {config.get('trading_platform', 'Not configured')}"
        )
        console.print(
            f"AI Provider: {config.get('decision_engine', {}).get('ai_provider', 'Not configured')}"
        )
        console.print(
            f"Storage Path: {config.get('persistence', {}).get('storage_path', 'data/decisions')}"
        )
        
        # Try to initialize engine to verify configuration
        _engine = FinanceFeedbackEngine(config)  # noqa: F841 (used for init test)
        console.print(
            "\n[bold green]✓ Engine initialized successfully[/bold green]"
        )
        
    except Exception as e:
        console.print(
            "\n[bold red]✗ Engine initialization failed[/bold red]"
        )
        console.print(f"Error: {str(e)}")
        raise click.Abort()


@cli.command()
@click.option(
    '--confirm',
    is_flag=True,
    help='Skip confirmation prompt'
)
@click.pass_context
def wipe_decisions(ctx, confirm):
    """Delete all stored trading decisions."""
    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)
        
        # Get current count
        count = engine.decision_store.get_decision_count()
        
        if count == 0:
            console.print("[yellow]No decisions to wipe.[/yellow]")
            return
        
        console.print(
            f"[bold yellow]Warning: This will delete all {count} "
            f"stored decisions![/bold yellow]"
        )
        
        # Confirm unless --confirm flag or interactive mode
        if not confirm:
            if ctx.obj.get('interactive'):
                response = console.input(
                    "Are you sure you want to continue? [y/N]: "
                )
            else:
                response = click.confirm(
                    "Are you sure you want to continue?",
                    default=False
                )
                response = 'y' if response else 'n'
            
            if response.lower() != 'y':
                console.print("[yellow]Cancelled.[/yellow]")
                return
        
        # Wipe all decisions
        deleted = engine.decision_store.wipe_all_decisions()
        console.print(
            f"[bold green]✓ Wiped {deleted} decisions[/bold green]"
        )
        
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.argument('asset_pair')
@click.option('--start', '-s', required=True, help='Start date YYYY-MM-DD')
@click.option('--end', '-e', required=True, help='End date YYYY-MM-DD')
@click.option(
    '--strategy',
    default='sma_crossover',
    show_default=True,
    help='Strategy name'
)
@click.option(
    '--real-data',
    is_flag=True,
    help='Use real Alpha Vantage historical daily candles if available'
)
@click.option('--short-window', type=int, help='Override short SMA window')
@click.option('--long-window', type=int, help='Override long SMA window')
@click.option(
    '--initial-balance',
    type=float,
    help='Override starting balance'
)
@click.option('--fee', type=float, help='Override fee percentage per trade')
@click.option(
    '--rl-learning-rate',
    type=float,
    help='Override RL learning rate for ensemble_weight_rl'
)
@click.pass_context
def backtest(
    ctx,
    asset_pair,
    start,
    end,
    strategy,
    real_data,
    short_window,
    long_window,
    initial_balance,
    fee,
    rl_learning_rate,
):
    """Run a simple historical strategy simulation (experimental)."""
    try:
        config = ctx.obj['config']
        bt_conf = config.setdefault('backtesting', {})
        if real_data:
            bt_conf['use_real_data'] = True
        if rl_learning_rate is not None:
            rl_conf = bt_conf.setdefault('rl', {})
            rl_conf['learning_rate'] = rl_learning_rate
        engine = FinanceFeedbackEngine(config)

        console.print(
            f"[bold blue]Backtesting {asset_pair} {start}→{end} [{strategy}]"  # noqa: E501
        )

        results = engine.backtest(
            asset_pair=asset_pair,
            start=start,
            end=end,
            strategy=strategy,
            short_window=short_window,
            long_window=long_window,
            initial_balance=initial_balance,
            fee_percentage=fee,
        )

        metrics = results['metrics']
        strat = results['strategy']

        table = Table(title="Backtest Summary")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", style="green", justify="right")

        table.add_row("Strategy", strat['name'])
        if 'short_window' in strat:
            table.add_row("Short SMA", str(strat['short_window']))
        if 'long_window' in strat:
            table.add_row("Long SMA", str(strat['long_window']))
        if strategy == 'ensemble_weight_rl':
            provs = strat.get('providers', [])
            table.add_row("Providers", ",".join(provs))
        table.add_row("Candles", str(results.get('candles_used', 0)))
        table.add_row(
            "Starting Balance", f"${metrics['starting_balance']:.2f}"
        )
        table.add_row("Final Balance", f"${metrics['final_balance']:.2f}")
        table.add_row("Net Return %", f"{metrics['net_return_pct']:.2f}%")
        table.add_row("Total Trades", str(metrics['total_trades']))
        table.add_row("Win Rate %", f"{metrics['win_rate']:.2f}%")
        table.add_row("Max Drawdown %", f"{metrics['max_drawdown_pct']:.2f}%")

        if metrics.get('insufficient_data'):
            console.print(
                "[yellow]Insufficient data: windows too large; metrics placeholder.[/yellow]"  # noqa: E501
            )
        console.print(table)

        if results['trades']:
            trades_table = Table(title="Trades")
            trades_table.add_column("Time", style="cyan")
            trades_table.add_column("Type", style="magenta")
            trades_table.add_column("Price", justify="right")
            trades_table.add_column("Size", justify="right")
            trades_table.add_column("Fee", justify="right")
            trades_table.add_column("PnL", justify="right")
            for t in results['trades']:
                trades_table.add_row(
                    t['timestamp'].split('T')[0],
                    t['type'],
                    f"${t['price']:.2f}",
                    f"{t['size']:.6f}",
                    f"${t['fee']:.2f}",
                    f"${t.get('pnl', 0):.2f}",
                )
            console.print(trades_table)

        # RL metadata table if using ensemble_weight_rl
        if strategy == 'ensemble_weight_rl' and 'rl_metadata' in results:
            rl = results['rl_metadata']
            weights = rl.get('final_weights', {})
            rl_table = Table(title="RL Final Weights & Reward")
            rl_table.add_column("Provider", style="cyan")
            rl_table.add_column("Final Weight", justify="right")
            for p, w in weights.items():
                rl_table.add_row(p, f"{w:.4f}")
            rl_table.add_row(
                "Total Reward",
                f"{rl.get('total_reward', 0):.2f}"
            )
            console.print(rl_table)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.group()
@click.pass_context
def monitor(ctx):
    """Live trade monitoring commands."""
    pass


@monitor.command()
@click.pass_context
def start(ctx):
    """Start live trade monitoring."""
    try:
        config = ctx.obj['config']
        
        # Initialize engine
        engine = FinanceFeedbackEngine(config=config)
        
        # Check platform supports monitoring
        if not hasattr(engine.trading_platform, 'get_portfolio_breakdown'):
            console.print(
                "[red]Error:[/red] Current platform doesn't support "
                "portfolio monitoring"
            )
            return
        
        from finance_feedback_engine.monitoring import TradeMonitor
        
        console.print("\n[bold cyan]🔍 Starting Live Trade Monitor[/bold cyan]\n")
        
        # Create and start monitor
        trade_monitor = TradeMonitor(
            platform=engine.trading_platform,
            detection_interval=30,  # Check for new trades every 30s
            poll_interval=30  # Update positions every 30s
        )
        
        trade_monitor.start()
        
        console.print("[green]✓ Monitor started successfully[/green]")
        console.print(
            f"  Max concurrent trades: {trade_monitor.MAX_CONCURRENT_TRADES}"
        )
        console.print(
            f"  Detection interval: {trade_monitor.detection_interval}s"
        )
        console.print(
            f"  Poll interval: {trade_monitor.poll_interval}s"
        )
        console.print("\n[yellow]Monitor is running in background...[/yellow]")
        console.print(
            "[dim]Use 'python main.py monitor status' to check status[/dim]"
        )
        console.print(
            "[dim]Use 'python main.py monitor stop' to stop monitoring[/dim]"
        )
        
        # Keep process alive
        import time
        try:
            while trade_monitor.is_running:
                time.sleep(5)
        except KeyboardInterrupt:
            console.print("\n\n[yellow]Stopping monitor...[/yellow]")
            trade_monitor.stop()
            console.print("[green]✓ Monitor stopped[/green]")
        
    except Exception as e:
        console.print(f"[red]Error starting monitor:[/red] {e}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())


@monitor.command(name='status')
@click.pass_context
def monitor_status(ctx):
    """Show live trade monitoring status."""
    try:
        config = ctx.obj['config']
        
        engine = FinanceFeedbackEngine(config=config)
        
        from finance_feedback_engine.monitoring import TradeMonitor
        
        # Note: In production, you'd store monitor instance globally
        # For now, show what trades are currently open on platform
        
        console.print("\n[bold cyan]📊 Trade Monitor Status[/bold cyan]\n")
        
        try:
            portfolio = engine.trading_platform.get_portfolio_breakdown()
            positions = portfolio.get('futures_positions', [])
            
            if not positions:
                console.print("[yellow]No open positions detected[/yellow]")
                return
            
            table = Table(title="Open Positions (Monitored)")
            table.add_column("Product ID", style="cyan")
            table.add_column("Side", style="white")
            table.add_column("Contracts", style="green", justify="right")
            table.add_column("Entry", style="yellow", justify="right")
            table.add_column("Current", style="yellow", justify="right")
            table.add_column("PnL", style="white", justify="right")
            
            for pos in positions:
                product_id = pos.get('product_id', 'N/A')
                side = pos.get('side', 'N/A')
                contracts = pos.get('contracts', 0)
                entry = pos.get('entry_price', 0)
                current = pos.get('current_price', 0)
                pnl = pos.get('unrealized_pnl', 0)
                
                pnl_color = "green" if pnl >= 0 else "red"
                pnl_str = f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]"
                
                table.add_row(
                    product_id,
                    side,
                    f"{contracts:.0f}",
                    f"${entry:,.2f}",
                    f"${current:,.2f}",
                    pnl_str
                )
            
            console.print(table)
            console.print(
                f"\n[dim]Total open positions: {len(positions)}[/dim]"
            )
            
        except Exception as e:
            console.print(f"[red]Error fetching positions:[/red] {e}")
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())


@monitor.command()
@click.pass_context
def metrics(ctx):
    """Show trade performance metrics."""
    try:
        from finance_feedback_engine.monitoring import TradeMetricsCollector
        
        console.print("\n[bold cyan]📈 Trade Performance Metrics[/bold cyan]\n")
        
        # Load metrics from disk
        collector = TradeMetricsCollector()
        
        # Load all metric files
        import json
        from pathlib import Path
        
        metrics_dir = Path("data/trade_metrics")
        if not metrics_dir.exists():
            console.print(
                "[yellow]No trade metrics found yet[/yellow]"
            )
            console.print(
                "[dim]Metrics will appear here once trades complete[/dim]"
            )
            return
        
        metric_files = list(metrics_dir.glob("trade_*.json"))
        
        if not metric_files:
            console.print("[yellow]No completed trades yet[/yellow]")
            return
        
        # Load all metrics
        all_metrics = []
        for file in metric_files:
            try:
                with open(file, 'r') as f:
                    metric = json.load(f)
                    all_metrics.append(metric)
            except Exception as e:
                console.print(f"[dim]Warning: Could not load {file.name}: {e}[/dim]")
        
        if not all_metrics:
            console.print("[yellow]No valid metrics found[/yellow]")
            return
        
        # Calculate aggregate stats
        winning = [m for m in all_metrics if m.get('realized_pnl', 0) > 0]
        losing = [m for m in all_metrics if m.get('realized_pnl', 0) <= 0]
        
        total_pnl = sum(m.get('realized_pnl', 0) for m in all_metrics)
        avg_pnl = total_pnl / len(all_metrics)
        win_rate = (len(winning) / len(all_metrics) * 100) if all_metrics else 0
        
        # Display summary
        console.print(f"Total Trades:     {len(all_metrics)}")
        console.print(f"Winning Trades:   [green]{len(winning)}[/green]")
        console.print(f"Losing Trades:    [red]{len(losing)}[/red]")
        console.print(f"Win Rate:         {win_rate:.1f}%")
        
        pnl_color = "green" if total_pnl >= 0 else "red"
        console.print(f"Total P&L:        [{pnl_color}]${total_pnl:,.2f}[/{pnl_color}]")
        
        avg_color = "green" if avg_pnl >= 0 else "red"
        console.print(f"Average P&L:      [{avg_color}]${avg_pnl:,.2f}[/{avg_color}]")
        
        # Show recent trades
        console.print("\n[bold]Recent Trades:[/bold]\n")
        
        table = Table()
        table.add_column("Product", style="cyan")
        table.add_column("Side", style="white")
        table.add_column("Duration", style="yellow")
        table.add_column("PnL", style="white", justify="right")
        table.add_column("Exit Reason", style="dim")
        
        # Sort by exit time and show last 10
        sorted_metrics = sorted(
            all_metrics,
            key=lambda m: m.get('exit_time', ''),
            reverse=True
        )[:10]
        
        for m in sorted_metrics:
            product = m.get('product_id', 'N/A')
            side = m.get('side', 'N/A')
            duration = m.get('holding_duration_hours', 0)
            pnl = m.get('realized_pnl', 0)
            reason = m.get('exit_reason', 'unknown')
            
            pnl_color = "green" if pnl >= 0 else "red"
            pnl_str = f"[{pnl_color}]${pnl:,.2f}[/{pnl_color}]"
            
            table.add_row(
                product,
                side,
                f"{duration:.2f}h",
                pnl_str,
                reason
            )
        
        console.print(table)
        
    except Exception as e:
        console.print(f"[red]Error:[/red] {e}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())



@cli.command(name='retrain-meta-learner')
@click.option(
    '--force',
    is_flag=True,
    help='Force retraining even if performance criteria are not met.'
)
@click.pass_context
def retrain_meta_learner(ctx, force):
    """Check stacking ensemble performance and retrain if needed."""
    try:
        from train_meta_learner import run_training
        
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)
        
        console.print("\n[bold cyan]Checking meta-learner performance...[/bold cyan]")
        
        # Ensure memory is loaded
        if not engine.memory.trade_outcomes:
            console.print("[yellow]No trade history found in memory. Cannot check performance.[/yellow]")
            return

        perf = engine.memory.get_strategy_performance_summary()
        
        stacking_perf = perf.get('stacking')
        
        if not stacking_perf:
            console.print("[yellow]No performance data found for the 'stacking' strategy.[/yellow]")
            console.print("Generate some decisions using the stacking strategy to gather data.")
            return
            
        win_rate = stacking_perf.get('win_rate', 0)
        total_trades = stacking_perf.get('total_trades', 0)
        
        console.print(f"Stacking strategy performance: {win_rate:.2f}% win rate over {total_trades} trades.")
        
        # Define retraining criteria
        win_rate_threshold = 55.0
        min_trades_threshold = 20
        
        should_retrain = False
        if force:
            console.print("[yellow]--force flag detected. Forcing retraining...[/yellow]")
            should_retrain = True
        elif total_trades < min_trades_threshold:
            console.print(f"Skipping retraining: Not enough trades ({total_trades} < {min_trades_threshold}).")
        elif win_rate >= win_rate_threshold:
            console.print(f"Skipping retraining: Win rate is acceptable ({win_rate:.2f}% >= {win_rate_threshold:.2f}%).")
        else:
            console.print(f"[yellow]Performance threshold not met. Retraining meta-learner...[/yellow]")
            should_retrain = True
            
        if should_retrain:
            run_training()
            console.print("[bold green]✓ Meta-learner retraining process complete.[/bold green]")
        else:
            console.print("[bold green]✓ No retraining needed at this time.[/bold green]")

    except ImportError:
        console.print("[bold red]Error:[/bold red] Could not import 'train_meta_learner'. Make sure it is in the project root.")
        raise click.Abort()
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


@cli.command(name="run-agent")
@click.option(
    '--take-profit', '-tp',
    type=float,
    default=0.05,
    show_default=True,
    help='Portfolio-level take-profit percentage (decimal, e.g., 0.05 for 5%).'
)
@click.option(
    '--stop-loss', '-sl',
    type=float,
    default=0.02,
    show_default=True,
    help='Portfolio-level stop-loss percentage (decimal, e.g., 0.02 for 2%).'
)
@click.option(
    '--setup',
    is_flag=True,
    help='Run interactive config setup before starting the agent.'
)
@click.pass_context
def run_agent(ctx, take_profit, stop_loss, setup):
    """Starts the autonomous trading agent."""
    import asyncio
    from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
    from finance_feedback_engine.agent.config import TradingAgentConfig
    from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
    
    # Compatibility: Detect legacy percentage inputs (1-100) and convert to decimals
    if 1 <= take_profit <= 100:
        console.print(f"[yellow]Warning: Detected legacy take-profit percentage {take_profit}%. Converting to decimal: {take_profit/100:.3f}[/yellow]")
        take_profit /= 100
    elif take_profit > 100:
        console.print(f"[yellow]Warning: Unusually high take-profit value {take_profit}. Proceeding without conversion.[/yellow]")
    if 1 <= stop_loss <= 100:
        console.print(f"[yellow]Warning: Detected legacy stop-loss percentage {stop_loss}%. Converting to decimal: {stop_loss/100:.3f}[/yellow]")
        stop_loss /= 100
    elif stop_loss > 100:
        console.print(f"[red]Error: Invalid stop-loss value {stop_loss}. Stop-loss cannot exceed 100%.[/red]")
        raise click.Abort()

    if setup:
        console.print("\n[bold yellow]Running initial setup...[/bold yellow]")
        ctx.invoke(config_editor)
        console.print("\n[bold green]✓ Setup complete. Reloading configuration...[/bold green]\n")
        # Reload config to apply any changes made in the editor
        ctx.obj['config'] = load_tiered_config()

    console.print("\n[bold cyan]🚀 Initializing Autonomous Agent...[/bold cyan]")

    try:
        config = ctx.obj['config']
        
        # We need the full engine to get the initialized components
        engine = FinanceFeedbackEngine(config)

        agent_config_data = config.get('agent', {})
        agent_config = TradingAgentConfig(**agent_config_data)

        if not agent_config.autonomous.enabled:
            console.print("[yellow]Autonomous agent is not enabled in the configuration.[/yellow]")
            console.print("[dim]Enable it by setting `agent.autonomous.enabled: true` in your config file.[/dim]")
            return

        console.print("[green]✓ Agent configuration loaded.[/green]")
        console.print(f"  Portfolio Take Profit: {take_profit:.2%}")
        console.print(f"  Portfolio Stop Loss: {stop_loss:.2%}")
        
        trade_monitor = TradeMonitor(
            platform=engine.trading_platform,
            portfolio_take_profit_percentage=take_profit,
            portfolio_stop_loss_percentage=stop_loss,
        )
        engine.enable_monitoring_integration(trade_monitor=trade_monitor)


        # Create and start the agent
        agent = TradingLoopAgent(
            config=agent_config,
            engine=engine,
            trade_monitor=engine.trade_monitor,
            portfolio_memory=engine.memory_engine,
            trading_platform=engine.trading_platform,
        )

        console.print("[green]✓ Autonomous agent initialized.[/green]")
        console.print("[yellow]Press Ctrl+C to stop the agent.[/yellow]")

        loop = asyncio.get_event_loop()
        try:
            loop.run_until_complete(agent.run())
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutdown signal received. Stopping agent gracefully...[/yellow]")
            agent.stop()
            # Allow time for cleanup
            loop.run_until_complete(asyncio.sleep(1))
        finally:
            loop.close()
            console.print("[bold green]✓ Agent stopped.[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error starting agent:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


if __name__ == '__main__':
    cli()
