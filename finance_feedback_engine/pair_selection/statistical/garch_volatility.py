"""
GARCH Volatility Forecaster for Forward-Looking Volatility Estimates.

Uses GARCH(1,1) model to forecast volatility based on volatility clustering patterns.

Research backing:
- Engle (1982): ARCH model for volatility clustering
- Bollerslev (1986): Generalized ARCH (GARCH)
- Widely used in risk management and options pricing
- Captures the empirical fact that high volatility tends to cluster

GARCH(1,1) specification:
    σ²_t = ω + α·ε²_{t-1} + β·σ²_{t-1}

Where:
    σ²_t = Conditional variance at time t
    ω = Constant term
    α = ARCH coefficient (shock impact)
    β = GARCH coefficient (persistence)
    ε²_{t-1} = Squared residual (shock)
"""

import logging
from dataclasses import dataclass
from typing import Dict, List, Optional

import numpy as np

logger = logging.getLogger(__name__)


@dataclass
class GARCHForecast:
    """
    GARCH volatility forecast result.

    Attributes:
        forecasted_vol: Forecasted annualized volatility (e.g., 0.25 = 25%)
        model_params: GARCH model parameters {omega, alpha, beta}
        volatility_regime: Classification: "low" | "medium" | "high"
        historical_vol: Historical annualized volatility for comparison
        confidence_intervals: 95% confidence interval for forecast
        persistence: alpha + beta (close to 1 = high persistence)
    """

    forecasted_vol: float
    model_params: Dict[str, float]
    volatility_regime: str
    historical_vol: float
    confidence_intervals: Dict[str, float]
    persistence: float


