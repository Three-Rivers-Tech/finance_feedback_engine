"""
Pulse data formatting with clean separation of concerns.

Refactored from cli/main.py::_display_pulse_data (149 lines)
Now follows SOLID principles with proper value objects and single responsibilities.
"""

from typing import Dict, Any, Optional
from dataclasses import dataclass
from rich.console import Console
from rich.table import Table
import logging

logger = logging.getLogger(__name__)


# CONSTANTS - Extracted from magic numbers
class TechnicalIndicatorThresholds:
    """Centralized thresholds for technical indicators."""

    RSI_OVERBOUGHT = 70.0
    RSI_OVERSOLD = 30.0

    ADX_STRONG_TREND = 25.0
    ADX_DEVELOPING_TREND = 20.0

    BOLLINGER_UPPER_BREAK = 1.0
    BOLLINGER_LOWER_BREAK = 0.0

    FRESH_PULSE_MINUTES = 10.0
    MIN_ALIGNMENT_TIMEFRAMES = 3


@dataclass(frozen=True)
class RSILevel:
    """RSI indicator value with interpretation - VALUE OBJECT pattern."""

    value: float

    @property
    def interpretation(self) -> str:
        """Get RSI interpretation."""
        if self.value > TechnicalIndicatorThresholds.RSI_OVERBOUGHT:
            return "OVERBOUGHT"
        elif self.value < TechnicalIndicatorThresholds.RSI_OVERSOLD:
            return "OVERSOLD"
        return "NEUTRAL"

    @property
    def color(self) -> str:
        """Get display color for RSI level."""
        if self.value > TechnicalIndicatorThresholds.RSI_OVERBOUGHT:
            return "red"
        elif self.value < TechnicalIndicatorThresholds.RSI_OVERSOLD:
            return "green"
        return "yellow"


@dataclass(frozen=True)
class TimeframeData:
    """Single timeframe technical data - VALUE OBJECT pattern."""

    timeframe: str
    trend: str
    signal_strength: int
    rsi: RSILevel
    macd: Dict[str, float]
    bollinger_bands: Dict[str, float]
    adx: Dict[str, float]
    atr: float
    volatility: str

    @classmethod
    def from_dict(cls, tf: str, data: Dict[str, Any]) -> 'TimeframeData':
        """Factory method for creating from API response."""
        return cls(
            timeframe=tf,
            trend=data.get('trend', 'RANGING'),
            signal_strength=data.get('signal_strength', 0),
            rsi=RSILevel(data.get('rsi', 50.0)),
            macd=data.get('macd', {}),
            bollinger_bands=data.get('bollinger_bands', {}),
            adx=data.get('adx', {}),
            atr=data.get('atr', 0.0),
            volatility=data.get('volatility', 'medium')
        )


class PulseDataFetcher:
    """
    Fetches pulse data from engine.

    SINGLE RESPONSIBILITY: Data retrieval only.
    """

    def __init__(self, engine):
        """Initialize with engine instance."""
        self.engine = engine

    def fetch_pulse(self, asset_pair: str) -> Optional[Dict[str, Any]]:
        """
        Fetch multi-timeframe pulse data.

        Returns:
            Pulse data dict with 'timeframes' key, or None if unavailable
        """
        # Try monitoring context first (real-time data)
        if hasattr(self.engine, 'monitoring_context_provider'):
            try:
                context = self.engine.monitoring_context_provider.get_monitoring_context(asset_pair)
                pulse = context.get('multi_timeframe_pulse')
                if pulse and 'timeframes' in pulse:
                    return pulse
            except Exception as e:
                logger.debug(f"Monitoring context unavailable: {e}")

        # Fallback to data provider
        if hasattr(self.engine, 'data_provider'):
            try:
                fetched = self.engine.data_provider.get_comprehensive_market_data(asset_pair)
                pulse = (fetched or {}).get('multi_timeframe_pulse') or (fetched or {}).get('pulse')

                # Normalize structure
                if pulse and 'timeframes' not in pulse and isinstance(pulse, dict):
                    pulse = {'timeframes': pulse}

                if pulse and 'timeframes' in pulse:
                    return pulse
            except Exception as e:
                logger.warning(f"Pulse fetch failed: {e}")

        return None


