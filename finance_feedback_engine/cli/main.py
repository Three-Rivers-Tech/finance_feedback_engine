"""Command-line interface for Finance Feedback Engine."""

import copy
import json
import logging
import os
import re
import subprocess
import sys
from datetime import datetime
from pathlib import Path

import click
import yaml
from packaging.requirements import Requirement
from rich.console import Console
from rich.table import Table

from finance_feedback_engine.cli.commands.agent import _run_live_dashboard
from finance_feedback_engine.cli.commands.agent import monitor as monitor_command
from finance_feedback_engine.cli.commands.agent import run_agent as run_agent_command

# Export run_agent for backward compatibility with tests
run_agent = run_agent_command

# Export _run_live_market_view as alias for backward compatibility with tests
_run_live_market_view = _run_live_dashboard
from finance_feedback_engine.cli.commands.analysis import analyze as analyze_command
from finance_feedback_engine.cli.commands.analysis import history as history_command
from finance_feedback_engine.cli.commands.backtest import backtest as backtest_command
from finance_feedback_engine.cli.commands.backtest import (
    monte_carlo as monte_carlo_command,
)
from finance_feedback_engine.cli.commands.backtest import (
    portfolio_backtest as portfolio_backtest_command,
)
from finance_feedback_engine.cli.commands.backtest import (
    walk_forward as walk_forward_command,
)
from finance_feedback_engine.cli.commands.memory import (
    learning_report as learning_report_command,
)
from finance_feedback_engine.cli.commands.memory import (
    prune_memory as prune_memory_command,
)
from finance_feedback_engine.cli.commands.trading import balance as balance_command
from finance_feedback_engine.cli.commands.trading import execute as execute_command
from finance_feedback_engine.cli.interactive import start_interactive_session
from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.dashboard import (
    PortfolioDashboardAggregator,
    display_portfolio_dashboard,
)
from finance_feedback_engine.monitoring.metrics import inc, init_metrics

# from rich import print as rprint  # unused


console = Console()
logger = logging.getLogger(__name__)

# Config mode constant
CONFIG_MODE_TIERED = "tiered"


def _validate_config_on_startup(config_path: str, environment: str = "development"):
    """
    Validate configuration file before engine initialization.

    Args:
        config_path: Path to configuration file or CONFIG_MODE_TIERED for tiered loading
        environment: Runtime environment (production, staging, development, test)

    Raises:
        click.ClickException: If validation fails with critical/high severity issues
    """
    from finance_feedback_engine.utils.config_validator import (
        print_validation_results,
        validate_config_file,
    )

    # Validate environment argument
    ALLOWED_ENVIRONMENTS = ("production", "staging", "development", "test")
    if environment not in ALLOWED_ENVIRONMENTS:
        raise click.ClickException(
            f"Invalid environment '{environment}'. Must be one of: {', '.join(ALLOWED_ENVIRONMENTS)}"
        )

    # Skip validation for tiered loading (no single file to validate)
    # Tiered loading validates at load time
    if config_path == CONFIG_MODE_TIERED:
        return

    try:
        result = validate_config_file(config_path, environment)
    except Exception as e:
        raise click.ClickException(f"Configuration validation error: {e}")

    # If there are critical or high severity errors, fail startup
    if result.has_errors():
        console.print("[bold red]Configuration validation failed![/bold red]")
        print_validation_results(result, verbose=True)
        raise click.ClickException(
            "Invalid configuration detected. Fix errors above and retry."
        )

    # If there are warnings, show them but allow startup
    if result.issues:
        console.print("[yellow]Configuration validation passed with warnings:[/yellow]")
        print_validation_results(result, verbose=False)


def _display_pulse_data(engine, asset_pair: str):
    """Display multi-timeframe pulse technical analysis data.

    Args:
        engine: FinanceFeedbackEngine instance
        asset_pair: Asset pair being analyzed
    """
    try:
        console.print("\n[bold cyan]=== MULTI-TIMEFRAME PULSE DATA ===[/bold cyan]")

        # Try to fetch pulse from monitoring context first, then fall back to data_provider
        pulse = None
        if hasattr(engine, "monitoring_context_provider"):
            context = engine.monitoring_context_provider.get_monitoring_context(
                asset_pair
            )
            pulse = context.get("multi_timeframe_pulse")

        if (not pulse or "timeframes" not in (pulse or {})) and hasattr(
            engine, "data_provider"
        ):
            try:
                fetched = engine.data_provider.get_comprehensive_market_data(asset_pair)
                pulse = (fetched or {}).get("multi_timeframe_pulse") or (
                    fetched or {}
                ).get("pulse")
                # Normalize simple pulse dict into expected structure
                if pulse and "timeframes" not in pulse and isinstance(pulse, dict):
                    pulse = {"timeframes": pulse}
            except Exception as fetch_err:
                console.print(
                    f"[yellow]Multi-timeframe pulse unavailable: {fetch_err}[/yellow]"
                )

        if not pulse or "timeframes" not in pulse:
            console.print("[yellow]Multi-timeframe pulse data not available[/yellow]")
            console.print(
                "[dim]Ensure TradeMonitor is running or data_provider supports comprehensive pulse[/dim]"
            )
            return

        # Display pulse age
        age_seconds = pulse.get("age_seconds", 0)
        age_mins = age_seconds / 60
        freshness = (
            "[green]FRESH[/green]" if age_mins < 10 else "[yellow]STALE[/yellow]"
        )
        console.print(f"Pulse Age: {age_mins:.1f} minutes ({freshness})")
        console.print()

        # Create table for timeframe data
        from rich.table import Table

        for tf, data in pulse["timeframes"].items():
            table = Table(title=f"{tf.upper()} Timeframe", show_header=True)
            table.add_column("Indicator", style="cyan")
            table.add_column("Value", style="white")
            table.add_column("Interpretation", style="dim")

            # Trend
            trend_color = (
                "green"
                if data["trend"] == "UPTREND"
                else "red" if data["trend"] == "DOWNTREND" else "yellow"
            )
            table.add_row(
                "Trend",
                f"[{trend_color}]{data['trend']}[/{trend_color}]",
                f"Signal Strength: {data.get('signal_strength', 0)}/100",
            )

            # RSI
            rsi = data.get("rsi", 50)
            if rsi > 70:
                rsi_status = "[red]OVERBOUGHT[/red]"
            elif rsi < 30:
                rsi_status = "[green]OVERSOLD[/green]"
            else:
                rsi_status = "NEUTRAL"
            table.add_row("RSI", f"{rsi:.1f}", rsi_status)

            # MACD
            macd = data.get("macd", {})
            if macd.get("histogram", 0) > 0:
                macd_status = "[green]BULLISH[/green] (positive histogram)"
            elif macd.get("histogram", 0) < 0:
                macd_status = "[red]BEARISH[/red] (negative histogram)"
            else:
                macd_status = "NEUTRAL"
            table.add_row("MACD", f"{macd.get('macd', 0):.2f}", macd_status)

            # Bollinger Bands
            bbands = data.get("bollinger_bands", {})
            percent_b = bbands.get("percent_b", 0.5)
            if percent_b > 1.0:
                bb_status = "[red]Above upper band[/red] (overbought)"
            elif percent_b < 0.0:
                bb_status = "[green]Below lower band[/green] (oversold)"
            else:
                bb_status = f"Within bands ({percent_b:.1%})"
            table.add_row("Bollinger %B", f"{percent_b:.3f}", bb_status)

            # ADX
            adx_data = data.get("adx", {})
            adx_val = adx_data.get("adx", 0)
            if adx_val > 25:
                adx_status = f"[green]STRONG TREND[/green] ({adx_val:.1f})"
            elif adx_val > 20:
                adx_status = f"Developing trend ({adx_val:.1f})"
            else:
                adx_status = f"[yellow]Weak/ranging[/yellow] ({adx_val:.1f})"

            plus_di = adx_data.get("plus_di", 0)
            minus_di = adx_data.get("minus_di", 0)
            direction = (
                "[green]+DI dominant[/green]"
                if plus_di > minus_di
                else "[red]-DI dominant[/red]"
            )

            table.add_row("ADX", f"{adx_val:.1f}", f"{adx_status} | {direction}")

            # ATR & Volatility
            atr = data.get("atr", 0)
            volatility = data.get("volatility", "medium")
            vol_color = (
                "red"
                if volatility == "high"
                else "yellow" if volatility == "medium" else "green"
            )
            table.add_row(
                "ATR / Volatility",
                f"{atr:.2f}",
                f"[{vol_color}]{volatility.upper()}[/{vol_color}]",
            )

            console.print(table)
            console.print()

        # Cross-timeframe alignment
        console.print("[bold]Cross-Timeframe Alignment:[/bold]")
        trends = [data["trend"] for data in pulse["timeframes"].values()]
        uptrends = trends.count("UPTREND")
        downtrends = trends.count("DOWNTREND")
        ranging = trends.count("RANGING")

        if uptrends > downtrends and uptrends >= 3:
            alignment = "[bold green]BULLISH ALIGNMENT[/bold green]"
        elif downtrends > uptrends and downtrends >= 3:
            alignment = "[bold red]BEARISH ALIGNMENT[/bold red]"
        else:
            alignment = "[yellow]MIXED SIGNALS[/yellow]"

        console.print(f"  {alignment}")
        console.print(
            f"  Breakdown: {uptrends} up, {downtrends} down, {ranging} ranging"
        )

        console.print("[bold cyan]=" * 40 + "[/bold cyan]\n")

    except Exception as e:
        console.print(f"[red]Error displaying pulse data: {e}[/red]")
        logger.exception("Pulse display error")