class GARCHVolatilityForecaster:
    """
    GARCH(1,1) volatility clustering model for forward-looking volatility estimates.

    Fits GARCH models to historical returns and forecasts future volatility.
    Useful for identifying pairs with predictable volatility patterns.
    """

    def __init__(
        self,
        p: int = 1,
        q: int = 1,
        fitting_window_days: int = 90,
        forecast_horizon_days: int = 7,
    ):
        """
        Initialize GARCH Volatility Forecaster.

        Args:
            p: ARCH lag order (default: 1)
            q: GARCH lag order (default: 1)
            fitting_window_days: Days of data to use for fitting (default: 90)
            forecast_horizon_days: Days ahead to forecast (default: 7)
        """
        self.p = p
        self.q = q
        self.fitting_window_days = fitting_window_days
        self.forecast_horizon_days = forecast_horizon_days

        logger.info(
            f"GARCH Forecaster initialized: GARCH({p},{q}), "
            f"fitting window={fitting_window_days}d, horizon={forecast_horizon_days}d"
        )

    def forecast_volatility(
        self, asset_pair: str, data_provider
    ) -> Optional[GARCHForecast]:
        """
        Fit GARCH(1,1) and forecast next N days of volatility.

        Args:
            asset_pair: Trading pair identifier
            data_provider: UnifiedDataProvider for fetching data

        Returns:
            GARCHForecast with volatility estimates and model parameters,
            or None if fitting fails
        """
        try:
            # Try to import arch library
            try:
                from arch import arch_model
            except ImportError:
                logger.error(
                    "arch library not installed. Install with: pip install arch"
                )
                return self._fallback_volatility_estimate(asset_pair, data_provider)

            # Fetch historical data (90 days for stable fitting)
            candles, provider = data_provider.get_candles(
                asset_pair=asset_pair, granularity="1d", limit=self.fitting_window_days
            )

            if not candles or len(candles) < 30:
                logger.warning(
                    f"{asset_pair}: Insufficient data for GARCH "
                    f"({len(candles) if candles else 0} candles). Using fallback."
                )
                return self._fallback_volatility_estimate(asset_pair, data_provider)

            # Calculate returns
            returns = self._calculate_returns(candles)

            if len(returns) < 30:
                logger.warning(
                    f"{asset_pair}: Insufficient returns for GARCH "
                    f"({len(returns)} returns). Using fallback."
                )
                return self._fallback_volatility_estimate(asset_pair, data_provider)

            # Scale returns to percentage for better numerical stability
            returns_pct = np.array(returns) * 100

            # Fit GARCH(1,1) model
            model = arch_model(
                returns_pct, vol="Garch", p=self.p, q=self.q, dist="normal"
            )

            # Fit with suppressed output
            fit = model.fit(disp="off", show_warning=False)

            # Extract parameters
            params = {
                "omega": fit.params.get("omega", 0.0),
                "alpha": fit.params.get(f"alpha[{self.p}]", 0.0),
                "beta": fit.params.get(f"beta[{self.q}]", 0.0),
            }

            # Calculate persistence (alpha + beta close to 1 means high persistence)
            persistence = params["alpha"] + params["beta"]

            # Forecast next horizon_days
            forecast = fit.forecast(horizon=self.forecast_horizon_days)

            # Extract forecasted variance (in percentage squared)
            forecasted_var = forecast.variance.values[-1, :]

            # Convert to annualized volatility (rescale from pct to decimal, then annualize)
            forecasted_vol_daily = np.sqrt(np.mean(forecasted_var)) / 100
            forecasted_vol = forecasted_vol_daily * np.sqrt(252)  # Annualized

            # Calculate historical volatility for comparison
            historical_vol = np.std(returns) * np.sqrt(252)

            # Classify volatility regime
            if forecasted_vol < historical_vol * 0.8:
                regime = "low"
            elif forecasted_vol > historical_vol * 1.2:
                regime = "high"
            else:
                regime = "medium"

            # Calculate 95% confidence intervals (rough approximation)
            ci_lower = forecasted_vol * 0.8
            ci_upper = forecasted_vol * 1.2

            result = GARCHForecast(
                forecasted_vol=forecasted_vol,
                model_params=params,
                volatility_regime=regime,
                historical_vol=historical_vol,
                confidence_intervals={"lower": ci_lower, "upper": ci_upper},
                persistence=persistence,
            )

            logger.info(
                f"{asset_pair} GARCH forecast: {forecasted_vol:.4f} "
                f"(regime: {regime}, persistence: {persistence:.3f}, "
                f"historical: {historical_vol:.4f})"
            )

            return result

        except Exception as e:
            logger.warning(
                f"GARCH fitting failed for {asset_pair}: {e}. Using fallback."
            )
            return self._fallback_volatility_estimate(asset_pair, data_provider)

    def _fallback_volatility_estimate(
        self, asset_pair: str, data_provider
    ) -> Optional[GARCHForecast]:
        """
        Fallback to simple historical volatility if GARCH fitting fails.

        Args:
            asset_pair: Trading pair identifier
            data_provider: UnifiedDataProvider

        Returns:
            GARCHForecast with simple historical vol, or None
        """
        try:
            # Fetch 30 days of data as fallback
            candles, provider = data_provider.get_candles(
                asset_pair=asset_pair, granularity="1d", limit=30
            )

            if not candles or len(candles) < 10:
                logger.warning(
                    f"{asset_pair}: Insufficient data for fallback volatility"
                )
                return None

            # Calculate returns
            returns = self._calculate_returns(candles)

            if len(returns) < 10:
                return None

            # Simple historical volatility (annualized)
            historical_vol = np.std(returns) * np.sqrt(252)

            # Use historical vol as forecast
            result = GARCHForecast(
                forecasted_vol=historical_vol,
                model_params={"omega": 0.0, "alpha": 0.0, "beta": 0.0},
                volatility_regime="medium",
                historical_vol=historical_vol,
                confidence_intervals={
                    "lower": historical_vol * 0.8,
                    "upper": historical_vol * 1.2,
                },
                persistence=0.0,
            )

            logger.info(
                f"{asset_pair} fallback volatility: {historical_vol:.4f} (historical)"
            )

            return result

        except Exception as e:
            logger.error(f"Fallback volatility estimation failed for {asset_pair}: {e}")
            return None

    def _calculate_returns(self, candles: List[Dict]) -> List[float]:
        """
        Calculate percentage returns from OHLCV candles.

        Args:
            candles: List of candle dictionaries with 'close' prices

        Returns:
            List of percentage returns
        """
        if not candles or len(candles) < 2:
            return []

        returns = []
        for i in range(1, len(candles)):
            prev_close = candles[i - 1].get("close")
            curr_close = candles[i].get("close")

            if prev_close is None or curr_close is None or prev_close == 0:
                continue

            ret = (curr_close - prev_close) / prev_close
            returns.append(ret)

        return returns
