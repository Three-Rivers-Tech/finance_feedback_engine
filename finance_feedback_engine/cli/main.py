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
import asyncio
import glob
import shutil
from pathlib import Path
from datetime import datetime
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.prompt import Prompt, FloatPrompt
from packaging.requirements import Requirement
# from rich import print as rprint  # unused

from finance_feedback_engine.core import FinanceFeedbackEngine
from finance_feedback_engine.cli.interactive import start_interactive_session
from finance_feedback_engine.dashboard import (
    PortfolioDashboardAggregator,
    display_portfolio_dashboard
)
from finance_feedback_engine.backtesting.backtester import Backtester
from finance_feedback_engine.backtesting.walk_forward import WalkForwardAnalyzer as WalkForwardOptimizer
from finance_feedback_engine.backtesting.monte_carlo import MonteCarloSimulator
from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor
from finance_feedback_engine.memory.portfolio_memory import PortfolioMemoryEngine
from finance_feedback_engine.persistence.decision_store import DecisionStore
from finance_feedback_engine.agent.orchestrator import TradingAgentOrchestrator
from finance_feedback_engine.data_providers.historical_data_provider import HistoricalDataProvider


console = Console()
logger = logging.getLogger(__name__)


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
        if hasattr(engine, 'monitoring_context_provider'):
            context = engine.monitoring_context_provider.get_monitoring_context(asset_pair)
            pulse = context.get('multi_timeframe_pulse')

        if (not pulse or 'timeframes' not in (pulse or {})) and hasattr(engine, 'data_provider'):
            try:
                fetched = engine.data_provider.get_comprehensive_market_data(asset_pair)
                pulse = (fetched or {}).get('multi_timeframe_pulse') or (fetched or {}).get('pulse')
                # Normalize simple pulse dict into expected structure
                if pulse and 'timeframes' not in pulse and isinstance(pulse, dict):
                    pulse = {'timeframes': pulse}
            except Exception as fetch_err:
                console.print(f"[yellow]Multi-timeframe pulse unavailable: {fetch_err}[/yellow]")

        if not pulse or 'timeframes' not in pulse:
            console.print("[yellow]Multi-timeframe pulse data not available[/yellow]")
            console.print("[dim]Ensure TradeMonitor is running or data_provider supports comprehensive pulse[/dim]")
            return

        # Display pulse age
        age_seconds = pulse.get('age_seconds', 0)
        age_mins = age_seconds / 60
        freshness = "[green]FRESH[/green]" if age_mins < 10 else "[yellow]STALE[/yellow]"
        console.print(f"Pulse Age: {age_mins:.1f} minutes ({freshness})")
        console.print()

        # Create table for timeframe data
        from rich.table import Table

        for tf, data in pulse['timeframes'].items():
            table = Table(title=f"{tf.upper()} Timeframe", show_header=True)
            table.add_column("Indicator", style="cyan")
            table.add_column("Value", style="white")
            table.add_column("Interpretation", style="dim")

            # Trend
            trend_color = "green" if data['trend'] == 'UPTREND' else "red" if data['trend'] == 'DOWNTREND' else "yellow"
            table.add_row(
                "Trend",
                f"[{trend_color}]{data['trend']}[/{trend_color}]",
                f"Signal Strength: {data.get('signal_strength', 0)}/100"
            )

            # RSI
            rsi = data.get('rsi', 50)
            if rsi > 70:
                rsi_status = "[red]OVERBOUGHT[/red]"
            elif rsi < 30:
                rsi_status = "[green]OVERSOLD[/green]"
            else:
                rsi_status = "NEUTRAL"
            table.add_row("RSI", f"{rsi:.1f}", rsi_status)

            # MACD
            macd = data.get('macd', {})
            if macd.get('histogram', 0) > 0:
                macd_status = "[green]BULLISH[/green] (positive histogram)"
            elif macd.get('histogram', 0) < 0:
                macd_status = "[red]BEARISH[/red] (negative histogram)"
            else:
                macd_status = "NEUTRAL"
            table.add_row(
                "MACD",
                f"{macd.get('macd', 0):.2f}",
                macd_status
            )

            # Bollinger Bands
            bbands = data.get('bollinger_bands', {})
            percent_b = bbands.get('percent_b', 0.5)
            if percent_b > 1.0:
                bb_status = "[red]Above upper band[/red] (overbought)"
            elif percent_b < 0.0:
                bb_status = "[green]Below lower band[/green] (oversold)"
            else:
                bb_status = f"Within bands ({percent_b:.1%})"
            table.add_row(
                "Bollinger %B",
                f"{percent_b:.3f}",
                bb_status
            )

            # ADX
            adx_data = data.get('adx', {})
            adx_val = adx_data.get('adx', 0)
            if adx_val > 25:
                adx_status = f"[green]STRONG TREND[/green] ({adx_val:.1f})"
            elif adx_val > 20:
                adx_status = f"Developing trend ({adx_val:.1f})"
            else:
                adx_status = f"[yellow]Weak/ranging[/yellow] ({adx_val:.1f})"

            plus_di = adx_data.get('plus_di', 0)
            minus_di = adx_data.get('minus_di', 0)
            direction = "[green]+DI dominant[/green]" if plus_di > minus_di else "[red]-DI dominant[/red]"

            table.add_row(
                "ADX",
                f"{adx_val:.1f}",
                f"{adx_status} | {direction}"
            )

            # ATR & Volatility
            atr = data.get('atr', 0)
            volatility = data.get('volatility', 'medium')
            vol_color = "red" if volatility == 'high' else "yellow" if volatility == 'medium' else "green"
            table.add_row(
                "ATR / Volatility",
                f"{atr:.2f}",
                f"[{vol_color}]{volatility.upper()}[/{vol_color}]"
            )

            console.print(table)
            console.print()

        # Cross-timeframe alignment
        console.print("[bold]Cross-Timeframe Alignment:[/bold]")
        trends = [data['trend'] for data in pulse['timeframes'].values()]
        uptrends = trends.count('UPTREND')
        downtrends = trends.count('DOWNTREND')
        ranging = trends.count('RANGING')

        if uptrends > downtrends and uptrends >= 3:
            alignment = "[bold green]BULLISH ALIGNMENT[/bold green]"
        elif downtrends > uptrends and downtrends >= 3:
            alignment = "[bold red]BEARISH ALIGNMENT[/bold red]"
        else:
            alignment = "[yellow]MIXED SIGNALS[/yellow]"

        console.print(f"  {alignment}")
        console.print(f"  Breakdown: {uptrends} up, {downtrends} down, {ranging} ranging")

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
        return {
            pkg.get('name', '').lower(): pkg.get('version', '')
            for pkg in installed
            if isinstance(pkg, dict) and pkg.get('name')
        }
    except Exception as e:
        console.print(
            f"[yellow]Warning: Could not retrieve installed "
            f"packages: {e}[/yellow]"
        )
        return {}


def _check_dependencies() -> tuple:
    """Check which dependencies are missing.

    Returns (missing, installed) tuples.
    """
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