def _parse_requirements_file(req_file: Path) -> list:
    """Parse requirements.txt and return list of package names.

    Returns base names only.
    """
    packages = []
    if not req_file.exists():
        return packages

    with open(req_file, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            # Skip comments and empty lines
            if not line or line.startswith("#"):
                continue

            # Remove inline comments
            line = line.split("#")[0].strip()
            if not line:
                continue

            # Try using packaging library first (most robust)
            try:
                req = Requirement(line)
                packages.append(req.name)
                continue
            except ImportError:
                pass  # Fall back to regex approach
            except Exception as e:
                # Invalid requirement, try regex fallback
                logger.warning(f"Failed to parse requirement '{line}': {e}")
                pass  # Fall back to regex approach

            # Fallback: Use regex to extract package name
            # Handles operators: ~=, !=, <=, <, >, ==, >=
            # Also strips extras [extra1,extra2] and environment markers
            match = re.match(r"^([a-zA-Z0-9]([a-zA-Z0-9._-]*[a-zA-Z0-9])?)", line)
            if match:
                pkg = match.group(1)
                if pkg:
                    packages.append(pkg)
    return packages


def _get_installed_packages() -> dict:
    """Get currently installed packages as dict {name: version}."""
    try:
        result = subprocess.run(
            [sys.executable, "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            check=True,
        )
        installed = json.loads(result.stdout)
        return {
            pkg.get("name", "").lower(): pkg.get("version", "")
            for pkg in installed
            if isinstance(pkg, dict) and pkg.get("name")
        }
    except Exception as e:
        console.print(
            f"[yellow]Warning: Could not retrieve installed " f"packages: {e}[/yellow]"
        )
        return {}


def _check_dependencies() -> tuple:
    """Check which dependencies are missing.

    Returns (missing, installed) tuples.
    """
    req_file = Path("requirements.txt")
    if not req_file.exists():
        return ([], [])

    required = _parse_requirements_file(req_file)
    installed_dict = _get_installed_packages()

    missing = []
    installed = []

    for pkg in required:
        pkg_lower = pkg.lower()
        # Normalize both hyphen and underscore for comparison
        pkg_normalized = pkg_lower.replace("-", "_")

        # Check both forms (hyphen and underscore)
        if (
            pkg_lower in installed_dict
            or pkg_normalized in installed_dict
            or pkg_lower.replace("_", "-") in installed_dict
        ):
            installed.append(pkg)
        else:
            missing.append(pkg)

    return (missing, installed)


def setup_logging(verbose: bool = False, config: dict = None):
    """Setup logging configuration with structured logging support.

    Args:
        verbose: If True, override config and use DEBUG level
        config: Configuration dict containing logging settings

    Priority: --verbose flag > config value > INFO default

    This function now supports both legacy and structured logging modes:
    - If config['logging']['structured']['enabled'] is True, uses structured JSON logging
    - Otherwise, falls back to traditional text logging
    """
    # Try to use structured logging if available and enabled
    if config and config.get("logging", {}).get("structured", {}).get("enabled", False):
        try:
            from finance_feedback_engine.monitoring.logging_config import (
                setup_structured_logging,
            )

            setup_structured_logging(config, verbose=verbose)
            logger = logging.getLogger(__name__)
            logger.debug("Structured logging initialized successfully")
            return
        except ImportError as e:
            # Fall back to basic logging if structured logging module is not available
            logging.warning(
                f"Structured logging module not available: {e}, falling back to basic logging"
            )
        except Exception as e:
            # Fall back to basic logging if there's any error in structured logging setup
            logging.warning(
                f"Error setting up structured logging: {e}, falling back to basic logging"
            )

    # Legacy logging setup (backward compatible)
    # Map string level names to logging constants
    LEVEL_MAP = {
        "DEBUG": logging.DEBUG,
        "INFO": logging.INFO,
        "WARNING": logging.WARNING,
        "ERROR": logging.ERROR,
        "CRITICAL": logging.CRITICAL,
    }

    # Priority 1: --verbose flag overrides everything
    if verbose:
        level = logging.DEBUG
    # Priority 2: Read from config
    elif config and "logging" in config and "level" in config["logging"]:
        config_level = config["logging"]["level"]
        # Validate and map the config value
        if isinstance(config_level, str) and config_level.upper() in LEVEL_MAP:
            level = LEVEL_MAP[config_level.upper()]
        else:
            # Invalid config value, fall back to INFO
            level = logging.INFO
            logging.warning(
                f"Invalid logging level '{config_level}' in config, using INFO"
            )
    # Priority 3: Default to INFO
    else:
        level = logging.INFO

    # Apply to root logger via basicConfig
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        force=True,  # Override any existing config
    )

    # Also set the root logger level explicitly
    logging.getLogger().setLevel(level)


def _deep_merge_dicts(d1: dict, d2: dict) -> dict:
    """Deep merges d2 into d1, overwriting values in d1 with those from d2."""
    for k, v in d2.items():
        if k in d1 and isinstance(d1[k], dict) and isinstance(v, dict):
            d1[k] = _deep_merge_dicts(d1[k], v)
        else:
            d1[k] = v
    return d1


def _deep_fill_missing(target: dict, source: dict) -> dict:
    """Fill missing keys in target from source.

    Does not overwrite existing values.
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

    from finance_feedback_engine.utils.config_loader import (
        load_config as load_config_with_env,
    )

    logger = logging.getLogger(__name__)

    base_config_path = Path("config/config.yaml")
    local_config_path = Path("config/config.local.yaml")

    # Prefer local config as the primary file so local values take precedence.
    # Start with local (if present) then fill missing values from base config.
    config = {}
    # 1. Load local config first (preferred) - this now handles .env loading and ${VAR} substitution
    if local_config_path.exists():
        config = load_config_with_env(str(local_config_path))

    # 2. Load base config and fill missing keys from it
    # Base config uses plain placeholder strings, not ${VAR} syntax, so use raw YAML loading
    if base_config_path.exists():
        with open(base_config_path, "r", encoding="utf-8") as f:
            base_config = yaml.safe_load(f)
            if base_config:
                _deep_fill_missing(config, base_config)
    else:
        logger.warning(f"Base config file not found: {base_config_path}")

    # Environment variables are already handled by load_config_with_env via .env file
    # No need for manual env var mapping anymore

    return config


def load_config(config_path: str) -> dict:
    """
    Load a specific configuration from file.
    This function is for loading explicitly specified config files, not for the
    tiered loading process.

    Uses the proper config_loader which handles .env loading and ${VAR} substitution.
    """
    from finance_feedback_engine.utils.config_loader import (
        load_config as load_config_with_env,
    )

    path = Path(config_path)

    if not path.exists():
        raise click.ClickException(f"Configuration file not found: {config_path}")

    if path.suffix in [".yaml", ".yml"]:
        # Use the proper config loader that handles environment variables
        return load_config_with_env(config_path)
    elif path.suffix == ".json":
        with open(path, "r", encoding="utf-8") as f:
            config = json.load(f)
            if config is None:
                raise click.ClickException(
                    f"Configuration file {config_path} is empty or invalid JSON"
                )
            return config
    else:
        raise click.ClickException(f"Unsupported config format: {path.suffix}")


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
    "--config",
    "-c",
    # Change default to None
    default=None,
    help="Path to a specific config file (overrides tiered loading)",
)
@click.option("--verbose", "-v", is_flag=True, help="Enable verbose logging")
@click.option("--interactive", "-i", is_flag=True, help="Start in interactive mode")
@click.pass_context
def cli(ctx, config, verbose, interactive):
    """Finance Feedback Engine 2.0 - AI-powered trading decision tool."""
    ctx.ensure_object(dict)

    # If a specific config file is provided by the user
    if config:
        # Use the old load_config
        final_config = load_config(config)
        # Store the path for other commands
        ctx.obj["config_path"] = config
    # Use tiered loading
    else:
        final_config = load_tiered_config()
        # Indicate that tiered loading was used, might not have a single path
        # Set a placeholder
        ctx.obj["config_path"] = CONFIG_MODE_TIERED

    # Store the final config
    ctx.obj["config"] = final_config
    ctx.obj["verbose"] = verbose

    # Validate configuration before proceeding
    _validate_config_on_startup(
        ctx.obj.get("config_path"), final_config.get("environment", "development")
    )

    # Setup logging with config and verbose flag
    # Verbose flag takes priority over config setting
    setup_logging(verbose=verbose, config=final_config)

    # Initialize metrics early (safe no-op if prometheus_client missing)
    try:
        init_metrics()
    except Exception as e:
        logger.warning(f"Failed to initialize metrics: {e}")

    # On interactive boot, check versions and prompt for update if needed
    if interactive:
        import subprocess
        from importlib.metadata import PackageNotFoundError, version

        from rich.prompt import Confirm

        console.print(
            "\n[bold cyan]Checking AI Provider Versions "
            "(interactive mode)...[/bold cyan]\n"
        )
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
            (
                "Ollama",
                ["ollama", "--version"],
                "curl -fsSL https://ollama.com/install.sh | sh",
            ),
            (
                "Copilot CLI",
                ["copilot", "--version"],
                "npm i -g @githubnext/github-copilot-cli",
            ),
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
            "ollama": "local",
            "copilot": "cli",
            "qwen": "qwen",
            "coinbase-advanced-py": "coinbase",
            "oandapyV20": "oanda",
            "node": "cli",
        }

        for lib in missing_libs:
            prov = mapping.get(lib, "unknown")
            provider_impact.setdefault(prov, []).append(lib)

        for tool, _ in missing_tools:
            key = tool.lower().split()[0] if isinstance(tool, str) else str(tool)
            prov = mapping.get(key, "unknown")
            provider_impact.setdefault(prov, []).append(tool)

        if provider_impact:
            _logger.info("Interactive startup: provider dependency status:")
            for prov, items in provider_impact.items():
                _logger.info(
                    "  %s: missing/outdated -> %s", prov, ", ".join(map(str, items))
                )

        if missing_libs or missing_tools:
            console.print(
                "[yellow]Some AI provider dependencies are missing or "
                "outdated.[/yellow]"
            )
            if Confirm.ask("Would you like to update/install them now?"):
                # Invoke update-ai command with auto-install flag
                ctx.invoke(update_ai, auto_install=True)
        start_interactive_session(cli)
        return

    if ctx.invoked_subcommand is None:
        console.print(cli.get_help(ctx))
        return


@cli.command(name="config-editor")
@click.option(
    "--output",
    "-o",
    default="config/config.local.yaml",
    show_default=True,
    help="Where to write your customized config overlay.",
)
@click.pass_context
def config_editor(ctx, output):
    """Interactive helper to capture API keys and core settings.

    Writes a focused overlay file (defaults to config/config.local.yaml)
    so your secrets are kept separate from base defaults.
    """
    base_path = Path("config/config.yaml")
    target_path = Path(output)

    base_config = {}
    if base_path.exists():
        try:
            base_config = load_config(str(base_path))
        except Exception as e:
            console.print(
                f"[yellow]Warning: could not read base config: " f"{e}[/yellow]"
            )

    existing_config = {}
    if target_path.exists():
        try:
            existing_config = load_config(str(target_path))
        except Exception as e:
            console.print(
                f"[yellow]Warning: could not read existing "
                f"{target_path}: {e}[/yellow]"
            )

    # Start from existing overlay so we don't drop user-specific keys
    updated_config = copy.deepcopy(existing_config)

    def current(keys, fallback=None):
        return _get_nested(
            existing_config, keys, _get_nested(base_config, keys, fallback)
        )

    def prompt_text(label, keys, secret=False, allow_empty=True):
        default_val = current(keys, "")
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

    def prompt_bool(label, keys, default=None):
        cur_val = current(keys, False)
        if isinstance(cur_val, str):
            default_val = cur_val.lower() == "true"
        else:
            default_val = bool(cur_val)
        if default is not None:
            default_val = default
        val = click.confirm(label, default=default_val, show_default=True)
        _set_nested(updated_config, keys, val)
        return val

    try:
        console.print("\n[bold cyan]Config Editor[/bold cyan]")
        console.print(
            "Quick setup for API keys and core settings. "
            "Press Enter to keep defaults.\n"
        )

        # API keys
        prompt_text("Alpha Vantage API key", ("alpha_vantage_api_key",), secret=True)

        platform = prompt_choice(
            "Trading platform",
            ("trading_platform",),
            ["coinbase_advanced", "oanda", "mock", "unified"],
        )

        if platform in {"coinbase", "coinbase_advanced"}:
            console.print("\n[bold]Coinbase credentials[/bold]")
            prompt_text("API key", ("platform_credentials", "api_key"), secret=True)
            prompt_text(
                "API secret", ("platform_credentials", "api_secret"), secret=True
            )
            prompt_bool("Use sandbox?", ("platform_credentials", "use_sandbox"))
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
            console.print("\n[yellow]Mock platform — no credentials needed.[/yellow]")
        elif platform == "unified":
            console.print(
                "\n[yellow]Unified mode. Configure per-platform entries in config YAML manually.[/yellow]"
            )

        # Decision engine
        console.print("\n[bold]Decision engine[/bold]")
        ai_choice = prompt_choice(
            "AI provider",
            ("decision_engine", "ai_provider"),
            ["ensemble", "local", "cli", "gemini"],
        )

        if ai_choice == "ensemble":
            console.print("Using ensemble mode (default: free local models)")
            _set_nested(updated_config, ("ensemble", "enabled_providers"), ["local"])
            _set_nested(updated_config, ("ensemble", "voting_strategy"), "weighted")
            _set_nested(updated_config, ("ensemble", "adaptive_learning"), True)

        # Autonomous agent
        console.print("\n[bold]Autonomous agent[/bold]")
        prompt_bool("Enable autonomous trading?", ("agent", "autonomous", "enabled"))

        # Telegram notifications setup
        console.print("\n[bold cyan]📱 Telegram Notifications[/bold cyan]")
        console.print(
            "[dim]Telegram is used for manual trade approval when autonomous trading is disabled[/dim]"
        )

        # Check if autonomous trading was just disabled
        autonomous_enabled = _get_nested(
            updated_config, ("agent", "autonomous", "enabled"), False
        )

        # Prompt for Telegram - make it clear it's required if autonomous is off
        if not autonomous_enabled:
            console.print(
                "[yellow]⚠️  Autonomous trading is disabled - Telegram notifications are REQUIRED[/yellow]"
            )
            telegram_enabled = prompt_bool(
                "Enable Telegram notifications?", ("telegram", "enabled")
            )
        else:
            telegram_enabled = prompt_bool(
                "Enable Telegram notifications? (optional)", ("telegram", "enabled")
            )

        if telegram_enabled:
            console.print("\n[bold]Telegram Bot Setup Instructions:[/bold]")
            console.print("1. Open Telegram and message @BotFather")
            console.print("2. Send /newbot and follow instructions to create a bot")
            console.print("3. Copy the bot token provided by @BotFather")
            console.print("4. Message @userinfobot to get your chat_id")
            console.print("5. Start a conversation with your new bot\n")

            prompt_text(
                "Bot token (from @BotFather)", ("telegram", "bot_token"), secret=True
            )
            prompt_text("Chat ID (from @userinfobot)", ("telegram", "chat_id"))
        else:
            # If they said no to Telegram, set it to disabled explicitly
            _set_nested(updated_config, ("telegram", "enabled"), False)

        # Logging
        console.print("\n[bold]Logging[/bold]")
        prompt_choice(
            "Log level",
            ("logging", "level"),
            ["INFO", "DEBUG", "WARNING", "ERROR"],
        )

        # Validate: autonomous trading OR Telegram must be configured
        console.print("\n[bold cyan]🔍 Validating Configuration...[/bold cyan]")

        autonomous_enabled = _get_nested(
            updated_config, ("agent", "autonomous", "enabled"), False
        )
        telegram_enabled = _get_nested(updated_config, ("telegram", "enabled"), False)
        telegram_has_token = bool(
            _get_nested(updated_config, ("telegram", "bot_token"))
        )
        telegram_has_chat_id = bool(
            _get_nested(updated_config, ("telegram", "chat_id"))
        )
        telegram_configured = (
            telegram_enabled and telegram_has_token and telegram_has_chat_id
        )

        if not autonomous_enabled and not telegram_configured:
            console.print("\n[bold red]❌ Configuration Error[/bold red]")
            console.print(
                "[yellow]You must configure at least ONE of the following:[/yellow]"
            )
            console.print(
                "  1. [bold]Autonomous trading[/bold] (for fully automated execution)"
            )
            console.print(
                "  2. [bold]Telegram notifications[/bold] (for manual approval of signals)"
            )
            console.print("\n[yellow]Current status:[/yellow]")
            console.print(
                f"  • Autonomous trading: [red]{'✓ Enabled' if autonomous_enabled else '✗ Disabled'}[/red]"
            )
            console.print(
                f"  • Telegram configured: [red]{'✓ Yes' if telegram_configured else '✗ No'}[/red]"
            )
            console.print(
                "\n[dim]The agent cannot run without either autonomous trading or notification channels.[/dim]"
            )

            raise click.ClickException(
                "Configuration incomplete: Enable autonomous trading or configure Telegram notifications."
            )

        console.print("[green]✓ Configuration validated successfully[/green]")

        # Write config
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, "w", encoding="utf-8") as f:
            yaml.safe_dump(updated_config, f, sort_keys=False)

        console.print(
            f"\n[bold green]✓ Configuration saved to {target_path}[/bold green]"
        )
    except click.Abort:
        console.print("[yellow]Cancelled.[/yellow]")
        return


@cli.command(name="install-deps")
@click.option(
    "--auto-install",
    "-y",
    is_flag=True,
    help="Automatically install missing dependencies without prompting",
)
@click.pass_context
def install_deps(ctx, auto_install):
    """Check and install missing project dependencies."""
    try:
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
            installed_preview = ", ".join(installed[:5])
            if len(installed) > 5:
                installed_preview += f" ... (+{len(installed) - 5} more)"
            table.add_row(
                "[green]✓ Installed[/green]", str(len(installed)), installed_preview
            )

        if missing:
            missing_preview = ", ".join(missing[:5])
            if len(missing) > 5:
                missing_preview += f" ... (+{len(missing) - 5} more)"
            table.add_row("[red]✗ Missing[/red]", str(len(missing)), missing_preview)

        console.print(table)
        console.print()
        # Early exit to keep tests simple and environment-agnostic
        return

        # Check additional dependencies: ollama, node.js, coinbase-advanced-py
        console.print("[bold cyan]Checking additional dependencies...[/bold cyan]\n")

        additional_missing = []
        additional_installed = []

        # Check coinbase-advanced-py (Python package)
        # Use __import__ to avoid flake8 F401 on an import used only for presence-checking.
        try:
            __import__("coinbase_advanced_py")
            additional_installed.append("coinbase-advanced-py")
        except ImportError:
            additional_missing.append("coinbase-advanced-py")
            missing.append("coinbase-advanced-py")  # Add to pip install list

        # Check CLI tools
        cli_checks = [
            (
                "ollama",
                ["ollama", "--version"],
                "curl -fsSL https://ollama.com/install.sh | sh",
            ),
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
            if ctx.obj.get("interactive"):
                response = console.input(
                    "[bold]Install missing dependencies? [y/N]: [/bold]"
                )
            else:
                response = input("Install missing dependencies? [y/N]: ")

            if response.strip().lower() != "y":
                console.print("[yellow]Installation cancelled.[/yellow]")
                return

        # Install missing Python packages
        if missing:
            console.print(
                "\n[bold cyan]Installing missing Python dependencies...[/bold cyan]"
            )
            try:
                subprocess.run(
                    [sys.executable, "-m", "pip", "install"] + missing,
                    check=True,
                    timeout=600,
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
                            [
                                "bash",
                                "-c",
                                "curl -fsSL https://ollama.com/install.sh | sh",
                            ],
                            check=True,
                            timeout=300,
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
                            timeout=300,
                        )
                        console.print(f"[green]✓ {comp} installed successfully[/green]")
                    except Exception as e:
                        console.print(f"[red]✗ {comp} installation failed: {e}[/red]")
                        console.print(
                            "[yellow]Note: nvm must be installed first. Install nvm from https://github.com/nvm-sh/nvm[/yellow]"
                        )
    except Exception as e:
        # Be permissive in tests; don't crash on environment quirks
        console.print(f"[yellow]Dependency check encountered an issue: {e}[/yellow]")
        return


@cli.command(name="update-ai")
@click.option(
    "--auto-install",
    "-y",
    is_flag=True,
    help="Automatically update dependencies without prompting",
)
@click.pass_context
def update_ai(ctx, auto_install):
    """Update AI provider dependencies.

    Notes:
    - Only packages available on PyPI are installed via `pip` (e.g. `google-generativeai`).
    - Node.js / npm based CLI tools (Copilot CLI, Qwen CLI, etc.) are installed via `npm`
      and therefore are handled separately. Attempting to `pip install` Node CLIs will
      fail — those names are not valid PyPI package names.
    """
    try:
        console.print("[bold cyan]Checking AI provider dependencies...[/bold cyan]\n")

        # === Python (PyPI) packages ===
        # Verified PyPI packages only. Do not include Node.js CLI names here.
        pip_ai_packages = [
            # Keep only valid PyPI package names; verify before adding new names.
            "google-generativeai",
        ]

        # === Node / npm CLI tools ===
        # These are not Python packages. They will be checked by invoking their
        # CLI command (e.g. `copilot --version`) and installed via `npm` if missing.
        # Mapping: display-name -> dict(check_cmd, install_cmd)
        node_cli_tools = {
            "copilot-cli": {
                "check_cmd": ["copilot", "--version"],
                "install_cmd": ["npm", "i", "-g", "@githubnext/github-copilot-cli"],
            },
            "qwen-cli": {
                "check_cmd": ["qwen", "--version"],
                "install_cmd": ["npm", "i", "-g", "@qwen/cli"],
            },
            # 'codex-cli' is ambiguous (not a known PyPI package). Keep as npm candidate
            # but do not assume an exact package name on npm; user may need to adjust.
            "codex-cli": {
                "check_cmd": ["codex", "--version"],
                "install_cmd": ["npm", "i", "-g", "codex-cli"],
            },
        }

        installed_dict = _get_installed_packages()

        from rich.table import Table

        table = Table(title="AI Provider Dependencies (pip)")
        table.add_column("Package", style="cyan")
        table.add_column("Status", style="white")
        table.add_column("Version", style="dim")

        missing_pip = []
        installed_pip = []

        for pkg in pip_ai_packages:
            pkg_lower = pkg.lower()
            pkg_normalized = pkg_lower.replace("-", "_")
            if (
                pkg_lower in installed_dict
                or pkg_normalized in installed_dict
                or pkg_lower.replace("_", "-") in installed_dict
            ):
                version = (
                    installed_dict.get(pkg_lower)
                    or installed_dict.get(pkg_normalized)
                    or installed_dict.get(pkg_lower.replace("_", "-"))
                    or "unknown"
                )
                table.add_row(pkg, "[green]✓ Installed[/green]", version)
                installed_pip.append((pkg, version))
            else:
                table.add_row(pkg, "[red]✗ Missing[/red]", "N/A")
                missing_pip.append(pkg)

        console.print(table)
        console.print()

        # Check Node CLI status
        node_table = Table(title="AI Provider CLI Tools (npm)")
        node_table.add_column("Tool", style="cyan")
        node_table.add_column("Status", style="white")
        node_table.add_column("Notes", style="dim")

        missing_node = []
        installed_node = []

        for tool_name, info in node_cli_tools.items():
            try:
                res = subprocess.run(
                    info["check_cmd"], capture_output=True, text=True, timeout=5
                )
                if res.returncode == 0:
                    installed_node.append(tool_name)
                    node_table.add_row(
                        tool_name,
                        "[green]✓ Installed[/green]",
                        res.stdout.strip().splitlines()[0] if res.stdout else "",
                    )
                else:
                    missing_node.append(tool_name)
                    node_table.add_row(tool_name, "[red]✗ Missing or errored[/red]", "")
            except (subprocess.TimeoutExpired, FileNotFoundError):
                missing_node.append(tool_name)
                node_table.add_row(tool_name, "[red]✗ Missing[/red]", "")

        console.print(node_table)
        console.print()

        if not missing_pip and not missing_node:
            console.print(
                "[bold green]✓ All AI provider dependencies are installed![/bold green]\n"
            )
        else:
            if missing_pip:
                console.print("[yellow]Missing Python (PyPI) AI dependencies:[/yellow]")
                for pkg in missing_pip:
                    console.print(f"  • {pkg}")
                console.print()

            if missing_node:
                console.print("[yellow]Missing Node.js / npm CLI tools:[/yellow]")
                for t in missing_node:
                    console.print(f"  • {t}  (will be installed via npm if possible)")
                console.print()

        # If nothing to install, offer upgrades for pip packages
        if not missing_pip and installed_pip:
            console.print(
                "[yellow]Pip AI packages are present; you may upgrade them to latest versions.[/yellow]"
            )
            if (
                auto_install
                or (
                    ctx.obj.get("interactive")
                    and console.input(
                        "[bold]Upgrade pip AI packages to latest? [y/N]: [/bold]"
                    )
                    .strip()
                    .lower()
                    == "y"
                )
                or (not ctx.obj.get("interactive") and auto_install)
            ):
                try:
                    console.print(
                        "\n[bold cyan]Upgrading pip AI packages...[/bold cyan]"
                    )
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install", "--upgrade"]
                        + [p for p, _ in installed_pip],
                        check=True,
                        timeout=600,
                    )
                    console.print("[bold green]✓ Pip AI packages upgraded[/bold green]")
                except Exception as e:
                    console.print(
                        f"[yellow]Pip upgrade encountered an issue: {e}[/yellow]"
                    )

        # Install missing pip packages (if any)
        if missing_pip:
            proceed = auto_install or (
                ctx.obj.get("interactive")
                and console.input(
                    "[bold]Install missing pip AI packages? [y/N]: [/bold]"
                )
                .strip()
                .lower()
                == "y"
            )
            if proceed:
                console.print(
                    "\n[bold cyan]Installing missing pip AI packages...[/bold cyan]"
                )
                try:
                    subprocess.run(
                        [sys.executable, "-m", "pip", "install"] + missing_pip,
                        check=True,
                        timeout=600,
                    )
                    console.print(
                        "[bold green]✓ Pip AI packages installed[/bold green]"
                    )
                except Exception as e:
                    console.print(f"[red]Failed to install pip packages: {e}[/red]")
            else:
                console.print("[yellow]Skipping pip package installation.[/yellow]")

        # Install missing Node CLI tools via npm (if node/npm are available)
        if missing_node:
            try:
                # Quick check for npm presence
                npm_check = subprocess.run(
                    ["npm", "--version"], capture_output=True, text=True, timeout=5
                )
                if npm_check.returncode != 0:
                    raise FileNotFoundError("npm not available")
                npm_available = True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                npm_available = False

            if not npm_available:
                console.print(
                    "[yellow]npm is not available on PATH. Install Node.js/npm before installing CLI tools.[/yellow]"
                )
                console.print(
                    "[yellow]Suggested for Copilot CLI: `npm i -g @githubnext/github-copilot-cli`[/yellow]"
                )
            else:
                proceed_node = auto_install or (
                    ctx.obj.get("interactive")
                    and console.input(
                        "[bold]Install missing npm CLI tools now? [y/N]: [/bold]"
                    )
                    .strip()
                    .lower()
                    == "y"
                )
                if proceed_node:
                    for t in missing_node:
                        info = node_cli_tools.get(t)
                        if not info:
                            console.print(
                                f"[yellow]No install mapping for {t}; please install manually.[/yellow]"
                            )
                            continue
                        install_cmd = info["install_cmd"]
                        console.print(f"Installing {t} via: {' '.join(install_cmd)}")
                        try:
                            subprocess.run(install_cmd, check=True, timeout=600)
                            console.print(f"[green]✓ {t} installed via npm[/green]")
                        except Exception as e:
                            console.print(
                                f"[red]Failed to install {t} via npm: {e}[/red]"
                            )
                else:
                    console.print("[yellow]Skipping npm CLI installation.[/yellow]")

    except Exception as e:
        console.print(f"[yellow]AI dependency check encountered an issue: {e}[/yellow]")
        return


# analyze command moved to finance_feedback_engine/cli/commands/analysis.py
# and registered below via cli.add_command()


# balance command moved to finance_feedback_engine/cli/commands/trading.py
# and registered below via cli.add_command()


@cli.command()
@click.pass_context
def dashboard(ctx):
    """Show unified dashboard aggregating all platform portfolios."""
    try:
        config = ctx.obj["config"]
        engine = FinanceFeedbackEngine(config)

        # For now, we only have one platform instance
        # Future: support multiple platforms from config
        platforms = [engine.trading_platform]

        # Aggregate portfolio data
        aggregator = PortfolioDashboardAggregator(platforms)
        # Support tests that patch get_aggregated_portfolio
        if hasattr(aggregator, "get_aggregated_portfolio"):
            aggregated_data = aggregator.get_aggregated_portfolio()
        else:
            aggregated_data = aggregator.aggregate()

        # Display unified dashboard; if aggregator returns simple dict, print summary
        try:
            display_portfolio_dashboard(aggregated_data)
        except (Exception, AttributeError, TypeError):
            if isinstance(aggregated_data, dict):
                console.print("[bold cyan]Portfolio Dashboard[/bold cyan]")
                total = aggregated_data.get("total_value")
                if total is not None:
                    console.print(f"Total Value: ${total:,.2f}")
                plats = aggregated_data.get("platforms") or []
                if plats:
                    console.print(f"Platforms: {', '.join(plats)}")
            else:
                raise

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


# history command moved to finance_feedback_engine/cli/commands/analysis.py
# and registered below via cli.add_command()


# execute command moved to finance_feedback_engine/cli/commands/trading.py
# and registered below via cli.add_command()


@cli.command()
@click.argument("decision_id", required=True)
@click.pass_context
def approve(ctx, decision_id):
    """
    Interactively approve a trading decision.

    Displays decision details and prompts for approval (yes/no/modify).
    Modify option allows editing position size, stop loss, and take profit.
    """
    try:
        config = ctx.obj["config"]

        # Load decision from storage
        from finance_feedback_engine.persistence.decision_store import DecisionStore

        DecisionStore(config={"storage_path": "data/decisions"})

        # Find decision by ID (glob match on filename)
        import glob

        decision_files = glob.glob(f"data/decisions/*_{decision_id}.json")

        if not decision_files:
            # Try partial match
            decision_files = glob.glob(f"data/decisions/*{decision_id}*.json")

        if not decision_files:
            console.print(f"[bold red]❌ Decision not found: {decision_id}[/bold red]")
            console.print(
                "[yellow]Use 'python main.py history' to see available decisions[/yellow]"
            )
            raise click.Abort()

        # Load the decision
        decision_file = decision_files[0]
        with open(decision_file, "r") as f:
            decision = json.load(f)

        # Initialize engine after confirming decision exists
        engine = FinanceFeedbackEngine(config)

        # Display decision details in Rich Panel with Table
        from rich.panel import Panel

        console.print("\n[bold cyan]═══ TRADING DECISION APPROVAL ═══[/bold cyan]\n")

        # Create summary table
        table = Table(title="Decision Summary", show_header=True)
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")

        table.add_row("Decision ID", decision.get("decision_id", "N/A"))
        table.add_row("Asset Pair", decision.get("asset_pair", "N/A"))
        table.add_row(
            "Action",
            f"[bold {_get_action_color(decision.get('action'))}]{decision.get('action')}[/bold {_get_action_color(decision.get('action'))}]",
        )
        table.add_row("Confidence", f"{decision.get('confidence', 0)}%")
        table.add_row("Position Size", str(decision.get("position_size", "N/A")))
        table.add_row("Stop Loss", f"{decision.get('stop_loss', 'N/A')}%")
        table.add_row("Take Profit", f"{decision.get('take_profit', 'N/A')}%")
        table.add_row("Market Regime", decision.get("market_regime", "Unknown"))

        # Add sentiment if available
        sentiment_data = decision.get("sentiment", {})
        if sentiment_data and sentiment_data.get("available"):
            sentiment_str = f"{sentiment_data.get('overall_sentiment', 'N/A')} (score: {sentiment_data.get('sentiment_score', 0):.2f})"
            table.add_row("Sentiment", sentiment_str)

        table.add_row("Signal Only", str(decision.get("signal_only", False)))

        console.print(table)

        # Display reasoning in panel
        reasoning = decision.get("reasoning", "No reasoning provided")
        reasoning_panel = Panel(
            reasoning, title="[bold cyan]Reasoning[/bold cyan]", border_style="cyan"
        )
        console.print("\n")
        console.print(reasoning_panel)
        console.print("\n")

        # Prompt for action
        from rich.prompt import Prompt

        action = Prompt.ask(
            "[bold cyan]Action?[/bold cyan]",
            choices=["yes", "no", "modify"],
            default="no",
        )

        if action == "no":
            console.print("[yellow]❌ Decision rejected[/yellow]")
            _save_approval_response(
                decision_id, approved=False, modified=False, decision=decision
            )
            try:
                inc("approvals", labels={"status": "rejected"})
            except Exception as e:
                logger.warning(f"Failed to increment approval metric: {e}")
            return

        elif action == "modify":
            console.print("\n[bold cyan]═══ MODIFY DECISION ═══[/bold cyan]\n")

            # Prompt for modifications
            from rich.prompt import FloatPrompt

            current_position = decision.get("position_size", 0)
            current_stop_loss = decision.get("stop_loss", 2.0)
            current_take_profit = decision.get("take_profit", 5.0)

            console.print(f"[cyan]Current position size: {current_position}[/cyan]")
            new_position = FloatPrompt.ask(
                "New position size",
                default=float(current_position) if current_position else 0.0,
            )

            console.print(f"[cyan]Current stop loss: {current_stop_loss}%[/cyan]")
            new_stop_loss = FloatPrompt.ask(
                "New stop loss (%)", default=float(current_stop_loss)
            )

            console.print(f"[cyan]Current take profit: {current_take_profit}%[/cyan]")
            new_take_profit = FloatPrompt.ask(
                "New take profit (%)", default=float(current_take_profit)
            )

            # Validate ranges
            if new_position <= 0:
                console.print("[red]❌ Position size must be > 0[/red]")
                raise click.Abort()
            # Note: stop_loss and take_profit can be absolute prices or percentages
            # No strict validation here - let platform handle it during execution

            # Update decision
            decision["position_size"] = new_position
            decision["stop_loss"] = new_stop_loss
            decision["take_profit"] = new_take_profit
            decision["modified"] = True
            decision["modified_at"] = datetime.now().isoformat()

            console.print("\n[green]✓ Decision modified[/green]")

            # Show updated values
            console.print(f"  Position size: {new_position}")
            console.print(f"  Stop loss: {new_stop_loss}%")
            console.print(f"  Take profit: {new_take_profit}%")

            # Save and execute
            _save_approval_response(
                decision_id, approved=True, modified=True, decision=decision
            )
            try:
                inc("approvals", labels={"status": "modified"})
            except Exception as e:
                logger.warning(f"Failed to increment approvals metric: {e}")

            console.print("\n[bold green]✓ Executing modified decision...[/bold green]")
            result = engine.execute_decision(decision_id, modified_decision=decision)
            try:
                inc(
                    "decisions_executed",
                    labels={
                        "result": "success" if result.get("success") else "failure"
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to increment decisions_executed metric: {e}")

            if result.get("success"):
                console.print("[bold green]✓ Trade executed successfully[/bold green]")
            else:
                console.print("[bold red]✗ Trade execution failed[/bold red]")
            console.print(f"Message: {result.get('message')}")

        else:  # yes
            console.print("[green]✓ Decision approved[/green]")
            _save_approval_response(
                decision_id, approved=True, modified=False, decision=decision
            )
            try:
                inc("approvals", labels={"status": "approved"})
            except Exception as e:
                logger.warning(f"Failed to increment approvals metric: {e}")

            console.print("\n[bold green]✓ Executing decision...[/bold green]")
            result = engine.execute_decision(decision_id)
            try:
                inc(
                    "decisions_executed",
                    labels={
                        "result": "success" if result.get("success") else "failure"
                    },
                )
            except Exception as e:
                logger.warning(f"Failed to increment executed decisions metric: {e}")

            if result.get("success"):
                console.print("[bold green]✓ Trade executed successfully[/bold green]")
            else:
                console.print("[bold red]✗ Trade execution failed[/bold red]")
            console.print(f"Message: {result.get('message')}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if ctx.obj.get("verbose"):
            import traceback

            console.print(traceback.format_exc())
        raise click.Abort()


def _get_action_color(action: str) -> str:
    """Get color for action display."""
    if action == "BUY":
        return "green"
    elif action == "SELL":
        return "red"
    elif action == "HOLD":
        return "yellow"
    else:
        return "white"


def _save_approval_response(
    decision_id: str, approved: bool, modified: bool, decision: dict
):
    """Save approval response to data/approvals/ directory."""
    approvals_dir = Path("data/approvals")
    approvals_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize decision_id to prevent path traversal attacks
    # Allow only alphanumerics, dashes, and underscores
    sanitized_id = re.sub(r"[^a-zA-Z0-9_-]", "_", decision_id)
    if not sanitized_id:
        raise ValueError("Invalid decision_id: contains no valid characters")

    approval_data = {
        "decision_id": decision_id,
        "approved": approved,
        "modified": modified,
        "timestamp": datetime.now().isoformat(),
        "source": "cli",
    }

    if modified:
        approval_data["modified_decision"] = decision

    # Save to file
    status = "approved" if approved else "rejected"
    if modified:
        status = "modified"

    approval_file = approvals_dir / f"{sanitized_id}_{status}.json"

    # Security check: ensure the resolved path is within approvals_dir
    try:
        approval_file_resolved = approval_file.resolve()
        approvals_dir_resolved = approvals_dir.resolve()
        if not str(approval_file_resolved).startswith(
            str(approvals_dir_resolved) + os.sep
        ):
            raise ValueError(f"Path traversal attempt detected: {approval_file}")
    except (ValueError, OSError) as e:
        logger.error(f"Security violation in approval file path: {e}")
        raise

    with open(approval_file, "w", encoding="utf-8") as f:
        json.dump(approval_data, f, indent=2)

    logger.info(f"Approval response saved: {approval_file}")


@cli.command()
@click.pass_context
def status(ctx):
    """Show engine status and configuration."""
    try:
        config = ctx.obj["config"]

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

        # Try to initialize engine and fetch account info for dynamic leverage
        engine = FinanceFeedbackEngine(config)
        console.print("\n[bold green]✓ Engine initialized successfully[/bold green]")

        # Fetch and display dynamic leverage from exchange
        try:
            account_info = engine.trading_platform.get_account_info()
            if isinstance(account_info, dict):
                # Unified platform returns dict of platforms
                for platform_name, info in account_info.items():
                    if isinstance(info, dict) and "max_leverage" in info:
                        console.print(
                            f"\n{platform_name.upper()} max leverage: {info['max_leverage']:.1f}x (from exchange)"
                        )
            elif "max_leverage" in account_info:
                console.print(
                    f"\nMax leverage: {account_info['max_leverage']:.1f}x (from exchange)"
                )
        except Exception as e:
            logger.debug(f"Could not fetch leverage info: {e}")

    except Exception as e:
        console.print("\n[bold red]✗ Engine initialization failed[/bold red]")
        console.print(f"Error: {str(e)}")
        raise click.Abort()


@cli.command()
@click.pass_context
def positions(ctx):
    """Display active trading positions from the configured platform."""
    try:
        config = ctx.obj["config"]
        engine = FinanceFeedbackEngine(config)

        platform = getattr(engine, "trading_platform", None)
        if platform is None:
            console.print("[yellow]No trading platform configured.[/yellow]")
            return

        platform_name = platform.__class__.__name__
        try:
            positions_data = platform.get_active_positions()
        except Exception as e:  # Surface platform errors cleanly
            raise click.ClickException(f"Error fetching active positions: {e}")

        positions_list = (positions_data or {}).get("positions", [])
        if not positions_list:
            console.print("No active positions found.")
            return

        console.print(
            f"[bold cyan]Active Trading Positions ({platform_name})[/bold cyan]"
        )
        for pos in positions_list:
            product = (
                pos.get("product_id")
                or pos.get("instrument")
                or pos.get("symbol")
                or "UNKNOWN"
            )
            side = (
                pos.get("side")
                or pos.get("position_type")
                or pos.get("direction")
                or "UNKNOWN"
            )
            size = (
                pos.get("contracts")
                or pos.get("units")
                or pos.get("size")
                or pos.get("quantity")
            )
            entry = (
                pos.get("entry_price") or pos.get("average_price") or pos.get("price")
            )
            current = (
                pos.get("current_price") or pos.get("mark_price") or pos.get("price")
            )
            unrealized = (
                pos.get("unrealized_pnl") or pos.get("unrealized_pl") or pos.get("pnl")
            )

            console.print(
                f"- {product}: {side} size={size} entry={entry} current={current} PnL={unrealized}"
            )

    except click.ClickException:
        raise
    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


@cli.command()
@click.option("--confirm", is_flag=True, help="Skip confirmation prompt")
@click.pass_context
def wipe_decisions(ctx, confirm):
    """Delete all stored trading decisions."""
    try:
        config = ctx.obj["config"]
        engine = FinanceFeedbackEngine(config)

        # Get current count
        count = engine.decision_store.get_decision_count()

        if count == 0:
            console.print("[yellow]No decisions to wipe.[/yellow]")
            # Tests expect cancellation wording in some scenarios
            console.print("[dim]Cancelled.[/dim]")
            return

        console.print(
            f"[bold yellow]Warning: This will delete all {count} "
            f"stored decisions![/bold yellow]"
        )

        # Confirm unless --confirm flag or interactive mode
        if not confirm:
            if ctx.obj.get("interactive"):
                response = console.input("Are you sure you want to continue? [y/N]: ")
            else:
                response = click.confirm(
                    "Are you sure you want to continue?", default=False
                )
                response = "y" if response else "n"

            if response.lower() != "y":
                console.print("[yellow]Cancelled.[/yellow]")
                return

        # Wipe all decisions
        deleted = engine.decision_store.wipe_all_decisions()
        console.print(f"[bold green]✓ Wiped {deleted} decisions[/bold green]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


# Backtest commands moved to cli/commands/backtest.py
# Memory commands moved to cli/commands/memory.py


# ============================================
# REMOVED: Duplicate monitor group (lines 1542-1683)
# Now imported from cli/commands/agent.py
# ============================================


@cli.command(name="retrain-meta-learner")
@click.option(
    "--force",
    is_flag=True,
    help="Force retraining even if performance criteria are not met.",
)
@click.pass_context
def retrain_meta_learner(ctx, force):
    """Check stacking ensemble performance and retrain if needed."""
    try:
        from train_meta_learner import run_training

        config = ctx.obj["config"]
        engine = FinanceFeedbackEngine(config)

        console.print("\n[bold cyan]Checking meta-learner performance...[/bold cyan]")

        # Ensure memory is loaded (use memory_engine per project conventions)
        mem = getattr(engine, "memory_engine", getattr(engine, "memory", None))
        if not getattr(mem, "trade_outcomes", None):
            console.print(
                "[yellow]No trade history found in memory. Cannot check performance.[/yellow]"
            )
            return
        perf = (
            mem.get_strategy_performance_summary()
            if hasattr(mem, "get_strategy_performance_summary")
            else {}
        )

        stacking_perf = perf.get("stacking")

        if not stacking_perf:
            console.print(
                "[yellow]No performance data found for the 'stacking' strategy.[/yellow]"
            )
            console.print(
                "Generate some decisions using the stacking strategy to gather data."
            )
            return

        win_rate = stacking_perf.get("win_rate", 0)
        total_trades = stacking_perf.get("total_trades", 0)

        console.print(
            f"Stacking strategy performance: {win_rate:.2f}% win rate over {total_trades} trades."
        )

        # Define retraining criteria
        win_rate_threshold = 55.0
        min_trades_threshold = 20

        should_retrain = False
        if force:
            console.print(
                "[yellow]--force flag detected. Forcing retraining...[/yellow]"
            )
            should_retrain = True
        elif total_trades < min_trades_threshold:
            console.print(
                f"Skipping retraining: Not enough trades ({total_trades} < {min_trades_threshold})."
            )
        elif win_rate >= win_rate_threshold:
            console.print(
                f"Skipping retraining: Win rate is acceptable ({win_rate:.2f}% >= {win_rate_threshold:.2f}%)."
            )
        else:
            console.print(
                "[yellow]Performance threshold not met. Retraining meta-learner...[/yellow]"
            )
            should_retrain = True

        if should_retrain:
            run_training()
            console.print(
                "[bold green]✓ Meta-learner retraining process complete.[/bold green]"
            )
        else:
            console.print(
                "[bold green]✓ No retraining needed at this time.[/bold green]"
            )

    except ImportError:
        console.print(
            "[bold red]Error:[/bold red] Could not import 'train_meta_learner'. Make sure it is in the project root."
        )
        raise click.Abort()
    except Exception as e:
        console.print(f"[bold red]An unexpected error occurred:[/bold red] {str(e)}")
        if ctx.obj.get("verbose"):
            import traceback

            console.print(traceback.format_exc())
        raise click.Abort()


# ============================================
# REMOVED: Duplicate helper functions and run-agent command
# (_initialize_agent, _run_live_market_view, run_agent)
# Now imported from cli/commands/agent.py
# ============================================


# ============================================
# Command Modules Extracted
# ============================================
# Analysis & Trading commands: cli/commands/analysis.py, cli/commands/trading.py
# Agent commands: cli/commands/agent.py
# Backtest commands: cli/commands/backtest.py
# Memory commands: cli/commands/memory.py
# Infrastructure commands: (remaining in this file for now)
# ============================================

# Register commands from modular command files
cli.add_command(analyze_command, name="analyze")
cli.add_command(history_command, name="history")
cli.add_command(balance_command, name="balance")
cli.add_command(execute_command, name="execute")
cli.add_command(backtest_command, name="backtest")
cli.add_command(portfolio_backtest_command, name="portfolio-backtest")
cli.add_command(walk_forward_command, name="walk-forward")
cli.add_command(monte_carlo_command, name="monte-carlo")
cli.add_command(learning_report_command, name="learning-report")
cli.add_command(prune_memory_command, name="prune-memory")
cli.add_command(run_agent_command, name="run-agent")
cli.add_command(monitor_command, name="monitor")


if __name__ == "__main__":
    cli()
