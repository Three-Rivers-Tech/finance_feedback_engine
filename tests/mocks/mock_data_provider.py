from typing import Any, Dict

import pandas as pd


class MockHistoricalDataProvider:
    def __init__(self, full_historical_data: pd.DataFrame):
        self.full_historical_data = full_historical_data

    def get_historical_data(
        self,
        asset_pair: str,
        start_date: str,
        end_date: str,
        **kwargs,
    ) -> pd.DataFrame:
        start_dt = pd.to_datetime(start_date)
        end_dt = pd.to_datetime(end_date)

        # Filter the full dataset by the requested date range
        mask = (self.full_historical_data.index >= start_dt) & (
            self.full_historical_data.index <= end_dt
        )
        return self.full_historical_data.loc[mask]

    def get_market_data(self, asset_pair: str, **kwargs) -> Dict[str, Any]:
        # Return the last row of the dataset for a simple market data query
        if not self.full_historical_data.empty:
            return self.full_historical_data.iloc[-1].to_dict()
        return {}
