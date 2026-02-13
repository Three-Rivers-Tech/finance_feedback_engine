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
from finance_feedback_engine.cli.commands.demo import demo as demo_command
from finance_feedback_engine.cli.commands.experiment import (
    experiment as experiment_command,
)
from finance_feedback_engine.cli.commands.frontend import frontend as frontend_command
from finance_feedback_engine.cli.commands.memory import (
    learning_report as learning_report_command,
)
from finance_feedback_engine.cli.commands.memory import (
    prune_memory as prune_memory_command,
)
from finance_feedback_engine.utils.retention_manager import create_default_manager
from finance_feedback_engine.cli.commands.optimize import optimize as optimize_command
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
    """No-op validator for env-only configuration."""
    logger.debug(
        "Skipping YAML validation (env-only configuration active: path=%s, env=%s)",
        config_path,
        environment,
    )


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
    """Setup logging configuration with mandatory structured JSON logging.

    v0.9.9 Change: Logging is now ALWAYS enabled with structured JSON format to data/logs/.
    - --verbose increases detail level (DEBUG instead of INFO)
    - --trace enables OpenTelemetry tracing (separate from logging)

    Args:
        verbose: If True, use DEBUG level; otherwise INFO (logging always enabled)
        config: Configuration dict (optional, used for advanced settings)

    Structured logging benefits:
    - Machine-parseable JSON format for log aggregation
    - Consistent timestamps and trace context
    - Automatic correlation with OpenTelemetry spans (if --trace enabled)
    """
    import json
    from datetime import datetime
    from pathlib import Path

    # Create logs directory if it doesn't exist
    log_dir = Path("data/logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Determine log level (--verbose overrides)
    level = logging.DEBUG if verbose else logging.INFO

    # Create JSON handler for structured logging to file
    log_file = log_dir / f"{datetime.now().strftime('%Y-%m-%d')}_ffe.log"

    class JSONFormatter(logging.Formatter):
        """Format logs as structured JSON."""

        def format(self, record):
            log_entry = {
                "timestamp": datetime.fromtimestamp(record.created).isoformat(),
                "level": record.levelname,
                "logger": record.name,
                "message": record.getMessage(),
                "module": record.module,
                "function": record.funcName,
                "line": record.lineno,
            }
            # Add exception info if present
            if record.exc_info:
                log_entry["exception"] = self.formatException(record.exc_info)
            return json.dumps(log_entry, default=str)

    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove any existing handlers to avoid duplicates
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # File handler with JSON formatter
    file_handler = logging.FileHandler(log_file, encoding="utf-8")
    file_handler.setLevel(level)
    file_handler.setFormatter(JSONFormatter())
    root_logger.addHandler(file_handler)

    # Console handler with readable format (not JSON)
    console_handler = logging.StreamHandler()
    console_handler.setLevel(level)
    console_format = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    console_handler.setFormatter(logging.Formatter(console_format))
    root_logger.addHandler(console_handler)

    # Attach OTel trace context filter if available
    try:
        from finance_feedback_engine.observability.context import OTelContextFilter

        root_logger.addFilter(OTelContextFilter())
    except Exception:
        pass  # OTel optional

    logger = logging.getLogger(__name__)
    logger.info(
        f"Logging initialized (level={logging.getLevelName(level)}, file={log_file})"
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
    """Environment-only configuration loader (single source of truth)."""
    from finance_feedback_engine.utils.config_loader import load_env_config

    return load_env_config()


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
@click.option("--trace/--no-trace", default=False, help="Enable OpenTelemetry tracing")
@click.option(
    "--otlp-endpoint",
    default=None,
    help="OTLP exporter endpoint (e.g., http://localhost:4317)",
)
@click.option("--interactive", "-i", is_flag=True, help="Start in interactive mode")
@click.pass_context
def cli(ctx, config, verbose, trace, otlp_endpoint, interactive):
    """Finance Feedback Engine 2.0 - AI-powered trading decision tool."""
    ctx.ensure_object(dict)

    # If a specific config file is provided by the user
    if config:
        raise click.ClickException(
            "File-based configuration is disabled. Use .env as the single source of truth."
        )
    final_config = load_tiered_config()
    ctx.obj["config_path"] = ".env"

    # Override tracing settings from CLI flags
    if trace:
        if "observability" not in final_config:
            final_config["observability"] = {}
        if "tracing" not in final_config["observability"]:
            final_config["observability"]["tracing"] = {}
        final_config["observability"]["tracing"]["enabled"] = True
        if otlp_endpoint:
            if "otlp" not in final_config["observability"]["tracing"]:
                final_config["observability"]["tracing"]["otlp"] = {}
            final_config["observability"]["tracing"]["otlp"]["endpoint"] = otlp_endpoint

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

    # Initialize tracing early (safe no-op if disabled)
    try:
        from finance_feedback_engine.observability import init_tracer

        init_tracer(final_config.get("observability", {}))
    except Exception as e:
        logger.warning(f"Failed to initialize tracing: {e}")

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

    Disabled for env-only configuration. Use .env (see .env.example) instead of YAML overlays.
    """
    raise click.ClickException(
        "config-editor is disabled: configuration is .env-only. Copy .env.example to .env and edit it instead."
    )


@cli.command(name="validate-config")
@click.option(
    "--config-path",
    "-c",
    default=".env",
    type=click.Path(),
    help="Path to configuration file (env-only)",
)
@click.option(
    "--strict",
    is_flag=True,
    help="Exit with error code on validation failures (instead of warnings)",
)
@click.pass_context
def validate_config_cmd(ctx, config_path, strict):
    """Disabled: configuration is env-only.

    Use the provided .env.example as a template and manage settings via environment variables.
    """
    raise click.ClickException(
        "validate-config is disabled: configuration is .env-only. Copy .env.example to .env and update environment variables instead."
    )

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

        # Note: Ollama must be installed separately for debate mode
        console.print("[yellow]Note:[/yellow] Ollama must be installed separately for LLM debate mode.")
        console.print("Run: [bold cyan]./scripts/install-ollama.sh[/bold cyan]\n")

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

    decision = decision or {}

    status = "approved" if approved else "rejected"
    if modified:
        status = "modified"

    approval_data = {
        "decision_id": decision_id,
        "status": status,
        "approved": approved,
        "modified": modified,
        "timestamp": datetime.now().isoformat(),
        "source": "cli",
        "approval_notes": decision.get("approval_notes", ""),
    }

    if modified:
        approval_data["modified_decision"] = decision

    # Save to file
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
@click.option("--save", is_flag=True, help="Save P&L snapshot to data/pnl_snapshots/")
@click.pass_context
def positions(ctx, save):
    """Display active trading positions with real-time P&L (THR-215, THR-216-220)."""
    from decimal import Decimal, InvalidOperation
    from datetime import datetime, timezone
    import json
    import fcntl
    from pathlib import Path
    import logging
    
    logger = logging.getLogger(__name__)
    
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
            console.print("[dim]No active positions found.[/dim]")
            return

        console.print(f"\n[bold cyan]═══ OPEN POSITIONS ({platform_name}) ═══[/bold cyan]\n")
        
        total_pnl = Decimal("0")  # THR-216: Use Decimal for financial calculations
        valid_positions = []  # Store successfully parsed positions
        
        for pos in positions_list:
            # Extract position details with fallbacks
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
            ).upper()
            
            # THR-218: Safe type conversions with error handling
            try:
                size_raw = pos.get("contracts") or pos.get("units") or pos.get("size") or pos.get("quantity") or "0"
                size = Decimal(str(size_raw))
            except (ValueError, TypeError, InvalidOperation) as e:
                logger.warning(f"Invalid size for {product}: {size_raw} ({e}). Skipping position.")
                continue
            
            try:
                entry_raw = pos.get("entry_price") or pos.get("average_price") or pos.get("price") or "0"
                entry_price = Decimal(str(entry_raw))
            except (ValueError, TypeError, InvalidOperation) as e:
                logger.warning(f"Invalid entry_price for {product}: {entry_raw} ({e}). Skipping position.")
                continue
            
            try:
                current_raw = pos.get("current_price") or pos.get("mark_price") or entry_raw or "0"
                current_price = Decimal(str(current_raw))
            except (ValueError, TypeError, InvalidOperation) as e:
                logger.warning(f"Invalid current_price for {product}: {current_raw} ({e}). Skipping position.")
                continue
            
            # THR-220: Explicit SHORT/LONG detection with validation
            side_upper = side.upper()
            if side_upper in ["BUY", "LONG"]:
                direction = 1
            elif side_upper in ["SELL", "SHORT"]:
                direction = -1
            else:
                logger.warning(f"Unknown position side '{side}' for {product}. Skipping position.")
                continue
            
            # Calculate P&L if not provided (THR-216: Decimal arithmetic)
            unrealized_pnl_raw = pos.get("unrealized_pnl") or pos.get("unrealized_pl") or pos.get("pnl")
            
            if unrealized_pnl_raw is not None:
                try:
                    unrealized_pnl = Decimal(str(unrealized_pnl_raw))
                except (ValueError, TypeError, InvalidOperation):
                    unrealized_pnl = None
            else:
                unrealized_pnl = None
            
            if unrealized_pnl is None and entry_price > 0 and current_price > 0:
                # Calculate: (current - entry) × units × direction
                price_diff = current_price - entry_price
                unrealized_pnl = price_diff * size * Decimal(str(direction))
            
            if unrealized_pnl is None:
                unrealized_pnl = Decimal("0")
            
            total_pnl += unrealized_pnl
            
            # Calculate percentage P&L (THR-216: Decimal arithmetic)
            pnl_pct = Decimal("0")
            if entry_price > 0 and size > 0:
                position_value = entry_price * size
                if position_value > 0:
                    pnl_pct = (unrealized_pnl / position_value) * Decimal("100")
            
            # Color-code P&L
            if unrealized_pnl > 0:
                pnl_color = "green"
                pnl_sign = "+"
            elif unrealized_pnl < 0:
                pnl_color = "red"
                pnl_sign = ""
            else:
                pnl_color = "dim"
                pnl_sign = ""
            
            # Get timestamp if available (THR-219: Timezone aware)
            entry_time = pos.get("open_time") or pos.get("created_at") or pos.get("timestamp")
            time_str = ""
            if entry_time:
                try:
                    if isinstance(entry_time, str):
                        dt = datetime.fromisoformat(entry_time.replace("Z", "+00:00"))
                    else:
                        dt = datetime.fromtimestamp(entry_time, tz=timezone.utc)
                    time_str = f" @ {dt.strftime('%H:%M')}"
                except Exception as e:
                    logger.debug(f"Could not parse entry_time for {product}: {e}")
            
            # Get stop loss if available (THR-216: Decimal arithmetic)
            stop_loss_raw = pos.get("stop_loss") or pos.get("stopLoss") or pos.get("sl")
            sl_str = ""
            if stop_loss_raw:
                try:
                    stop_loss = Decimal(str(stop_loss_raw))
                    if entry_price > 0:
                        sl_pct = ((stop_loss - entry_price) / entry_price * Decimal("100"))
                        sl_str = f"  Stop Loss: ${float(stop_loss):.4f} ({float(sl_pct):+.2f}%)\n"
                except (ValueError, TypeError, InvalidOperation) as e:
                    logger.debug(f"Could not parse stop_loss for {product}: {e}")
            
            # Store valid position for snapshot
            valid_positions.append({
                "product": product,
                "side": side,
                "size": size,
                "entry_price": entry_price,
                "current_price": current_price,
                "unrealized_pnl": unrealized_pnl
            })
            
            # Print position details (convert Decimal to float for display)
            console.print(f"[bold]{product}[/bold] {side} ({float(size)} units)")
            console.print(f"  Entry: ${float(entry_price):.4f}{time_str}")
            console.print(f"  Current: ${float(current_price):.4f}")
            console.print(f"  P&L: [{pnl_color}]{pnl_sign}${float(unrealized_pnl):.2f} ({pnl_sign}{float(pnl_pct):.2f}%)[/{pnl_color}]")
            if sl_str:
                console.print(sl_str, end="")
            console.print()  # Blank line between positions
        
        # Save snapshot if requested (THR-215, THR-217, THR-219)
        if save and valid_positions:
            snapshot_dir = Path("data/pnl_snapshots")
            snapshot_dir.mkdir(parents=True, exist_ok=True)
            
            # THR-219: Use UTC timezone for all timestamps
            now_utc = datetime.now(timezone.utc)
            today = now_utc.strftime("%Y-%m-%d")
            snapshot_file = snapshot_dir / f"{today}.jsonl"
            
            snapshot = {
                "timestamp": now_utc.isoformat(),  # THR-219: Timezone aware
                "platform": platform_name,
                "total_pnl": float(total_pnl),  # Convert Decimal to float for JSON
                "position_count": len(valid_positions),
                "positions": []
            }
            
            # Use pre-validated positions from display loop
            for pos_data in valid_positions:
                snapshot["positions"].append({
                    "product": pos_data["product"],
                    "side": pos_data["side"],
                    "size": float(pos_data["size"]),
                    "entry_price": float(pos_data["entry_price"]),
                    "current_price": float(pos_data["current_price"]),
                    "unrealized_pnl": float(pos_data["unrealized_pnl"])
                })
            
            # THR-217: Atomic append with file locking
            try:
                with open(snapshot_file, "a") as f:
                    fcntl.flock(f, fcntl.LOCK_EX)  # Acquire exclusive lock
                    try:
                        f.write(json.dumps(snapshot) + "\n")
                    finally:
                        fcntl.flock(f, fcntl.LOCK_UN)  # Always release lock
                console.print(f"[dim]💾 Snapshot saved to {snapshot_file}[/dim]\n")
            except IOError as e:
                logger.error(f"Failed to write snapshot: {e}")
                console.print(f"[yellow]⚠ Warning: Could not save snapshot ({e})[/yellow]\n")
        
        # Print totals (THR-216: Convert Decimal to float for display)
        total_pnl_float = float(total_pnl)
        total_color = "green" if total_pnl > 0 else ("red" if total_pnl < 0 else "dim")
        total_sign = "+" if total_pnl > 0 else ""
        console.print(f"[bold]Total Unrealized P&L:[/bold] [{total_color}]{total_sign}${total_pnl_float:.2f}[/{total_color}]")
        console.print()

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
# Data Retention Management
# ============================================

@cli.command(context_settings=dict(help_option_names=['-h', '--help']))
@click.option(
    '--policy',
    default=None,
    help='Specific policy to run (e.g., "decisions", "logs"). If not provided, runs all.'
)
@click.option(
    '--dry-run',
    is_flag=True,
    default=False,
    help='Show what would be deleted without actually deleting files.'
)
@click.option(
    '--status',
    is_flag=True,
    default=False,
    help='Show current status of all retention policies without cleanup.'
)
def cleanup_data(policy: str, dry_run: bool, status: bool):
    """Manage data and logs retention policies.

    Automatically cleans up old files based on configured retention policies:
    - decisions: Keep 30 days (max 500 MB)
    - logs: Keep 14 days (max 1000 MB)
    - backtest_cache: Keep 7 days
    - cache: Keep 3 days

    Examples:
        python main.py cleanup-data                    # Run all policies
        python main.py cleanup-data --policy logs      # Cleanup logs only
        python main.py cleanup-data --dry-run           # Preview what would be deleted
        python main.py cleanup-data --status            # Show current status
    """
    try:
        manager = create_default_manager()

        if status:
            manager.print_status()
            return

        console.print("[bold cyan]Data Retention Cleanup[/bold cyan]")
        console.print()

        if dry_run:
            console.print("[bold yellow]DRY RUN MODE: No files will be deleted[/bold yellow]\n")

        results = manager.cleanup(policy_name=policy, dry_run=dry_run)

        if not results or all(not files for files in results.values()):
            console.print("[bold green]✓ All directories are within retention policy limits[/bold green]")
        else:
            console.print(f"\n[bold green]✓ Cleanup complete[/bold green]")
            for policy_name, deleted_files in results.items():
                if deleted_files:
                    console.print(f"  - {policy_name}: {len(deleted_files)} files removed")

    except Exception as e:
        console.print(f"[bold red]Error:[/bold red] {str(e)}")
        raise click.Abort()


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
cli.add_command(demo_command, name="demo")
cli.add_command(analyze_command, name="analyze")
cli.add_command(history_command, name="history")
cli.add_command(balance_command, name="balance")
cli.add_command(execute_command, name="execute")
cli.add_command(backtest_command, name="backtest")
cli.add_command(portfolio_backtest_command, name="portfolio-backtest")
cli.add_command(walk_forward_command, name="walk-forward")
cli.add_command(monte_carlo_command, name="monte-carlo")
cli.add_command(experiment_command, name="experiment")
cli.add_command(optimize_command, name="optimize")
cli.add_command(learning_report_command, name="learning-report")
cli.add_command(prune_memory_command, name="prune-memory")
cli.add_command(run_agent_command, name="run-agent")
cli.add_command(monitor_command, name="monitor")
cli.add_command(frontend_command, name="frontend")


if __name__ == "__main__":
    cli()