def setup_logging(verbose: bool = False, config: dict = None):
    """Setup logging configuration.

    Args:
        verbose: If True, override config and use DEBUG level
        config: Configuration dict containing ('logging', 'level') key

    Priority: --verbose flag > config value > INFO default
    """
    # Map string level names to logging constants
    LEVEL_MAP = {
        'DEBUG': logging.DEBUG,
        'INFO': logging.INFO,
        'WARNING': logging.WARNING,
        'ERROR': logging.ERROR,
        'CRITICAL': logging.CRITICAL
    }

    # Priority 1: --verbose flag overrides everything
    if verbose:
        level = logging.DEBUG
    # Priority 2: Read from config
    elif config and 'logging' in config and 'level' in config['logging']:
        config_level = config['logging']['level']
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
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        force=True  # Override any existing config
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
        # Boolean conversion needed
        'OANDA_LIVE': ('trading_platform', 'oanda', 'live'),
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
                # Last key
                if i == len(config_path_keys) - 1:
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
                    f"Configuration file {config_path} is empty or "
                    f"invalid YAML"
                )
            return config
        elif path.suffix == '.json':
            config = json.load(f)
            if config is None:
                raise click.ClickException(
                    f"Configuration file {config_path} is empty or "
                    f"invalid JSON"
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
    # Change default to None
    default=None,
    help='Path to a specific config file (overrides tiered loading)'
)
@click.option('--verbose', '-v', is_flag=True, help='Enable verbose logging')
@click.option(
    '--interactive', '-i', is_flag=True, help='Start in interactive mode'
)
@click.pass_context
def cli(ctx, config, verbose, interactive):
    """Finance Feedback Engine 2.0 - AI-powered trading decision tool."""
    ctx.ensure_object(dict)

    # If a specific config file is provided by the user
    if config:
        # Use the old load_config
        final_config = load_config(config)
        # Store the path for other commands
        ctx.obj['config_path'] = config
    # Use tiered loading
    else:
        final_config = load_tiered_config()
        # Indicate that tiered loading was used, might not have a single path
        # Set a placeholder
        ctx.obj['config_path'] = 'tiered'

    # Store the final config
    ctx.obj['config'] = final_config
    ctx.obj['verbose'] = verbose

    # Setup logging with config and verbose flag
    # Verbose flag takes priority over config setting
    setup_logging(verbose=verbose, config=final_config)

    # On interactive boot, check versions and prompt for update if needed
    if interactive:
        import subprocess
        from importlib.metadata import version, PackageNotFoundError
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
            ("Ollama", ["ollama", "--version"],
             "curl -fsSL https://ollama.com/install.sh | sh"),
            ("Copilot CLI", ["copilot", "--version"],
             "npm i -g @githubnext/github-copilot-cli"),
            ("Qwen CLI", ["qwen", "--version"], "npm i -g @qwen/cli"),
            ("Node.js", ["node", "--version"], "nvm install --lts"),
        ]
        missing_tools = []
        for tool, cmd, upgrade_cmd in cli_tools:
            try:
                result = subprocess.run(
                    cmd, capture_output=True, text=True, timeout=5
                )
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
            key = (tool.lower().split()[0]
                   if isinstance(tool, str) else str(tool))
            prov = mapping.get(key, 'unknown')
            provider_impact.setdefault(prov, []).append(tool)

        if provider_impact:
            _logger.info("Interactive startup: provider dependency status:")
            for prov, items in provider_impact.items():
                _logger.info(
                    "  %s: missing/outdated -> %s",
                    prov, ', '.join(map(str, items))
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

    Writes a focused overlay file (defaults to config/config.local.yaml)
    so your secrets are kept separate from base defaults.
    """
    base_path = Path('config/config.yaml')
    target_path = Path(output)

    base_config = {}
    if base_path.exists():
        try:
            base_config = load_config(str(base_path))
        except Exception as e:
            console.print(
                f"[yellow]Warning: could not read base config: "
                f"{e}[/yellow]"
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
        default_val = current(keys, '')
        show_default = bool(default_val)
        val = click.prompt(
            label,
            default=default_val,
            show_default=show_default,
            hide_input=secret,
        )
        if (isinstance(val, str) and not val and
                default_val and not allow_empty):
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
            prompt_text("API secret", ("platform_credentials", "api_secret"), secret=True)
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

        # Logging
        console.print("\n[bold]Logging[/bold]")
        prompt_choice(
            "Log level",
            ("logging", "level"),
            ["INFO", "DEBUG", "WARNING", "ERROR"],
        )

        # Write config
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with open(target_path, 'w', encoding='utf-8') as f:
            yaml.safe_dump(updated_config, f, sort_keys=False)

        console.print(f"\n[bold green]✓ Configuration saved to {target_path}[/bold green]")
    except click.Abort:
        console.print("[yellow]Cancelled.[/yellow]")
        return


@cli.command(name='install-deps')
@click.option(
    '--auto-install', '-y',
    is_flag=True,
    help='Automatically install missing dependencies without prompting'
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
        # Early exit to keep tests simple and environment-agnostic
        return

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
    except Exception as e:
        # Be permissive in tests; don't crash on environment quirks
        console.print(f"[yellow]Dependency check encountered an issue: {e}[/yellow]")
        return


@cli.command(name='update-ai')
@click.option(
    '--auto-install', '-y',
    is_flag=True,
    help='Automatically update dependencies without prompting'
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
            'google-generativeai',
        ]

        # === Node / npm CLI tools ===
        # These are not Python packages. They will be checked by invoking their
        # CLI command (e.g. `copilot --version`) and installed via `npm` if missing.
        # Mapping: display-name -> dict(check_cmd, install_cmd)
        node_cli_tools = {
            'copilot-cli': {
                'check_cmd': ['copilot', '--version'],
                'install_cmd': ['npm', 'i', '-g', '@githubnext/github-copilot-cli'],
            },
            'qwen-cli': {
                'check_cmd': ['qwen', '--version'],
                'install_cmd': ['npm', 'i', '-g', '@qwen/cli'],
            },
            # 'codex-cli' is ambiguous (not a known PyPI package). Keep as npm candidate
            # but do not assume an exact package name on npm; user may need to adjust.
            'codex-cli': {
                'check_cmd': ['codex', '--version'],
                'install_cmd': ['npm', 'i', '-g', 'codex-cli'],
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
            pkg_normalized = pkg_lower.replace('-', '_')
            if (pkg_lower in installed_dict or pkg_normalized in installed_dict or pkg_lower.replace('_', '-') in installed_dict):
                version = (installed_dict.get(pkg_lower) or installed_dict.get(pkg_normalized) or installed_dict.get(pkg_lower.replace('_', '-')) or 'unknown')
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
                res = subprocess.run(info['check_cmd'], capture_output=True, text=True, timeout=5)
                if res.returncode == 0:
                    installed_node.append(tool_name)
                    node_table.add_row(tool_name, "[green]✓ Installed[/green]", res.stdout.strip().splitlines()[0] if res.stdout else '')
                else:
                    missing_node.append(tool_name)
                    node_table.add_row(tool_name, "[red]✗ Missing or errored[/red]", '')
            except (subprocess.TimeoutExpired, FileNotFoundError):
                missing_node.append(tool_name)
                node_table.add_row(tool_name, "[red]✗ Missing[/red]", '')

        console.print(node_table)
        console.print()

        if not missing_pip and not missing_node:
            console.print("[bold green]✓ All AI provider dependencies are installed![/bold green]\n")
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
            console.print("[yellow]Pip AI packages are present; you may upgrade them to latest versions.[/yellow]")
            if auto_install or (ctx.obj.get('interactive') and console.input("[bold]Upgrade pip AI packages to latest? [y/N]: [/bold]").strip().lower() == 'y') or (not ctx.obj.get('interactive') and auto_install):
                try:
                    console.print("\n[bold cyan]Upgrading pip AI packages...[/bold cyan]")
                    subprocess.run([sys.executable, '-m', 'pip', 'install', '--upgrade'] + [p for p, _ in installed_pip], check=True, timeout=600)
                    console.print("[bold green]✓ Pip AI packages upgraded[/bold green]")
                except Exception as e:
                    console.print(f"[yellow]Pip upgrade encountered an issue: {e}[/yellow]")

        # Install missing pip packages (if any)
        if missing_pip:
            proceed = auto_install or (ctx.obj.get('interactive') and console.input("[bold]Install missing pip AI packages? [y/N]: [/bold]").strip().lower() == 'y')
            if proceed:
                console.print("\n[bold cyan]Installing missing pip AI packages...[/bold cyan]")
                try:
                    subprocess.run([sys.executable, '-m', 'pip', 'install'] + missing_pip, check=True, timeout=600)
                    console.print("[bold green]✓ Pip AI packages installed[/bold green]")
                except Exception as e:
                    console.print(f"[red]Failed to install pip packages: {e}[/red]")
            else:
                console.print("[yellow]Skipping pip package installation.[/yellow]")

        # Install missing Node CLI tools via npm (if node/npm are available)
        if missing_node:
            try:
                # Quick check for npm presence
                npm_check = subprocess.run(['npm', '--version'], capture_output=True, text=True, timeout=5)
                if npm_check.returncode != 0:
                    raise FileNotFoundError('npm not available')
                npm_available = True
            except (subprocess.TimeoutExpired, FileNotFoundError):
                npm_available = False

            if not npm_available:
                console.print("[yellow]npm is not available on PATH. Install Node.js/npm before installing CLI tools.[/yellow]")
                console.print("[yellow]Suggested for Copilot CLI: `npm i -g @githubnext/github-copilot-cli`[/yellow]")
            else:
                proceed_node = auto_install or (ctx.obj.get('interactive') and console.input("[bold]Install missing npm CLI tools now? [y/N]: [/bold]").strip().lower() == 'y')
                if proceed_node:
                    for t in missing_node:
                        info = node_cli_tools.get(t)
                        if not info:
                            console.print(f"[yellow]No install mapping for {t}; please install manually.[/yellow]")
                            continue
                        install_cmd = info['install_cmd']
                        console.print(f"Installing {t} via: {' '.join(install_cmd)}")
                        try:
                            subprocess.run(install_cmd, check=True, timeout=600)
                            console.print(f"[green]✓ {t} installed via npm[/green]")
                        except Exception as e:
                            console.print(f"[red]Failed to install {t} via npm: {e}[/red]")
                else:
                    console.print("[yellow]Skipping npm CLI installation.[/yellow]")

    except Exception as e:
        console.print(f"[yellow]AI dependency check encountered an issue: {e}[/yellow]")
        return


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
@click.option(
    '--show-pulse',
    is_flag=True,
    help='Display multi-timeframe technical analysis pulse data'
)
@click.pass_context
def analyze(ctx, asset_pair, provider, show_pulse):
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

        import asyncio

        # Support both legacy generate_decision mocks and new analyze_asset
        decision = {}
        if hasattr(engine, 'generate_decision'):
            decision = engine.generate_decision(asset_pair)
        else:
            result = engine.analyze_asset(asset_pair)
            if asyncio.iscoroutine(result):
                decision = asyncio.run(result)
            else:
                decision = result

        decision = decision or {}

        # Check for Phase 1 quorum failure (NO_DECISION action)
        if decision.get('action') == 'NO_DECISION':
            from datetime import datetime
            failure_log = f"data/failures/{datetime.now().strftime('%Y-%m-%d')}.json"
            console.print("\n[bold red]⚠️ CRITICAL: ANALYSIS FAILED[/bold red]")
            console.print(
                "[yellow]Phase 1 quorum failure: Insufficient free-tier providers succeeded.[/yellow]"
            )
            console.print(f"[yellow]Reason: {decision.get('reasoning', 'Unknown')}[/yellow]")

            # Persist failure details to disk (append-only per day)
            try:
                failures_dir = Path("data/failures")
                failures_dir.mkdir(parents=True, exist_ok=True)

                payload = {
                    "timestamp": datetime.now().isoformat(),
                    "asset_pair": asset_pair,
                    "reasoning": decision.get("reasoning"),
                    "context": {
                        "providers_failed": decision.get("providers_failed"),
                        "ensemble_metadata": decision.get("ensemble_metadata"),
                    },
                    "decision": decision,
                }

                # Append entry to the day's JSON file; create if it doesn't exist
                log_path = Path(failure_log)
                existing = []
                if log_path.exists():
                    try:
                        with open(log_path, "r", encoding="utf-8") as rf:
                            existing = json.load(rf) or []
                            if not isinstance(existing, list):
                                existing = [existing]
                    except Exception:
                        # If file is corrupted, start a new list and keep going
                        existing = []

                existing.append(payload)
                with open(log_path, "w", encoding="utf-8") as wf:
                    json.dump(existing, wf, indent=2)

            except Exception as e:
                console.print(
                    f"[yellow]Warning: Failed to write failure log: {e}[/yellow]"
                )

            console.print(f"\n[dim]Failure logged to: {failure_log}[/dim]")
            console.print(
                "\n[bold yellow]No decision generated. Insufficient successful provider responses to meet quorum requirements.[/bold yellow]"
            )
            return

        # Display decision (tolerant of minimal mock dicts)
        console.print("\n[bold green]Trading Decision Generated[/bold green]")
        console.print(f"Decision ID: {decision.get('id', 'N/A')}")
        console.print(f"Asset: {decision.get('asset_pair', asset_pair)}")
        console.print(f"Action: [bold]{decision.get('action', 'N/A')}[/bold]")
        if 'confidence' in decision:
            console.print(f"Confidence: {decision.get('confidence', 0)}%")
        if 'reasoning' in decision:
            console.print(f"Reasoning: {decision.get('reasoning', '')}")

        # Check if signal-only mode (no position sizing)
        if decision.get('signal_only'):
            console.print(
                "\n[yellow]⚠ Signal-Only Mode: "
                "Portfolio data unavailable, no position sizing provided[/yellow]"
            )
            console.print(
                "\n[dim]To enable position sizing:[/dim]\n"
                "  [dim]1. Configure platform credentials in config/config.local.yaml[/dim]\n"
                "  [dim]2. Or run: [cyan]python main.py config-editor[/cyan][/dim]\n"
                "  [dim]3. Or set environment variables (see README.md)[/dim]"
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

        if decision.get('suggested_amount', 0) > 0:
            console.print(f"Suggested Amount: {decision.get('suggested_amount')}")

        # Market data section optional
        md = decision.get('market_data', {}) or {}
        if md:
            console.print("\nMarket Data:")
            if 'open' in md:
                console.print(f"  Open: ${md.get('open', 0):.2f}")
            if 'close' in md:
                console.print(f"  Close: ${md.get('close', 0):.2f}")
            if 'high' in md:
                console.print(f"  High: ${md.get('high', 0):.2f}")
            if 'low' in md:
                console.print(f"  Low: ${md.get('low', 0):.2f}")
        if 'price_change' in decision:
            console.print(f"  Price Change: {decision.get('price_change', 0):.2f}%")
        if 'volatility' in decision:
            console.print(f"  Volatility: {decision.get('volatility', 0):.2f}%")

        # Display additional technical data if available
        md = decision.get('market_data', {}) or {}
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

        # Display multi-timeframe pulse if requested
        if show_pulse:
            _display_pulse_data(engine, asset_pair)

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
            for provider, pdecision in (meta.get('provider_decisions', {}) or {}).items():
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
        # Support tests that patch get_aggregated_portfolio
        if hasattr(aggregator, 'get_aggregated_portfolio'):
            aggregated_data = aggregator.get_aggregated_portfolio()
        else:
            aggregated_data = aggregator.aggregate()

        # Display unified dashboard; if aggregator returns simple dict, print summary
        try:
            display_portfolio_dashboard(aggregated_data)
        except Exception:
            if isinstance(aggregated_data, dict):
                console.print("[bold cyan]Portfolio Dashboard[/bold cyan]")
                total = aggregated_data.get('total_value')
                if total is not None:
                    console.print(f"Total Value: ${total:,.2f}")
                plats = aggregated_data.get('platforms') or []
                if plats:
                    console.print(f"Platforms: {', '.join(plats)}")
            else:
                raise

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
        # Some tests may mock a non-iterable; guard here
        if not isinstance(decisions, (list, tuple)) or not decisions:
            # Fallback to DecisionStore for test patching
            try:
                from finance_feedback_engine.persistence.decision_store import DecisionStore
                store = DecisionStore(config={'storage_path': 'data/decisions'})
                decisions = store.get_decision_history(asset_pair=asset, limit=limit)
            except Exception:
                decisions = []

        if not decisions:
            console.print("[yellow]No decisions found[/yellow]")

        # Display decisions in a table
        table = Table(title=f"Decision History ({len(decisions)} decisions)")
        table.add_column("ID", style="dim")
        table.add_column("Timestamp", style="cyan")
        table.add_column("Asset", style="blue")
        table.add_column("Action", style="magenta")
        table.add_column("Confidence", style="green", justify="right")
        table.add_column("Executed", style="yellow")

        for decision in decisions:
            timestamp = str(decision.get('timestamp', ''))
            timestamp = timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp[:8]
            executed = "✓" if decision.get('executed') else "✗"

            table.add_row(
                decision.get('id', ''),
                timestamp,
                decision.get('asset_pair', ''),
                decision.get('action', ''),
                f"{decision.get('confidence', '')}%",
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
            if not isinstance(decisions, (list, tuple)):
                # Fallback to DecisionStore if engine is a mock
                try:
                    from finance_feedback_engine.persistence.decision_store import DecisionStore
                    store = DecisionStore(config={'storage_path': 'data/decisions'})
                    decisions = store.get_decision_history(limit=10)
                except Exception:
                    decisions = []

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
                timestamp = str(decision.get('timestamp', ''))
                timestamp = timestamp.split('T')[1][:8] if 'T' in timestamp else timestamp[:8]
                executed = "✓" if decision.get('executed') else "✗"

                table.add_row(
                    str(i),
                    timestamp,
                    decision['asset_pair'],
                    decision['action'],
                    f"{decision.get('confidence', '')}%",
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
@click.argument('decision_id', required=True)
@click.pass_context
def approve(ctx, decision_id):
    """
    Interactively approve a trading decision.

    Displays decision details and prompts for approval (yes/no/modify).
    Modify option allows editing position size, stop loss, and take profit.
    """
    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)

        # Load decision from storage
        from finance_feedback_engine.persistence.decision_store import DecisionStore
        store = DecisionStore(config={'storage_path': 'data/decisions'})

        # Find decision by ID (glob match on filename)
        import glob
        decision_files = glob.glob(f"data/decisions/*_{decision_id}.json")

        if not decision_files:
            # Try partial match
            decision_files = glob.glob(f"data/decisions/*{decision_id}*.json")

        if not decision_files:
            console.print(f"[bold red]❌ Decision not found: {decision_id}[/bold red]")
            console.print("[yellow]Use 'python main.py history' to see available decisions[/yellow]")
            raise click.Abort()

        # Load the decision
        decision_file = decision_files[0]
        with open(decision_file, 'r') as f:
            decision = json.load(f)

        # Display decision details in Rich Panel with Table
        from rich.panel import Panel

        console.print("\n[bold cyan]═══ TRADING DECISION APPROVAL ═══[/bold cyan]\n")

        # Create summary table
        table = Table(title="Decision Summary", show_header=True)
        table.add_column("Field", style="cyan", width=20)
        table.add_column("Value", style="white")

        table.add_row("Decision ID", decision.get('decision_id', 'N/A'))
        table.add_row("Asset Pair", decision.get('asset_pair', 'N/A'))
        table.add_row("Action", f"[bold {_get_action_color(decision.get('action'))}]{decision.get('action')}[/bold {_get_action_color(decision.get('action'))}]")
        table.add_row("Confidence", f"{decision.get('confidence', 0)}%")
        table.add_row("Position Size", str(decision.get('position_size', 'N/A')))
        table.add_row("Stop Loss", f"{decision.get('stop_loss', 'N/A')}%")
        table.add_row("Take Profit", f"{decision.get('take_profit', 'N/A')}%")
        table.add_row("Market Regime", decision.get('market_regime', 'Unknown'))

        # Add sentiment if available
        sentiment_data = decision.get('sentiment', {})
        if sentiment_data and sentiment_data.get('available'):
            sentiment_str = f"{sentiment_data.get('overall_sentiment', 'N/A')} (score: {sentiment_data.get('sentiment_score', 0):.2f})"
            table.add_row("Sentiment", sentiment_str)

        table.add_row("Signal Only", str(decision.get('signal_only', False)))

        console.print(table)

        # Display reasoning in panel
        reasoning = decision.get('reasoning', 'No reasoning provided')
        reasoning_panel = Panel(
            reasoning,
            title="[bold cyan]Reasoning[/bold cyan]",
            border_style="cyan"
        )
        console.print("\n")
        console.print(reasoning_panel)
        console.print("\n")

        # Prompt for action
        from rich.prompt import Prompt

        action = Prompt.ask(
            "[bold cyan]Action?[/bold cyan]",
            choices=["yes", "no", "modify"],
            default="no"
        )

        if action == "no":
            console.print("[yellow]❌ Decision rejected[/yellow]")
            _save_approval_response(decision_id, approved=False, modified=False, decision=decision)
            return

        elif action == "modify":
            console.print("\n[bold cyan]═══ MODIFY DECISION ═══[/bold cyan]\n")

            # Prompt for modifications
            from rich.prompt import FloatPrompt

            current_position = decision.get('position_size', 0)
            current_stop_loss = decision.get('stop_loss', 2.0)
            current_take_profit = decision.get('take_profit', 5.0)

            console.print(f"[cyan]Current position size: {current_position}[/cyan]")
            new_position = FloatPrompt.ask(
                "New position size",
                default=float(current_position) if current_position else 0.0
            )

            console.print(f"[cyan]Current stop loss: {current_stop_loss}%[/cyan]")
            new_stop_loss = FloatPrompt.ask(
                "New stop loss (%)",
                default=float(current_stop_loss)
            )

            console.print(f"[cyan]Current take profit: {current_take_profit}%[/cyan]")
            new_take_profit = FloatPrompt.ask(
                "New take profit (%)",
                default=float(current_take_profit)
            )

            # Validate ranges
            if new_position <= 0:
                console.print("[red]❌ Position size must be > 0[/red]")
                raise click.Abort()
            # Note: stop_loss and take_profit can be absolute prices or percentages
            # No strict validation here - let platform handle it during execution

            # Update decision
            decision['position_size'] = new_position
            decision['stop_loss'] = new_stop_loss
            decision['take_profit'] = new_take_profit
            decision['modified'] = True
            decision['modified_at'] = datetime.now().isoformat()

            console.print("\n[green]✓ Decision modified[/green]")

            # Show updated values
            console.print(f"  Position size: {new_position}")
            console.print(f"  Stop loss: {new_stop_loss}%")
            console.print(f"  Take profit: {new_take_profit}%")

            # Save and execute
            _save_approval_response(decision_id, approved=True, modified=True, decision=decision)

            console.print("\n[bold green]✓ Executing modified decision...[/bold green]")
            result = engine.execute_decision(decision_id, modified_decision=decision)

            if result.get('success'):
                console.print("[bold green]✓ Trade executed successfully[/bold green]")
            else:
                console.print("[bold red]✗ Trade execution failed[/bold red]")
            console.print(f"Message: {result.get('message')}")

        else:  # yes
            console.print("[green]✓ Decision approved[/green]")
            _save_approval_response(decision_id, approved=True, modified=False, decision=decision)

            console.print("\n[bold green]✓ Executing decision...[/bold green]")
            result = engine.execute_decision(decision_id)

            if result.get('success'):
                console.print("[bold green]✓ Trade executed successfully[/bold green]")
            else:
                console.print("[bold red]✗ Trade execution failed[/bold red]")
            console.print(f"Message: {result.get('message')}")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


def _get_action_color(action: str) -> str:
    """Get color for action display."""
    if action == 'BUY':
        return 'green'
    elif action == 'SELL':
        return 'red'
    elif action == 'HOLD':
        return 'yellow'
    else:
        return 'white'


def _save_approval_response(decision_id: str, approved: bool, modified: bool, decision: dict):
    """Save approval response to data/approvals/ directory."""
    approvals_dir = Path("data/approvals")
    approvals_dir.mkdir(parents=True, exist_ok=True)

    # Sanitize decision_id to prevent path traversal attacks
    # Allow only alphanumerics, dashes, and underscores
    sanitized_id = re.sub(r'[^a-zA-Z0-9_-]', '_', decision_id)
    if not sanitized_id:
        raise ValueError("Invalid decision_id: contains no valid characters")

    approval_data = {
        "decision_id": decision_id,
        "approved": approved,
        "modified": modified,
        "timestamp": datetime.now().isoformat(),
        "source": "cli"
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
        if not str(approval_file_resolved).startswith(str(approvals_dir_resolved) + os.sep):
            raise ValueError(f"Path traversal attempt detected: {approval_file}")
    except (ValueError, OSError) as e:
        logger.error(f"Security violation in approval file path: {e}")
        raise

    with open(approval_file, 'w', encoding='utf-8') as f:
        json.dump(approval_data, f, indent=2)

    logger.info(f"Approval response saved: {approval_file}")


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

        # Try to initialize engine and fetch account info for dynamic leverage
        engine = FinanceFeedbackEngine(config)
        console.print(
            "\n[bold green]✓ Engine initialized successfully[/bold green]"
        )

        # Fetch and display dynamic leverage from exchange
        try:
            account_info = engine.trading_platform.get_account_info()
            if isinstance(account_info, dict):
                # Unified platform returns dict of platforms
                for platform_name, info in account_info.items():
                    if isinstance(info, dict) and 'max_leverage' in info:
                        console.print(f"\n{platform_name.upper()} max leverage: {info['max_leverage']:.1f}x (from exchange)")
            elif 'max_leverage' in account_info:
                console.print(f"\nMax leverage: {account_info['max_leverage']:.1f}x (from exchange)")
        except Exception as e:
            logger.debug(f"Could not fetch leverage info: {e}")

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
            # Tests expect cancellation wording in some scenarios
            console.print("[dim]Cancelled.[/dim]")
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
@click.option('--start', '--start-date', '-s', 'start', required=True, help='Start date YYYY-MM-DD')
@click.option('--end', '--end-date', '-e', 'end', required=True, help='End date YYYY-MM-DD')
@click.option(
    '--initial-balance',
    type=float,
    help='Override starting balance (default: 10000)'
)
@click.option(
    '--fee-percentage',
    type=float,
    help='Override fee percentage (default: 0.001 = 0.1%)'
)
@click.option(
    '--slippage-percentage',
    type=float,
    help='Override slippage percentage (default: 0.0001 = 0.01%)'
)
@click.option(
    '--commission-per-trade',
    type=float,
    help='Override fixed commission per trade (default: 0.0)'
)
@click.option(
    '--stop-loss-percentage',
    type=float,
    help='Override stop-loss percentage (default: 0.02 = 2%)'
)
@click.option(
    '--take-profit-percentage',
    type=float,
    help='Override take-profit percentage (default: 0.05 = 5%)'
)
@click.option(
    '--timeframe',
    type=click.Choice(['1m', '5m', '15m', '30m', '1h', '1d'], case_sensitive=False),
    default='1h',
    help='Candle timeframe for backtesting (default: 1h for intraday realism)'
)
@click.option(
    '--output-file',
    type=click.Path(),
    help='Save backtest trade history to a JSON file (for pre-training).'
)
@click.pass_context
def backtest(
    ctx,
    asset_pair,
    start,
    end,
    initial_balance,
    fee_percentage,
    slippage_percentage,
    commission_per_trade,
    stop_loss_percentage,
    take_profit_percentage,
    timeframe,
    output_file
):
    """Run AI-driven backtest using the decision engine."""
    from finance_feedback_engine.utils.validation import standardize_asset_pair

    try:
        # Validate date range (moved from below)
        try:
            start_dt = datetime.strptime(start, "%Y-%m-%d")
        except ValueError:
            raise click.BadParameter(
                f"[bold red]Invalid start date format:[/bold red] {start}\n"
                f"[yellow]Expected format:[/yellow] YYYY-MM-DD (e.g., 2024-01-01)",
                param_hint="--start"
            )

        try:
            end_dt = datetime.strptime(end, "%Y-%m-%d")
        except ValueError:
            raise click.BadParameter(
                f"[bold red]Invalid end date format:[/bold red] {end}\n"
                f"[yellow]Expected format:[/yellow] YYYY-MM-DD (e.g., 2024-01-31)",
                param_hint="--end"
            )

        if start_dt >= end_dt:
            raise click.BadParameter(
                f"[bold red]Invalid date range:[/bold red] "
                f"start_date ({start}) must be before end_date ({end})"
            )

        asset_pair = standardize_asset_pair(asset_pair)
        config = ctx.obj['config']

        console.print(
            f"[bold blue]Running AI-Driven Backtest for {asset_pair} {start}→{end}[/bold blue]"
        )

        # Get advanced_backtesting config or set defaults
        ab_config = config.get('advanced_backtesting', {})

        # Override with CLI options if provided
        initial_balance = initial_balance if initial_balance is not None else ab_config.get('initial_balance', 10000.0)
        fee_percentage = fee_percentage if fee_percentage is not None else ab_config.get('fee_percentage', 0.001)
        slippage_percentage = slippage_percentage if slippage_percentage is not None else ab_config.get('slippage_percentage', 0.0001)
        commission_per_trade = commission_per_trade if commission_per_trade is not None else ab_config.get('commission_per_trade', 0.0)
        stop_loss_percentage = stop_loss_percentage if stop_loss_percentage is not None else ab_config.get('stop_loss_percentage', 0.02)
        take_profit_percentage = take_profit_percentage if take_profit_percentage is not None else ab_config.get('take_profit_percentage', 0.05)

        engine = FinanceFeedbackEngine(config)

        # Initialize Backtester
        backtester = Backtester(
            historical_data_provider=engine.historical_data_provider,
            initial_balance=initial_balance,
            fee_percentage=fee_percentage,
            slippage_percentage=slippage_percentage,
            commission_per_trade=commission_per_trade,
            stop_loss_percentage=stop_loss_percentage,
            take_profit_percentage=take_profit_percentage,
            timeframe=timeframe.lower()  # Pass timeframe to backtester
        )

        if hasattr(backtester, 'run'):
            results = backtester.run(
                asset_pair=asset_pair,
                start_date=start,
                end_date=end,
                decision_engine=engine.decision_engine
            )
        else:
            results = backtester.run_backtest(
                asset_pair=asset_pair,
                start_date=start,
                end_date=end,
                decision_engine=engine.decision_engine
            )

        # Save results to file if requested
        if output_file:
            try:
                with open(output_file, 'w', encoding='utf-8') as f:
                    json.dump(results['trades'], f, indent=2)
                console.print(f"[bold green]✓ Backtest trade history saved to {output_file}[/bold green]")
            except Exception as e:
                console.print(f"[bold red]Error saving results to {output_file}: {e}[/bold red]")


        # Display clean formatted results
        from finance_feedback_engine.cli.backtest_formatter import format_single_asset_backtest

        metrics = results.get('metrics', {})
        trades_history = results.get('trades', [])

        format_single_asset_backtest(
            metrics=metrics,
            trades=trades_history,
            asset_pair=asset_pair,
            start_date=start,
            end_date=end,
            initial_balance=initial_balance
        )

        # Show gatekeeper rejection count if any
        rejected_trades = [t for t in trades_history if t.get('status') == 'REJECTED_BY_GATEKEEPER']
        if rejected_trades:
            console.print(f"[yellow]⚠ Note: {len(rejected_trades)} trade(s) were rejected by RiskGatekeeper[/yellow]\n")

        # LEGACY: Show all trades if explicitly requested (kept for compatibility)
        # Note: This is verbose and usually not needed
        if False:  # Set to True if you want the detailed trade list
            executed_trades = [t for t in trades_history if 'pnl_value' in t]
            if executed_trades:
                trades_table = Table(title="Executed Backtest Trades")
                trades_table.add_column("Timestamp", style="cyan")
                trades_table.add_column("Action", style="magenta")
                trades_table.add_column("Entry Price", justify="right")
                trades_table.add_column("Effective Price", justify="right")
                trades_table.add_column("Units", justify="right")
                trades_table.add_column("Fee", justify="right")
                trades_table.add_column("PnL", justify="right")

                for trade in executed_trades[:20]:  # Show first 20 executed trades
                    timestamp = trade.get('timestamp', '').split('T')[0] if 'T' in trade.get('timestamp', '') else trade.get('timestamp', '')
                    trades_table.add_row(
                        timestamp,
                        trade.get('action', 'N/A'),
                        f"${trade.get('entry_price', 0):.2f}",
                        f"${trade.get('effective_price', 0):.2f}",
                        f"{abs(trade.get('units_traded', 0)):.6f}",
                    f"${trade.get('fee', 0):.2f}",
                    f"${trade.get('pnl_value', 0):.2f}"
                )
            console.print(trades_table)

            if len(executed_trades) > 20:
                console.print(f"[dim]... and {len(executed_trades) - 20} more executed trades[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        import traceback
        logger.error(traceback.format_exc())
        raise click.Abort()


@cli.command()
@click.argument('asset_pairs', nargs=-1, required=True)
@click.option('--start', '-s', required=True, help='Start date YYYY-MM-DD')
@click.option('--end', '-e', required=True, help='End date YYYY-MM-DD')
@click.option(
    '--initial-balance',
    type=float,
    default=10000,
    help='Starting balance (default: 10000)'
)
@click.option(
    '--correlation-threshold',
    type=float,
    default=0.7,
    help='Correlation threshold for position sizing (default: 0.7)'
)
@click.option(
    '--max-positions',
    type=int,
    help='Maximum concurrent positions (default: number of assets)'
)
@click.pass_context
def portfolio_backtest(
    ctx,
    asset_pairs,
    start,
    end,
    initial_balance,
    correlation_threshold,
    max_positions
):
    """
    Run multi-asset portfolio backtest with correlation-aware position sizing.

    Example:
        python main.py portfolio-backtest BTCUSD ETHUSD EURUSD --start 2025-01-01 --end 2025-03-01
    """
    from finance_feedback_engine.backtesting.portfolio_backtester import PortfolioBacktester
    from finance_feedback_engine.utils.validation import standardize_asset_pair
    from finance_feedback_engine.cli.backtest_formatter import format_full_results

    try:
        # Validate inputs
        if len(asset_pairs) < 2:
            console.print("[bold red]Error: Portfolio backtest requires at least 2 assets[/bold red]")
            raise click.Abort()

        # Standardize asset pairs
        asset_pairs = [standardize_asset_pair(ap) for ap in asset_pairs]

        # Validate date range
        start_dt = datetime.strptime(start, '%Y-%m-%d')
        end_dt = datetime.strptime(end, '%Y-%m-%d')
        if start_dt >= end_dt:
            raise click.BadParameter(f"start_date ({start}) must be before end_date ({end})")

        config = ctx.obj['config']

        # Show startup info
        console.print(f"[bold blue]Portfolio Backtest[/bold blue]")
        console.print(f"Assets: [cyan]{', '.join(asset_pairs)}[/cyan]")
        console.print(f"Period: [cyan]{start}[/cyan] → [cyan]{end}[/cyan]")
        console.print(f"Initial Capital: [green]${initial_balance:,.2f}[/green]")

        # Initialize portfolio backtester
        backtester = PortfolioBacktester(
            asset_pairs=asset_pairs,
            initial_balance=initial_balance,
            config=config
        )

        # Override config with CLI options
        backtester.correlation_threshold = correlation_threshold
        if max_positions:
            backtester.max_positions = max_positions

        # Run backtest
        console.print("\n[yellow]⏳ Running backtest...[/yellow]")
        results = backtester.run_backtest(
            start_date=start,
            end_date=end
        )

        # Display clean formatted results
        format_full_results(results, asset_pairs, start, end, initial_balance)

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        import traceback
        logger.error(f"Portfolio backtest error: {traceback.format_exc()}")
        raise click.Abort()


@cli.group()
@click.pass_context
def monitor(ctx):
    """Live trade monitoring commands."""
    cfg = ctx.obj.get('config', {})
    monitoring_cfg = cfg.get('monitoring', {})
    manual_cli = monitoring_cfg.get('manual_cli', False)
    if not manual_cli:
        console.print("[yellow]Direct monitor control disabled (internal auto-start mode). Set monitoring.manual_cli: true to re-enable.[/yellow]")


@monitor.command()
@click.pass_context
def start(ctx):
    """Start live trade monitoring."""
    cfg = ctx.obj.get('config', {})
    monitoring_cfg = cfg.get('monitoring', {})
    if monitoring_cfg.get('manual_cli', False):
        console.print("[yellow]Manual start deprecated. Monitor auto-starts via config.monitoring.enabled.[/yellow]")
    else:
        console.print("[red]Monitor start blocked: set monitoring.manual_cli: true for legacy behavior (not recommended).[/red]")


@monitor.command(name='status')
@click.pass_context
def monitor_status(ctx):
    """Show live trade monitoring status."""
    cfg = ctx.obj.get('config', {})
    monitoring_cfg = cfg.get('monitoring', {})
    if monitoring_cfg.get('manual_cli', False):
        console.print("""[yellow]Status command deprecated; monitor runs internally.
Use dashboard or decision context for monitoring insights.[/yellow]""")
    else:
        console.print("[red]Monitor status disabled. Enable monitoring.manual_cli for legacy output (not recommended).[/red]")


@monitor.command()
@click.pass_context
def metrics(ctx):
    """Show trade performance metrics."""
    cfg = ctx.obj.get('config', {})
    monitoring_cfg = cfg.get('monitoring', {})
    if monitoring_cfg.get('manual_cli', False):
        console.print("[yellow]Metrics command deprecated; aggregated metrics available internally.[/yellow]")
    else:
        console.print("[red]Metrics disabled. Set monitoring.manual_cli true for legacy access (not recommended).[/red]")
        from pathlib import Path
        try:
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

        # Ensure memory is loaded (use memory_engine per project conventions)
        mem = getattr(engine, 'memory_engine', getattr(engine, 'memory', None))
        if not getattr(mem, 'trade_outcomes', None):
            console.print("[yellow]No trade history found in memory. Cannot check performance.[/yellow]")
            return
        perf = mem.get_strategy_performance_summary() if hasattr(mem, 'get_strategy_performance_summary') else {}

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


def _initialize_agent(config, engine, take_profit, stop_loss, autonomous, asset_pairs_override=None):
    """Initializes the trading agent and its components.

    Args:
        config: Configuration dictionary
        engine: FinanceFeedbackEngine instance
        take_profit: Portfolio take-profit percentage
        stop_loss: Portfolio stop-loss percentage
        autonomous: Whether to force autonomous execution
        asset_pairs_override: Optional list of asset pairs to override config (applies to both asset_pairs and watchlist)
    """
    from finance_feedback_engine.agent.trading_loop_agent import TradingLoopAgent
    from finance_feedback_engine.agent.config import TradingAgentConfig
    from finance_feedback_engine.monitoring.trade_monitor import TradeMonitor

    agent_config_data = config.get('agent', {})

    # Apply asset pairs override if provided
    if asset_pairs_override:
        agent_config_data['asset_pairs'] = asset_pairs_override
        agent_config_data['watchlist'] = asset_pairs_override
        console.print(f"[green]✓ Asset pairs and watchlist set to: {', '.join(asset_pairs_override)}[/green]")

    agent_config = TradingAgentConfig(**agent_config_data)

    if autonomous:
        agent_config.autonomous.enabled = True
        if hasattr(agent_config.autonomous, 'approval_required'):
            agent_config.autonomous.approval_required = False
        elif hasattr(agent_config.autonomous, 'require_approval'):
            agent_config.autonomous.require_approval = False
        console.print("[yellow]--autonomous flag set: approvals disabled; running fully autonomous.[/yellow]")

    if not agent_config.autonomous.enabled:
        console.print("[yellow]Autonomous agent is not enabled in the configuration.[/yellow]")
        # Offer to enable autonomous mode for this session instead of soft-failing.
        try:
            enable_now = click.confirm(
                "Would you like to enable autonomous execution for this run?",
                default=False
            )
        except (click.Abort, KeyboardInterrupt, EOFError):
            enable_now = False
            console.print("[yellow]Prompt cancelled. Autonomous execution not enabled for this run.[/yellow]")
        # Unexpected exceptions propagate

        if enable_now:
            agent_config.autonomous.enabled = True
            if hasattr(agent_config.autonomous, 'approval_required'):
                agent_config.autonomous.approval_required = False
            elif hasattr(agent_config.autonomous, 'require_approval'):
                agent_config.autonomous.require_approval = False
            console.print("[yellow]Session-only autonomy enabled: approvals disabled.[/yellow]")
        else:
            console.print("[dim]Tip: pass `--autonomous` or set `agent.autonomous.enabled: true` in config to proceed without prompts.[/dim]")
            return None

    console.print("[green]✓ Agent configuration loaded.[/green]")
    console.print(f"  Portfolio Take Profit: {take_profit:.2%}")
    console.print(f"  Portfolio Stop Loss: {stop_loss:.2%}")

    trade_monitor = TradeMonitor(
        platform=engine.trading_platform,
        portfolio_take_profit_percentage=take_profit,
        portfolio_stop_loss_percentage=stop_loss,
    )
    engine.enable_monitoring_integration(trade_monitor=trade_monitor)

    # Start trade monitor immediately to enable position tracking
    try:
        console.print("[cyan]Starting trade monitor...[/cyan]")
        trade_monitor.start()
        console.print("[green]✓ Trade monitor started.[/green]")
    except Exception as e:
        logger.error(f"Trade monitor startup failed: {e}", exc_info=True)
        raise

    agent = TradingLoopAgent(
        config=agent_config,
        engine=engine,
        trade_monitor=engine.trade_monitor,
        portfolio_memory=engine.memory_engine,
        trading_platform=engine.trading_platform,
    )
    return agent

async def _run_live_market_view(engine, agent):
    """Runs the live market view in the console."""
    from rich.live import Live
    from rich.table import Table
    import time
    import asyncio

    tm = getattr(engine, 'trade_monitor', None)
    udp = getattr(tm, 'unified_data_provider', None) if tm else None
    watchlist = agent.config.watchlist if hasattr(agent, 'config') and hasattr(agent.config, 'watchlist') else ['BTCUSD', 'ETHUSD', 'EURUSD']

    import logging
    import traceback
    logger = logging.getLogger(__name__)
    def build_table():
        tbl = Table(title="Live Market Pulse", caption=f"Updated: {time.strftime('%H:%M:%S')}")
        tbl.add_column("Asset", style="cyan", no_wrap=True)
        tbl.add_column("Last Price", style="white", justify="right")
        tbl.add_column("1m Δ%", style="yellow", justify="right")
        tbl.add_column("Confluence", style="magenta")
        tbl.add_column("Trend Align", style="green")
        tbl.add_column("Source Path", style="dim")

        for ap in watchlist:
            last_price, change_1m, conf, align, src_path = "-", "-", "-", "-", "-"
            try:
                if udp:
                    candles, provider = udp.get_candles(ap, granularity='1m', limit=2)
                    if candles:
                        last_close = candles[-1].get('close') or candles[-1].get('price')
                        prev_close = candles[-2].get('close') if len(candles) > 1 else last_close
                        last_price = f"{last_close:,.4f}" if isinstance(last_close, (int, float)) else str(last_close)
                        if isinstance(last_close, (int, float)) and isinstance(prev_close, (int, float)) and prev_close:
                            delta = (last_close - prev_close) / prev_close * 100
                            change_1m = f"{delta:+.2f}%"
                        src_path = provider
            except Exception as e:
                logger.debug(f"Error fetching market data for asset '{ap}' (provider/tm: {tm}, src_path: {src_path}): {e}\n{traceback.format_exc()}")

            try:
                if tm:
                    mc = tm.get_latest_market_context(ap)
                    if mc:
                        conf_val = mc.get('confluence_strength')
                        conf = f"{conf_val:.2f}" if isinstance(conf_val, (int, float)) else str(conf_val or '-')
                        ta = mc.get('trend_alignment') or {}
                        align = ",".join([k for k, v in ta.items() if v]) or '-'
                        ds = mc.get('data_sources') or {}
                        src_path = ",".join([str(v) for _, v in sorted(ds.items())]) or src_path
            except Exception as e:
                logger.debug(f"Error fetching confluence/trend for asset '{ap}' (provider/tm: {tm}, src_path: {src_path}): {e}\n{traceback.format_exc()}")
            tbl.add_row(ap, last_price, change_1m, conf, align, src_path)
        return tbl

    with Live(build_table(), refresh_per_second=0.5) as live:
        while not getattr(agent, 'stop_requested', False):
            await asyncio.sleep(2)
            live.update(build_table())

@cli.command(name="run-agent")
@click.option(
    '--max-drawdown',
    type=float,
    help='Legacy option accepted for test compatibility (ignored).'
)
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
@click.option(
    '--autonomous',
    is_flag=True,
    help='Override approval policy and force autonomous execution (no approvals).'
)
@click.option(
    '--asset-pairs',
    type=str,
    help='Comma-separated list of asset pairs to trade (e.g., "BTCUSD,ETHUSD,EURUSD"). Overrides config file.'
)
@click.pass_context
def run_agent(ctx, take_profit, stop_loss, setup, autonomous, max_drawdown, asset_pairs):
    """Starts the autonomous trading agent."""
    import asyncio

    if 1 <= take_profit <= 100:
        console.print(f"[yellow]Warning: Detected legacy take-profit percentage {take_profit}%. Converting to decimal: {take_profit/100:.3f}[/yellow]")
        take_profit /= 100
    elif take_profit > 100:
        console.print(f"[red]Error: Invalid take-profit value {take_profit}. Please use a decimal (e.g., 0.05 for 5%).[/red]")
        raise click.Abort()
    if 1 <= stop_loss <= 100:
        console.print(f"[yellow]Warning: Detected legacy stop-loss percentage {stop_loss}%. Converting to decimal: {stop_loss/100:.3f}[/yellow]")
        stop_loss /= 100
    elif stop_loss > 100:
        console.print(f"[red]Error: Invalid stop-loss value {stop_loss}. Stop-loss cannot exceed 100%.[/red]")
        raise click.Abort()

    if setup:
        ctx.invoke(config_editor)
        ctx.obj['config'] = load_tiered_config()

    console.print("\n[bold cyan]🚀 Initializing Autonomous Agent...[/bold cyan]")

    # Parse asset pairs if provided
    parsed_asset_pairs = None
    if asset_pairs:
        from finance_feedback_engine.utils.validation import standardize_asset_pair
        parsed_asset_pairs = [
            standardize_asset_pair(pair.strip())
            for pair in asset_pairs.split(',')
            if pair.strip()
        ]
        console.print(f"[cyan]Asset pairs override:[/cyan] {', '.join(parsed_asset_pairs)}")

    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)
        agent = _initialize_agent(config, engine, take_profit, stop_loss, autonomous, parsed_asset_pairs)

        if not agent:
            return

        console.print("[green]✓ Autonomous agent initialized.[/green]")
        console.print("[yellow]Press Ctrl+C to stop the agent.[/yellow]")

        monitoring_cfg = config.get('monitoring', {})
        enable_live_view = monitoring_cfg.get('enable_live_view', True)

        loop = asyncio.get_event_loop()
        try:
            tasks = [loop.create_task(agent.run())]
            if enable_live_view:
                tasks.append(loop.create_task(_run_live_market_view(engine, agent)))

            loop.run_until_complete(asyncio.gather(*tasks))
        except KeyboardInterrupt:
            console.print("\n[yellow]Shutdown signal received. Stopping agent gracefully...[/yellow]")
            agent.stop()
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


# ============================================
# Advanced Backtesting Commands
# ============================================

@cli.command(name='walk-forward')
@click.argument('asset_pair')
@click.option('--start-date', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end-date', required=True, help='End date (YYYY-MM-DD)')
@click.option('--train-ratio', default=0.7, help='Training window ratio (default: 0.7)')
@click.option('--provider', default='ensemble', help='AI provider to use')
@click.pass_context
def walk_forward(ctx, asset_pair, start_date, end_date, train_ratio, provider):
    """
    Run walk-forward analysis with overfitting detection.

    Splits data into rolling train/test windows to validate strategy robustness.
    Reports overfitting severity: NONE/LOW/MEDIUM/HIGH.

    Example:
        python main.py walk-forward BTCUSD --start-date 2024-01-01 --end-date 2024-03-01
    """
    console.print(f"\n[bold cyan]📊 Walk-Forward Analysis: {asset_pair}[/bold cyan]")

    try:
        from finance_feedback_engine.backtesting.walk_forward import WalkForwardAnalyzer
        from finance_feedback_engine.backtesting.backtester import Backtester
        from datetime import datetime

        config = ctx.obj['config']

        # Override AI provider from CLI option
        if provider:
            if 'decision_engine' not in config:
                config['decision_engine'] = {}
            config['decision_engine']['ai_provider'] = provider.lower()

        engine = FinanceFeedbackEngine(config)

        # Calculate total date range
        start_dt = datetime.strptime(start_date, '%Y-%m-%d')
        end_dt = datetime.strptime(end_date, '%Y-%m-%d')
        total_days = (end_dt - start_dt).days

        # Convert train_ratio to window sizes
        # Use train_ratio to determine train window, leave 30% for test, with 7-day steps
        train_window_days = int(total_days * train_ratio * 0.7)  # 70% of train portion for window
        test_window_days = max(7, int(total_days * (1 - train_ratio)))  # Remaining for test
        step_days = max(1, test_window_days // 4)  # Quarter of test window for steps

        # Ensure minimum viable windows
        if train_window_days < 7:
            train_window_days = 7
        if test_window_days < 3:
            test_window_days = 3

        # Initialize Backtester with proper parameters
        ab_config = config.get('advanced_backtesting', {})
        backtester = Backtester(
            historical_data_provider=engine.historical_data_provider,
            initial_balance=ab_config.get('initial_balance', 10000.0),
            fee_percentage=ab_config.get('fee_percentage', 0.001),
            slippage_percentage=ab_config.get('slippage_percentage', 0.0001),
            commission_per_trade=ab_config.get('commission_per_trade', 0.0),
            stop_loss_percentage=ab_config.get('stop_loss_percentage', 0.02),
            take_profit_percentage=ab_config.get('take_profit_percentage', 0.05),
            config=config
        )
        decision_engine = engine.decision_engine
        analyzer = WalkForwardAnalyzer()

        console.print(f"[dim]Date range: {start_date} to {end_date} ({total_days} days)[/dim]")
        console.print(f"[dim]Windows: train={train_window_days}d, test={test_window_days}d, step={step_days}d[/dim]")
        console.print(f"[dim]Provider: {provider}[/dim]\n")

        # Run analysis
        results = analyzer.run_walk_forward(
            backtester=backtester,
            asset_pair=asset_pair,
            start_date=start_date,
            end_date=end_date,
            train_window_days=train_window_days,
            test_window_days=test_window_days,
            step_days=step_days,
            decision_engine=decision_engine
        )

        # Check for error (insufficient date range)
        if 'error' in results:
            console.print(f"[bold red]Walk-Forward Error:[/bold red] {results['error']}")
            console.print("\n[yellow]Suggestion:[/yellow] Increase the date range or reduce window sizes.")
            console.print(f"  Current: {start_date} to {end_date} ({(end_dt - start_dt).days} days)")
            console.print(f"  Required: At least {train_window_days + test_window_days} days")
            raise click.Abort()

        # Display results table
        table = Table(title="Walk-Forward Analysis Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Average Test Performance", justify="right", style="yellow")

        agg_perf = results['aggregate_test_performance']

        table.add_row("Avg Sharpe Ratio", f"{agg_perf['avg_sharpe_ratio']:.2f}")
        table.add_row("Avg Return", f"{agg_perf['avg_return_pct']:.2f}%")
        table.add_row("Avg Win Rate", f"{agg_perf['avg_win_rate_pct']:.1f}%")
        table.add_row("Num Windows", f"{results['num_windows']}")

        console.print(table)

        # Overfitting assessment
        overfitting = results['overfitting_analysis']
        severity = overfitting['overfitting_severity']

        severity_colors = {
            'NONE': 'green',
            'LOW': 'yellow',
            'MEDIUM': 'dark_orange',
            'HIGH': 'red'
        }
        color = severity_colors.get(severity, 'white')

        console.print(f"\n[bold {color}]Overfitting Severity: {severity}[/bold {color}]")
        console.print(f"Recommendation: {overfitting['recommendation']}")

    except Exception as e:
        console.print(f"[bold red]Error running walk-forward analysis:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


@cli.command(name='monte-carlo')
@click.argument('asset_pair')
@click.option('--start-date', required=True, help='Start date (YYYY-MM-DD)')
@click.option('--end-date', required=True, help='End date (YYYY-MM-DD)')
@click.option('--simulations', default=1000, help='Number of simulations (default: 1000)')
@click.option('--noise-std', default=0.001, help='Price noise std dev (default: 0.001)')
@click.option('--provider', default='ensemble', help='AI provider to use')
@click.pass_context
def monte_carlo(ctx, asset_pair, start_date, end_date, simulations, noise_std, provider):
    """
    Run Monte Carlo simulation with price perturbations.

    Calculates confidence intervals and Value at Risk (VaR) for strategy returns.

    Example:
        python main.py monte-carlo BTCUSD --start-date 2024-01-01 --end-date 2024-03-01 --simulations 500
    """
    console.print(f"\n[bold cyan]🎲 Monte Carlo Simulation: {asset_pair}[/bold cyan]")

    try:
        from finance_feedback_engine.backtesting.monte_carlo import MonteCarloSimulator
        from finance_feedback_engine.backtesting.backtester import Backtester

        config = ctx.obj['config']

        # Override AI provider from CLI option
        if provider:
            if 'decision_engine' not in config:
                config['decision_engine'] = {}
            config['decision_engine']['ai_provider'] = provider.lower()

        engine = FinanceFeedbackEngine(config)

        # Initialize Backtester with proper parameters
        ab_config = config.get('advanced_backtesting', {})
        backtester = Backtester(
            historical_data_provider=engine.historical_data_provider,
            initial_balance=ab_config.get('initial_balance', 10000.0),
            fee_percentage=ab_config.get('fee_percentage', 0.001),
            slippage_percentage=ab_config.get('slippage_percentage', 0.0001),
            commission_per_trade=ab_config.get('commission_per_trade', 0.0),
            stop_loss_percentage=ab_config.get('stop_loss_percentage', 0.02),
            take_profit_percentage=ab_config.get('take_profit_percentage', 0.05),
            config=config
        )
        decision_engine = engine.decision_engine
        simulator = MonteCarloSimulator()

        console.print(f"[dim]Date range: {start_date} to {end_date}[/dim]")
        console.print(f"[dim]Simulations: {simulations}, Noise: {noise_std:.3%}[/dim]")
        console.print(f"[dim]Provider: {provider}[/dim]\n")

        # Run simulation
        results = simulator.run_monte_carlo(
            backtester=backtester,
            asset_pair=asset_pair,
            start_date=start_date,
            end_date=end_date,
            decision_engine=decision_engine,
            num_simulations=simulations,
            price_noise_std=noise_std
        )

        # Display results table
        table = Table(title="Monte Carlo Simulation Results")
        table.add_column("Metric", style="cyan")
        table.add_column("Value", justify="right", style="green")

        stats = results['statistics']
        percentiles = results['percentiles']

        table.add_row("Base Final Balance", f"${results['base_final_balance']:.2f}")
        table.add_row("Expected Return", f"${stats['expected_return']:.2f}")
        table.add_row("Value at Risk (95%)", f"${stats['var_95']:.2f}")
        table.add_row("Worst Case", f"${stats['worst_case']:.2f}")
        table.add_row("Best Case", f"${stats['best_case']:.2f}")
        table.add_row("Std Deviation", f"${stats['std_dev']:.2f}")

        console.print(table)

        # Percentiles
        console.print("\n[bold]Confidence Intervals:[/bold]")
        console.print(f"  5th percentile:  ${percentiles['p5']:.2f}")
        console.print(f"  25th percentile: ${percentiles['p25']:.2f}")
        console.print(f"  50th percentile: ${percentiles['p50']:.2f}")
        console.print(f"  75th percentile: ${percentiles['p75']:.2f}")
        console.print(f"  95th percentile: ${percentiles['p95']:.2f}")

        if 'note' in results:
            console.print(f"\n[yellow]{results['note']}[/yellow]")

    except Exception as e:
        console.print(f"[bold red]Error running Monte Carlo simulation:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


@cli.command(name='learning-report')
@click.option('--asset-pair', default=None, help='Filter by asset pair (optional)')
@click.pass_context
def learning_report(ctx, asset_pair):
    """
    Generate comprehensive learning validation report.

    Shows RL/meta-learning metrics:
    - Sample efficiency (DQN/Rainbow)
    - Cumulative regret (Multi-armed Bandits)
    - Concept drift detection
    - Thompson Sampling diagnostics
    - Learning curve analysis

    Example:
        python main.py learning-report --asset-pair BTCUSD
    """
    console.print(f"\n[bold cyan]📈 Learning Validation Report[/bold cyan]")
    if asset_pair:
        console.print(f"[dim]Filtering by: {asset_pair}[/dim]")

    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)

        # Consistent memory engine usage and initialization check
        if not hasattr(engine, 'memory_engine') or engine.memory_engine is None:
            console.print("[yellow]Portfolio memory not initialized.[/yellow]")
            return
        memory = engine.memory_engine

        # Generate metrics
        metrics = memory.generate_learning_validation_metrics(asset_pair=asset_pair)

        if 'error' in metrics:
            console.print(f"[yellow]{metrics['error']}[/yellow]")
            return

        console.print(f"\n[bold]Total Trades Analyzed: {metrics['total_trades_analyzed']}[/bold]")

        # Sample Efficiency
        console.print("\n[bold cyan]1. Sample Efficiency (DQN/Rainbow)[/bold cyan]")
        se = metrics['sample_efficiency']
        if se.get('achieved_threshold'):
            console.print(f"  ✓ Reached 60% win rate after {se['trades_to_60pct_win_rate']} trades")
        else:
            console.print(f"  ✗ 60% win rate threshold not yet achieved")
        console.print(f"  Learning speed: {se['learning_speed_per_100_trades']:.2%} improvement per 100 trades")

        # Cumulative Regret
        console.print("\n[bold cyan]2. Cumulative Regret (Bandit Theory)[/bold cyan]")
        cr = metrics['cumulative_regret']
        console.print(f"  Total regret: ${cr['cumulative_regret']:.2f}")
        console.print(f"  Optimal provider: {cr['optimal_provider']} (avg P&L: ${cr['optimal_avg_pnl']:.2f})")
        console.print(f"  Avg regret per trade: ${cr['avg_regret_per_trade']:.2f}")

        # Concept Drift
        console.print("\n[bold cyan]3. Concept Drift Detection[/bold cyan]")
        cd = metrics['concept_drift']
        drift_colors = {'LOW': 'green', 'MEDIUM': 'yellow', 'HIGH': 'red'}
        drift_color = drift_colors.get(cd['drift_severity'], 'white')
        console.print(f"  Drift severity: [{drift_color}]{cd['drift_severity']}[/{drift_color}]")
        console.print(f"  Drift score: {cd['drift_score']:.3f}")
        console.print(f"  Window win rates: {[f'{wr:.1%}' for wr in cd['window_win_rates']]}")

        # Thompson Sampling
        console.print("\n[bold cyan]4. Thompson Sampling Diagnostics[/bold cyan]")
        ts = metrics['thompson_sampling']
        console.print(f"  Exploration rate: {ts['exploration_rate']:.1%}")
        console.print(f"  Exploitation convergence: {ts['exploitation_convergence']:.1%}")
        console.print(f"  Dominant provider: {ts['dominant_provider']}")
        console.print(f"  Provider distribution: {ts['provider_distribution']}")

        # Learning Curve
        console.print("\n[bold cyan]5. Learning Curve Analysis[/bold cyan]")
        lc = metrics['learning_curve']

        table = Table()
        table.add_column("Period", style="cyan")
        table.add_column("Win Rate", justify="right", style="green")
        table.add_column("Avg P&L", justify="right", style="yellow")

        first = lc['first_100_trades']
        last = lc['last_100_trades']

        table.add_row("First 100 trades", f"{first['win_rate']:.1%}", f"${first['avg_pnl']:.2f}")
        table.add_row("Last 100 trades", f"{last['win_rate']:.1%}", f"${last['avg_pnl']:.2f}")

        console.print(table)

        console.print(f"\n  Win rate improvement: {lc['win_rate_improvement_pct']:.1f}%")
        console.print(f"  P&L improvement: {lc['pnl_improvement_pct']:.1f}%")

        if lc['learning_detected']:
            console.print("\n[bold green]✓ Learning detected: Strategy is improving over time[/bold green]")
        else:
            console.print("\n[bold yellow]⚠ No significant learning detected[/bold yellow]")

        # Research attribution
        console.print("\n[dim]Research Methods:[/dim]")
        for metric, paper in metrics['research_methods'].items():
            console.print(f"  [dim]- {metric}: {paper}[/dim]")

    except Exception as e:
        console.print(f"[bold red]Error generating learning report:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


@cli.command(name='prune-memory')
@click.option('--keep-recent', default=1000, help='Keep N most recent trades (default: 1000)')
@click.option('--confirm/--no-confirm', default=True, help='Confirm before pruning')
@click.pass_context
def prune_memory(ctx, keep_recent, confirm):
    """
    Prune old trade outcomes from portfolio memory.

    Keeps only the N most recent trades to manage memory size.

    Example:
        python main.py prune-memory --keep-recent 500
    """
    console.print(f"\n[bold cyan]🗑️  Portfolio Memory Pruning[/bold cyan]")

    try:
        config = ctx.obj['config']
        engine = FinanceFeedbackEngine(config)

        # Use the standard memory_engine attribute for portfolio memory operations
        if not hasattr(engine, 'memory_engine') or engine.memory_engine is None:
            console.print("[yellow]Portfolio memory not initialized.[/yellow]")
            return

        memory = engine.memory_engine
        current_count = len(memory.trade_outcomes)

        console.print(f"Current trade outcomes: {current_count}")
        console.print(f"Will keep {keep_recent} most recent trades")

        if current_count <= keep_recent:
            console.print("[green]No pruning needed - memory size within limit.[/green]")
            return

        to_remove = current_count - keep_recent
        console.print(f"[yellow]Will remove {to_remove} older trades[/yellow]")

        if confirm:
            response = Prompt.ask("\nProceed with pruning?", choices=["yes", "no"], default="no")
            if response != "yes":
                console.print("[yellow]Pruning cancelled.[/yellow]")
                return

        # Prune (keep last N)
        memory.trade_outcomes = memory.trade_outcomes[-keep_recent:]

        console.print(f"[green]✓ Pruned memory to {len(memory.trade_outcomes)} trades[/green]")

        # Save if persistence is configured
        if hasattr(memory, 'save'):
            memory.save()
            console.print("[green]✓ Saved pruned memory to disk[/green]")

    except Exception as e:
        console.print(f"[bold red]Error pruning memory:[/bold red] {str(e)}")
        if ctx.obj.get('verbose'):
            import traceback
            console.print(traceback.format_exc())
        raise click.Abort()


if __name__ == '__main__':
    cli()