class TimeframeTableFormatter:
    """
    Formats single timeframe data into Rich table.

    SINGLE RESPONSIBILITY: Presentation logic only.
    """

    def format_timeframe(self, tf_data: TimeframeData) -> Table:
        """Create formatted table for single timeframe."""
        table = Table(title=f"{tf_data.timeframe.upper()} Timeframe", show_header=True)
        table.add_column("Indicator", style="cyan")
        table.add_column("Value", style="white")
        table.add_column("Interpretation", style="dim")

        # Trend row
        trend_color = self._get_trend_color(tf_data.trend)
        table.add_row(
            "Trend",
            f"[{trend_color}]{tf_data.trend}[/{trend_color}]",
            f"Signal Strength: {tf_data.signal_strength}/100"
        )

        # RSI row - using value object (eliminates primitive obsession)
        table.add_row(
            "RSI",
            f"{tf_data.rsi.value:.1f}",
            f"[{tf_data.rsi.color}]{tf_data.rsi.interpretation}[/{tf_data.rsi.color}]"
        )

        # MACD row
        macd_status = self._interpret_macd(tf_data.macd)
        table.add_row(
            "MACD",
            f"{tf_data.macd.get('macd', 0):.2f}",
            macd_status
        )

        # Bollinger Bands
        bb_status = self._interpret_bollinger(tf_data.bollinger_bands)
        percent_b = tf_data.bollinger_bands.get('percent_b', 0.5)
        table.add_row(
            "Bollinger %B",
            f"{percent_b:.3f}",
            bb_status
        )

        # ADX
        adx_status = self._interpret_adx(tf_data.adx)
        table.add_row(
            "ADX",
            f"{tf_data.adx.get('adx', 0):.1f}",
            adx_status
        )

        # Volatility
        vol_color = self._get_volatility_color(tf_data.volatility)
        table.add_row(
            "ATR / Volatility",
            f"{tf_data.atr:.2f}",
            f"[{vol_color}]{tf_data.volatility.upper()}[/{vol_color}]"
        )

        return table

    @staticmethod
    def _get_trend_color(trend: str) -> str:
        """Map trend to display color."""
        return {
            'UPTREND': 'green',
            'DOWNTREND': 'red',
            'RANGING': 'yellow'
        }.get(trend.upper(), 'white')

    @staticmethod
    def _interpret_macd(macd: Dict[str, float]) -> str:
        """Interpret MACD histogram."""
        histogram = macd.get('histogram', 0)
        if histogram > 0:
            return "[green]BULLISH[/green] (positive histogram)"
        elif histogram < 0:
            return "[red]BEARISH[/red] (negative histogram)"
        return "NEUTRAL"

    @staticmethod
    def _interpret_bollinger(bbands: Dict[str, float]) -> str:
        """Interpret Bollinger Band position."""
        percent_b = bbands.get('percent_b', 0.5)
        if percent_b > TechnicalIndicatorThresholds.BOLLINGER_UPPER_BREAK:
            return "[red]Above upper band[/red] (overbought)"
        elif percent_b < TechnicalIndicatorThresholds.BOLLINGER_LOWER_BREAK:
            return "[green]Below lower band[/green] (oversold)"
        return f"Within bands ({percent_b:.1%})"

    def _interpret_adx(self, adx_data: Dict[str, float]) -> str:
        """Interpret ADX trend strength."""
        adx_val = adx_data.get('adx', 0)
        plus_di = adx_data.get('plus_di', 0)
        minus_di = adx_data.get('minus_di', 0)

        # Strength interpretation
        if adx_val > TechnicalIndicatorThresholds.ADX_STRONG_TREND:
            strength = f"[green]STRONG TREND[/green] ({adx_val:.1f})"
        elif adx_val > TechnicalIndicatorThresholds.ADX_DEVELOPING_TREND:
            strength = f"Developing trend ({adx_val:.1f})"
        else:
            strength = f"[yellow]Weak/ranging[/yellow] ({adx_val:.1f})"

        # Direction
        direction = ("[green]+DI dominant[/green]" if plus_di > minus_di
                    else "[red]-DI dominant[/red]")

        return f"{strength} | {direction}"

    @staticmethod
    def _get_volatility_color(volatility: str) -> str:
        """Map volatility level to color."""
        return {
            'high': 'red',
            'medium': 'yellow',
            'low': 'green'
        }.get(volatility.lower(), 'white')


