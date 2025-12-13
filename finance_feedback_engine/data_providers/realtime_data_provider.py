import asyncio
import logging
from typing import Dict, Any, Callable, Optional

from alpha_vantage.async_support.timeseries import TimeSeries

from finance_feedback_engine.utils.financial_data_validator import FinancialDataValidator
from finance_feedback_engine.persistence.timeseries_data_store import TimeSeriesDataStore


logger = logging.getLogger(__name__)

class RealtimeDataProvider:
    """
    Manages real-time financial data ingestion via Alpha Vantage.

    This class provides a robust framework for polling Alpha Vantage for
    real-time data, performing initial validation, and passing it to a handler
    for further processing or storage.

    Implementation Notes:
    - **Asynchronous Operations:** Leverages `asyncio` for efficient,
      non-blocking I/O.
    - **Configurable Connection:** Allows flexible configuration of the Alpha
      Vantage API key and the polling interval.
    - **Error Handling:** Implements robust error handling for connection
      issues.
    - **Data Validation Hook:** Integrates data validation using
      `FinancialDataValidator` to ensure data quality at the point of ingestion.
    - **Callback Mechanism:** Uses a `data_handler` callback to allow for
      flexible processing of ingested data, decoupling ingestion from business
      logic.
    """
    def __init__(
        self,
        api_key: str,
        symbol: str,
        data_handler: Callable[[Dict[str, Any]], None],
        interval: int = 60,
    ):
        self.api_key = api_key
        self.symbol = symbol
        self.data_handler = data_handler
        self.interval = interval
        self._is_running = False
        self._task: Optional[asyncio.Task] = None
        self.ts = TimeSeries(key=self.api_key, output_format='pandas')
        self.validator = FinancialDataValidator()
        self.data_store = TimeSeriesDataStore()

    async def _listen_for_data(self):
        """Polls Alpha Vantage for new data."""
        while self._is_running:
            try:
                data, _ = await self.ts.get_intraday(
                    data, _ = await self.ts.get_intraday(
                        symbol=self.symbol, interval='1min', outputsize='compact'
                    )
                )
                
                # The Alpha Vantage API returns data in a descending order by time.
                # We only want the latest data point.
                latest_data = data.head(1).to_dict('records')[0]
                
                # Convert the index (timestamp) to a column
                latest_data['timestamp'] = data.index[0]
                
                errors = self.validator.validate_single_entry(latest_data)
                if errors:
                    logger.warning(f"Invalid data received: {errors} - Data: {latest_data}")
                else:
                    self.data_handler(latest_data)
                    self.data_store.save_data(self.symbol, latest_data)

            except Exception as e:
                logger.exception(f"Unexpected error while polling for data: {e}")

            await asyncio.sleep(self.interval)

    async def start(self):
        """Starts the real-time data ingestion process."""
        self._is_running = True
        logger.info("Starting RealtimeDataProvider...")
        self._task = asyncio.create_task(self._listen_for_data())

    async def stop(self):
        """Stops the real-time data ingestion process."""
        self._is_running = False
        if self._task:
            self._task.cancel()
        await self.close()
        logger.info("RealtimeDataProvider stopped.")

    async def close(self):
        """Closes the aiohttp session."""
        await self.ts.close()