class CrossTimeframeAnalyzer:
    """
    Analyzes alignment across multiple timeframes.

    SINGLE RESPONSIBILITY: Multi-timeframe analysis logic only.
    """

    def analyze_alignment(self, timeframes: Dict[str, TimeframeData]) -> Dict[str, Any]:
        """
        Analyze cross-timeframe trend alignment.

        Returns:
            Dict with 'alignment', 'color', 'uptrends', 'downtrends', 'ranging'
        """
        trends = [tf.trend for tf in timeframes.values()]

        uptrends = trends.count('UPTREND')
        downtrends = trends.count('DOWNTREND')
        ranging = trends.count('RANGING')

        # Determine alignment
        min_count = TechnicalIndicatorThresholds.MIN_ALIGNMENT_TIMEFRAMES

        if uptrends > downtrends and uptrends >= min_count:
            alignment = "BULLISH ALIGNMENT"
            color = "bold green"
        elif downtrends > uptrends and downtrends >= min_count:
            alignment = "BEARISH ALIGNMENT"
            color = "bold red"
        else:
            alignment = "MIXED SIGNALS"
            color = "yellow"

        return {
            'alignment': alignment,
            'color': color,
            'uptrends': uptrends,
            'downtrends': downtrends,
            'ranging': ranging
        }


class PulseDisplayService:
    """
    Orchestrates pulse data display.

    FACADE pattern - coordinates fetcher, formatters, and analyzers.
    """

    def __init__(self, console: Optional[Console] = None):
        """Initialize with optional console."""
        self.console = console or Console()
        self.fetcher: Optional[PulseDataFetcher] = None
        self.table_formatter = TimeframeTableFormatter()
        self.analyzer = CrossTimeframeAnalyzer()

    def set_fetcher(self, fetcher: PulseDataFetcher):
        """Dependency injection for data fetcher."""
        self.fetcher = fetcher

    def display_pulse(self, asset_pair: str):
        """
        Display complete pulse analysis.

        FACADE: Coordinates all components to display pulse data.
        """
        if not self.fetcher:
            raise ValueError("PulseDataFetcher not injected. Call set_fetcher() first.")

        try:
            self.console.print("\n[bold cyan]=== MULTI-TIMEFRAME PULSE DATA ===[/bold cyan]")

            # STEP 1: Fetch data
            pulse = self.fetcher.fetch_pulse(asset_pair)

            if not pulse or 'timeframes' not in pulse:
                self._display_unavailable_message()
                return

            # STEP 2: Display freshness
            self._display_freshness(pulse.get('age_seconds', 0))

            # STEP 3: Convert to value objects
            timeframe_data = {
                tf: TimeframeData.from_dict(tf, data)
                for tf, data in pulse['timeframes'].items()
            }

            # STEP 4: Format and display each timeframe
            for tf_data in timeframe_data.values():
                table = self.table_formatter.format_timeframe(tf_data)
                self.console.print(table)
                self.console.print()

            # STEP 5: Cross-timeframe analysis
            alignment = self.analyzer.analyze_alignment(timeframe_data)
            self._display_alignment(alignment)

            self.console.print("[bold cyan]" + "=" * 40 + "[/bold cyan]\n")

        except Exception as e:
            self.console.print(f"[red]Error displaying pulse data: {e}[/red]")
            logger.exception("Pulse display error")

    def _display_unavailable_message(self):
        """Display message when pulse data is unavailable."""
        self.console.print("[yellow]Multi-timeframe pulse data not available[/yellow]")
        self.console.print(
            "[dim]Ensure TradeMonitor is running or data_provider supports "
            "comprehensive pulse[/dim]"
        )

    def _display_freshness(self, age_seconds: float):
        """Display pulse data freshness."""
        age_mins = age_seconds / 60
        fresh_threshold = TechnicalIndicatorThresholds.FRESH_PULSE_MINUTES
        freshness = "[green]FRESH[/green]" if age_mins < fresh_threshold else "[yellow]STALE[/yellow]"
        self.console.print(f"Pulse Age: {age_mins:.1f} minutes ({freshness})")
        self.console.print()

    def _display_alignment(self, alignment: Dict[str, Any]):
        """Display cross-timeframe alignment analysis."""
        self.console.print("[bold]Cross-Timeframe Alignment:[/bold]")
        self.console.print(f"  [{alignment['color']}]{alignment['alignment']}[/{alignment['color']}]")
        self.console.print(
            f"  Breakdown: {alignment['uptrends']} up, "
            f"{alignment['downtrends']} down, {alignment['ranging']} ranging"
        )


def display_pulse_data(engine, asset_pair: str, console: Optional[Console] = None):
    """
    Display multi-timeframe pulse data for asset pair.

    Public API for CLI commands. This is the only function that should be imported
    from this module.

    Args:
        engine: FinanceFeedbackEngine instance
        asset_pair: Asset pair to analyze
        console: Optional Rich console (creates new one if not provided)

    Example:
        from finance_feedback_engine.cli.formatters.pulse_formatter import display_pulse_data
        display_pulse_data(engine, "BTCUSD")
    """
    service = PulseDisplayService(console)
    fetcher = PulseDataFetcher(engine)
    service.set_fetcher(fetcher)
    service.display_pulse(asset_pair)
